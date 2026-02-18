"""Tests for URL configuration encoding/decoding."""

import re

import pytest

from simulation.config_loader import load_defaults
from simulation.url_config import decode_config, encode_config


def test_round_trip():
    """Encode and decode produces identical config."""
    config = load_defaults()
    encoded = encode_config(config)
    decoded = decode_config(encoded)
    assert decoded == config


def test_url_safe():
    """Encoded string contains only URL-safe characters."""
    config = load_defaults()
    encoded = encode_config(config)
    # URL-safe base64: A-Z, a-z, 0-9, -, _, =
    assert re.match(r"^[A-Za-z0-9_-]+=*$", encoded)


def test_corrupted_string():
    """Corrupted input raises clear ValueError."""
    with pytest.raises(ValueError, match="Failed to decode config"):
        decode_config("not_valid_base64!!!")


def test_empty_string():
    """Empty string raises clear error."""
    with pytest.raises(ValueError):
        decode_config("")


def test_compression_effectiveness():
    """Verify gzip compression reduces size significantly."""
    config = load_defaults()
    json_str = config.model_dump_json()
    encoded = encode_config(config)

    # Encoded length should be significantly less than raw JSON
    # Typical: ~8300 bytes JSON → ~2000-3000 bytes compressed+encoded
    assert len(encoded) < len(json_str) * 0.5
