"""
Pipeline execution endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
from weaver.orchestrator.pipeline_engine import PipelineEngine
from weaver.shared.schemas import (
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    PipelineSyncExecutionResponse,
    PipelineStatusResponse,
    PipelineStatus
)
from weaver.shared.exceptions import PipelineExecutionError, WeaverError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Global pipeline engine instance
# TODO: Consider dependency injection for better testability
pipeline_engine = PipelineEngine()


@router.post("/execute", response_model=PipelineExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_pipeline(
    request: PipelineExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute the complete 8-stage pipeline.
    
    This endpoint queues the pipeline for background execution and returns immediately.
    Use the returned pipeline_id to check execution status.
    
    Args:
        request: Pipeline execution request with source file and config
        background_tasks: FastAPI background tasks
    
    Returns:
        Pipeline execution response with pipeline_id
    """
    try:
        # Generate pipeline ID (will be done by engine, but we need it for response)
        import uuid
        pipeline_id = str(uuid.uuid4())
        
        # Queue pipeline execution in background
        background_tasks.add_task(
            _execute_pipeline_background,
            pipeline_id,
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
        result = pipeline_engine.execute(
            source_file=request.source_file,
            config_override=request.config
        )
        
        logger.info(f"Pipeline executed successfully: {result['pipeline_id']}")
        
        # Convert to response model
        return PipelineSyncExecutionResponse(
            pipeline_id=result["pipeline_id"],
            status=result["status"],
            source_file=result["source_file"],
            result=result["result"],
            stage_outputs=result.get("stage_outputs", {}),
            created_at=result["created_at"],
            completed_at=result["completed_at"]
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
    execution = pipeline_engine.get_execution_status(pipeline_id)
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found"
        )
    
    return PipelineStatusResponse(
        pipeline_id=pipeline_id,
        status=execution["status"],
        current_stage=execution.get("current_stage"),
        completed_stages=execution.get("completed_stages", []),
        message=f"Pipeline {execution['status'].value}",
        created_at=execution["created_at"],
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
    executions = pipeline_engine.list_executions()
    return executions


@router.get("/stages", response_model=list[Dict[str, Any]])
async def list_stages():
    """
    List all available pipeline stages.
    
    Returns:
        List of stage metadata
    """
    try:
        stages = []
        for stage_number in range(8):
            metadata = pipeline_engine.stage_loader.get_stage_metadata(stage_number)
            stages.append({
                "stage_number": metadata.stage_number,
                "name": metadata.name,
                "description": metadata.description,
                "version": metadata.version,
                "author": metadata.author
            })
        return stages
    
    except Exception as e:
        logger.error(f"Failed to list stages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stages: {str(e)}"
        )


def _execute_pipeline_background(
    pipeline_id: str,
    source_file: str,
    config: Optional[Dict[str, Any]]
):
    """
    Background task for pipeline execution.
    
    Args:
        pipeline_id: Pipeline execution ID
        source_file: Source design file path
        config: Optional configuration overrides
    """
    try:
        logger.info(f"Starting background pipeline execution: {pipeline_id}")
        result = pipeline_engine.execute(source_file, config)
        logger.info(f"Background pipeline execution completed: {pipeline_id}")
    
    except Exception as e:
        logger.error(f"Background pipeline execution failed: {pipeline_id} - {str(e)}")
