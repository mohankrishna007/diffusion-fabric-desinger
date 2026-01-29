"""
Stage loader - Dynamically discovers and loads pipeline stages using registry pattern.
"""

from typing import Dict, List
from weaver.diffusion.stages.base import BaseStage, StageMetadata
from weaver.diffusion.orchestrator.stage_registry import stage_registry, StageRegistration
from weaver.shared.exceptions import StageNotFoundError, ConfigurationError


class StageLoader:
    """
    Loads and manages pipeline stage instances using the stage registry.
    Provides caching and lazy loading of stages.
    """
    
    def __init__(self):
        self._stage_cache: Dict[str, BaseStage] = {}
        self._stage_metadata: Dict[str, StageMetadata] = {}
    
    def load_stage(self, stage_id: str) -> BaseStage:
        """
        Load a stage by its identifier.
        
        Args:
            stage_id: Stage identifier (e.g., "input_acquisition")
        
        Returns:
            Instantiated stage
        
        Raises:
            StageNotFoundError: If stage cannot be loaded
        """
        # Check cache first
        if stage_id in self._stage_cache:
            return self._stage_cache[stage_id]
        
        try:
            # Get stage class from registry
            stage_class = stage_registry.get_stage_class(stage_id)
            
            # Instantiate the stage
            stage_instance = stage_class()
            
            # Cache the stage
            self._stage_cache[stage_id] = stage_instance
            self._stage_metadata[stage_id] = stage_instance.metadata
            
            return stage_instance
            
        except StageNotFoundError:
            raise
        except Exception as e:
            raise ConfigurationError(
                f"Failed to instantiate stage '{stage_id}': {str(e)}"
            ) from e
    
    def load_all_stages(self, stage_ids: List[str]) -> Dict[str, BaseStage]:
        """
        Load multiple stages.
        
        Args:
            stage_ids: List of stage identifiers to load
        
        Returns:
            Dictionary mapping stage IDs to stage instances
        """
        stages = {}
        for stage_id in stage_ids:
            stages[stage_id] = self.load_stage(stage_id)
        return stages
    
    def get_stage_metadata(self, stage_id: str) -> StageMetadata:
        """
        Get metadata for a stage without fully loading it.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            Stage metadata
        """
        if stage_id not in self._stage_metadata:
            stage = self.load_stage(stage_id)
            self._stage_metadata[stage_id] = stage.metadata
        
        return self._stage_metadata[stage_id]
    
    def get_registration(self, stage_id: str) -> StageRegistration:
        """
        Get full registration information for a stage.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            Stage registration
        """
        return stage_registry.get_registration(stage_id)
    
    def get_all_registrations(self) -> Dict[str, StageRegistration]:
        """
        Get all registered stages.
        
        Returns:
            Dictionary mapping stage IDs to registrations
        """
        return stage_registry.get_all_registrations()
    
    def clear_cache(self) -> None:
        """Clear the stage cache."""
        self._stage_cache.clear()
        self._stage_metadata.clear()

