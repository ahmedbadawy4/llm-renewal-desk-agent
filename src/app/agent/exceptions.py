class InjectionDetectedError(RuntimeError):
    """Raised when retrieved evidence contains prompt injection indicators."""

    def __init__(self, message: str = "retrieved content contained adversarial instructions") -> None:
        super().__init__(message)
