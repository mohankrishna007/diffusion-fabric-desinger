"""
Weaver - Modular AI Services for Fabric Design

A modular package containing various AI-powered services for fabric design and processing.
Each sub-package is self-contained and can be used independently.

Available Sub-Packages:
- weaver.diffusion: Diffusion-based fabric design pipeline for loom-compatible output
- weaver.shared: Shared utilities, schemas, and constants

Future Sub-Packages:
- weaver.preprocessing: Image preprocessing services
- weaver.denoise: Denoising services
- weaver.validate: Standalone validation services

Public API:
- DiffusionPipelineEngine: Main pipeline execution engine
"""

__version__ = "1.0.0"
__author__ = "Weaver AI Team"

# Export main services from sub-packages
from weaver.diffusion import DiffusionPipelineEngine

__all__ = ['DiffusionPipelineEngine']
