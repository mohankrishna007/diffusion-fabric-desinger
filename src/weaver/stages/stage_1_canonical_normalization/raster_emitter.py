"""
Raster Emitter - Stage 1 Sub-Module

PURPOSE:
Convert normalized PIL Image to canonical raster representation with
hybrid storage strategy (in-memory or file-based).

GUARANTEES:
- Output is NumPy array (H, W, 3) dtype=uint8
- Small images stored in-memory
- Large images stored as .npy files
- Deterministic tensor representation
- No encoding ambiguity (raw pixel values)

FORBIDDEN:
- Must not apply compression
- Must not alter pixel values
- Must not introduce encoding artifacts
"""

from pathlib import Path
from PIL import Image
import numpy as np
from weaver.shared.schemas import CanonicalRaster
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

logger = get_logger(__name__)


def emit_canonical_raster(
    img: Image.Image,
    pipeline_id: str,
    storage_dir: Path,
    dpi: int,
    repeat_unit_px: dict,
    memory_threshold_mb: int
) -> CanonicalRaster:
    """
    Convert PIL Image to canonical raster with hybrid storage.
    
    WHY:
    Canonical raster is the SINGLE SOURCE OF TRUTH for all downstream stages.
    It must be:
    1. Deterministic (exact pixel values, no encoding)
    2. Efficient (in-memory for small images, file for large)
    3. Type-safe (NumPy array with enforced shape/dtype)
    
    Hybrid Storage Strategy:
    - ALWAYS save .npy file (single source of truth on disk)
    - Small images (< threshold): ALSO store in-memory for performance
    - Large images (>= threshold): Only file path (memory efficient)
    
    Why .npy format?
    - Lossless (exact dtype and shape preservation)
    - Fast (direct memory mapping, no decoding)
    - Deterministic (no compression ambiguity)
    - No metadata (no EXIF, ICC, etc.)
    
    Args:
        img: PIL Image in canonical RGB mode
        pipeline_id: Pipeline execution ID
        storage_dir: Directory for .npy file storage
        dpi: Canonical DPI
        repeat_unit_px: Repeat unit {width, height} dict
        memory_threshold_mb: Threshold for in-memory vs file storage
        
    Returns:
        CanonicalRaster with either pixel_array or pixel_array_path set
        
    Raises:
        CanonicalizationError: If raster emission fails
    """
    logger.debug("Converting PIL Image to canonical raster")
    
    try:
        # Convert to NumPy array
        pixel_array = np.array(img, dtype=np.uint8)
        
        # Validate array properties
        if pixel_array.ndim != 3:
            raise CanonicalizationError(
                f"Invalid pixel array dimensions: expected 3D (H, W, 3), got {pixel_array.ndim}D",
                details={"shape": pixel_array.shape}
            )
        
        if pixel_array.shape[2] != 3:
            raise CanonicalizationError(
                f"Invalid channel count: expected 3 (RGB), got {pixel_array.shape[2]}",
                details={"shape": pixel_array.shape}
            )
        
        if pixel_array.dtype != np.uint8:
            raise CanonicalizationError(
                f"Invalid dtype: expected uint8, got {pixel_array.dtype}",
                details={"dtype": str(pixel_array.dtype)}
            )
        
        height_px, width_px, _ = pixel_array.shape
        
        # Calculate memory size in MB
        memory_size_mb = pixel_array.nbytes / (1024 * 1024)
        
        logger.debug(
            f"Canonical raster: {width_px}x{height_px}, "
            f"size={memory_size_mb:.2f}MB, threshold={memory_threshold_mb}MB"
        )
        
        # ALWAYS save to file (source of truth)
        storage_dir.mkdir(parents=True, exist_ok=True)
        npy_path = storage_dir / "canonical_raster.npy"
        np.save(str(npy_path), pixel_array)
        logger.debug(f"Saved canonical raster to {npy_path} ({memory_size_mb:.2f}MB)")
        
        # Decide whether to ALSO keep in-memory for performance
        if memory_size_mb < memory_threshold_mb:
            # Small image: keep in-memory AND file
            logger.debug(f"Keeping in-memory (below {memory_threshold_mb}MB threshold)")
            
            return CanonicalRaster(
                schema_version="stage1.v1",
                width_px=width_px,
                height_px=height_px,
                dpi=dpi,
                color_mode="RGB",
                bit_depth=8,
                pixel_array=pixel_array,
                pixel_array_path=str(npy_path),
                repeat_unit_px=repeat_unit_px
            )
        else:
            # Large image: file only (memory efficient)
            logger.debug(f"File only (above {memory_threshold_mb}MB threshold)")
            
            return CanonicalRaster(
                schema_version="stage1.v1",
                width_px=width_px,
                height_px=height_px,
                dpi=dpi,
                color_mode="RGB",
                bit_depth=8,
                pixel_array=None,
                pixel_array_path=str(npy_path),
                repeat_unit_px=repeat_unit_px
            )
        
    except CanonicalizationError:
        raise
    except Exception as e:
        raise CanonicalizationError(
            "Failed to emit canonical raster",
            details={
                "image_size": img.size,
                "image_mode": img.mode,
                "error": str(e)
            }
        ) from e


def load_canonical_raster(raster: CanonicalRaster) -> np.ndarray:
    """
    Load pixel array from canonical raster (in-memory or file).
    
    Helper function for downstream stages to access pixel data
    without caring about storage strategy.
    
    Args:
        raster: CanonicalRaster object
        
    Returns:
        NumPy array (H, W, 3) uint8
        
    Raises:
        CanonicalizationError: If pixel array cannot be loaded
    """
    try:
        if raster.pixel_array is not None:
            # In-memory storage
            return raster.pixel_array
        
        if raster.pixel_array_path is not None:
            # File-based storage
            pixel_array = np.load(raster.pixel_array_path)
            
            # Validate loaded array
            if pixel_array.shape != (raster.height_px, raster.width_px, 3):
                raise CanonicalizationError(
                    f"Loaded array shape mismatch: expected "
                    f"({raster.height_px}, {raster.width_px}, 3), "
                    f"got {pixel_array.shape}",
                    details={
                        "path": raster.pixel_array_path,
                        "expected_shape": (raster.height_px, raster.width_px, 3),
                        "actual_shape": pixel_array.shape
                    }
                )
            
            if pixel_array.dtype != np.uint8:
                raise CanonicalizationError(
                    f"Loaded array dtype mismatch: expected uint8, got {pixel_array.dtype}",
                    details={
                        "path": raster.pixel_array_path,
                        "dtype": str(pixel_array.dtype)
                    }
                )
            
            return pixel_array
        
        # Should never reach here due to CanonicalRaster validation
        raise CanonicalizationError(
            "CanonicalRaster has neither pixel_array nor pixel_array_path set"
        )
        
    except CanonicalizationError:
        raise
    except Exception as e:
        raise CanonicalizationError(
            "Failed to load canonical raster pixel array",
            details={"error": str(e)}
        ) from e


def validate_canonical_raster(raster: CanonicalRaster) -> None:
    """
    Validate canonical raster invariants.
    
    Checks:
    - Schema version is current
    - Color mode is RGB
    - Bit depth is 8
    - Path is always set (source of truth)
    - Array is optional for small images (performance)
    - Pixel array loadable and matches declared dimensions
    - Repeat grid divisibility
    
    Args:
        raster: CanonicalRaster to validate
        
    Raises:
        CanonicalizationError: If any invariant is violated
    """
    # Validate schema version
    if raster.schema_version != "stage1.v1":
        raise CanonicalizationError(
            f"Unsupported canonical raster schema version: {raster.schema_version}",
            details={"version": raster.schema_version, "expected": "stage1.v1"}
        )
    
    # Validate color mode
    if raster.color_mode != "RGB":
        raise CanonicalizationError(
            f"Invalid color mode: expected RGB, got {raster.color_mode}",
            details={"color_mode": raster.color_mode}
        )
    
    # Validate bit depth
    if raster.bit_depth != 8:
        raise CanonicalizationError(
            f"Invalid bit depth: expected 8, got {raster.bit_depth}",
            details={"bit_depth": raster.bit_depth}
        )
    
    # Validate storage: path must always be present (source of truth)
    has_array = raster.pixel_array is not None
    has_path = raster.pixel_array_path is not None
    
    if not has_path:
        raise CanonicalizationError(
            "CanonicalRaster must have pixel_array_path set (source of truth)"
        )
    
    # Array is optional (small images have both for performance)
    
    # Validate pixel array loadable
    try:
        pixel_array = load_canonical_raster(raster)
    except Exception as e:
        raise CanonicalizationError(
            "Failed to load canonical raster pixel array during validation",
            details={"error": str(e)}
        ) from e
    
    # Validate repeat grid divisibility
    repeat_w = raster.repeat_unit_px["width"]
    repeat_h = raster.repeat_unit_px["height"]
    
    if raster.width_px % repeat_w != 0:
        raise CanonicalizationError(
            "Repeat grid violation: width not divisible by repeat width",
            details={
                "width_px": raster.width_px,
                "repeat_width_px": repeat_w,
                "remainder": raster.width_px % repeat_w
            }
        )
    
    if raster.height_px % repeat_h != 0:
        raise CanonicalizationError(
            "Repeat grid violation: height not divisible by repeat height",
            details={
                "height_px": raster.height_px,
                "repeat_height_px": repeat_h,
                "remainder": raster.height_px % repeat_h
            }
        )
    
    logger.debug("Canonical raster validation passed")
