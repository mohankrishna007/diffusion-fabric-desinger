"""
Image Decoder - Stage 0 Sub-Module

PURPOSE:
Decode image using PIL and extract actual metadata for validation.
This establishes the ACTUAL properties of the image file.

GUARANTEES:
- Lossless PIL decoding
- Complete metadata extraction (width, height, mode, format, DPI, bit depth)
- No pixel manipulation
- No format conversion

RATIONALE:
Decoding reveals actual image properties needed for consistency validation.
We must verify declared metadata matches reality.

FORBIDDEN:
- Must not modify pixels
- Must not convert color modes
- Must not apply transformations
- Must not infer missing metadata
"""

import os
from pathlib import Path
from typing import Dict, Any, Tuple

from PIL import Image

from weaver.shared.exceptions import InputFormatError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def decode_image(image_path: str) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Decode image and extract metadata.
    
    WHY:
    Use PIL for lossless decoding. Extract actual image properties
    to validate against declared metadata. No assumptions, no inference.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (PIL Image, metadata dict)
        
    Raises:
        InputFormatError: If image cannot be decoded
    """
    logger.debug(f"Decoding image: {image_path}")
    
    try:
        img = Image.open(image_path)
        
        # Extract DPI if present in image metadata
        dpi_info = img.info.get("dpi", None)
        image_dpi = None
        if dpi_info:
            # DPI can be a tuple (x_dpi, y_dpi)
            image_dpi = dpi_info[0] if isinstance(dpi_info, tuple) else dpi_info
        
        # Determine bit depth based on mode
        bit_depth = _get_bit_depth(img.mode)
        
        # Extract comprehensive metadata
        image_info = {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
            "dpi": image_dpi,
            "bit_depth": bit_depth,
            "file_size": os.path.getsize(image_path)
        }
        
        logger.debug(
            f"Image decoded: {img.width}x{img.height} {img.mode} "
            f"{img.format} {bit_depth}-bit DPI={image_dpi}"
        )
        
        return img, image_info
        
    except Exception as e:
        logger.error(f"Image decode failed: {str(e)}")
        raise InputFormatError(
            message=f"Failed to decode image: {str(e)}",
            stage_number=0,
            details={
                "image_path": image_path,
                "error": str(e),
                "error_type": type(e).__name__,
                "rationale": "Image must be readable by PIL to proceed with validation"
            }
        ) from e


def _get_bit_depth(color_mode: str) -> int:
    """
    Determine bit depth from PIL color mode.
    
    Mode reference:
    - "1": 1-bit pixels, black and white
    - "L": 8-bit pixels, grayscale
    - "P": 8-bit pixels, palette-indexed
    - "RGB": 3x8-bit pixels, true color
    - "RGBA": 4x8-bit pixels, true color with transparency
    - "LA": 2x8-bit pixels, grayscale with alpha
    - "I": 32-bit signed integer pixels
    - "F": 32-bit floating point pixels
    - "I;16": 16-bit integer pixels
    
    Args:
        color_mode: PIL image mode string
        
    Returns:
        Bit depth per channel
    """
    mode_to_depth = {
        "1": 1,
        "L": 8,
        "P": 8,
        "RGB": 8,
        "RGBA": 8,
        "LA": 8,
        "I": 32,
        "F": 32,
        "I;16": 16,
        "I;16B": 16,
        "I;16L": 16,
        "I;16N": 16
    }
    
    return mode_to_depth.get(color_mode, 8)


def validate_image_decoded(img: Image.Image, image_info: Dict[str, Any]) -> None:
    """
    Validate that image was successfully decoded with all required metadata.
    
    Args:
        img: Decoded PIL Image
        image_info: Metadata dictionary
        
    Raises:
        InputFormatError: If decoded image is invalid
    """
    if img is None:
        raise InputFormatError(
            message="Image decode returned None",
            stage_number=0,
            details={"rationale": "PIL decode failed silently"}
        )
    
    # Validate required metadata fields
    required_fields = ["width", "height", "mode", "format", "bit_depth", "file_size"]
    missing_fields = [field for field in required_fields if field not in image_info]
    
    if missing_fields:
        raise InputFormatError(
            message=f"Missing required metadata fields: {missing_fields}",
            stage_number=0,
            details={
                "missing_fields": missing_fields,
                "image_info": image_info
            }
        )
    
    # Validate dimensions are positive
    if image_info["width"] <= 0 or image_info["height"] <= 0:
        raise InputFormatError(
            message="Invalid image dimensions",
            stage_number=0,
            details={
                "width": image_info["width"],
                "height": image_info["height"],
                "rationale": "Image dimensions must be positive integers"
            }
        )
    
    logger.debug("Image decode validation passed")
