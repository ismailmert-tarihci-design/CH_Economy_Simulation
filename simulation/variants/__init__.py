"""Variant registry for A/B testing different game economies.

Usage:
    import simulation.variants as variants

    # List available variants
    for v in variants.list_variants():
        print(v.variant_id, v.display_name)

    # Get a specific variant
    info = variants.get("variant_a")
    result = info.run_simulation(config, rng=None)
"""

from simulation.variants.protocol import VariantInfo

_REGISTRY: dict[str, VariantInfo] = {}


def register(info: VariantInfo) -> None:
    """Register a variant. Called at import time by each variant's __init__."""
    _REGISTRY[info.variant_id] = info


def get(variant_id: str) -> VariantInfo:
    """Get a registered variant by ID. Raises KeyError if not found."""
    return _REGISTRY[variant_id]


def list_variants() -> list[VariantInfo]:
    """Return all registered variants in registration order."""
    return list(_REGISTRY.values())


def variant_ids() -> list[str]:
    """Return all registered variant IDs."""
    return list(_REGISTRY.keys())


# Auto-register Variant A (always available — uses existing code in-place)
from simulation.variants.variant_a import register_variant_a  # noqa: E402

register_variant_a()

# Auto-register Variant B if available
try:
    from simulation.variants.variant_b import register_variant_b  # noqa: E402

    register_variant_b()
except ImportError:
    pass
