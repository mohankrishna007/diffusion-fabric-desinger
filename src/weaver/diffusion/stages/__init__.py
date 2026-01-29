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
    from weaver.diffusion.stages.input_acquisition.processor import InputAcquisitionStage
    ALL_STAGES.append(InputAcquisitionStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 0: {e}")

try:
    from weaver.diffusion.stages.canonical_normalization.processor import CanonicalNormalizationStage
    ALL_STAGES.append(CanonicalNormalizationStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 1: {e}")

try:
    from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
    ALL_STAGES.append(StructuralIntentStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 2: {e}")

try:
    from weaver.diffusion.stages.diffusion_refinement.processor import DiffusionRefinementStage
    ALL_STAGES.append(DiffusionRefinementStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 3: {e}")

try:
    from weaver.diffusion.stages.repeat_enforcement.processor import RepeatEnforcementStage
    ALL_STAGES.append(RepeatEnforcementStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 4: {e}")

try:
    from weaver.diffusion.stages.geometry_cleanup.processor import GeometryCleanupStage
    ALL_STAGES.append(GeometryCleanupStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 5: {e}")

try:
    from weaver.diffusion.stages.color_constraint.processor import ColorConstraintStage
    ALL_STAGES.append(ColorConstraintStage)
except ImportError as e:
    warnings.warn(f"Could not import Stage 6: {e}")

try:
    from weaver.diffusion.stages.precam_validation.processor import PreCAMValidationStage
    ALL_STAGES.append(PreCAMValidationStage)
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

