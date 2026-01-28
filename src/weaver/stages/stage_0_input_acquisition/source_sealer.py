"""
Source Sealer - Stage 0 Sub-Module

PURPOSE:
Compute cryptographic hash of raw image bytes for immutability proof.
Any modification to source image will change hash, breaking the seal.

GUARANTEES:
- SHA-256 hash computed from raw bytes
- Deterministic (same file = same hash)
- Tamper-evident (any change = different hash)
- Memory-efficient (streaming hash computation)

RATIONALE:
Manufacturing requires immutable source of truth. Hash provides cryptographic
proof that source image has not been modified since validation.

FORBIDDEN:
- Must not use weak hashes (MD5, SHA-1)
- Must not hash decoded pixels (use raw file bytes)
- Must not skip hashing for performance
"""

import hashlib
from typing import Dict, Any

from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def compute_image_hash(image_path: str) -> str:
    """
    Compute SHA-256 hash of raw image bytes.
    
    WHY:
    Cryptographic hash provides immutability proof. Any modification to
    source image will change hash, allowing detection of tampering.
    
    Manufacturing traceability requires proving that processed output
    corresponds to validated input. Hash provides this proof.
    
    Args:
        image_path: Path to image file
        
    Returns:
        SHA-256 hash as hexadecimal string (64 characters)
    """
    logger.debug(f"Computing SHA-256 hash: {image_path}")
    
    sha256 = hashlib.sha256()
    
    # Read in 64KB chunks for memory efficiency
    # (handles large files without loading entire file into RAM)
    chunk_size = 65536  # 64KB
    
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    
    hash_hex = sha256.hexdigest()
    
    logger.debug(f"SHA-256 hash computed: {hash_hex}")
    
    return hash_hex


def verify_image_hash(image_path: str, expected_hash: str) -> bool:
    """
    Verify that image hash matches expected value.
    
    Used to detect tampering after initial validation.
    
    Args:
        image_path: Path to image file
        expected_hash: Expected SHA-256 hash (hex string)
        
    Returns:
        True if hash matches, False if tampered
    """
    logger.debug(f"Verifying image hash: {image_path}")
    
    actual_hash = compute_image_hash(image_path)
    
    if actual_hash == expected_hash:
        logger.debug("Hash verification passed")
        return True
    else:
        logger.warning(
            f"Hash mismatch - image may have been tampered! "
            f"Expected: {expected_hash}, Actual: {actual_hash}"
        )
        return False


def create_source_seal(image_path: str) -> Dict[str, Any]:
    """
    Create complete source seal with hash and metadata.
    
    Returns comprehensive seal data for immutability tracking.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dict with raw_hash, algorithm, timestamp
    """
    import os
    from datetime import datetime
    
    raw_hash = compute_image_hash(image_path)
    
    seal = {
        "raw_hash": raw_hash,
        "hash_algorithm": "SHA-256",
        "sealed_at": datetime.utcnow().isoformat(),
        "file_size": os.path.getsize(image_path),
        "image_path": image_path
    }
    
    logger.info(f"Source sealed: {raw_hash} at {seal['sealed_at']}")
    
    return seal


def validate_seal_integrity(seal: Dict[str, Any], current_image_path: str) -> bool:
    """
    Validate that seal is still intact.
    
    Checks:
    - Image file still exists
    - Hash still matches
    - File size unchanged
    
    Args:
        seal: Seal dict from create_source_seal
        current_image_path: Current path to image
        
    Returns:
        True if seal intact, False if compromised
    """
    import os
    
    # Check file exists
    if not os.path.exists(current_image_path):
        logger.error(f"Seal broken: image file not found at {current_image_path}")
        return False
    
    # Check file size (fast check)
    current_size = os.path.getsize(current_image_path)
    if current_size != seal.get("file_size"):
        logger.error(
            f"Seal broken: file size changed from {seal.get('file_size')} "
            f"to {current_size} bytes"
        )
        return False
    
    # Check hash (comprehensive check)
    expected_hash = seal.get("raw_hash")
    if not expected_hash:
        logger.error("Seal broken: missing raw_hash in seal data")
        return False
    
    if not verify_image_hash(current_image_path, expected_hash):
        logger.error("Seal broken: hash mismatch")
        return False
    
    logger.info("Seal integrity verified")
    return True
