"""
Pipeline stages package.
Each stage is implemented as an independent module that conforms to the BaseStage contract.
All stages are imported and made available as a module-level dictionary.
"""

from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
import warnings

# Import all stage classes
# Map stage class names to actual classes for dynamic loading
STAGE_CLASSES = {}

try:
    from weaver.diffusion.stages.input_acquisition.processor import InputAcquisitionStage
    STAGE_CLASSES['InputAcquisitionStage'] = InputAcquisitionStage
except ImportError as e:
    warnings.warn(f"Could not import InputAcquisitionStage: {e}")

try:
    from weaver.diffusion.stages.canonical_normalization.processor import CanonicalNormalizationStage
    STAGE_CLASSES['CanonicalNormalizationStage'] = CanonicalNormalizationStage
except ImportError as e:
    warnings.warn(f"Could not import CanonicalNormalizationStage: {e}")

try:
    from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
    STAGE_CLASSES['StructuralIntentStage'] = StructuralIntentStage
except ImportError as e:
    warnings.warn(f"Could not import StructuralIntentStage: {e}")

try:
    from weaver.diffusion.stages.diffusion_refinement.processor import DiffusionRefinementStage
    STAGE_CLASSES['DiffusionRefinementStage'] = DiffusionRefinementStage
except ImportError as e:
    warnings.warn(f"Could not import DiffusionRefinementStage: {e}")

try:
    from weaver.diffusion.stages.repeat_enforcement.processor import RepeatEnforcementStage
    STAGE_CLASSES['RepeatEnforcementStage'] = RepeatEnforcementStage
except ImportError as e:
    warnings.warn(f"Could not import RepeatEnforcementStage: {e}")

try:
    from weaver.diffusion.stages.geometry_cleanup.processor import GeometryCleanupStage
    STAGE_CLASSES['GeometryCleanupStage'] = GeometryCleanupStage
except ImportError as e:
    warnings.warn(f"Could not import GeometryCleanupStage: {e}")

try:
    from weaver.diffusion.stages.color_constraint.processor import ColorConstraintStage
    STAGE_CLASSES['ColorConstraintStage'] = ColorConstraintStage
except ImportError as e:
    warnings.warn(f"Could not import ColorConstraintStage: {e}")

try:
    from weaver.diffusion.stages.precam_validation.processor import PreCAMValidationStage
    STAGE_CLASSES['PreCAMValidationStage'] = PreCAMValidationStage
except ImportError as e:
    warnings.warn(f"Could not import PreCAMValidationStage: {e}")


__all__ = ["BaseStage", "StageMetadata", "STAGE_CLASSES"]

