"""
Exception hierarchy for the pipeline system.
"""

from typing import Any, Dict, Optional


class WeaverError(Exception):
    """Base exception for all Weaver AI errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class PipelineError(WeaverError):
    """Base exception for pipeline-level errors."""
    pass


class StageError(WeaverError):
    """Base exception for stage-specific errors."""
    
    def __init__(self, message: str, stage_number: int, details: Optional[Dict[str, Any]] = None):
        self.stage_number = stage_number
        super().__init__(message, details)


class ValidationError(StageError):
    """Raised when input/output contract validation fails."""
    pass


class ConfigurationError(WeaverError):
    """Raised when configuration is invalid or missing."""
    pass


class StageNotFoundError(PipelineError):
    """Raised when a required stage cannot be loaded."""
    
    def __init__(self, stage_number: int):
        super().__init__(
            f"Stage {stage_number} not found or cannot be loaded",
            details={"stage_number": stage_number}
        )


class ContractViolationError(ValidationError):
    """Raised when a stage violates its input/output contract."""
    
    def __init__(self, stage_number: int, violations: list[str]):
        super().__init__(
            f"Stage {stage_number} violated its contract",
            stage_number=stage_number,
            details={"violations": violations}
        )


class ManufacturingConstraintError(StageError):
    """Raised when manufacturing constraints are violated."""
    pass


class PipelineExecutionError(PipelineError):
    """Raised when pipeline execution fails."""
    pass


class StageTimeoutError(StageError):
    """Raised when a stage execution exceeds timeout."""
    
    def __init__(self, stage_number: int, timeout_seconds: float):
        super().__init__(
            f"Stage {stage_number} exceeded timeout of {timeout_seconds}s",
            stage_number=stage_number,
            details={"timeout_seconds": timeout_seconds}
        )


# ============================================================================
# STAGE 0 - INPUT ACQUISITION EXCEPTIONS
# Manufacturing-first validation errors with zero tolerance
# ============================================================================

class InputFormatError(ValidationError):
    """
    Raised when input file format is not on the lossless allowlist.
    
    RATIONALE: Lossy formats (JPEG, WEBP) introduce compression artifacts
    that destroy thread-level precision needed for CAM export. Only lossless
    formats (PNG, TIFF, BMP) preserve manufacturing intent.
    """
    pass


class MetadataConsistencyError(ValidationError):
    """
    Raised when declared metadata conflicts with actual image properties.
    
    RATIONALE: Metadata inconsistency indicates data corruption or manual
    error. CAM systems require perfect metadata trust - any discrepancy
    halts the pipeline to prevent dimensional errors in physical fabric.
    """
    pass


class DimensionalConstraintError(ValidationError):
    """
    Raised when image dimensions exceed manufacturing equipment limits.
    
    RATIONALE: Jacquard looms have fixed maximum dimensions. Oversized
    designs cannot be manufactured and must be rejected at input to
    prevent downstream resource waste.
    """
    pass


class RepeatIntegrityError(ValidationError):
    """
    Raised when image dimensions are not integer multiples of repeat unit.
    
    RATIONALE: Non-integer tiling creates partial repeats at boundaries,
    which cannot be woven. Repeat unit must tile perfectly (width % repeat_w == 0)
    or the design is physically impossible to manufacture.
    """
    pass


class ResourceProtectionError(ValidationError):
    """
    Raised when input file exceeds memory or processing resource limits.
    
    RATIONALE: Prevents DoS and resource exhaustion. Stage 0 protects
    downstream stages from processing maliciously large or malformed files.
    """
    pass


class InputSchemaError(ValidationError):
    """
    Raised when input design package is missing required metadata fields.
    
    RATIONALE: Stage 0 requires explicit metadata (dpi, repeat_unit_px, color_mode).
    No inference allowed - missing data means incomplete specification and
    must be rejected to maintain source-of-truth integrity.
    """
    pass


# ============================================================================
# STAGE 2 - STRUCTURAL INTENT DEFINITION EXCEPTIONS
# Geometric invariant extraction with zero tolerance for ambiguity
# ============================================================================

class TopologyViolationError(ValidationError):
    """
    Raised when skeleton topology is broken or disconnected.
    
    RATIONALE: Broken topology indicates edge detection failure or
    structural inconsistency. Downstream diffusion and CAM stages
    require topologically sound skeletons - fragments or disconnected
    nodes cannot be reliably processed.
    """
    pass


class RegionLeakageError(ValidationError):
    """
    Raised when a detected region is not fully enclosed or overlaps with another.
    
    RATIONALE: Leaking regions indicate unclosed boundaries that violate
    manufacturing intent. CAM systems require closed, non-overlapping
    regions for proper thread path generation. Ambiguous boundaries
    must fail rather than be inferred.
    """
    pass


class BoundaryInconsistencyError(ValidationError):
    """
    Raised when repeat boundary mask does not align with declared repeat dimensions.
    
    RATIONALE: Repeat boundaries are immutable constraints for tiling.
    Any pixel-level misalignment between declared dimensions and generated
    mask indicates incorrect metadata or edge detection failure, which
    would cause repeat violations in downstream stages.
    """
    pass
