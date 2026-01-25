"""
Pipeline execution endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
from weaver.orchestrator.pipeline_engine import PipelineEngine
from weaver.shared.schemas import (
    PipelineExecutionRequest,
    PipelineExecutionResponse,
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


@router.post("/execute/sync", response_model=Dict[str, Any])
async def execute_pipeline_sync(request: PipelineExecutionRequest):
    """
    Execute the pipeline synchronously (blocking).
    
    This endpoint blocks until pipeline execution completes.
    Use for testing or when immediate results are required.
    
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
        return result
    
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
