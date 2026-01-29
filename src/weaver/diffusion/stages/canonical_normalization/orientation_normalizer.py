"""
Orientation Normalizer - Stage 1 Sub-Module

PURPOSE:
Remove EXIF rotation flags and apply physical pixel rotation to ensure
canonical orientation. EXIF rotation is "hidden state" - canonical raster
must not depend on metadata flags.

GUARANTEES:
- EXIF orientation tag applied to pixel data
- EXIF orientation flag cleared/removed
- Pixel dimensions reflect true orientation
- Deterministic output regardless of EXIF flags

FORBIDDEN:
- Must not alter pixel data beyond EXIF rotation
- Must not crop or pad
- Must not apply any smoothing
"""

from PIL import Image, ImageOps
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def normalize_orientation(img: Image.Image) -> Image.Image:
    """
    Apply EXIF rotation and clear orientation flags.
    
    WHY:
    Some image formats (JPEG, TIFF) store rotation in EXIF metadata rather
    than physically rotating pixels. This creates ambiguity - the same pixel
    grid can represent different visual orientations depending on metadata
    interpretation.
    
    Canonical raster eliminates this by:
    1. Reading EXIF orientation tag
    2. Physically rotating/transposing pixels
    3. Clearing EXIF orientation flag
    
    Result: Pixel grid matches visual orientation, no metadata dependency.
    
    Args:
        img: PIL Image with potential EXIF rotation flags
        
    Returns:
        PIL Image with orientation applied and flags cleared
        
    Raises:
        CanonicalizationError: If orientation normalization fails
    """
    try:
        # Apply EXIF transpose (no-op if no EXIF orientation present)
        img_transposed = ImageOps.exif_transpose(img)
        
        if img_transposed is None:
            # Fallback: exif_transpose returns None for some edge cases
            logger.warning("exif_transpose returned None, using original image")
            return img
        
        logger.debug(
            f"Orientation normalized: {img.size} -> {img_transposed.size}"
        )
        
        return img_transposed
        
    except Exception as e:
        raise CanonicalizationError(
            "Failed to normalize image orientation",
            details={
                "original_size": img.size,
                "original_mode": img.mode,
                "error": str(e)
            }
        ) from e


def validate_orientation_normalized(img: Image.Image) -> None:
    """
    Validate that orientation has been normalized.
    
    Checks:
    - Image has no EXIF orientation flags (or flag is 1 = normal)
    
    Args:
        img: PIL Image to validate
        
    Raises:
        CanonicalizationError: If orientation normalization invariant violated
    """
    try:
        # Check EXIF orientation tag
        exif_data = img.getexif()
        if exif_data:
            # Tag 0x0112 = Orientation
            orientation = exif_data.get(0x0112, 1)
            if orientation != 1:
                raise CanonicalizationError(
                    "EXIF orientation flag not cleared after normalization",
                    details={"orientation_tag": orientation}
                )
    except CanonicalizationError:
        raise
    except Exception as e:
        # EXIF parsing errors are non-critical if image is valid
        logger.warning(f"Could not validate EXIF orientation: {e}")

