"""
Diffusion Fabric Design Pipeline Service

This module contains the complete 8-stage diffusion pipeline for fabric design,
including the orchestrator and all stage processors.

Components:
- service.DiffusionPipelineService: Main service interface
- orchestrator: Pipeline execution engine and stage loading
- stages: Individual stage processors (Stage 0-7)
"""

from weaver.diffusion.service import DiffusionPipelineService

__all__ = ['DiffusionPipelineService']

