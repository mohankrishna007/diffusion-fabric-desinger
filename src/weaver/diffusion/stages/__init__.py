"""
Pipeline stages package.
Each stage is implemented as an independent module that conforms to the BaseStage contract.
"""

from weaver.diffusion.stages.base import BaseStage, StageMetadata

__all__ = ["BaseStage", "StageMetadata"]

