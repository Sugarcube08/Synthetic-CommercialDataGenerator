class SynthDataError(Exception):
    """Base exception for synth-data-creator."""
    pass


class ConfigurationError(SynthDataError):
    """Raised when application configuration is invalid."""
    pass


class SchemaInitError(SynthDataError):
    """Raised when database schema initialization fails."""
    pass


class SchemaVerificationError(SynthDataError):
    """Raised when database schema verification fails."""
    pass


class GenerationError(SynthDataError):
    """Raised when synthetic data generation fails."""
    pass


class JobNotFoundError(SynthDataError):
    """Raised when a status request is made for a non-existent job."""
    pass


class JobAlreadyRunningError(SynthDataError):
    """Raised when a new job is requested while another is already running."""
    pass
