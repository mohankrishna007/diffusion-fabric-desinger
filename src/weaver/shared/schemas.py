"""
Shared Pydantic schemas for pipeline data contracts.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional
from datetime import datetime
from enum import Enum


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


class StageInput(BaseModel):
    """
    Base input schema for all stages.
    Each stage extends this with specific fields.
    """
    model_config = ConfigDict(
        frozen=True,
        extra='forbid',
        str_strip_whitespace=True
    )
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    stage_number: int = Field(..., ge=0, le=7, description="Stage number (0-7)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class StageOutput(BaseModel):
    """
    Base output schema for all stages.
    Each stage extends this with specific result fields.
    """
    model_config = ConfigDict(
        frozen=True,
        extra='forbid'
    )
    
    stage_number: int = Field(..., ge=0, le=7, description="Stage number (0-7)")
    status: StageStatus = Field(..., description="Execution status")
    message: str = Field(default="", description="Status message")
    data: Dict[str, Any] = Field(default_factory=dict, description="Output data")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Execution metrics")
    errors: list[str] = Field(default_factory=list, description="Validation errors")


class PipelineContext(BaseModel):
    """
    Shared context passed through the pipeline execution.
    Contains metadata and state that all stages can access.
    """
    model_config = ConfigDict(extra='allow')
    
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Pipeline creation timestamp")
    source_file: str = Field(..., description="Original input file path")
    workspace_dir: Optional[str] = Field(default=None, description="Workspace directory for stage artifacts")
    config: Dict[str, Any] = Field(default_factory=dict, description="Pipeline configuration")
    stage_outputs: Dict[int, StageOutput] = Field(default_factory=dict, description="Outputs from completed stages")


class ValidationResult(BaseModel):
    """Result of contract validation."""
    model_config = ConfigDict(frozen=True)
    
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation error messages")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


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


class ErrorDetail(BaseModel):
    """Detailed error information."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Pipeline execution failed at stage 0",
                "details": {
                    "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
                    "error": "File format '.jpg' not allowed. Only lossless formats permitted: ['.bmp', '.png', '.tiff', '.tif']",
                    "completed_stages": []
                }
            }
        }
    )
    
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": {
                    "message": "Pipeline execution failed at stage 0",
                    "details": {
                        "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
                        "error": "File format '.jpg' not allowed. Only lossless formats permitted: ['.bmp', '.png', '.tiff', '.tif']",
                        "completed_stages": []
                    }
                }
            }
        }
    )
    
    detail: ErrorDetail = Field(..., description="Error details")

