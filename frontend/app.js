const form = document.getElementById("contactForm");
const messageEl = document.getElementById("formMessage");
const submitBtn = document.getElementById("submitBtn");
const themeToggle = document.getElementById("themeToggle");

const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
});

function buildPayload(formEl) {
  const raw = Object.fromEntries(new FormData(formEl));
  const payload = {
    name: (raw.name || "").trim(),
    phone: (raw.phone || "").trim(),
    email: (raw.email || "").trim(),
    comment: (raw.comment || "").trim(),
  };
  if (raw.company_fax && String(raw.company_fax).trim()) {
    payload.company_fax = String(raw.company_fax).trim();
  }
  return payload;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  messageEl.textContent = "";
  messageEl.className = "form__msg";
  submitBtn.disabled = true;

  const payload = buildPayload(form);

  if (payload.comment.length < 10) {
    messageEl.textContent = "Напиши чуть подробнее (хотя бы 10 символов)";
    messageEl.classList.add("error");
    submitBtn.disabled = false;
    return;
  }

  try {
    const res = await fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const body = await res.json();

    if (!res.ok) {
      const details = body?.error?.details?.map((d) => `${d.label || d.field}: ${d.message}`).join("; ");
      throw new Error(details || body?.error?.message || "Ошибка отправки");
    }

    messageEl.textContent = body.message || "Ок, отправил. Проверь почту.";
    messageEl.classList.add("success");
    form.reset();
  } catch (err) {
    messageEl.textContent = err.message || "Что-то пошло не так, попробуй ещё раз";
    messageEl.classList.add("error");
  } finally {
    submitBtn.disabled = false;
  }
});
