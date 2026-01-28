"""
Color Space Normalizer - Stage 1 Sub-Module

PURPOSE:
Convert all color modes to canonical RGB (8-bit per channel).
Eliminates color mode ambiguity by standardizing to single representation.

GUARANTEES:
- Output is always RGB mode (3 channels)
- Each channel is 8-bit (0-255)
- Alpha channel resolved according to policy (flattened or stripped)
- ICC color profiles stripped
- Palette-based modes resolved to RGB
- Grayscale modes converted to RGB

FORBIDDEN:
- Must not apply color correction/adjustment
- Must not alter color values beyond mode conversion
- Must not introduce compression artifacts
"""

from PIL import Image
from weaver.shared.schemas import AlphaPolicy
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def normalize_color_space(img: Image.Image, alpha_policy: AlphaPolicy) -> tuple[Image.Image, list[str]]:
    """
    Convert image to canonical RGB color space.
    
    WHY:
    Different image formats support different color modes:
    - PNG: RGB, RGBA, L, LA, P (palette), 1 (binary)
    - BMP: RGB, L, P
    - TIFF: RGB, RGBA, L, LA, CMYK, etc.
    
    Downstream stages (diffusion, CAM export) require consistent RGB.
    This function eliminates all color mode ambiguity.
    
    Conversion Rules:
    - RGB → keep (already canonical)
    - RGBA → flatten on background or strip (per policy)
    - LA (grayscale + alpha) → flatten on background or strip
    - L (grayscale) → replicate to RGB channels
    - P (palette) → resolve palette to RGB
    - 1 (binary) → convert to RGB
    - CMYK → not supported (Stage 0 should reject)
    
    Args:
        img: PIL Image in any supported color mode
        alpha_policy: Policy for handling alpha channel
        
    Returns:
        Tuple of (RGB PIL Image, list of transformations applied)
        
    Raises:
        CanonicalizationError: If color mode is unsupported or conversion fails
    """
    transformations = []
    original_mode = img.mode
    
    logger.debug(f"Normalizing color space from {original_mode} to RGB")
    
    try:
        # Case 1: Already RGB - no conversion needed
        if img.mode == "RGB":
            logger.debug("Image already in RGB mode")
            return img, transformations
        
        # Case 2: RGBA - resolve alpha channel
        if img.mode == "RGBA":
            img = _resolve_rgba(img, alpha_policy)
            transformations.append(f"RGBA_to_RGB_{alpha_policy.value}")
            
        # Case 3: LA (grayscale + alpha) - resolve alpha channel
        elif img.mode == "LA":
            img = _resolve_la(img, alpha_policy)
            transformations.append(f"LA_to_RGB_{alpha_policy.value}")
            
        # Case 4: L (grayscale) - replicate to RGB
        elif img.mode == "L":
            img = img.convert("RGB")
            transformations.append("L_to_RGB")
            
        # Case 5: P (palette) - resolve palette
        elif img.mode == "P":
            # Check if palette has transparency
            if "transparency" in img.info:
                # Convert to RGBA first, then resolve alpha
                img = img.convert("RGBA")
                img = _resolve_rgba(img, alpha_policy)
                transformations.append(f"P_with_transparency_to_RGB_{alpha_policy.value}")
            else:
                img = img.convert("RGB")
                transformations.append("P_to_RGB")
                
        # Case 6: 1 (binary/1-bit) - convert to RGB
        elif img.mode == "1":
            img = img.convert("RGB")
            transformations.append("1_to_RGB")
            
        # Case 7: Unsupported modes
        else:
            raise CanonicalizationError(
                f"Unsupported color mode: {original_mode}",
                details={
                    "mode": original_mode,
                    "size": img.size,
                    "supported_modes": ["RGB", "RGBA", "L", "LA", "P", "1"]
                }
            )
        
        # Strip ICC profile for deterministic color interpretation
        _strip_icc_profile(img)
        transformations.append("ICC_profile_stripped")
        
        # Final validation
        if img.mode != "RGB":
            raise CanonicalizationError(
                f"Color space normalization failed: result is {img.mode}, expected RGB",
                details={"original_mode": original_mode, "result_mode": img.mode}
            )
        
        logger.debug(f"Color space normalized: {original_mode} -> RGB")
        logger.debug(f"Transformations applied: {transformations}")
        
        return img, transformations
        
    except CanonicalizationError:
        raise
    except Exception as e:
        raise CanonicalizationError(
            f"Failed to normalize color space from {original_mode}",
            details={"mode": original_mode, "error": str(e)}
        ) from e


def _resolve_rgba(img: Image.Image, policy: AlphaPolicy) -> Image.Image:
    """
    Resolve RGBA image to RGB according to policy.
    
    WHY:
    Manufacturing systems (CAM software, loom controllers) cannot interpret
    alpha transparency. Fabric is either woven thread (color) or unwoven
    (white background). Alpha must be resolved to concrete RGB values.
    
    Policies:
    - FLATTEN_WHITE: Composite on white (255, 255, 255) - textile standard
    - FLATTEN_BLACK: Composite on black (0, 0, 0) - alternative
    - STRIP: Discard alpha, keep RGB channels only
    
    Args:
        img: RGBA PIL Image
        policy: AlphaPolicy enum value
        
    Returns:
        RGB PIL Image
    """
    if policy == AlphaPolicy.STRIP:
        # Discard alpha channel, keep RGB only
        return img.convert("RGB")
    
    # Flatten on background color
    bg_color = (255, 255, 255) if policy == AlphaPolicy.FLATTEN_WHITE else (0, 0, 0)
    
    # Create solid background
    rgb_img = Image.new("RGB", img.size, bg_color)
    
    # Composite using alpha as mask
    alpha_channel = img.split()[3]  # Extract alpha channel
    rgb_img.paste(img, mask=alpha_channel)
    
    return rgb_img


def _resolve_la(img: Image.Image, policy: AlphaPolicy) -> Image.Image:
    """
    Resolve LA (grayscale + alpha) to RGB according to policy.
    
    Args:
        img: LA PIL Image
        policy: AlphaPolicy enum value
        
    Returns:
        RGB PIL Image
    """
    if policy == AlphaPolicy.STRIP:
        # Discard alpha, convert grayscale to RGB
        l_img = img.convert("L")
        return l_img.convert("RGB")
    
    # Flatten on background color
    bg_color = (255, 255, 255) if policy == AlphaPolicy.FLATTEN_WHITE else (0, 0, 0)
    
    # Convert grayscale to RGB
    l_img = img.split()[0]  # Extract luminance channel
    gray_rgb = Image.merge("RGB", [l_img, l_img, l_img])
    
    # Create solid background
    rgb_img = Image.new("RGB", img.size, bg_color)
    
    # Composite using alpha as mask
    alpha_channel = img.split()[1]  # Extract alpha channel
    rgb_img.paste(gray_rgb, mask=alpha_channel)
    
    return rgb_img


def _strip_icc_profile(img: Image.Image) -> None:
    """
    Strip ICC color profile from image metadata.
    
    WHY:
    ICC profiles define device-specific color interpretations.
    Canonical raster requires DETERMINISTIC color values - same RGB
    triplet must always mean same physical color.
    
    ICC profiles introduce ambiguity:
    - Same RGB values can appear different on different devices
    - Profile interpretation varies by software
    - Manufacturing systems may ignore profiles
    
    Solution: Strip ICC profiles, interpret RGB in standard sRGB space.
    
    Args:
        img: PIL Image (modified in-place)
    """
    if "icc_profile" in img.info:
        img.info.pop("icc_profile")
        logger.debug("ICC profile stripped from image metadata")


def validate_color_space_normalized(img: Image.Image) -> None:
    """
    Validate that color space has been normalized to canonical RGB.
    
    Checks:
    - Mode is RGB
    - No ICC profile in metadata
    
    Args:
        img: PIL Image to validate
        
    Raises:
        CanonicalizationError: If color space normalization invariant violated
    """
    if img.mode != "RGB":
        raise CanonicalizationError(
            f"Color space normalization violated: mode is {img.mode}, expected RGB",
            details={"mode": img.mode}
        )
    
    if "icc_profile" in img.info:
        raise CanonicalizationError(
            "ICC profile not stripped after color space normalization",
            details={"has_icc_profile": True}
        )
