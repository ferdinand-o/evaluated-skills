"""Gemeinsame Fehler-Antwortform der API — siehe docs/decisions.md."""


class ApiError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_response(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}
