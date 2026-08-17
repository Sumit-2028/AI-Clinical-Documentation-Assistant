"""Provider errors shared by all AI adapter implementations."""


class AIProviderError(RuntimeError):
    """Base class for expected provider failures."""


class AIProviderConfigurationError(AIProviderError):
    """The provider cannot be used with the current configuration."""


class AIProviderTimeoutError(AIProviderError):
    """The provider did not respond within the configured timeout."""


class AIProviderRequestError(AIProviderError):
    """The provider rejected the request or could not be reached."""


class AIProviderResponseError(AIProviderError):
    """The provider response did not satisfy the adapter boundary."""
