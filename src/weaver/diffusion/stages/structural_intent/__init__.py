"""
Stage 2: Structural Intent Definition
Responsibility: Extract and lock structural invariants for downstream stages.
"""

from weaver.diffusion.stages.structural_intent.processor import (
    StructuralIntentStage,
    Stage2Input,
    Stage2Output,
)

__all__ = ["StructuralIntentStage", "Stage2Input", "Stage2Output"]


