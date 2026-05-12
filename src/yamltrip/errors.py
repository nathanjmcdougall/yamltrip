"""yamltrip error types."""


class YAMLTripError(Exception):
    """Base exception for all yamltrip errors."""


class ParseError(YAMLTripError):
    """Raised when YAML input cannot be parsed."""


class QueryError(YAMLTripError):
    """Raised when a path query fails (path not found)."""


class PatchError(YAMLTripError):
    """Raised when a patch operation fails."""


class KeyExistsError(PatchError):
    """Raised by add() when the key already exists."""


class KeyMissingError(PatchError):
    """Raised by replace() when the key doesn't exist."""
