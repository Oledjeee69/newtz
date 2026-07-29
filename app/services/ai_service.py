import json
import logging
import re
from typing import Any, Literal

import httpx

from app.config import Settings
from app.schemas.contact import AIAnalysis

logger = logging.getLogger(__name__)

AISource = Literal["openai", "groq", "gemini", "fallback"]

POSITIVE_WORDS = {"спасибо", "отлично", "интерес", "сотруднич", "предлож", "хочу", "готов", "нравится"}
NEGATIVE_WORDS = {"плохо", "ужас", "жалоб", "обман", "разочар", "не работает", "ошибка", "претенз"}
JOB_WORDS = {"ваканс", "работ", "job", "hire", "трудоустрой", "резюме", "cv"}
COLLAB_WORDS = {"сотруднич", "проект", "партнёр", "партнер", "разработ", "backend", "frontend"}
QUESTION_WORDS = {"как", "сколько", "можно", "вопрос", "подскаж", "?"}
FEEDBACK_WORDS = {"отзыв", "feedback", "мнение", "совет"}

ANALYSIS_PROMPT = """Ты — ассистент backend-сервиса лендинга разработчика.
Проанализируй комментарий пользователя и верни ТОЛЬКО валидный JSON без markdown.

Поля:
- sentiment: positive | neutral | negative
- sentiment_score: число от 0 до 1
- request_type: job_offer | collaboration | question | feedback | spam_suspicion | other
- summary: краткое описание на русском (до 120 символов)
- suggested_reply: вежливый ответ пользователю на русском (2-3 предложения)

Комментарий:
\"\"\"
{comment}
\"\"\"
"""


def parse_ai_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    required = {"sentiment", "sentiment_score", "request_type", "summary", "suggested_reply"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Missing AI fields: {missing}")
    return data


class AIService:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def analyze(self, comment: str, user_name: str) -> AIAnalysis:
        providers = self._settings.ai_provider_chain
        for provider in providers:
            try:
                if provider == "openai":
                    result = await self._call_openai(comment)
                elif provider == "groq":
                    result = await self._call_groq(comment)
                elif provider == "gemini":
                    result = await self._call_gemini(comment)
                else:
                    continue
                return AIAnalysis(**result, source=provider)
            except Exception as exc:
                logger.warning("%s AI failed, trying next provider: %s", provider, exc)

        return self._analyze_fallback(comment, user_name)

    async def _call_openai(self, comment: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.openai_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Отвечай только JSON."},
                {"role": "user", "content": ANALYSIS_PROMPT.format(comment=comment)},
            ],
        }
        return await self._post_json(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            content_path=("choices", 0, "message", "content"),
        )

    async def _call_groq(self, comment: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.groq_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Отвечай только JSON."},
                {"role": "user", "content": ANALYSIS_PROMPT.format(comment=comment)},
            ],
        }
        return await self._post_json(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            content_path=("choices", 0, "message", "content"),
        )

    async def _call_gemini(self, comment: str) -> dict[str, Any]:
        model = self._settings.gemini_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={self._settings.gemini_api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": ANALYSIS_PROMPT.format(comment=comment)}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        timeout = httpx.Timeout(self._settings.ai_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return parse_ai_json(content)

    async def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        content_path: tuple[str | int, ...],
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(self._settings.ai_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=json)
            response.raise_for_status()
            data = response.json()
            content: Any = data
            for key in content_path:
                content = content[key]
            return parse_ai_json(str(content))

    def _analyze_fallback(self, comment: str, user_name: str) -> AIAnalysis:
        lower = comment.lower()

        pos = sum(1 for w in POSITIVE_WORDS if w in lower)
        neg = sum(1 for w in NEGATIVE_WORDS if w in lower)

        if pos > neg:
            sentiment = "positive"
            score = min(0.95, 0.55 + pos * 0.1)
        elif neg > pos:
            sentiment = "negative"
            score = min(0.95, 0.55 + neg * 0.1)
        else:
            sentiment = "neutral"
            score = 0.5

        request_type = "other"
        if any(w in lower for w in JOB_WORDS):
            request_type = "job_offer"
        elif any(w in lower for w in COLLAB_WORDS):
            request_type = "collaboration"
        elif any(w in lower for w in QUESTION_WORDS):
            request_type = "question"
        elif any(w in lower for w in FEEDBACK_WORDS):
            request_type = "feedback"
        elif len(comment) < 15 or re.search(r"https?://", lower):
            request_type = "spam_suspicion"

        type_labels = {
            "job_offer": "предложение о работе",
            "collaboration": "запрос на сотрудничество",
            "question": "вопрос",
            "feedback": "отзыв",
            "spam_suspicion": "подозрительное обращение",
            "other": "общее обращение",
        }

        summary = f"{type_labels[request_type].capitalize()}: {comment[:80]}{'...' if len(comment) > 80 else ''}"
        safe_name = user_name.split()[0] if user_name else "коллега"
        suggested_reply = (
            f"Здравствуйте, {safe_name}! Спасибо за обращение. "
            f"Я получил ваше сообщение и свяжусь с вами в ближайшее время."
        )

        return AIAnalysis(
            sentiment=sentiment,
            sentiment_score=round(score, 2),
            request_type=request_type,
            summary=summary,
            suggested_reply=suggested_reply,
            source="fallback",
        )
