"""
Unified Pipeline Service
High-level abstraction over the pipeline engine for use by multiple interfaces
(REST API, Streamlit UI, Python package, CLI, etc.)
"""

import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from weaver.diffusion.orchestrator.pipeline_engine import PipelineEngine
from weaver.shared.schemas import PipelineStatus
from weaver.shared.exceptions import PipelineExecutionError, ValidationError
from weaver.shared.constants import (
    MIN_DPI, MAX_DPI, VALID_COLOR_MODES,
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT, MAX_FILE_SIZE_BYTES
)


logger = logging.getLogger(__name__)


class DiffusionPipelineService:
    """
    Unified service layer for diffusion fabric design pipeline execution.
    
    This service specifically handles the 8-stage diffusion fabric pipeline.
    Design allows adding other services (e.g., DenoiseService, PreprocessService)
    alongside this one for modular architecture.
    
    Provides a consistent interface for:
    - REST API endpoints
    - Streamlit UI
    - Direct Python package usage
    - CLI tools
    - Future interfaces (gRPC, GraphQL, etc.)
    
    Benefits:
    - Single source of truth for pipeline operations
    - Consistent error handling across interfaces
    - Centralized business logic
    - Easy to test and maintain
    - Extensible for new interfaces
    """
    
    def __init__(
        self,
        workspace_base_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the pipeline service.
        
        Args:
            workspace_base_dir: Base directory for pipeline workspaces (default: "storage")
            config: Optional global configuration for the pipeline engine
        """
        self.pipeline_engine = PipelineEngine(config=config)
        self.workspace_base_dir = Path(workspace_base_dir or "storage")
        self.workspace_base_dir.mkdir(exist_ok=True)
        
        # Track active pipelines for status queries
        self._active_pipelines: Dict[str, Dict[str, Any]] = {}
    
    # ========================================================================
    # PUBLIC API - Main entry points
    # ========================================================================
    
    def execute_pipeline(
        self,
        image_path: str,
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        workspace_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete 8-stage pipeline.
        
        This is the main entry point for pipeline execution from any interface.
        
        Args:
            image_path: Path to input fabric design image
            config: Pipeline configuration with Stage 0 parameters:
                - dpi: DPI value (72-1200)
                - color_mode: Color mode (RGB, RGBA, L, LA)
                - repeat_unit: {width: int, height: int}
            progress_callback: Optional callback for progress updates (stage_number, message)
            workspace_dir: Optional custom workspace directory for this pipeline
        
        Returns:
            Pipeline execution result:
            {
                'pipeline_id': str,
                'status': str,
                'source_file': str,
                'result': dict,
                'stage_outputs': dict,
                'created_at': str,
                'completed_at': str,
                'completed_stages': list,
                'errors': list
            }
        
        Raises:
            PipelineExecutionError: If pipeline execution fails
            ValidationError: If input validation fails
        """
        # Generate unique pipeline ID
        pipeline_id = str(uuid.uuid4())
        
        # Validate inputs
        self._validate_inputs(image_path, config)
        
        # Build pipeline configuration
        pipeline_config = self._build_config(config or {})
        
        # Create workspace if needed
        if workspace_dir:
            workspace_path = Path(workspace_dir)
        else:
            workspace_path = self.workspace_base_dir / pipeline_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize pipeline tracking
        self._active_pipelines[pipeline_id] = {
            'pipeline_id': pipeline_id,
            'status': PipelineStatus.RUNNING,
            'source_file': image_path,
            'config': pipeline_config,
            'workspace_dir': str(workspace_path),
            'created_at': datetime.utcnow(),
            'current_stage': None,
            'completed_stages': [],
            'stage_outputs': {},
            'errors': []
        }
        
        logger.info(f"Starting pipeline execution: {pipeline_id} for {Path(image_path).name}")
        
        try:
            # Execute pipeline with optional progress tracking
            if progress_callback:
                result = self._execute_with_progress(
                    image_path,
                    pipeline_config,
                    progress_callback
                )
            else:
                result = self.pipeline_engine.execute(image_path, pipeline_config)
            
            # Update pipeline tracking
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
                details={'pipeline_id': pipeline_id, 'error': str(e)}
            ) from e
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a pipeline execution.
        
        Args:
            pipeline_id: Pipeline ID to query
        
        Returns:
            Pipeline status information or None if not found:
            {
                'pipeline_id': str,
                'status': str,
                'source_file': str,
                'config': dict,
                'created_at': datetime,
                'current_stage': int,
                'completed_stages': list,
                'errors': list
            }
        """
        return self._active_pipelines.get(pipeline_id)
    
    def list_pipelines(
        self,
        limit: int = 50,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List recent pipeline executions.
        
        Args:
            limit: Maximum number of pipelines to return
            status_filter: Optional status to filter by (e.g., 'completed', 'failed')
        
        Returns:
            List of pipeline information dictionaries
        """
        pipelines = list(self._active_pipelines.values())
        
        # Filter by status if requested
        if status_filter:
            pipelines = [p for p in pipelines if p.get('status') == status_filter]
        
        # Sort by creation time (most recent first)
        pipelines.sort(
            key=lambda p: p.get('created_at', datetime.min),
            reverse=True
        )
        
        return pipelines[:limit]
    
    def validate_config(
        self,
        image_path: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate configuration without executing the pipeline.
        
        Args:
            image_path: Path to input image
            config: Configuration to validate
        
        Returns:
            Validation result:
            {
                'valid': bool,
                'errors': list,
                'warnings': list
            }
        """
        errors = []
        warnings = []
        
        try:
            # Validate image path
            if not Path(image_path).exists():
                errors.append(f"Image file not found: {image_path}")
            
            # Validate config structure
            self._validate_config_schema(config, errors, warnings)
            
            # Validate against Stage 0 requirements
            if not errors:
                self._validate_stage_0_requirements(image_path, config, errors, warnings)
        
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def cleanup_pipeline(
        self,
        pipeline_id: str,
        remove_workspace: bool = False
    ) -> None:
        """
        Clean up pipeline resources.
        
        Args:
            pipeline_id: Pipeline ID to clean up
            remove_workspace: Whether to remove workspace directory
        """
        # Remove from active pipelines
        if pipeline_id in self._active_pipelines:
            pipeline_info = self._active_pipelines[pipeline_id]
            del self._active_pipelines[pipeline_id]
            
            # Optionally remove workspace
            if remove_workspace:
                workspace_dir = Path(pipeline_info.get('workspace_dir', ''))
                if workspace_dir.exists():
                    import shutil
                    shutil.rmtree(workspace_dir)
                    logger.info(f"Removed workspace for pipeline {pipeline_id}")
    
    # ========================================================================
    # PRIVATE METHODS - Internal implementation
    # ========================================================================
    
    def _validate_inputs(
        self,
        image_path: str,
        config: Optional[Dict[str, Any]]
    ) -> None:
        """Validate input parameters."""
        # Check image exists
        if not Path(image_path).exists():
            raise ValidationError(
                message=f"Image file not found: {image_path}",
                stage_number=0,
                details={'image_path': image_path}
            )
        
        # Check file size
        file_size = Path(image_path).stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                message=f"File size {file_size} exceeds maximum {MAX_FILE_SIZE_BYTES}",
                stage_number=0,
                details={'file_size': file_size, 'max_size': MAX_FILE_SIZE_BYTES}
            )
    
    def _build_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build pipeline configuration from input config.
        
        Ensures config is in the format expected by pipeline engine.
        """
        # Pipeline engine expects flat structure with these keys:
        # - dpi
        # - color_mode
        # - repeat_unit (dict with width, height)
        
        return {
            'dpi': config.get('dpi'),
            'color_mode': config.get('color_mode'),
            'repeat_unit': config.get('repeat_unit')
        }
    
    def _execute_with_progress(
        self,
        image_path: str,
        config: Dict[str, Any],
        progress_callback: Callable[[int, str], None]
    ) -> Dict[str, Any]:
        """Execute pipeline with progress callbacks."""
        from weaver.shared.constants import STAGE_NAMES
        
        # Call progress for each stage
        # (In production, this would integrate with actual stage execution)
        for stage_num in range(8):
            stage_name = STAGE_NAMES.get(stage_num, f"Stage {stage_num}")
            progress_callback(stage_num, stage_name)
        
        # Execute the actual pipeline
        result = self.pipeline_engine.execute(image_path, config)
        
        return result
    
    def _format_result(
        self,
        pipeline_id: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format pipeline result for output."""
        pipeline_info = self._active_pipelines.get(pipeline_id, {})
        
        # Handle datetime serialization
        created_at = pipeline_info.get('created_at')
        completed_at = pipeline_info.get('completed_at')
        
        return {
            'pipeline_id': pipeline_id,
            'status': result.get('status', PipelineStatus.COMPLETED),
            'source_file': pipeline_info.get('source_file'),
            'result': result.get('result', {}),
            'stage_outputs': result.get('stage_outputs', {}),
            'created_at': created_at.isoformat() if created_at else None,
            'completed_at': completed_at.isoformat() if completed_at else None,
            'completed_stages': list(range(8)) if result.get('status') == PipelineStatus.COMPLETED else [],
            'errors': pipeline_info.get('errors', [])
        }
    
    def _validate_config_schema(
        self,
        config: Dict[str, Any],
        errors: List[str],
        warnings: List[str]
    ) -> None:
        """Validate configuration schema."""
        # Check required fields
        if 'dpi' not in config:
            errors.append("Missing required field: dpi")
        elif not isinstance(config['dpi'], int):
            errors.append("DPI must be an integer")
        elif not (MIN_DPI <= config['dpi'] <= MAX_DPI):
            errors.append(f"DPI must be between {MIN_DPI} and {MAX_DPI}")
        
        if 'color_mode' not in config:
            errors.append("Missing required field: color_mode")
        elif config['color_mode'] not in VALID_COLOR_MODES:
            errors.append(f"Invalid color mode. Must be one of {VALID_COLOR_MODES}")
        
        if 'repeat_unit' not in config:
            errors.append("Missing required field: repeat_unit")
        else:
            repeat = config['repeat_unit']
            if not isinstance(repeat, dict):
                errors.append("repeat_unit must be a dictionary")
            elif 'width' not in repeat or 'height' not in repeat:
                errors.append("repeat_unit must have 'width' and 'height'")
            elif repeat.get('width', 0) <= 0 or repeat.get('height', 0) <= 0:
                errors.append("repeat_unit width and height must be positive")
    
    def _validate_stage_0_requirements(
        self,
        image_path: str,
        config: Dict[str, Any],
        errors: List[str],
        warnings: List[str]
    ) -> None:
        """Validate against Stage 0 requirements."""
        try:
            from PIL import Image
            
            img = Image.open(image_path)
            width, height = img.size
            
            # Check dimensions
            if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                errors.append(
                    f"Image dimensions ({width}x{height}) exceed maximum "
                    f"({MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT})"
                )
            
            # Check perfect tiling
            repeat = config.get('repeat_unit', {})
            repeat_width = repeat.get('width', 0)
            repeat_height = repeat.get('height', 0)
            
            if repeat_width > 0 and repeat_height > 0:
                if width % repeat_width != 0:
                    errors.append(
                        f"Image width {width} not divisible by repeat width {repeat_width}"
                    )
                if height % repeat_height != 0:
                    errors.append(
                        f"Image height {height} not divisible by repeat height {repeat_height}"
                    )
            
            # Check color mode match
            if img.mode != config.get('color_mode'):
                warnings.append(
                    f"Image color mode {img.mode} differs from declared {config.get('color_mode')}"
                )
            
            # Check DPI match
            dpi_info = img.info.get('dpi')
            if dpi_info:
                actual_dpi = int(round(dpi_info[0]))
                declared_dpi = config.get('dpi', 0)
                tolerance = max(1, int(declared_dpi * 0.01))
                if abs(actual_dpi - declared_dpi) > tolerance:
                    warnings.append(
                        f"Image DPI {actual_dpi} differs from declared {declared_dpi} "
                        f"(tolerance: ±{tolerance})"
                    )
        
        except Exception as e:
            errors.append(f"Error validating image: {str(e)}")

