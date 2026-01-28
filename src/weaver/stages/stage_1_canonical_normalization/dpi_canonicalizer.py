"""
DPI Canonicalizer - Stage 1 Sub-Module

PURPOSE:
Enforce canonical DPI by rescaling pixel grid to match target DPI.
This normalizes physical dimension interpretation across all inputs.

GUARANTEES:
- Output DPI matches canonical_dpi from config
- Pixel dimensions scaled proportionally
- Repeat unit grid remains integer-divisible after rescaling
- High-quality resampling (LANCZOS/BICUBIC)
- Aspect ratio preserved

FORBIDDEN:
- Must not alter design topology (motifs, structure)
- Must not apply smoothing beyond resampling filter
- Must not crop or pad
- Must not break repeat grid alignment

WHY THIS IS ALLOWED:
While Stage 1 generally forbids geometry changes, DPI canonicalization is
the ONE EXCEPTION because it:
1. Changes pixel DIMENSIONS but preserves design TOPOLOGY
2. Is a deterministic mathematical transformation (scale factor = canonical_dpi / input_dpi)
3. Ensures all downstream stages operate on consistent physical resolution
4. Does not add/remove motifs, smooth geometry, or alter design intent

This is "representation normalization", not "design modification".
"""

from PIL import Image
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)

# PIL resampling filter mapping
RESAMPLING_FILTERS = {
    "LANCZOS": Image.Resampling.LANCZOS,    # Highest quality, slower
    "BICUBIC": Image.Resampling.BICUBIC,    # High quality, fast
    "BILINEAR": Image.Resampling.BILINEAR,  # Medium quality, faster
    "NEAREST": Image.Resampling.NEAREST,    # Exact pixels, fastest (no interpolation)
}


def canonicalize_dpi(
    img: Image.Image,
    input_dpi: int,
    canonical_dpi: int,
    repeat_width_px: int,
    repeat_height_px: int,
    resampling_method: str = "LANCZOS"
) -> tuple[Image.Image, dict]:
    """
    Rescale image to enforce canonical DPI.
    
    WHY:
    Different input images may have different DPI settings (72, 150, 300, 600, etc.).
    Canonical raster enforces a SINGLE DPI for deterministic physical interpretation:
    - Ensures consistent thread density across designs
    - Simplifies downstream CAM export (no per-image DPI handling)
    - Normalizes feature sizes to manufacturing constraints
    
    Algorithm:
    1. Calculate scale factor: canonical_dpi / input_dpi
    2. Rescale pixel grid using high-quality resampling
    3. Validate repeat unit remains integer-divisible
    4. Set DPI metadata to canonical value
    
    Args:
        img: PIL Image in RGB mode
        input_dpi: Original DPI from Stage 0
        canonical_dpi: Target DPI from config
        repeat_width_px: Repeat unit width at input_dpi
        repeat_height_px: Repeat unit height at input_dpi
        resampling_method: Resampling algorithm name
        
    Returns:
        Tuple of (rescaled PIL Image, metadata dict)
        
    Raises:
        CanonicalizationError: If DPI rescaling fails or breaks repeat grid
    """
    # Early exit: no rescaling needed
    if input_dpi == canonical_dpi:
        logger.debug(f"DPI already canonical ({canonical_dpi}), no rescaling needed")
        img.info["dpi"] = (canonical_dpi, canonical_dpi)
        return img, {
            "scale_factor": 1.0,
            "rescaled": False,
            "original_size": img.size,
            "canonical_size": img.size,
            "original_repeat": (repeat_width_px, repeat_height_px),
            "canonical_repeat": (repeat_width_px, repeat_height_px),
            "resampling_method": resampling_method
        }
    
    logger.debug(f"Canonicalizing DPI: {input_dpi} -> {canonical_dpi}")
    
    try:
        # Calculate scale factor
        scale_factor = canonical_dpi / input_dpi
        
        # Calculate new dimensions
        original_width, original_height = img.size
        new_width = int(round(original_width * scale_factor))
        new_height = int(round(original_height * scale_factor))
        
        # Calculate new repeat unit dimensions
        new_repeat_width = int(round(repeat_width_px * scale_factor))
        new_repeat_height = int(round(repeat_height_px * scale_factor))
        
        logger.debug(
            f"Rescaling dimensions: {original_width}x{original_height} -> "
            f"{new_width}x{new_height} (scale={scale_factor:.4f})"
        )
        logger.debug(
            f"Rescaling repeat unit: {repeat_width_px}x{repeat_height_px} -> "
            f"{new_repeat_width}x{new_repeat_height}"
        )
        
        # Validate repeat grid integrity BEFORE rescaling
        # This catches cases where rounding breaks divisibility
        if new_width % new_repeat_width != 0:
            raise CanonicalizationError(
                "DPI rescaling would break repeat grid alignment (width)",
                details={
                    "original_width": original_width,
                    "new_width": new_width,
                    "repeat_width": new_repeat_width,
                    "remainder": new_width % new_repeat_width,
                    "scale_factor": scale_factor,
                    "input_dpi": input_dpi,
                    "canonical_dpi": canonical_dpi,
                    "suggestion": "Input dimensions may not be compatible with canonical DPI"
                }
            )
        
        if new_height % new_repeat_height != 0:
            raise CanonicalizationError(
                "DPI rescaling would break repeat grid alignment (height)",
                details={
                    "original_height": original_height,
                    "new_height": new_height,
                    "repeat_height": new_repeat_height,
                    "remainder": new_height % new_repeat_height,
                    "scale_factor": scale_factor,
                    "input_dpi": input_dpi,
                    "canonical_dpi": canonical_dpi,
                    "suggestion": "Input dimensions may not be compatible with canonical DPI"
                }
            )
        
        # Get resampling filter
        if resampling_method not in RESAMPLING_FILTERS:
            logger.warning(
                f"Unknown resampling method '{resampling_method}', falling back to LANCZOS"
            )
            resampling_method = "LANCZOS"
        
        resample_filter = RESAMPLING_FILTERS[resampling_method]
        
        # Perform rescaling
        img_rescaled = img.resize(
            (new_width, new_height),
            resample=resample_filter
        )
        
        # Set DPI metadata
        img_rescaled.info["dpi"] = (canonical_dpi, canonical_dpi)
        
        logger.debug(f"DPI canonicalization complete using {resampling_method} resampling")
        
        return img_rescaled, {
            "scale_factor": scale_factor,
            "rescaled": True,
            "original_size": (original_width, original_height),
            "canonical_size": (new_width, new_height),
            "original_repeat": (repeat_width_px, repeat_height_px),
            "canonical_repeat": (new_repeat_width, new_repeat_height),
            "resampling_method": resampling_method
        }
        
    except CanonicalizationError:
        raise
    except Exception as e:
        raise CanonicalizationError(
            f"Failed to canonicalize DPI: {input_dpi} -> {canonical_dpi}",
            details={
                "input_dpi": input_dpi,
                "canonical_dpi": canonical_dpi,
                "image_size": img.size,
                "error": str(e)
            }
        ) from e


def validate_dpi_canonical(img: Image.Image, canonical_dpi: int) -> None:
    """
    Validate that DPI has been canonicalized.
    
    Checks:
    - DPI metadata matches canonical_dpi
    
    Args:
        img: PIL Image to validate
        canonical_dpi: Expected canonical DPI
        
    Raises:
        CanonicalizationError: If DPI canonicalization invariant violated
    """
    # Check DPI metadata
    dpi = img.info.get("dpi")
    
    if dpi is None:
        raise CanonicalizationError(
            "DPI metadata missing after canonicalization",
            details={"expected_dpi": canonical_dpi}
        )
    
    # DPI is stored as tuple (x_dpi, y_dpi)
    if isinstance(dpi, tuple):
        x_dpi, y_dpi = dpi
        if x_dpi != canonical_dpi or y_dpi != canonical_dpi:
            raise CanonicalizationError(
                f"DPI metadata mismatch: expected {canonical_dpi}, got {dpi}",
                details={
                    "expected_dpi": canonical_dpi,
                    "actual_dpi": dpi
                }
            )
    else:
        if dpi != canonical_dpi:
            raise CanonicalizationError(
                f"DPI metadata mismatch: expected {canonical_dpi}, got {dpi}",
                details={
                    "expected_dpi": canonical_dpi,
                    "actual_dpi": dpi
                }
            )
