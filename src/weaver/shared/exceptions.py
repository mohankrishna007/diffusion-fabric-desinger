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
