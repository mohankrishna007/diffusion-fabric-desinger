""" 
Diffusion Fabric Design Pipeline

This module contains the complete diffusion pipeline for fabric design.
Only DiffusionPipelineEngine is exposed for external use.

Internal components (not for external import):
- stage_loader: Internal stage loading mechanism
- stages: Individual stage processors (Stage 0-7)

Public API:
- DiffusionPipelineEngine: Core pipeline execution engine
"""

from weaver.diffusion.diffusion_pipeline_engine import DiffusionPipelineEngine

__all__ = ['DiffusionPipelineEngine']

