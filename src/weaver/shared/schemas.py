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
    source_file: str = Field(..., description="Path to input fabric design image")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional pipeline configuration overrides")


class PipelineExecutionResponse(BaseModel):
    """Response schema for pipeline execution."""
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    status: PipelineStatus = Field(..., description="Current pipeline status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Pipeline creation timestamp")


class PipelineStatusResponse(BaseModel):
    """Response schema for pipeline status query."""
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    status: PipelineStatus = Field(..., description="Current pipeline status")
    current_stage: Optional[int] = Field(None, description="Currently executing stage number")
    completed_stages: list[int] = Field(default_factory=list, description="List of completed stage numbers")
    message: str = Field(default="", description="Status message")
    created_at: datetime = Field(..., description="Pipeline creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Final pipeline result if completed")
    errors: list[str] = Field(default_factory=list, description="Error messages if failed")
