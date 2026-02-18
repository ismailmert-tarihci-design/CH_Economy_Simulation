"""
URL configuration encoding/decoding for shareable simulation configs.

Provides URL-safe compression and encoding of SimConfig objects for team collaboration.
Process: JSON → bytes → gzip → base64url → string
"""

import base64
import gzip

from simulation.models import SimConfig


def encode_config(config: SimConfig) -> str:
    """
    Encode SimConfig to URL-safe string.

    Process: JSON → bytes → gzip → base64url → string

    Args:
        config: SimConfig object to encode

    Returns:
        URL-safe base64-encoded string
    """
    json_bytes = config.model_dump_json().encode("utf-8")
    compressed = gzip.compress(json_bytes, compresslevel=6)
    encoded = base64.urlsafe_b64encode(compressed)
    return encoded.decode("ascii")


def decode_config(encoded: str) -> SimConfig:
    """
    Decode URL-safe string to SimConfig.

    Process: string → base64url decode → gzip decompress → JSON → SimConfig

    Args:
        encoded: URL-safe base64-encoded string

    Returns:
        Decoded SimConfig object

    Raises:
        ValueError: If decoding fails due to corruption or invalid format
    """
    try:
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        decompressed = gzip.decompress(decoded)
        json_str = decompressed.decode("utf-8")
        return SimConfig.model_validate_json(json_str)
    except Exception as e:
        raise ValueError(f"Failed to decode config: {e}") from e
