class DomainException(Exception):
    pass


class DeckNotFoundException(DomainException):
    def __init__(self, deck_id: str) -> None:
        super().__init__(f"Deck with ID {deck_id} not found")
        self.deck_id = deck_id


class SlideNotFoundException(DomainException):
    def __init__(self, slide_id: str) -> None:
        super().__init__(f"Slide with ID {slide_id} not found")
        self.slide_id = slide_id


class UnauthorizedAccessException(DomainException):
    def __init__(self, resource: str, user_id: str | None = None) -> None:
        super().__init__(f"User {user_id} is not authorized to access {resource}")
        self.resource = resource
        self.user_id = user_id


class InvalidDeckStatusException(DomainException):
    def __init__(self, deck_id: str, current_status: str, required_status: str) -> None:
        super().__init__(
            f"Deck {deck_id} is in status {current_status}, but {required_status} is required"
        )
        self.deck_id = deck_id
        self.current_status = current_status
        self.required_status = required_status


class DeckGenerationException(DomainException):
    def __init__(self, deck_id: str, reason: str) -> None:
        super().__init__(f"Failed to generate deck {deck_id}: {reason}")
        self.deck_id = deck_id
        self.reason = reason


class LLMException(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(f"LLM error: {message}")


class MessagingException(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Messaging error: {message}")
