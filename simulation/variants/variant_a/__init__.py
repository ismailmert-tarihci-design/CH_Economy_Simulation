"""Variant A — Classic Card System.

Thin adapter that registers the existing simulation code as a variant.
No files moved — just points to the existing modules in simulation/.
"""

from simulation.variants import register
from simulation.variants.protocol import VariantInfo


def register_variant_a() -> None:
    from simulation.orchestrator import run_simulation
    from simulation.config_loader import load_defaults
    from simulation.models import SimConfig, SimResult

    register(
        VariantInfo(
            variant_id="variant_a",
            display_name="Classic Card System",
            description="Original economy: Gold/Blue shared cards + Unique cards with exponential gap balancing.",
            run_simulation=run_simulation,
            load_defaults=load_defaults,
            config_class=SimConfig,
            result_class=SimResult,
        )
    )
