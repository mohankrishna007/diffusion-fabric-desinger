"""
Resource Guard - Stage 0 Sub-Module

PURPOSE:
Post-decode resource protection to prevent DoS and resource exhaustion.
Validates pixel count and file size after successful decode.

GUARANTEES:
- Pixel count within processing limits
- File size within storage limits
- No resource exhaustion attacks
- Fast-fail on excessive resources

RATIONALE:
Protects downstream stages from maliciously large files. Even if dimensions
pass, total pixel count or file size may still be excessive.

FORBIDDEN:
- Must not accept oversized files with warnings
- Must not attempt compression or optimization
- Must not allocate unbounded resources
"""

import os
from typing import Dict, Any

from weaver.shared.exceptions import ResourceProtectionError
from weaver.shared.constants import (
    MAX_FILE_SIZE_BYTES,
    MAX_PIXEL_COUNT
)
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_resource_limits(
    image_path: str,
    width: int,
    height: int
) -> Dict[str, Any]:
    """
    Validate resource protection limits after decode.
    
    WHY:
    Prevents DoS and resource exhaustion. Even if individual dimensions pass,
    total pixel count may be excessive. File size check catches compressed bombs.
    
    This is the FINAL resource check before accepting the design.
    
    Args:
        image_path: Path to image file
        width: Image width in pixels
        height: Image height in pixels
        
    Returns:
        Dict with resource validation results
        
    Raises:
        ResourceProtectionError: If resource limits exceeded
    """
    logger.debug(
        f"Validating resource limits: {width}x{height}, file={image_path}"
    )
    
    violations = []
    
    # Check file size
    file_size = os.path.getsize(image_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        violations.append(
            f"File size {file_size / 1_048_576:.1f}MB exceeds maximum "
            f"{MAX_FILE_SIZE_BYTES / 1_048_576:.0f}MB"
        )
    
    # Check pixel count
    pixel_count = width * height
    if pixel_count > MAX_PIXEL_COUNT:
        violations.append(
            f"Pixel count {pixel_count:,} exceeds maximum {MAX_PIXEL_COUNT:,}"
        )
    
    if violations:
        logger.error(f"Resource protection validation failed: {violations}")
        raise ResourceProtectionError(
            message="Resource protection limits exceeded",
            stage_number=0,
            details={
                "violations": violations,
                "file_size_bytes": file_size,
                "file_size_mb": file_size / 1_048_576,
                "pixel_count": pixel_count,
                "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
                "max_file_size_mb": MAX_FILE_SIZE_BYTES / 1_048_576,
                "max_pixel_count": MAX_PIXEL_COUNT,
                "rationale": (
                    "Resource limits prevent DoS and protect downstream stages "
                    "from processing maliciously large files. Pixel count and "
                    "file size checks ensure bounded memory and storage usage."
                )
            }
        )
    
    logger.debug(
        f"Resource limits validated: {pixel_count:,} pixels, "
        f"{file_size / 1_048_576:.2f}MB"
    )
    
    return {
        "file_size_bytes": file_size,
        "file_size_mb": file_size / 1_048_576,
        "pixel_count": pixel_count,
        "resources_validated": True
    }


def estimate_decode_memory(file_size_bytes: int) -> int:
    """
    Estimate memory required for image decode.
    
    PIL can allocate >2x decoded size during decoding (especially TIFF).
    This provides a conservative estimate for OOM protection.
    
    Args:
        file_size_bytes: File size in bytes
        
    Returns:
        Estimated memory in bytes (conservative upper bound)
    """
    # Conservative estimate: 3x file size
    # (accounts for PIL internal buffers during decode)
    return file_size_bytes * 3


def check_available_memory(required_bytes: int) -> bool:
    """
    Check if sufficient memory is available for operation.
    
    This is a placeholder for system-level memory checks.
    Could be enhanced with psutil or platform-specific APIs.
    
    Args:
        required_bytes: Required memory in bytes
        
    Returns:
        True if sufficient memory likely available
    """
    # Placeholder: always return True
    # Could implement actual memory checks with psutil:
    # import psutil
    # available = psutil.virtual_memory().available
    # return available > required_bytes * 1.5  # 50% safety margin
    
    return True
