"""
Shared Pydantic schemas for pipeline data contracts.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Any, Dict, Optional, Union
from datetime import datetime
from enum import Enum
import numpy as np


class AlphaPolicy(str, Enum):
    """Policy for handling alpha channel during canonical normalization."""
    FLATTEN_WHITE = "FLATTEN_WHITE"  # Composite on white background (255, 255, 255)
    FLATTEN_BLACK = "FLATTEN_BLACK"  # Composite on black background (0, 0, 0)
    STRIP = "STRIP"  # Remove alpha channel, keep RGB only


class StageStatus(str, Enum):
    """Stage execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineContext(BaseModel):
    """
    Shared context passed through the pipeline execution.
    Contains metadata and state that all stages can access.
    """
    model_config = ConfigDict(extra='allow')
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Pipeline creation timestamp")
    source_file: str = Field(..., description="Original input file path")
    source_data: Optional[Dict[str, Any]] = Field(default=None, description="Source data associated with input file")
    workspace_dir: Optional[str] = Field(default=None, description="Workspace directory for stage artifacts")
    config: Dict[str, Any] = Field(default_factory=dict, description="Pipeline configuration")
    stage_outputs: Dict[str, Any] = Field(default_factory=dict, description="Outputs from completed stages (StageResult objects)")


class PipelineExecutionRequest(BaseModel):
    """Request schema for pipeline execution."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_file": "d:/designs/fabric_pattern.png",
                "config": {
                    "dpi": 300,
                    "color_mode": "RGB",
                    "repeat_unit": {
                        "width": 200,
                        "height": 200
                    },
                    "max_colors": 16,
                    "min_line_width": 2
                }
            }
        }
    )
    
    source_file: str = Field(
        ..., 
        description="Path to input fabric design image (must be lossless: .bmp, .png, .tiff, .tif)",
        examples=["d:/designs/fabric_pattern.png"]
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Optional pipeline configuration overrides (dpi, color_mode, repeat_unit, max_colors, min_line_width)"
    )


class PipelineExecutionResponse(BaseModel):
    """Response schema for async pipeline execution."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Pipeline queued for execution",
                "created_at": "2026-01-26T12:00:00Z"
            }
        }
    )
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    status: PipelineStatus = Field(..., description="Current pipeline status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Pipeline creation timestamp")


class PipelineSyncExecutionResponse(BaseModel):
    """Response schema for synchronous pipeline execution."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "source_file": "d:/designs/fabric_pattern.png",
                "result": {
                    "output_file": "d:/output/fabric_pattern_processed.bmp",
                    "validation_passed": True,
                    "total_colors": 12,
                    "dimensions": {"width": 2000, "height": 2000}
                },
                "stage_outputs": {
                    "0": {"status": "completed", "message": "Input validated"},
                    "1": {"status": "completed", "message": "Normalized"},
                    "7": {"status": "completed", "message": "CAM ready"}
                },
                "created_at": "2026-01-26T12:00:00Z",
                "completed_at": "2026-01-26T12:00:15Z"
            }
        }
    )
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    status: PipelineStatus = Field(..., description="Final pipeline status")
    source_file: str = Field(..., description="Original input file path")
    result: Dict[str, Any] = Field(..., description="Final pipeline result with output file and validation metrics")
    stage_outputs: Dict[int, Any] = Field(..., description="Outputs from all completed stages")
    created_at: datetime = Field(..., description="Pipeline creation timestamp")
    completed_at: datetime = Field(..., description="Pipeline completion timestamp")


class PipelineStatusResponse(BaseModel):
    """Response schema for pipeline status query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "current_stage": 3,
                "completed_stages": [0, 1, 2],
                "message": "Executing Stage 3: Controlled Diffusion Refinement",
                "created_at": "2026-01-26T12:00:00Z",
                "updated_at": "2026-01-26T12:00:08Z",
                "result": None,
                "errors": []
            }
        }
    )
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    status: PipelineStatus = Field(..., description="Current pipeline status")
    current_stage: Optional[int] = Field(None, description="Currently executing stage number (0-7)")
    completed_stages: list[int] = Field(default_factory=list, description="List of completed stage numbers")
    message: str = Field(default="", description="Status message")
    created_at: datetime = Field(..., description="Pipeline creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Final pipeline result if completed")
    errors: list[str] = Field(default_factory=list, description="Error messages if failed")


# ============================================================================
# STAGE 1 - CANONICAL NORMALIZATION SCHEMAS
# Deterministic internal representation for manufacturing pipeline
# ============================================================================

class CanonicalRaster(BaseModel):
    """
    Canonical Raster - Single Deterministic Internal Representation.
    
    This is the NORMALIZED, UNAMBIGUOUS representation that all downstream
    stages consume. It removes ALL representational ambiguity:
    - Color mode: RGB only (no RGBA, L, P, or exotic modes)
    - Bit depth: 8-bit per channel (no 16-bit, 1-bit, or indexed)
    - Orientation: normalized (EXIF rotation applied, flag cleared)
    - Repeat grid: perfectly aligned (integer tile boundaries)
    - DPI: canonical DPI enforced (pixels rescaled if needed)
    - ICC profiles: stripped (deterministic color interpretation)
    - Encoding: hybrid storage (in-memory NumPy array OR .npy file based on size)
    
    This object is INTERNAL ONLY - never serialized to PNG/TIFF/BMP.
    
    Hybrid Storage Strategy:
    - Small images (< memory_threshold_mb): Store as in-memory NumPy array
    - Large images (>= memory_threshold_mb): Store as .npy file with path reference
    - Exactly one of pixel_array or pixel_array_path must be set
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
    
    schema_version: str = Field(
        default="stage1.v1",
        description="Canonical raster schema version"
    )
    width_px: int = Field(..., description="Image width in pixels (after DPI normalization)")
    height_px: int = Field(..., description="Image height in pixels (after DPI normalization)")
    dpi: int = Field(..., description="Canonical DPI (enforced via rescaling)")
    color_mode: str = Field(
        default="RGB",
        description="Color mode (always RGB after normalization)"
    )
    bit_depth: int = Field(
        default=8,
        description="Bit depth per channel (always 8 after normalization)"
    )
    pixel_array: Optional[np.ndarray] = Field(
        default=None,
        description="In-memory NumPy array (H, W, 3) uint8 for small images (optional performance optimization)"
    )
    pixel_array_path: Optional[str] = Field(
        default=None,
        description="Path to .npy file (always present as source of truth)"
    )
    repeat_unit_px: Dict[str, int] = Field(
        ...,
        description="Repeat unit {width, height} in pixels (after DPI normalization)"
    )
    
    @field_validator('pixel_array', 'pixel_array_path')
    @classmethod
    def validate_hybrid_storage(cls, v, info):
        """Validate storage fields."""
        return v
    
    def model_post_init(self, __context):
        """Validate that at least path is set (array is optional for small images)."""
        has_array = self.pixel_array is not None
        has_path = self.pixel_array_path is not None
        
        if not has_path:
            raise ValueError("CanonicalRaster must have pixel_array_path set (source of truth)")
        
        # Both can be set for small images (file + in-memory for performance)
        # Only path for large images (memory efficient)
        
        # Validate array shape if in-memory
        if has_array:
            if self.pixel_array.shape != (self.height_px, self.width_px, 3):
                raise ValueError(
                    f"pixel_array shape {self.pixel_array.shape} does not match "
                    f"declared dimensions ({self.height_px}, {self.width_px}, 3)"
                )
            if self.pixel_array.dtype != np.uint8:
                raise ValueError(f"pixel_array dtype must be uint8, got {self.pixel_array.dtype}")

