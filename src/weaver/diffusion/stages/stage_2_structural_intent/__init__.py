"""
Stage 2: Structural Intent Definition
Responsibility: Extract and lock structural invariants for downstream stages.
"""

from weaver.diffusion.stages.stage_2_structural_intent.processor import (
    Stage2StructuralIntent,
    Stage2Input,
    Stage2Output,
)

__all__ = ["Stage2StructuralIntent", "Stage2Input", "Stage2Output"]

