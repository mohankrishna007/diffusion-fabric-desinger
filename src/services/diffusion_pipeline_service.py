"""
Diffusion Pipeline Service
Service layer that abstracts DiffusionPipelineEngine for use by API and UI.
"""

import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

from weaver import DiffusionPipelineEngine
from weaver.shared.config_loader import load_pipeline_config
from weaver.shared.exceptions import PipelineExecutionError, ValidationError
from weaver.shared.schemas import PipelineStatus
from weaver.shared.validators import validate_image_config

logger = logging.getLogger(__name__)


class DiffusionPipelineService:
    """
    Service layer for Diffusion Pipeline execution.
    
    Abstracts DiffusionPipelineEngine for use by:
    - FastAPI REST API
    - Streamlit UI
    - CLI tools
    - Direct package usage
    
    Provides:
    - Pipeline execution with progress callbacks
    - Status tracking and monitoring
    - Configuration validation
    - Execution history management
    - Storage management
    """
    
    def __init__(
        self, 
        config: Optional[Dict[str, Any]] = None,
        storage_base_dir: Optional[str] = None
    ):
        """
        Initialize the pipeline service.
        
        Args:
            config: Pipeline configuration. If None, loads from default location.
            storage_base_dir: Base directory for pipeline storage. Defaults to ./storage
        """
        # Load config if not provided
        if config is None:
            logger.info("Loading pipeline configuration from default location")
            config = load_pipeline_config()
        
        self.config = config
        self.storage_base_dir = Path(storage_base_dir or "storage")
        self.storage_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize pipeline engine
        self.engine = DiffusionPipelineEngine(config=config)
        
        logger.info(f"Initialized DiffusionPipelineService with {len(self.engine.get_execution_order())} stages")
    
    def execute_pipeline(
        self,
        source_file: str,
        source_data: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete diffusion pipeline.
        
        Args:
            source_file: Path to input fabric design image
            source_data: Optional source data associated with the input
            progress_callback: Optional callback function(stage_number, message) for progress updates
        
        Returns:
            Pipeline execution result:
            {
                "pipeline_id": str,
                "status": PipelineStatus,
                "source_file": str,
                "result": dict,
                "stage_outputs": dict,
                "created_at": datetime,
                "completed_at": datetime
            }
        
        Raises:
            PipelineExecutionError: If pipeline execution fails
            ValidationError: If input validation fails
        """
        logger.info(f"Starting pipeline execution for: {source_file}")
        
        # Validate source file exists
        if not Path(source_file).exists():
            raise ValidationError(
                f"Source file does not exist: {source_file}",
                stage_number=0,
                details={"source_file": source_file}
            )
        
        # Execute pipeline with progress tracking
        if progress_callback:
            # Wrap progress callback to track stage execution
            def wrapped_callback(stage_number: int, message: str):
                logger.debug(f"Stage {stage_number}: {message}")
                progress_callback(stage_number, message)
            
            # Note: Current engine doesn't support callbacks yet
            # This is prepared for future enhancement
            logger.debug("Progress callback provided but not yet supported by engine")
        
        try:
            # Execute pipeline
            result = self.engine.execute(
                source_file=source_file,
                source_data=source_data
            )
            
            logger.info(f"Pipeline completed successfully: {result['pipeline_id']}")
            return result
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            raise
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a pipeline execution.
        
        Args:
            pipeline_id: Unique pipeline execution ID
        
        Returns:
            Pipeline status dict or None if not found:
            {
                "pipeline_id": str,
                "status": PipelineStatus,
                "source_file": str,
                "current_stage": str,
                "completed_stages": list,
                "stage_outputs": dict,
                "errors": list,
                "created_at": datetime
            }
        """
        return self.engine.get_execution_status(pipeline_id)
    
    def list_pipelines(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all pipeline executions.
        
        Args:
            limit: Maximum number of pipelines to return. None for all.
        
        Returns:
            List of pipeline execution records
        """
        executions = self.engine.list_executions()
        
        if limit:
            return executions[:limit]
        
        return executions
    
    def get_stage_metadata(self, pipeline_id: str, stage_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve stage metadata JSON from storage.
        
        Args:
            pipeline_id: Pipeline execution ID
            stage_id: Stage identifier
        
        Returns:
            Stage metadata dict or None if not found
        """
        metadata_file = self.storage_base_dir / pipeline_id / f"{stage_id}_metadata.json"
        
        if not metadata_file.exists():
            logger.warning(f"Stage metadata not found: {metadata_file}")
            return None
        
        try:
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading stage metadata: {str(e)}")
            return None
    
    def get_execution_order(self) -> List[str]:
        """
        Get the configured stage execution order.
        
        Returns:
            Ordered list of stage IDs
        """
        return self.engine.get_execution_order()
    
    def cleanup_pipeline(self, pipeline_id: str, remove_storage: bool = False) -> None:
        """
        Clean up pipeline execution data.
        
        Args:
            pipeline_id: Pipeline execution ID
            remove_storage: If True, also remove storage directory
        """
        # Remove from execution history
        if pipeline_id in self.engine._execution_history:
            del self.engine._execution_history[pipeline_id]
            logger.info(f"Removed pipeline from execution history: {pipeline_id}")
        
        # Optionally remove storage directory
        if remove_storage:
            storage_dir = self.storage_base_dir / pipeline_id
            if storage_dir.exists():
                import shutil
                shutil.rmtree(storage_dir)
                logger.info(f"Removed pipeline storage: {storage_dir}")
    
    def validate_config(self, source_file: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pipeline configuration without executing.
        
        Performs comprehensive pre-flight validation using shared validators.
        This provides the same validation that Stage 0 will perform, but
        earlier in the process for better user feedback.
        
        Args:
            source_file: Path to input image
            config: Configuration to validate
        
        Returns:
            Validation result:
            {
                "valid": bool,
                "detected": dict,
                "suggestions": dict,
                "errors": list[dict]  # [{field, error, value}]
            }
        """
        logger.debug(f"Validating config for {source_file}")
        
        # Use shared validators for comprehensive validation
        result = validate_image_config(
            image_path=source_file,
            config=config
        )
        
        # Convert to dict for compatibility
        return result.to_dict()
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        Get information about the current pipeline configuration.
        
        Returns:
            Configuration info:
            {
                "active_pipeline": str,
                "stage_count": int,
                "stages": list[str],
                "global_config": dict
            }
        """
        return {
            "active_pipeline": self.config.get("active_pipeline", "unknown"),
            "stage_count": len(self.engine.get_execution_order()),
            "stages": self.engine.get_execution_order(),
            "global_config": self.config.get("global", {})
        }
