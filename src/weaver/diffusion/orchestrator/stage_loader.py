"""
Stage loader - Dynamically discovers and loads pipeline stages.
"""

import importlib
from typing import Type, Dict
from weaver.diffusion.stages.base import BaseStage, StageMetadata
from weaver.shared.exceptions import StageNotFoundError, ConfigurationError


class StageLoader:
    """
    Loads and manages pipeline stage instances.
    Discovers stages by importing their modules and instantiating stage classes.
    """
    
    def __init__(self):
        self._stage_cache: Dict[int, BaseStage] = {}
        self._stage_metadata: Dict[int, StageMetadata] = {}
    
    def load_stage(self, stage_number: int) -> BaseStage:
        """
        Load a stage by its number.
        
        Args:
            stage_number: Stage number (0-7)
        
        Returns:
            Instantiated stage
        
        Raises:
            StageNotFoundError: If stage cannot be loaded
        """
        # Check cache first
        if stage_number in self._stage_cache:
            return self._stage_cache[stage_number]
        
        # Map stage numbers to module paths
        stage_map = {
            0: "weaver.diffusion.stages.stage_0_input_acquisition",
            1: "weaver.diffusion.stages.stage_1_canonical_normalization",
            2: "weaver.diffusion.stages.stage_2_structural_intent",
            3: "weaver.diffusion.stages.stage_3_diffusion_refinement",
            4: "weaver.diffusion.stages.stage_4_repeat_enforcement",
            5: "weaver.diffusion.stages.stage_5_geometry_cleanup",
            6: "weaver.diffusion.stages.stage_6_color_constraint",
            7: "weaver.diffusion.stages.stage_7_precam_validation",
        }
        
        stage_class_map = {
            0: "Stage0InputAcquisition",
            1: "Stage1CanonicalNormalization",
            2: "Stage2StructuralIntent",
            3: "Stage3DiffusionRefinement",
            4: "Stage4RepeatEnforcement",
            5: "Stage5GeometryCleanup",
            6: "Stage6ColorConstraint",
            7: "Stage7PreCAMValidation",
        }
        
        if stage_number not in stage_map:
            raise StageNotFoundError(stage_number)
        
        try:
            # Import the stage module
            module_path = stage_map[stage_number]
            module = importlib.import_module(module_path)
            
            # Get the stage class
            class_name = stage_class_map[stage_number]
            stage_class: Type[BaseStage] = getattr(module, class_name)
            
            # Instantiate the stage
            stage_instance = stage_class()
            
            # Cache the stage
            self._stage_cache[stage_number] = stage_instance
            self._stage_metadata[stage_number] = stage_instance.metadata
            
            return stage_instance
            
        except ImportError as e:
            raise StageNotFoundError(stage_number) from e
        except AttributeError as e:
            raise ConfigurationError(
                f"Stage {stage_number} module missing expected class {class_name}",
                details={"stage_number": stage_number, "class_name": class_name}
            ) from e
    
    def load_all_stages(self) -> Dict[int, BaseStage]:
        """
        Load all stages (0-7).
        
        Returns:
            Dictionary mapping stage numbers to stage instances
        """
        stages = {}
        for stage_number in range(8):
            stages[stage_number] = self.load_stage(stage_number)
        return stages
    
    def get_stage_metadata(self, stage_number: int) -> StageMetadata:
        """
        Get metadata for a stage without fully loading it.
        
        Args:
            stage_number: Stage number
        
        Returns:
            Stage metadata
        """
        if stage_number not in self._stage_metadata:
            stage = self.load_stage(stage_number)
            self._stage_metadata[stage_number] = stage.metadata
        
        return self._stage_metadata[stage_number]
    
    def clear_cache(self) -> None:
        """Clear the stage cache."""
        self._stage_cache.clear()
        self._stage_metadata.clear()

