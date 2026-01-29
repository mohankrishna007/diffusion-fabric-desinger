"""
Result classes for pipeline stages.
Each stage produces a Result that the next stage consumes.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path

class StageResult(BaseModel):
    """Base class for all stage results."""
    pipeline_id: str
    stage_metadata: Dict[str, Any] = Field(..., description="Metadata about the stage that produced this result")

class InputAcquisitionResult(StageResult):
    """Result from Stage 0: Input Acquisition"""
    raw_hash: str = Field(..., description="SHA-256 hash of raw input file")
    source_seal: Dict[str, Any] = Field(..., description="Immutability proof")
    
    # Input descriptor fields
    image_path: str
    width_px: int
    height_px: int
    dpi: int
    repeat_unit_px: Dict[str, int]  # {"width": int, "height": int}
    color_mode: str
    bit_depth: int


class CanonicalNormalizationResult(StageResult):
    """Result from Stage 1: Canonical Normalization"""
    
    # Canonical raster data
    pixel_array_path: Optional[str] = Field(None, description="Path to .npy file if hybrid storage")
    pixel_array: Optional[Any] = Field(None, description="In-memory array if small")
    width_px: int
    height_px: int
    dpi: int
    repeat_unit_px: Dict[str, int]
    color_mode: str


class StructuralIntentResult(StageResult):
    """Result from Stage 2: Structural Intent Extraction"""
    width_px: int
    height_px: int
    dpi: int
    repeat_width_px: int
    repeat_height_px: int
    edge_count: int
    skeleton_node_count: int
    skeleton_edge_count: int
    region_count: int
    topology_validated: bool
    repeat_boundary_validated: bool
    guarantees: list[str] = Field(default_factory=list)


class DiffusionRefinementResult(StageResult):
    """Result from Stage 3: Diffusion Refinement
    
    TODO: Implement diffusion refinement stage
    - Apply diffusion-based smoothing while preserving structural intent
    - Maintain topology from Stage 2
    - Return refined raster data
    """
    pass  # TODO: Add fields for diffusion refinement results


class RepeatEnforcementResult(StageResult):
    """Result from Stage 4: Repeat Enforcement
    
    TODO: Implement repeat enforcement stage
    - Validate perfect tiling across repeat boundaries
    - Detect and correct boundary misalignments
    - Ensure seamless repeat unit continuity
    """
    pass  # TODO: Add fields for repeat enforcement results


class GeometryCleanupResult(StageResult):
    """Result from Stage 5: Geometry Cleanup
    
    TODO: Implement geometry cleanup stage
    - Remove features below minimum manufacturable width
    - Simplify geometry while preserving intent
    - Apply manufacturing constraints
    """
    pass  # TODO: Add fields for geometry cleanup results


class ColorConstraintResult(StageResult):
    """Result from Stage 6: Color Constraint
    
    TODO: Implement color constraint stage
    - Apply thread palette constraints
    - Quantize colors to available threads
    - Generate color-constrained output
    """
    pass  # TODO: Add fields for color constraint results


class PreCAMValidationResult(StageResult):
    """Result from Stage 7: Pre-CAM Validation
    
    TODO: Implement pre-CAM validation stage
    - Final validation before CAM generation
    - Verify all manufacturing constraints met
    - Produce CAM-ready output
    """
    pass  # TODO: Add fields for pre-CAM validation results
