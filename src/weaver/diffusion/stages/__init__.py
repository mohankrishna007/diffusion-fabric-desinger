"""
Pipeline stages package.
Each stage is implemented as an independent module that conforms to the BaseStage contract.

This module imports all stage implementations to trigger their @stage_registry.register() decorators.
Import this package early in application startup to ensure all stages are registered.
"""

from weaver.diffusion.stages.base import BaseStage, StageMetadata

# Import all stage modules to trigger registration decorators
# The @stage_registry.register() decorator on each stage class automatically
# registers it when the module is imported

import warnings

ALL_STAGES = []

# Import each stage individually to allow partial registration on import errors
try:
    from weaver.diffusion.stages.stage_0_input_acquisition.processor import Stage0InputAcquisition
    ALL_STAGES.append(Stage0InputAcquisition)
except ImportError as e:
    warnings.warn(f"Could not import Stage 0: {e}")

try:
    from weaver.diffusion.stages.stage_1_canonical_normalization.processor import Stage1CanonicalNormalization
    ALL_STAGES.append(Stage1CanonicalNormalization)
except ImportError as e:
    warnings.warn(f"Could not import Stage 1: {e}")

try:
    from weaver.diffusion.stages.stage_2_structural_intent.processor import Stage2StructuralIntent
    ALL_STAGES.append(Stage2StructuralIntent)
except ImportError as e:
    warnings.warn(f"Could not import Stage 2: {e}")

try:
    from weaver.diffusion.stages.stage_3_diffusion_refinement.processor import Stage3DiffusionRefinement
    ALL_STAGES.append(Stage3DiffusionRefinement)
except ImportError as e:
    warnings.warn(f"Could not import Stage 3: {e}")

try:
    from weaver.diffusion.stages.stage_4_repeat_enforcement.processor import Stage4RepeatEnforcement
    ALL_STAGES.append(Stage4RepeatEnforcement)
except ImportError as e:
    warnings.warn(f"Could not import Stage 4: {e}")

try:
    from weaver.diffusion.stages.stage_5_geometry_cleanup.processor import Stage5GeometryCleanup
    ALL_STAGES.append(Stage5GeometryCleanup)
except ImportError as e:
    warnings.warn(f"Could not import Stage 5: {e}")

try:
    from weaver.diffusion.stages.stage_6_color_constraint.processor import Stage6ColorConstraint
    ALL_STAGES.append(Stage6ColorConstraint)
except ImportError as e:
    warnings.warn(f"Could not import Stage 6: {e}")

try:
    from weaver.diffusion.stages.stage_7_precam_validation.processor import Stage7PreCAMValidation
    ALL_STAGES.append(Stage7PreCAMValidation)
except ImportError as e:
    warnings.warn(f"Could not import Stage 7: {e}")



def get_registered_stage_count() -> int:
    """
    Get the number of registered stages.
    
    Returns:
        Number of stages registered in the global registry
    """
    from weaver.diffusion.orchestrator.stage_registry import stage_registry
    return len(stage_registry.get_all_registrations())


def validate_all_stages_registered() -> bool:
    """
    Validate that all expected stages are registered.
    
    Returns:
        True if all stages are registered, False otherwise
    """
    from weaver.diffusion.orchestrator.stage_registry import stage_registry
    registrations = stage_registry.get_all_registrations()
    
    expected_ids = {
        "input_acquisition",
        "canonical_normalization",
        "structural_intent",
        "diffusion_refinement",
        "repeat_enforcement",
        "geometry_cleanup",
        "color_constraint",
        "precam_validation",
    }
    
    registered_ids = set(registrations.keys())
    
    if expected_ids != registered_ids:
        missing = expected_ids - registered_ids
        extra = registered_ids - expected_ids
        
        if missing:
            import warnings
            warnings.warn(f"Missing stage registrations: {missing}")
        if extra:
            import warnings
            warnings.warn(f"Unexpected stage registrations: {extra}")
        
        return False
    
    return True


__all__ = ["BaseStage", "StageMetadata", "ALL_STAGES", "get_registered_stage_count", "validate_all_stages_registered"]

