"""Variant B — Hero Card System.

New economy: hero-specific card decks with tiers, Hero XP, linear skill trees,
hero jokers, and premium card packs.
"""


def register_variant_b() -> None:
    from simulation.variants import register
    from simulation.variants.protocol import VariantInfo
    from simulation.variants.variant_b.orchestrator import run_simulation
    from simulation.variants.variant_b.config_loader import load_defaults
    from simulation.variants.variant_b.models import HeroCardConfig, HeroSimResult

    register(
        VariantInfo(
            variant_id="variant_b",
            display_name="Hero Card System",
            description="Hero-specific card decks with tiers, Hero XP, skill trees, premium packs, and hero jokers.",
            run_simulation=run_simulation,
            load_defaults=load_defaults,
            config_class=HeroCardConfig,
            result_class=HeroSimResult,
            extra_snapshot_fields=[
                "hero_xp_today", "hero_levels", "hero_card_avg_levels",
                "skill_nodes_unlocked_today", "cards_unlocked_today",
                "jokers_received_today", "jokers_used_today",
                "premium_packs_opened", "premium_diamonds_spent",
            ],
        )
    )
