"""
Dimension Validator - Stage 0 Sub-Module

PURPOSE:
Validate image dimensions against Jacquard loom physical constraints.
Oversized designs cannot be manufactured.

GUARANTEES:
- Width within manufacturing limits
- Height within manufacturing limits
- Total pixel count within processing limits
- Fast-fail on oversized designs

RATIONALE:
Jacquard looms have fixed maximum dimensions. Processing oversized designs
wastes resources and cannot produce physical output.

FORBIDDEN:
- Must not accept oversized images with warnings
- Must not attempt auto-resizing
- Must not infer acceptable dimensions
"""

from typing import Dict, Any

from weaver.shared.exceptions import DimensionalConstraintError
from weaver.shared.constants import (
    MAX_IMAGE_WIDTH,
    MAX_IMAGE_HEIGHT,
    MAX_MEGAPIXELS
)
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_dimensions(width: int, height: int) -> Dict[str, Any]:
    """
    Validate image dimensions against manufacturing limits.
    
    WHY:
    Jacquard looms have fixed maximum dimensions (e.g., 10,000 x 10,000 pixels).
    Exceeding these limits means the design is physically impossible to manufacture.
    
    Checking dimensions early prevents wasted processing on impossible designs.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        
    Returns:
        Dict with dimension validation results
        
    Raises:
        DimensionalConstraintError: If dimensions exceed manufacturing limits
    """
    logger.debug(f"Validating dimensions: {width}x{height}")
    
    violations = []
    
    # Check width limit
    if width > MAX_IMAGE_WIDTH:
        violations.append(
            f"Width {width:,}px exceeds maximum {MAX_IMAGE_WIDTH:,}px"
        )
    
    # Check height limit
    if height > MAX_IMAGE_HEIGHT:
        violations.append(
            f"Height {height:,}px exceeds maximum {MAX_IMAGE_HEIGHT:,}px"
        )
    
    # Check total megapixels
    megapixels = (width * height) / 1_000_000
    if megapixels > MAX_MEGAPIXELS:
        violations.append(
            f"Image {megapixels:.1f}MP exceeds maximum {MAX_MEGAPIXELS}MP"
        )
    
    if violations:
        logger.error(f"Dimension validation failed: {violations}")
        raise DimensionalConstraintError(
            message="Dimensional constraints violated",
            stage_number=0,
            details={
                "violations": violations,
                "width_px": width,
                "height_px": height,
                "megapixels": megapixels,
                "max_width": MAX_IMAGE_WIDTH,
                "max_height": MAX_IMAGE_HEIGHT,
                "max_megapixels": MAX_MEGAPIXELS,
                "rationale": (
                    "Oversized designs exceed Jacquard loom physical limits "
                    "and cannot be manufactured. Early rejection prevents "
                    "wasted processing on impossible designs."
                )
            }
        )
    
    logger.debug(
        f"Dimension validation passed: {width}x{height} ({megapixels:.1f}MP)"
    )
    
    return {
        "width_px": width,
        "height_px": height,
        "megapixels": megapixels,
        "dimensions_validated": True
    }


def validate_dimensions_positive(width: int, height: int) -> None:
    """
    Validate that dimensions are positive integers.
    
    Basic sanity check - should be called before manufacturing limit checks.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        
    Raises:
        DimensionalConstraintError: If dimensions are not positive
    """
    violations = []
    
    if width <= 0:
        violations.append(f"Width must be positive, got {width}")
    
    if height <= 0:
        violations.append(f"Height must be positive, got {height}")
    
    if violations:
        raise DimensionalConstraintError(
            message="Invalid image dimensions",
            stage_number=0,
            details={
                "violations": violations,
                "width_px": width,
                "height_px": height,
                "rationale": "Image dimensions must be positive integers"
            }
        )
