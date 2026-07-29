class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500, code: str = "internal_error"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class RateLimitError(AppError):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(
            message="Слишком много запросов. Попробуйте позже.",
            status_code=429,
            code="rate_limit_exceeded",
        )


class EmailDeliveryError(AppError):
    def __init__(self, message: str = "Не удалось отправить email"):
        super().__init__(message=message, status_code=503, code="email_delivery_failed")
