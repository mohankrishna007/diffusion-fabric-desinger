"""
Stage loader - Loads pipeline stages directly from configuration.
"""

from typing import Dict, List
from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages import STAGE_CLASSES
from weaver.shared.exceptions import StageNotFoundError, ConfigurationError


class StageLoader:
    """
    Loads and manages pipeline stage instances.
    Stages are loaded directly based on class names from configuration.
    """
    
    def __init__(self):
        self._stage_cache: Dict[str, BaseStage] = {}
    
    def load_stage(self, class_name: str) -> BaseStage:
        """
        Load a stage by its class name.
        
        Args:
            class_name: Stage class name (e.g., "InputAcquisitionStage")
        
        Returns:
            Instantiated stage
        
        Raises:
            StageNotFoundError: If stage class not found
            ConfigurationError: If stage cannot be instantiated
        """
        # Check cache first
        if class_name in self._stage_cache:
            return self._stage_cache[class_name]
        
        # Get stage class
        if class_name not in STAGE_CLASSES:
            available = ", ".join(STAGE_CLASSES.keys())
            raise StageNotFoundError(
                f"Stage class '{class_name}' not found. Available: {available}"
            )
        
        try:
            stage_class = STAGE_CLASSES[class_name]
            stage_instance = stage_class()
            
            # Cache the stage
            self._stage_cache[class_name] = stage_instance
            
            return stage_instance
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to instantiate stage '{class_name}': {str(e)}"
            ) from e
    
    def load_all_stages(self, class_names: List[str]) -> Dict[str, BaseStage]:
        """
        Load multiple stages.
        
        Args:
            class_names: List of stage class names to load
        
        Returns:
            Dictionary mapping class names to stage instances
        """
        stages = {}
        for class_name in class_names:
            stages[class_name] = self.load_stage(class_name)
        return stages
    
    def clear_cache(self) -> None:
        """Clear the stage cache."""
        self._stage_cache.clear()

