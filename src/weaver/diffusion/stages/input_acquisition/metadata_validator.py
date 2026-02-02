"""
Metadata Validator - Stage 0 Sub-Module

PURPOSE:
Validate that declared metadata matches actual image properties.
Enforces manufacturing truth: what you declare MUST match reality.

GUARANTEES:
- Color mode consistency validated
- DPI consistency validated with format-specific rules
- No mismatched metadata passes

FORMAT-SPECIFIC DPI TRUST RULES:
- PNG, TIFF: DPI must be present in image AND match declared (fail if missing)
- BMP: Declared DPI is authoritative (only validate if BMP has non-zero DPI)

RATIONALE:
Metadata inconsistency causes dimensional errors in physical manufacturing.
BMP DPI is often unreliable (zero/missing), but PNG/TIFF DPI is trustworthy.

FORBIDDEN:
- Must not infer or correct metadata
- Must not accept mismatches with warnings
- Must not apply default values
"""

from typing import Dict, Any

from PIL import Image

from weaver.shared.exceptions import MetadataConsistencyError
from weaver.shared.logger import get_logger
from weaver.shared.validators import detect_dpi, detect_color_mode

logger = get_logger(__name__)


def validate_metadata_consistency(
    declared_dpi: int,
    declared_color_mode: str,
    image: Image.Image,
    image_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate declared metadata matches actual image properties.
    
    WHY:
    Dimensional accuracy requires matching DPI. Color mode must match for
    correct processing. Any mismatch indicates incomplete or incorrect design package.
    
    Format-specific DPI rules prevent false failures on BMP while maintaining
    strict validation for PNG/TIFF where DPI is reliable.
    
    Args:
        declared_dpi: DPI declared in input
        declared_color_mode: Color mode declared in input
        image: Decoded PIL Image
        image_info: Metadata dict from image_decoder
        
    Returns:
        Dict with validation results
        
    Raises:
        MetadataConsistencyError: If declared metadata conflicts with actual
    """
    logger.debug(
        f"Validating metadata: declared DPI={declared_dpi} mode={declared_color_mode}, "
        f"actual DPI={image_info.get('dpi')} mode={image_info['mode']}"
    )
    
    violations = []
    
    # Check color mode consistency
    violations.extend(_validate_color_mode(declared_color_mode, image_info["mode"]))
    
    # Check DPI consistency with format-specific rules
    violations.extend(
        _validate_dpi(declared_dpi, image_info["dpi"], image_info["format"])
    )
    
    if violations:
        logger.error(f"Metadata consistency validation failed: {violations}")
        raise MetadataConsistencyError(
            message="Metadata consistency validation failed",
            stage_number=0,
            details={
                "violations": violations,
                "file_format": image_info["format"],
                "declared_dpi": declared_dpi,
                "declared_color_mode": declared_color_mode,
                "actual_dpi": image_info["dpi"],
                "actual_color_mode": image_info["mode"],
                "rationale": (
                    "Metadata inconsistency prevents dimensional errors "
                    "in physical fabric manufacturing. "
                    f"Format-specific rules: {image_info['format']} DPI trust enforced."
                )
            }
        )
    
    logger.debug("Metadata consistency validation passed")
    
    return {
        "color_mode_validated": True,
        "dpi_validated": True,
        "format": image_info["format"]
    }


def _validate_color_mode(declared_mode: str, actual_mode: str) -> list[str]:
    """
    Validate color mode consistency.
    
    Args:
        declared_mode: Declared color mode
        actual_mode: Actual PIL color mode
        
    Returns:
        List of violation messages (empty if valid)
    """
    violations = []
    
    if declared_mode != actual_mode:
        violations.append(
            f"Color mode mismatch: declared '{declared_mode}' "
            f"but image is '{actual_mode}'"
        )
    
    return violations


def _validate_dpi(declared_dpi: int, actual_dpi: float | None, file_format: str) -> list[str]:
    """
    Validate DPI consistency with format-specific trust rules.
    
    FORMAT RULES:
    - PNG, TIFF: DPI MUST be present and match (strict)
    - BMP: Declared DPI is authoritative (lenient, only check if present & non-zero)
    
    RATIONALE:
    BMP format often has zero or missing DPI metadata. This is a known
    limitation of the BMP format, not a design package error.
    
    PNG and TIFF reliably embed DPI, so we require it and validate strictly.
    
    Args:
        declared_dpi: Declared DPI value
        actual_dpi: Actual DPI from image (None if missing)
        file_format: PIL-detected format (PNG, TIFF, BMP)
        
    Returns:
        List of violation messages (empty if valid)
    """
    violations = []
    
    if file_format in ("PNG", "TIFF"):
        # PNG/TIFF: DPI must be present and match (strict)
        violations.extend(
            _validate_dpi_strict(declared_dpi, actual_dpi, file_format)
        )
    
    elif file_format == "BMP":
        # BMP: Declared DPI is authoritative (only check if present & non-zero)
        violations.extend(
            _validate_dpi_lenient(declared_dpi, actual_dpi, file_format)
        )
    
    else:
        # Unknown format (should not reach here after format validation)
        violations.append(
            f"Unknown format '{file_format}' for DPI validation"
        )
    
    return violations


def _validate_dpi_strict(
    declared_dpi: int,
    actual_dpi: float | None,
    file_format: str
) -> list[str]:
    """
    Strict DPI validation for PNG/TIFF.
    
    Requires DPI to be present in image metadata AND match declared value.
    
    Args:
        declared_dpi: Declared DPI
        actual_dpi: Actual DPI from image
        file_format: Format name for error messages
        
    Returns:
        List of violations
    """
    violations = []
    
    if actual_dpi is None:
        violations.append(
            f"DPI metadata missing in {file_format} file. "
            f"PNG/TIFF must have embedded DPI for manufacturing trust."
        )
    else:
        # Allow 1% tolerance for floating point rounding
        tolerance = max(1, int(declared_dpi * 0.01))
        
        if abs(declared_dpi - actual_dpi) > tolerance:
            violations.append(
                f"DPI mismatch: declared {declared_dpi} "
                f"but {file_format} metadata is {actual_dpi:.1f} "
                f"(tolerance: ±{tolerance})"
            )
    
    return violations


def _validate_dpi_lenient(
    declared_dpi: int,
    actual_dpi: float | None,
    file_format: str
) -> list[str]:
    """
    Lenient DPI validation for BMP.
    
    Only validates DPI if present AND non-zero in BMP metadata.
    If missing or zero, trusts declared DPI (no violation).
    
    RATIONALE:
    BMP format commonly has zero or missing DPI. This is a format limitation,
    not a design error. We trust the designer's declared DPI for BMP.
    
    Args:
        declared_dpi: Declared DPI
        actual_dpi: Actual DPI from BMP (may be None or 0)
        file_format: Format name (should be "BMP")
        
    Returns:
        List of violations (empty unless BMP has non-zero DPI that mismatches)
    """
    violations = []
    
    # Only validate if BMP has non-zero DPI
    if actual_dpi is not None and actual_dpi > 0:
        # BMP has DPI metadata - validate it matches
        tolerance = max(1, int(declared_dpi * 0.01))
        
        if abs(declared_dpi - actual_dpi) > tolerance:
            violations.append(
                f"DPI mismatch: declared {declared_dpi} "
                f"but {file_format} header is {actual_dpi:.1f} "
                f"(tolerance: ±{tolerance})"
            )
    
    # If actual_dpi is None or 0, no violation (trust declared)
    
    return violations

