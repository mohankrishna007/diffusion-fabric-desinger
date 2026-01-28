"""
Pre-Decode Resource Guard - Stage 0 Sub-Module

PURPOSE:
Validate file size BEFORE PIL decoding to prevent OOM (Out-Of-Memory) crashes.
This is the FIRST line of defense against malicious or corrupted files.

GUARANTEES:
- File size checked before memory allocation
- Prevents OOM during PIL decode
- Fast-fail before expensive operations

RATIONALE:
PIL can allocate >2x decoded size during decoding (especially TIFF).
Checking file size first protects system resources.

FORBIDDEN:
- Must not decode or read full file contents
- Must not perform image analysis
- Must not apply inference or correction
"""

import os
from pathlib import Path
from typing import Dict, Any

from weaver.shared.exceptions import ResourceProtectionError
from weaver.shared.constants import MAX_FILE_SIZE_BYTES
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def validate_pre_decode_resources(image_path: str) -> Dict[str, Any]:
    """
    Pre-decode resource validation to prevent OOM.
    
    WHY:
    Checks file size BEFORE attempting PIL decode. This prevents
    out-of-memory crashes from maliciously large or corrupted files.
    
    PIL can allocate >2x decoded size during decode (especially TIFF).
    Failing early protects the system from OOM before resource limits are checked.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dict with file_size_bytes
        
    Raises:
        ResourceProtectionError: If file size suggests unsafe memory usage
    """
    logger.debug(f"Pre-decode resource check: {image_path}")
    
    violations = []
    
    # Check file size (fast, no I/O beyond stat)
    file_size = os.path.getsize(image_path)
    
    logger.debug(f"File size: {file_size / 1_048_576:.2f} MB")
    
    if file_size > MAX_FILE_SIZE_BYTES:
        violations.append(
            f"File size {file_size / 1_048_576:.1f}MB exceeds maximum "
            f"{MAX_FILE_SIZE_BYTES / 1_048_576:.0f}MB (pre-decode check)"
        )
    
    if violations:
        logger.error(f"Pre-decode resource validation failed: {violations}")
        raise ResourceProtectionError(
            message="Pre-decode resource limits exceeded",
            stage_number=0,
            details={
                "violations": violations,
                "file_size_bytes": file_size,
                "max_file_size": MAX_FILE_SIZE_BYTES,
                "rationale": (
                    "File size check prevents OOM during decode. "
                    "PIL can allocate >2x decoded size (especially TIFF). "
                    "Rejecting before decode protects system resources."
                )
            }
        )
    
    logger.debug("Pre-decode resource check passed")
    
    return {
        "file_size_bytes": file_size
    }
