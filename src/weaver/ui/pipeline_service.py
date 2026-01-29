"""
Pipeline Service for Streamlit UI
Integrates the Streamlit UI with the Weaver AI pipeline execution engine
"""

import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from weaver.orchestrator.pipeline_engine import PipelineEngine
from weaver.shared.schemas import PipelineStatus
from weaver.shared.exceptions import PipelineExecutionError, StageError


logger = logging.getLogger(__name__)


class PipelineService:
    """
    Service layer that connects Streamlit UI to the pipeline execution engine.
    
    Provides a simplified interface for UI operations while handling
    complex pipeline orchestration details.
    """
    
    def __init__(self, workspace_base_dir: Optional[str] = None):
        """
        Initialize the pipeline service.
        
        Args:
            workspace_base_dir: Base directory for pipeline workspaces
        """
        self.pipeline_engine = PipelineEngine()
        self.workspace_base_dir = Path(workspace_base_dir or "storage")
        self.workspace_base_dir.mkdir(exist_ok=True)
        
        # Track active pipelines
        self._active_pipelines: Dict[str, Dict[str, Any]] = {}
    
    def execute_pipeline(
        self,
        image_path: str,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete pipeline with the given configuration.
        
        Args:
            image_path: Path to input image
            config: Stage 0 configuration including:
                - dpi: DPI value
                - color_mode: Color mode
                - repeat_unit: Repeat dimensions {width, height}
            progress_callback: Optional callback for progress updates (stage_number, message)
        
        Returns:
            Pipeline execution result containing:
            - pipeline_id: Unique pipeline ID
            - status: Pipeline status
            - source_file: Original image path
            - result: Final result data
            - stage_outputs: Outputs from all stages
            - created_at: Creation timestamp
            - completed_at: Completion timestamp
        
        Raises:
            PipelineExecutionError: If pipeline execution fails
            ValueError: If configuration is invalid
        """
        # Validate inputs
        if not Path(image_path).exists():
            raise ValueError(f"Image file not found: {image_path}")
        
        # Create pipeline ID
        pipeline_id = str(uuid.uuid4())
        
        # Build pipeline configuration
        pipeline_config = self._build_pipeline_config(config)
        
        # Store pipeline info
        self._active_pipelines[pipeline_id] = {
            'pipeline_id': pipeline_id,
            'status': PipelineStatus.RUNNING,
            'source_file': image_path,
            'config': pipeline_config,
            'created_at': datetime.utcnow(),
            'current_stage': None,
            'completed_stages': [],
            'stage_outputs': {},
            'errors': []
        }
        
        logger.info(f"Starting pipeline {pipeline_id} for image: {image_path}")
        
        try:
            # Execute pipeline with progress tracking
            if progress_callback:
                # Wrap execution with progress updates
                result = self._execute_with_progress(
                    image_path,
                    pipeline_config,
                    progress_callback
                )
            else:
                # Direct execution
                result = self.pipeline_engine.execute(image_path, pipeline_config)
            
            # Update pipeline info
            self._active_pipelines[pipeline_id].update({
                'status': PipelineStatus.COMPLETED,
                'result': result,
                'completed_at': datetime.utcnow(),
                'current_stage': None
            })
            
            logger.info(f"Pipeline {pipeline_id} completed successfully")
            
            # Return formatted result
            return self._format_result(pipeline_id, result)
        
        except Exception as e:
            # Update pipeline with error
            self._active_pipelines[pipeline_id].update({
                'status': PipelineStatus.FAILED,
                'errors': [str(e)],
                'completed_at': datetime.utcnow(),
                'current_stage': None
            })
            
            logger.error(f"Pipeline {pipeline_id} failed: {str(e)}")
            raise PipelineExecutionError(
                message=f"Pipeline execution failed: {str(e)}",
                details={'pipeline_id': pipeline_id}
            ) from e
    
    def _build_pipeline_config(self, ui_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build pipeline configuration from UI config.
        
        Args:
            ui_config: Configuration from UI with dpi, color_mode, repeat_unit
        
        Returns:
            Complete pipeline configuration in format expected by pipeline engine
        """
        # Pipeline engine expects config keys at root level, not nested under stage_0
        # It looks for: config.get("dpi"), config.get("color_mode"), config.get("repeat_unit")
        pipeline_config = {
            'dpi': ui_config.get('dpi'),
            'color_mode': ui_config.get('color_mode'),
            'repeat_unit': ui_config.get('repeat_unit')
        }
        
        return pipeline_config
    
    def _execute_with_progress(
        self,
        image_path: str,
        config: Dict[str, Any],
        progress_callback: Callable[[int, str], None]
    ) -> Dict[str, Any]:
        """
        Execute pipeline with progress callbacks.
        
        Args:
            image_path: Path to input image
            config: Pipeline configuration
            progress_callback: Progress callback function
        
        Returns:
            Pipeline execution result
        """
        # Since we don't have direct stage callbacks in the current implementation,
        # we'll simulate progress by calling the callback for each stage
        # In a production implementation, you would integrate this into the pipeline engine
        
        from weaver.shared.constants import STAGE_NAMES
        
        # Call progress for each stage
        for stage_num in range(8):
            stage_name = STAGE_NAMES.get(stage_num, f"Stage {stage_num}")
            progress_callback(stage_num, stage_name)
        
        # Execute the actual pipeline
        result = self.pipeline_engine.execute(image_path, config)
        
        return result
    
    def _format_result(self, pipeline_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format pipeline result for UI consumption.
        
        Args:
            pipeline_id: Pipeline ID
            result: Raw pipeline result
        
        Returns:
            Formatted result dictionary
        """
        pipeline_info = self._active_pipelines.get(pipeline_id, {})
        
        formatted = {
            'pipeline_id': pipeline_id,
            'status': result.get('status', PipelineStatus.COMPLETED),
            'source_file': pipeline_info.get('source_file'),
            'result': result.get('result', {}),
            'stage_outputs': result.get('stage_outputs', {}),
            'created_at': pipeline_info.get('created_at').isoformat() if pipeline_info.get('created_at') else None,
            'completed_at': pipeline_info.get('completed_at').isoformat() if pipeline_info.get('completed_at') else None,
            'completed_stages': list(range(8)),  # All 8 stages completed
            'errors': pipeline_info.get('errors', [])
        }
        
        return formatted
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a pipeline execution.
        
        Args:
            pipeline_id: Pipeline ID to query
        
        Returns:
            Pipeline status information or None if not found
        """
        return self._active_pipelines.get(pipeline_id)
    
    def list_pipelines(self, limit: int = 50) -> list[Dict[str, Any]]:
        """
        List recent pipeline executions.
        
        Args:
            limit: Maximum number of pipelines to return
        
        Returns:
            List of pipeline information dictionaries
        """
        pipelines = list(self._active_pipelines.values())
        
        # Sort by creation time (most recent first)
        pipelines.sort(key=lambda p: p.get('created_at', datetime.min), reverse=True)
        
        return pipelines[:limit]
    
    def validate_stage_0_config(self, image_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Stage 0 configuration without executing the pipeline.
        
        Args:
            image_path: Path to input image
            config: Stage 0 configuration to validate
        
        Returns:
            Validation result with 'valid' bool and 'errors' list
        """
        from weaver.stages.stage_0_input_acquisition.processor import Stage0Input, RepeatUnit
        from weaver.shared.exceptions import InputSchemaError
        
        errors = []
        
        try:
            # Build Stage0Input for validation
            stage_0_input = Stage0Input(
                pipeline_id="validation",
                stage_number=0,
                image_path=image_path,
                dpi=config.get('dpi'),
                repeat_unit_px=RepeatUnit(
                    width=config.get('repeat_unit', {}).get('width'),
                    height=config.get('repeat_unit', {}).get('height')
                ),
                color_mode=config.get('color_mode')
            )
            
            # If we get here, Pydantic validation passed
            return {
                'valid': True,
                'errors': []
            }
        
        except InputSchemaError as e:
            errors.append(str(e))
        except ValueError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return {
            'valid': False,
            'errors': errors
        }
    
    def create_workspace(self, pipeline_id: str) -> Path:
        """
        Create a workspace directory for a pipeline execution.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            Path to created workspace directory
        """
        workspace_dir = self.workspace_base_dir / pipeline_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for each stage
        for stage_num in range(8):
            stage_dir = workspace_dir / f"stage_{stage_num}"
            stage_dir.mkdir(exist_ok=True)
        
        logger.info(f"Created workspace for pipeline {pipeline_id}: {workspace_dir}")
        
        return workspace_dir
    
    def cleanup_pipeline(self, pipeline_id: str, remove_workspace: bool = False) -> None:
        """
        Clean up pipeline resources.
        
        Args:
            pipeline_id: Pipeline ID to clean up
            remove_workspace: Whether to remove workspace directory
        """
        # Remove from active pipelines
        if pipeline_id in self._active_pipelines:
            del self._active_pipelines[pipeline_id]
        
        # Optionally remove workspace
        if remove_workspace:
            workspace_dir = self.workspace_base_dir / pipeline_id
            if workspace_dir.exists():
                import shutil
                shutil.rmtree(workspace_dir)
                logger.info(f"Removed workspace for pipeline {pipeline_id}")
