class GraphRepresentError(Exception):
    """Base exception for graph-represent."""


class RetryableProcessorError(GraphRepresentError):
    """Signals that the processor can be retried safely."""


class PermanentProcessorError(GraphRepresentError):
    """Signals that retrying will not help."""
