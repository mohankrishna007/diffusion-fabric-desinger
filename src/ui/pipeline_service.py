"""
UI Pipeline Service Wrapper for Streamlit
Provides Streamlit-specific interface over the shared DiffusionPipelineService
"""

import logging
import streamlit as st
from typing import Dict, Any, Optional, Callable

from services.diffusion_pipeline_service import DiffusionPipelineService


logger = logging.getLogger(__name__)


class PipelineService:
    """
    Streamlit-specific wrapper for the shared DiffusionPipelineService.
    
    This class provides Streamlit-specific adaptations like:
    - Session state integration
    - Streamlit progress bar updates
    - Streamlit-specific error handling and display
    
    For REST API, CLI, or direct package usage, use the shared
    services.DiffusionPipelineService directly.
    """
    
    def __init__(self, storage_base_dir: Optional[str] = None):
        """
        Initialize the UI pipeline service.
        
        Args:
            storage_base_dir: Base directory for pipeline storage
        """
        # Initialize shared service
        self.service = DiffusionPipelineService(storage_base_dir=storage_base_dir)
        logger.info("Initialized Streamlit Pipeline Service (wrapping DiffusionPipelineService)")

    
    def execute_pipeline(
        self,
        image_path: str,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete pipeline with Streamlit-specific UI adaptations.
        
        Args:
            image_path: Path to input image
            config: Source data for stage 0 including:
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
            ValidationError: If input validation fails
        """
        # Wrap progress callback with Streamlit-specific UI updates
        if progress_callback:
            streamlit_callback = self._wrap_progress_callback(progress_callback)
        else:
            streamlit_callback = None
        
        # Delegate to shared service
        return self.service.execute_pipeline(
            source_file=image_path,
            source_data=config,
            progress_callback=streamlit_callback
        )
    
    def _wrap_progress_callback(
        self,
        callback: Callable[[int, str], None]
    ) -> Callable[[int, str], None]:
        """
        Wrap user callback with Streamlit UI updates.
        
        Args:
            callback: Original callback function
        
        Returns:
            Wrapped callback that updates Streamlit UI
        """
        def streamlit_callback(stage_num: int, message: str):
            # Update session state for UI tracking
            if 'pipeline_current_stage' not in st.session_state:
                st.session_state.pipeline_current_stage = stage_num
            else:
                st.session_state.pipeline_current_stage = stage_num
            
            # Call original callback
            callback(stage_num, message)
        
        return streamlit_callback
    
    def validate_stage_0_config(self, image_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Stage 0 configuration without executing the pipeline.
        
        This wraps the shared service's validate_config method.
        
        Args:
            image_path: Path to input image
            config: Stage 0 configuration to validate
        
        Returns:
            Validation result with 'valid' bool and 'errors' list
        """
        return self.service.validate_config(image_path, config)
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline status from shared service."""
        return self.service.get_pipeline_status(pipeline_id)
    
    def list_pipelines(self, limit: int = 50) -> list[Dict[str, Any]]:
        """List pipelines from shared service."""
        return self.service.list_pipelines(limit=limit)
    
    def cleanup_pipeline(self, pipeline_id: str, remove_workspace: bool = False) -> None:
        """Clean up pipeline from shared service."""
        self.service.cleanup_pipeline(pipeline_id, remove_storage=remove_workspace)

