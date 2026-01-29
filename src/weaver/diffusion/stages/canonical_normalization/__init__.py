"""
Stage 1: Canonical Normalization

Converts validated but representation-ambiguous images into a single
deterministic canonical raster (RGB, 8-bit, EXIF-normalized, repeat-aligned).
"""

from weaver.diffusion.stages.canonical_normalization.processor import (
    CanonicalNormalizationStage,
    Stage1Input,
    Stage1Output,
)

__all__ = [
    "CanonicalNormalizationStage",
    "Stage1Input",
    "Stage1Output",
]


