class OzonAssistantError(Exception):
    """Base exception for expected application errors."""


class NotFoundError(OzonAssistantError):
    pass


class ValidationError(OzonAssistantError):
    pass


class ConflictError(OzonAssistantError):
    pass


class IntegrationError(OzonAssistantError):
    pass

