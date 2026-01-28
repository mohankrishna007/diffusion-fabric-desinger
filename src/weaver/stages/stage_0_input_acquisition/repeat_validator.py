"""
Repeat Validator - Stage 0 Sub-Module

PURPOSE:
Validate perfect repeat unit tiling. Non-integer tiling creates partial
repeats at boundaries, which cannot be woven.

GUARANTEES:
- Image dimensions are exact multiples of repeat dimensions
- No partial repeats at boundaries
- Repeat unit fits within image
- Perfect tiling validated

RATIONALE:
Weaving requires complete repeat units. Partial repeats at edges are
physically impossible to manufacture on Jacquard looms.

FORBIDDEN:
- Must not accept partial repeats with warnings
- Must not auto-crop or pad to fix tiling
- Must not infer repeat dimensions
- Must not suggest corrections
"""

from typing import Dict, Any

from weaver.shared.exceptions import RepeatIntegrityError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_repeat_integrity(
    image_width: int,
    image_height: int,
    repeat_width: int,
    repeat_height: int
) -> Dict[str, Any]:
    """
    Validate perfect repeat unit tiling.
    
    WHY:
    Weaving machines require complete repeat units. A design with 2.5 horizontal
    repeats is physically impossible to manufacture - you can't weave half a motif.
    
    This is a HARD manufacturing constraint, not a preference.
    
    Args:
        image_width: Image width in pixels
        image_height: Image height in pixels
        repeat_width: Repeat unit width in pixels
        repeat_height: Repeat unit height in pixels
        
    Returns:
        Dict with tiling validation results
        
    Raises:
        RepeatIntegrityError: If non-integer tiling detected or repeat exceeds image
    """
    logger.debug(
        f"Validating repeat integrity: image={image_width}x{image_height}, "
        f"repeat={repeat_width}x{repeat_height}"
    )
    
    violations = []
    
    # Check repeat unit doesn't exceed image dimensions
    violations.extend(
        _validate_repeat_fits(image_width, image_height, repeat_width, repeat_height)
    )
    
    # Check perfect tiling (only if repeat doesn't exceed image)
    if repeat_width <= image_width and repeat_height <= image_height:
        violations.extend(
            _validate_perfect_tiling(image_width, image_height, repeat_width, repeat_height)
        )
    
    if violations:
        logger.error(f"Repeat integrity validation failed: {violations}")
        raise RepeatIntegrityError(
            message="Repeat integrity validation failed",
            stage_number=0,
            details={
                "violations": violations,
                "image_width": image_width,
                "image_height": image_height,
                "repeat_width": repeat_width,
                "repeat_height": repeat_height,
                "tiles_x": image_width / repeat_width if repeat_width > 0 else 0,
                "tiles_y": image_height / repeat_height if repeat_height > 0 else 0,
                "rationale": (
                    "Partial repeats at boundaries cannot be woven - "
                    "design is physically impossible to manufacture. "
                    "Image dimensions must be exact multiples of repeat dimensions."
                )
            }
        )
    
    # Calculate tile counts
    tiles_x = image_width // repeat_width
    tiles_y = image_height // repeat_height
    
    logger.debug(
        f"Repeat integrity validated: {tiles_x}x{tiles_y} tiles "
        f"({tiles_x * tiles_y} total repeat units)"
    )
    
    return {
        "tiles_x": tiles_x,
        "tiles_y": tiles_y,
        "total_tiles": tiles_x * tiles_y,
        "perfect_tiling": True
    }


def _validate_repeat_fits(
    image_width: int,
    image_height: int,
    repeat_width: int,
    repeat_height: int
) -> list[str]:
    """
    Validate that repeat unit fits within image dimensions.
    
    A repeat unit larger than the image itself is invalid.
    
    Args:
        image_width: Image width
        image_height: Image height
        repeat_width: Repeat width
        repeat_height: Repeat height
        
    Returns:
        List of violations (empty if valid)
    """
    violations = []
    
    if repeat_width > image_width:
        violations.append(
            f"Repeat width {repeat_width}px exceeds image width {image_width}px - "
            f"repeat unit cannot be larger than image"
        )
    
    if repeat_height > image_height:
        violations.append(
            f"Repeat height {repeat_height}px exceeds image height {image_height}px - "
            f"repeat unit cannot be larger than image"
        )
    
    return violations


def _validate_perfect_tiling(
    image_width: int,
    image_height: int,
    repeat_width: int,
    repeat_height: int
) -> list[str]:
    """
    Validate perfect integer tiling of repeat units.
    
    Image dimensions must be exact multiples of repeat dimensions.
    Any remainder indicates partial repeats at boundaries.
    
    Args:
        image_width: Image width
        image_height: Image height
        repeat_width: Repeat width
        repeat_height: Repeat height
        
    Returns:
        List of violations (empty if perfect tiling)
    """
    violations = []
    
    # Check horizontal tiling
    if image_width % repeat_width != 0:
        remainder = image_width % repeat_width
        tiles_x = image_width / repeat_width
        violations.append(
            f"Width {image_width}px is not a multiple of repeat width "
            f"{repeat_width}px (remainder: {remainder}px, tiles: {tiles_x:.2f}). "
            f"Need {image_width - remainder}px or {image_width + (repeat_width - remainder)}px for perfect tiling."
        )
    
    # Check vertical tiling
    if image_height % repeat_height != 0:
        remainder = image_height % repeat_height
        tiles_y = image_height / repeat_height
        violations.append(
            f"Height {image_height}px is not a multiple of repeat height "
            f"{repeat_height}px (remainder: {remainder}px, tiles: {tiles_y:.2f}). "
            f"Need {image_height - remainder}px or {image_height + (repeat_height - remainder)}px for perfect tiling."
        )
    
    return violations


def calculate_tile_counts(
    image_width: int,
    image_height: int,
    repeat_width: int,
    repeat_height: int
) -> Dict[str, int]:
    """
    Calculate tile counts assuming perfect tiling.
    
    Call this AFTER validate_repeat_integrity to ensure perfect tiling.
    
    Args:
        image_width: Image width
        image_height: Image height
        repeat_width: Repeat width
        repeat_height: Repeat height
        
    Returns:
        Dict with tiles_x, tiles_y, total_tiles
    """
    tiles_x = image_width // repeat_width
    tiles_y = image_height // repeat_height
    
    return {
        "tiles_x": tiles_x,
        "tiles_y": tiles_y,
        "total_tiles": tiles_x * tiles_y
    }
