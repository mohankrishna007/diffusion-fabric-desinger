"""
Format Validator - Stage 0 Sub-Module

PURPOSE:
Enforce lossless format allowlist (PNG, TIFF, BMP ONLY).
JPEG and other lossy formats destroy thread-level precision.

GUARANTEES:
- Only lossless formats pass
- File extension matches PIL-detected format
- No ambiguous formats allowed

RATIONALE:
Lossy compression introduces artifacts that are invisible to humans but
catastrophic for CAM systems. Thread-level precision requires lossless formats.

FORBIDDEN:
- Must not accept JPEG, WEBP, HEIC, or any lossy format
- Must not attempt format conversion
- Must not allow ambiguous or unknown formats
"""

from pathlib import Path
from typing import Dict, Any

from weaver.shared.exceptions import InputFormatError
from weaver.shared.constants import LOSSLESS_INPUT_FORMATS
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_format_allowlist(image_path: str, detected_format: str) -> Dict[str, Any]:
    """
    Enforce lossless format allowlist.
    
    WHY:
    JPEG and other lossy formats introduce compression artifacts that destroy
    thread-level precision. Only PNG, TIFF, BMP are allowed for manufacturing.
    
    Manufacturing rationale:
    - JPEG: DCT artifacts, color subsampling, quantization errors
    - WEBP: Similar lossy compression issues
    - HEIC: Lossy by default, complex color space handling
    
    Args:
        image_path: Path to image file
        detected_format: PIL-detected format (e.g., "PNG", "TIFF", "JPEG")
        
    Returns:
        Dict with file_extension and validated_format
        
    Raises:
        InputFormatError: If format is not on lossless allowlist
    """
    logger.debug(f"Validating format: {detected_format} for {image_path}")
    
    file_ext = Path(image_path).suffix.lower()
    
    # Check file extension against allowlist
    if file_ext not in LOSSLESS_INPUT_FORMATS:
        logger.error(f"Forbidden format: {file_ext}")
        raise InputFormatError(
            message=(
                f"File format '{file_ext}' not allowed. "
                f"Only lossless formats permitted: {LOSSLESS_INPUT_FORMATS}"
            ),
            stage_number=0,
            details={
                "file_extension": file_ext,
                "detected_format": detected_format,
                "allowed_formats": LOSSLESS_INPUT_FORMATS,
                "rationale": (
                    "Lossy compression (JPEG, WEBP, HEIC) destroys thread-level "
                    "precision needed for CAM export. Compression artifacts cause "
                    "manufacturing errors in physical fabric production."
                )
            }
        )
    
    # Additional validation: PIL format should be consistent with extension
    # (handles cases where file extension lies)
    _validate_format_consistency(file_ext, detected_format)
    
    logger.debug(f"Format validation passed: {file_ext} / {detected_format}")
    
    return {
        "file_extension": file_ext,
        "validated_format": detected_format
    }


def _validate_format_consistency(file_ext: str, detected_format: str) -> None:
    """
    Validate that file extension matches PIL-detected format.
    
    Prevents cases where:
    - .png file is actually a JPEG (malicious or corrupted)
    - File extension has been changed without re-encoding
    
    Args:
        file_ext: File extension (e.g., ".png")
        detected_format: PIL-detected format (e.g., "PNG")
        
    Raises:
        InputFormatError: If format mismatch detected
    """
    # Map extensions to expected PIL formats
    extension_to_format = {
        ".png": "PNG",
        ".tiff": "TIFF",
        ".tif": "TIFF",
        ".bmp": "BMP"
    }
    
    expected_format = extension_to_format.get(file_ext)
    
    if expected_format is None:
        # Extension not in our allowlist
        raise InputFormatError(
            message=f"Unrecognized file extension: {file_ext}",
            stage_number=0,
            details={
                "file_extension": file_ext,
                "allowed_extensions": list(extension_to_format.keys()),
                "rationale": "Only known lossless extensions allowed"
            }
        )
    
    # Check if PIL-detected format matches expected format
    if detected_format != expected_format:
        raise InputFormatError(
            message=(
                f"Format mismatch: file extension '{file_ext}' suggests {expected_format}, "
                f"but PIL detected {detected_format}"
            ),
            stage_number=0,
            details={
                "file_extension": file_ext,
                "expected_format": expected_format,
                "detected_format": detected_format,
                "rationale": (
                    "File extension must match actual format. "
                    "Mismatched formats indicate corrupted or maliciously renamed files."
                )
            }
        )
    
    logger.debug(f"Format consistency check passed: {file_ext} matches {detected_format}")

