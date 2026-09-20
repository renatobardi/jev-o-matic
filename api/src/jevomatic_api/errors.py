"""Erro único da API: vira `{error: {code, message}}` com o status indicado."""


class TriageError(Exception):
    def __init__(
        self, code: str, message: str, status: int, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after
