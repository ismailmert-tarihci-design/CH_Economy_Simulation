"""Variant B — Hero Card System.

New economy: hero-specific card decks with tiers, Hero XP, linear skill trees,
hero jokers, and premium card packs. Built for A/B testing against Variant A.

This module is registered automatically when its dependencies are ready.
"""


def register_variant_b() -> None:
    # Deferred until Phase 4 when models + orchestrator are built
    raise ImportError("Variant B not yet implemented")
