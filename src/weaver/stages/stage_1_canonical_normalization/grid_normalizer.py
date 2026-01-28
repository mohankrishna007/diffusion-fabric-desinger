"""
Grid Normalizer - Stage 1 Sub-Module

PURPOSE:
Validate and enforce repeat grid integrity. Ensures canonical raster
pixel dimensions are perfectly divisible by repeat unit dimensions.

GUARANTEES:
- Width is integer multiple of repeat width
- Height is integer multiple of repeat height
- No sub-pixel misalignment
- Repeat unit tiles perfectly

FORBIDDEN:
- Must not crop image to fix grid
- Must not pad image to fix grid
- Must not alter repeat unit dimensions
- Grid violations must FAIL (no recovery)

WHY ASSERTION-ONLY:
Grid normalization is VALIDATION, not TRANSFORMATION.
If repeat grid is misaligned after orientation/DPI normalization,
it indicates:
1. Stage 0 contract violation (passed invalid dimensions)
2. DPI rescaling rounding error
3. Data corruption

None of these should be silently "fixed" - they are BUGS.
Canonical raster must preserve exact input structure.
"""

from PIL import Image
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_repeat_grid(
    img: Image.Image,
    repeat_width_px: int,
    repeat_height_px: int
) -> None:
    """
    Validate that image dimensions are perfectly divisible by repeat unit.
    
    WHY:
    Textile manufacturing requires EXACT repeat tiling:
    - Loom must know how many repeats fit in warp/weft
    - CAM export divides image into tiles
    - Any fractional repeat is a manufacturing error
    
    This validation ensures:
    - width_px % repeat_width_px == 0
    - height_px % repeat_height_px == 0
    
    If validation fails, it indicates a serious bug in:
    - Stage 0 validation (should have rejected invalid dimensions)
    - DPI canonicalization (rounding error broke grid)
    - Data corruption (dimensions changed unexpectedly)
    
    Args:
        img: PIL Image after orientation and DPI normalization
        repeat_width_px: Repeat unit width in pixels
        repeat_height_px: Repeat unit height in pixels
        
    Raises:
        CanonicalizationError: If repeat grid alignment is violated
    """
    width_px, height_px = img.size
    
    logger.debug(
        f"Validating repeat grid: image={width_px}x{height_px}, "
        f"repeat={repeat_width_px}x{repeat_height_px}"
    )
    
    # Validate width divisibility
    if width_px % repeat_width_px != 0:
        raise CanonicalizationError(
            "Repeat grid violation: width not divisible by repeat width",
            details={
                "width_px": width_px,
                "repeat_width_px": repeat_width_px,
                "remainder": width_px % repeat_width_px,
                "expected_multiples": [
                    repeat_width_px * n
                    for n in range(max(1, width_px // repeat_width_px - 1),
                                   width_px // repeat_width_px + 3)
                ],
                "diagnosis": (
                    "This indicates either:\n"
                    "1. Stage 0 validation failure (invalid dimensions passed)\n"
                    "2. DPI rescaling rounding error\n"
                    "3. Data corruption"
                )
            }
        )
    
    # Validate height divisibility
    if height_px % repeat_height_px != 0:
        raise CanonicalizationError(
            "Repeat grid violation: height not divisible by repeat height",
            details={
                "height_px": height_px,
                "repeat_height_px": repeat_height_px,
                "remainder": height_px % repeat_height_px,
                "expected_multiples": [
                    repeat_height_px * n
                    for n in range(max(1, height_px // repeat_height_px - 1),
                                   height_px // repeat_height_px + 3)
                ],
                "diagnosis": (
                    "This indicates either:\n"
                    "1. Stage 0 validation failure (invalid dimensions passed)\n"
                    "2. DPI rescaling rounding error\n"
                    "3. Data corruption"
                )
            }
        )
    
    # Calculate tile counts
    tiles_horizontal = width_px // repeat_width_px
    tiles_vertical = height_px // repeat_height_px
    total_tiles = tiles_horizontal * tiles_vertical
    
    logger.debug(
        f"Repeat grid validated: {tiles_horizontal}x{tiles_vertical} tiles "
        f"({total_tiles} total)"
    )
    
    # Sanity check: at least one complete repeat
    if tiles_horizontal < 1 or tiles_vertical < 1:
        raise CanonicalizationError(
            "Repeat grid validation failed: image smaller than repeat unit",
            details={
                "width_px": width_px,
                "height_px": height_px,
                "repeat_width_px": repeat_width_px,
                "repeat_height_px": repeat_height_px,
                "tiles_horizontal": tiles_horizontal,
                "tiles_vertical": tiles_vertical
            }
        )


def calculate_tile_counts(
    width_px: int,
    height_px: int,
    repeat_width_px: int,
    repeat_height_px: int
) -> dict:
    """
    Calculate tile counts for validated repeat grid.
    
    This function assumes validate_repeat_grid() has already passed.
    Use for metrics and logging.
    
    Args:
        width_px: Image width in pixels
        height_px: Image height in pixels
        repeat_width_px: Repeat unit width in pixels
        repeat_height_px: Repeat unit height in pixels
        
    Returns:
        Dict with tile count metrics
    """
    tiles_horizontal = width_px // repeat_width_px
    tiles_vertical = height_px // repeat_height_px
    total_tiles = tiles_horizontal * tiles_vertical
    
    return {
        "tiles_horizontal": tiles_horizontal,
        "tiles_vertical": tiles_vertical,
        "total_tiles": total_tiles,
        "repeat_width_px": repeat_width_px,
        "repeat_height_px": repeat_height_px
    }
