_RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def should_retry_status(status_code: int) -> bool:
    """Return True if the HTTP status code indicates a transient upstream failure."""
    return status_code in _RETRIABLE_STATUSES
