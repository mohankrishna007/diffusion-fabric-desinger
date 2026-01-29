"""
Stage 1: Canonical Normalization - Refactored Modular Architecture

PURPOSE:
Converts a VALIDATED but REPRESENTATION-AMBIGUOUS image into a SINGLE,
DETERMINISTIC internal representation called the CANONICAL RASTER.

ARCHITECTURE:
This processor orchestrates a linear pipeline of specialized sub-modules:
1. OrientationNormalizer - Apply EXIF rotation, clear flags
2. ColorSpaceNormalizer - Convert to RGB, resolve alpha, strip ICC
3. DPICanonicalizer - Rescale pixels to canonical DPI
4. GridNormalizer - Validate repeat grid integrity
5. RasterEmitter - Convert to NumPy array, apply hybrid storage

Each module is:
- Single-responsibility
- Side-effect free (except file I/O)
- Unit testable
- Composable

GUARANTEES:
- Color mode: RGB only (no RGBA, L, P, or exotic modes)
- Bit depth: 8-bit per channel
- Orientation: normalized (EXIF rotation applied)
- DPI: canonical DPI enforced (pixels rescaled if needed)
- ICC profiles: stripped (deterministic color interpretation)
- Repeat grid: perfectly aligned (width % repeat_w == 0)
- Encoding: hybrid storage (in-memory or .npy file based on size)

FORBIDDEN:
- No AI or diffusion
- No geometry smoothing beyond resampling
- No motif creation/deletion
- No cropping or padding
- No metadata inference
"""

import time
from pathlib import Path
from typing import List, Optional, cast
from PIL import Image

from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages.stage_result import InputAcquisitionResult, CanonicalNormalizationResult, StageResult
from weaver.shared.constants import WORKSPACE_BASE_DIR
from weaver.shared.schemas import (
    AlphaPolicy,
)
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger

# Import sub-modules
from .orientation_normalizer import normalize_orientation
from .colorspace_normalizer import normalize_color_space
from .dpi_canonicalizer import canonicalize_dpi
from .grid_normalizer import validate_repeat_grid, calculate_tile_counts
from .raster_emitter import emit_canonical_raster

logger = get_logger(__name__)


class CanonicalNormalizationStage(BaseStage):
    """
    Stage 1: Canonical Normalization
    
    Orchestrates linear pipeline of normalization sub-modules.
    
    PROCESSING PIPELINE:
    1. Load image from InputAcquisitionResult.image_path
    2. OrientationNormalizer: Apply EXIF rotation, clear flags
    3. ColorSpaceNormalizer: Convert to RGB, resolve alpha, strip ICC
    4. DPICanonicalizer: Rescale pixels to canonical DPI
    5. GridNormalizer: Validate repeat grid integrity
    6. RasterEmitter: Convert to NumPy, apply hybrid storage
    7. Validate: Check all post-execution invariants
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_id="canonical_normalization",
            name="Canonical Normalization",
            description="Converts validated input into deterministic canonical raster via modular pipeline",
            version="2.0.0",  # Version 2.0: Modular architecture with DPI rescaling
        )
    
    def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
        """Validate that prev_result is InputAcquisitionResult."""
        if not isinstance(prev_result, InputAcquisitionResult):
            raise TypeError(
                f"Stage 1 requires InputAcquisitionResult, got {type(prev_result).__name__}"
            )
    
    def _execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> CanonicalNormalizationResult:
        """
        Execute Stage 1: Canonical Normalization via modular pipeline.
        
        PIPELINE FLOW:
        1. Load image
        2. Normalize orientation (EXIF)
        3. Normalize color space (RGB + ICC strip)
        4. Canonicalize DPI (rescale pixels)
        5. Validate repeat grid
        6. Emit canonical raster (hybrid storage)
        
        Args:
            prev_result: InputAcquisitionResult from Stage 0
            pipeline_id: Unique pipeline execution ID
            config: Stage configuration dict
        
        Returns:
            CanonicalNormalizationResult with canonical raster
        """
        start_time = time.time()
        transformations: List[str] = []
        
        # Extract configuration values
        canonical_dpi = config.get("canonical_dpi", 300)
        memory_threshold_mb = config.get("memory_threshold_mb", 50)
        alpha_policy = AlphaPolicy(config.get("alpha_policy", "FLATTEN_WHITE"))
        strip_icc_profile = config.get("strip_icc_profile", True)
        resampling_method = config.get("resampling_method", "LANCZOS")
        
        # Cast to expected type (already validated)
        input_result = cast(InputAcquisitionResult, prev_result)
        
        # Extract values from previous stage result
        image_path = input_result.image_path
        dpi = input_result.dpi
        repeat_unit_px = input_result.repeat_unit_px
        raw_hash = input_result.raw_hash
        
        logger.info(f"Starting Stage 1 normalization: {image_path}")
        
        # STEP 1: Load image from validated path
        try:
            img = Image.open(image_path)
            logger.debug(f"Loaded image: {img.size}, mode={img.mode}")
        except Exception as e:
            raise CanonicalizationError(
                message=f"Failed to load image: {e}",
                stage_number=1,
                details={
                    "image_path": image_path,
                    "error": str(e),
                },
            )
        
        load_time_ms = int((time.time() - start_time) * 1000)
        pipeline_start = time.time()
        
        original_size = img.size
        original_mode = img.mode
        
        # STEP 2: Normalize orientation
        img = normalize_orientation(img)
        if img.size != original_size:
            transformations.append("EXIF_orientation_applied")
        
        # STEP 3: Normalize color space
        img, color_transforms = normalize_color_space(img, alpha_policy)
        transformations.extend(color_transforms)
        
        # STEP 4: Canonicalize DPI
        input_repeat_w = repeat_unit_px.get("width", 100)
        input_repeat_h = repeat_unit_px.get("height", 100)
        
        img, dpi_metadata = canonicalize_dpi(
            img=img,
            input_dpi=dpi,
            canonical_dpi=canonical_dpi,
            repeat_width_px=input_repeat_w,
            repeat_height_px=input_repeat_h,
            resampling_method=resampling_method
        )
        
        if dpi_metadata["rescaled"]:
            transformations.append(f"DPI_rescaled_{dpi}to{canonical_dpi}_{dpi_metadata['resampling_method']}")
        
        # Update repeat unit to canonical dimensions
        canonical_repeat_unit = {
            "width": dpi_metadata["canonical_repeat"][0],
            "height": dpi_metadata["canonical_repeat"][1]
        }
        
        # STEP 5: Validate repeat grid
        validate_repeat_grid(
            img=img,
            repeat_width_px=canonical_repeat_unit["width"],
            repeat_height_px=canonical_repeat_unit["height"]
        )
        
        tile_metrics = calculate_tile_counts(
            width_px=img.width,
            height_px=img.height,
            repeat_width_px=canonical_repeat_unit["width"],
            repeat_height_px=canonical_repeat_unit["height"]
        )
        
        pipeline_time_ms = int((time.time() - pipeline_start) * 1000)
        
        # STEP 6: Emit canonical raster (RasterEmitter)
        storage_dir = Path(WORKSPACE_BASE_DIR) / pipeline_id
        
        canonical_raster = emit_canonical_raster(
            img=img,
            pipeline_id=pipeline_id,
            storage_dir=storage_dir,
            dpi=canonical_dpi,
            repeat_unit_px=canonical_repeat_unit,
            memory_threshold_mb=memory_threshold_mb
        )
        
        total_time_ms = int((time.time() - start_time) * 1000)
        storage_type = "in_memory" if canonical_raster.pixel_array is not None else "file"
        original_size_str = f"{original_size[0]}x{original_size[1]}"
        canonical_size_str = f"{canonical_raster.width_px}x{canonical_raster.height_px}"
        
        logger.info(
            f"Stage 1 complete: {original_size_str} -> {canonical_size_str}, "
            f"{original_mode} -> RGB, {dpi}dpi -> {canonical_dpi}dpi ({total_time_ms}ms)"
        )
        
        # STEP 7: Build stage metadata (saved by pipeline engine)
        stage_metadata = {
            "stage_number": 1,
            "stage_name": "Canonical Normalization",
            "status": "COMPLETED",
            "pipeline_id": pipeline_id,
            "original_color_mode": original_mode,
            "transformations_applied": transformations,
            "normalization_config": {
                "canonical_dpi": canonical_dpi,
                "alpha_policy": alpha_policy.value,
                "strip_icc_profile": strip_icc_profile,
                "resampling_method": resampling_method
            },
            "metrics": {
                "load_time_ms": load_time_ms,
                "pipeline_time_ms": pipeline_time_ms,
                "total_time_ms": total_time_ms,
                "original_size": original_size_str,
                "canonical_size": canonical_size_str,
                "original_dpi": dpi,
                "canonical_dpi": canonical_dpi,
                "dpi_scale_factor": dpi_metadata["scale_factor"],
                "tiles_horizontal": tile_metrics["tiles_horizontal"],
                "tiles_vertical": tile_metrics["tiles_vertical"],
                "total_tiles": tile_metrics["total_tiles"],
                "storage_type": storage_type
            },
            "canonical_raster": {
                "width_px": canonical_raster.width_px,
                "height_px": canonical_raster.height_px,
                "dpi": canonical_raster.dpi,
                "color_mode": canonical_raster.color_mode,
                "bit_depth": canonical_raster.bit_depth,
                "repeat_unit_px": canonical_raster.repeat_unit_px,
                "pixel_array_path": canonical_raster.pixel_array_path,
                "storage_type": storage_type
            }
        }
        
        # STEP 8: Return result
        return CanonicalNormalizationResult(
            pipeline_id=pipeline_id,
            stage_metadata=stage_metadata,
            pixel_array_path=canonical_raster.pixel_array_path,
            pixel_array=canonical_raster.pixel_array,
            width_px=canonical_raster.width_px,
            height_px=canonical_raster.height_px,
            dpi=canonical_raster.dpi,
            repeat_unit_px=canonical_raster.repeat_unit_px,
            color_mode=canonical_raster.color_mode
        )

