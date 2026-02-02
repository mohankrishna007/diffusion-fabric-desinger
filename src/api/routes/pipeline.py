"""
Pipeline execution endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
from services.diffusion_pipeline_service import DiffusionPipelineService
from weaver.shared.schemas import (
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    PipelineSyncExecutionResponse,
    PipelineStatusResponse,
    PipelineStatus,
    ConfigValidationRequest,
    ConfigValidationResponse,
    ValidationErrorSchema
)
from weaver.shared.exceptions import PipelineExecutionError, WeaverError
from weaver.shared.validators import validate_image_config
from datetime import datetime
import logging
import base64

logger = logging.getLogger(__name__)

router = APIRouter()

# Global diffusion pipeline service instance
# Service layer abstracts DiffusionPipelineEngine for REST API usage
try:
    pipeline_service = DiffusionPipelineService()
    logger.info("Pipeline service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize pipeline service: {e}", exc_info=True)
    raise


@router.post("/execute", response_model=PipelineExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_pipeline(
    request: PipelineExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute the complete 8-stage pipeline asynchronously.
    
    This endpoint queues the pipeline for background execution and returns immediately.
    Use the returned pipeline_id to check execution status.
    
    Args:
        request: Pipeline execution request with source file and config
        background_tasks: FastAPI background tasks
    
    Returns:
        Pipeline execution response with pipeline_id
    """
    try:
        # Generate pipeline ID
        import uuid
        pipeline_id = str(uuid.uuid4())
        
        # Queue pipeline execution in background
        background_tasks.add_task(
            _execute_pipeline_background,
            request.source_file,
            request.config
        )
        
        logger.info(f"Pipeline queued for execution: {pipeline_id}")
        
        return PipelineExecutionResponse(
            pipeline_id=pipeline_id,
            status=PipelineStatus.QUEUED,
            message="Pipeline queued for execution",
            created_at=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Failed to queue pipeline: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue pipeline: {str(e)}"
        )


@router.post("/execute/sync", 
             response_model=PipelineSyncExecutionResponse,
             responses={
                 200: {
                     "description": "Pipeline executed successfully",
                     "model": PipelineSyncExecutionResponse
                 },
                 400: {
                     "description": "Bad request - Invalid input parameters",
                     "content": {
                         "application/json": {
                             "example": {
                                 "detail": {
                                     "message": "Invalid configuration",
                                     "details": {"error": "DPI must be between 72 and 1200"}
                                 }
                             }
                         }
                     }
                 },
                 422: {
                     "description": "Unprocessable Entity - Pipeline execution failed",
                     "content": {
                         "application/json": {
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
                     }
                 },
                 500: {
                     "description": "Internal Server Error",
                     "content": {
                         "application/json": {
                             "example": {
                                 "detail": "Unexpected error: Internal server failure"
                             }
                         }
                     }
                 }
             })
async def execute_pipeline_sync(request: PipelineExecutionRequest):
    """
    Execute the pipeline synchronously (blocking).
    
    This endpoint blocks until pipeline execution completes.
    Use for testing or when immediate results are required.
    
    **Input Requirements:**
    - source_file: Must be lossless format (.bmp, .png, .tiff, .tif)
    - config.dpi: 72-1200 (default: 300)
    - config.color_mode: RGB, RGBA, L, or LA (default: RGB)
    - config.repeat_unit: width/height must divide image dimensions evenly
    - Max image size: 10,000 x 10,000 pixels (100 megapixels)
    - Max file size: 500 MB
    
    **Returns:**
    Complete pipeline execution result with:
    - Pipeline ID and status
    - Final result with output file path
    - All stage outputs
    - Execution timestamps
    
    Args:
        request: Pipeline execution request
    
    Returns:
        Complete pipeline execution result
    """
    try:
        # Execute pipeline using shared service
        result = pipeline_service.execute_pipeline(
            source_file=request.source_file,
            source_data=request.config
        )
        
        logger.info(f"Pipeline executed successfully: {result['pipeline_id']}")
        
        # Convert to response model
        return PipelineSyncExecutionResponse(
            pipeline_id=result["pipeline_id"],
            status=result["status"],
            source_file=result["source_file"],
            result=result["result"],
            stage_outputs=result.get("stage_outputs", {}),
            created_at=datetime.fromisoformat(result["created_at"]) if isinstance(result["created_at"], str) else result["created_at"],
            completed_at=datetime.fromisoformat(result["completed_at"]) if isinstance(result["completed_at"], str) else result["completed_at"]
        )
    
    except PipelineExecutionError as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(e),
                "details": e.details
            }
        )
    
    except WeaverError as e:
        logger.error(f"Weaver error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(e),
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/status/{pipeline_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(pipeline_id: str):
    """
    Get execution status for a pipeline.
    
    Args:
        pipeline_id: Pipeline execution ID
    
    Returns:
        Pipeline status information
    """
    execution = pipeline_service.get_pipeline_status(pipeline_id)
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found"
        )
    
    # Convert datetime to ensure proper serialization
    created_at = execution.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    
    return PipelineStatusResponse(
        pipeline_id=pipeline_id,
        status=execution["status"],
        current_stage=execution.get("current_stage"),
        completed_stages=execution.get("completed_stages", []),
        message=f"Pipeline {execution['status'].value if hasattr(execution['status'], 'value') else execution['status']}",
        created_at=created_at,
        updated_at=datetime.utcnow(),
        result=execution.get("result"),
        errors=execution.get("errors", [])
    )


@router.get("/list", response_model=list[Dict[str, Any]])
async def list_pipelines():
    """
    List all pipeline executions.
    
    Returns:
        List of pipeline execution records
    """
    executions = pipeline_service.list_pipelines()
    return executions


@router.get("/stages", response_model=list[Dict[str, Any]])
async def list_stages():
    """
    List all available pipeline stages.
    
    Returns:
        List of stage metadata
    """
    try:
        # Get stages from pipeline engine configuration
        stages = []
        stage_configs = pipeline_service.engine._stages
        
        for stage_index, stage_config in enumerate(stage_configs):
            stages.append({
                "stage_id": stage_config["id"],
                "stage_number": stage_index,
                "name": stage_config["name"],
                "class_name": stage_config["class_name"],
                "description": stage_config.get("config", {}).get("description", "")
            })
        return stages
    
    except Exception as e:
        logger.error(f"Failed to list stages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stages: {str(e)}"
        )


@router.post("/validate", 
             response_model=ConfigValidationResponse,
             responses={
                 200: {
                     "description": "Validation completed (check 'valid' field for pass/fail)",
                     "model": ConfigValidationResponse
                 },
                 400: {
                     "description": "Bad request - Invalid request format",
                     "content": {
                         "application/json": {
                             "example": {
                                 "detail": "Invalid base64 image data"
                             }
                         }
                     }
                 }
             })
async def validate_config(request: ConfigValidationRequest):
    """
    Validate image and configuration without executing pipeline.
    
    This endpoint provides pre-flight validation for UI/API clients:
    - Detects DPI, color mode, and dimensions from image
    - Validates provided configuration against Stage 0 requirements
    - Suggests optimal repeat unit dimensions
    - Returns structured errors for display in UI
    
    Use cases:
    - Image upload: Detect properties and suggest configuration
    - Form validation: Check config before execution
    - Config-only: Validate DPI/color mode ranges without image
    
    Args:
        request: Validation request with optional base64 image and config
    
    Returns:
        Validation result with detection, suggestions, and errors
    
    Examples:
        # Detect from image only
        POST /api/v1/pipeline/validate
        {
            "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        }
        
        # Validate config with image
        POST /api/v1/pipeline/validate
        {
            "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAUA...",
            "config": {
                "dpi": 300,
                "color_mode": "RGB",
                "repeat_unit": {"width": 100, "height": 100}
            }
        }
        
        # Config-only validation
        POST /api/v1/pipeline/validate
        {
            "config": {
                "dpi": 5000,  # Will fail: exceeds MAX_DPI
                "color_mode": "RGB"
            }
        }
    """
    try:
        # Decode image if provided
        image_data = None
        if request.image_data:
            try:
                image_data = base64.b64decode(request.image_data)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid base64 image data: {str(e)}"
                )
        
        # Perform validation
        result = validate_image_config(
            image_data=image_data,
            config=request.config
        )
        
        # Convert to response schema
        return ConfigValidationResponse(
            valid=result.valid,
            detected=result.detected,
            suggestions=result.suggestions,
            errors=[
                ValidationErrorSchema(
                    field=error.field,
                    error=error.error,
                    value=error.value
                )
                for error in result.errors
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )


def _execute_pipeline_background(
    source_file: str,
    config: Optional[Dict[str, Any]]
):
    """
    Background task for pipeline execution.
    
    Args:
        source_file: Source design file path
        config: Optional configuration overrides
    """
    try:
        logger.info(f"Starting background pipeline execution for {source_file}")
        result = pipeline_service.execute_pipeline(
            source_file=source_file,
            source_data=config
        )
        logger.info(f"Background pipeline execution completed: {result['pipeline_id']}")
    
    except Exception as e:
        logger.error(f"Background pipeline execution failed: {source_file} - {str(e)}")
