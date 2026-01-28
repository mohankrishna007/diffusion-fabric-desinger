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
import yaml
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from PIL import Image

from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import (
    StageInput,
    StageOutput,
    StageStatus,
    CanonicalRaster,
    AlphaPolicy,
)
from weaver.shared.exceptions import CanonicalizationError
from weaver.shared.logger import get_logger
from pydantic import Field, ConfigDict

# Import sub-modules
from .orientation_normalizer import normalize_orientation, validate_orientation_normalized
from .colorspace_normalizer import normalize_color_space, validate_color_space_normalized
from .dpi_canonicalizer import canonicalize_dpi, validate_dpi_canonical
from .grid_normalizer import validate_repeat_grid, calculate_tile_counts
from .raster_emitter import emit_canonical_raster, validate_canonical_raster

logger = get_logger(__name__)


class Stage1Input(StageInput):
    """
    Input schema for Stage 1.
    
    Receives validated InputDescriptor fields from Stage 0.
    Stage 0 guarantees these fields are valid - do NOT re-validate.
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    # From InputDescriptor (Stage 0 output)
    image_path: str = Field(..., description="Path to immutable raw image")
    width_px: int = Field(..., description="Image width in pixels (at input DPI)")
    height_px: int = Field(..., description="Image height in pixels (at input DPI)")
    dpi: int = Field(..., description="Validated DPI from Stage 0")
    repeat_unit_px: Dict[str, int] = Field(
        ..., description="Repeat unit {width, height} in pixels (at input DPI)"
    )
    color_mode: str = Field(..., description="Original color mode from Stage 0")
    bit_depth: int = Field(..., description="Original bit depth from Stage 0")
    raw_hash: str = Field(..., description="SHA-256 hash of raw image")


class Stage1Output(StageOutput):
    """
    Output schema for Stage 1.
    
    Contains the canonical raster and normalization metadata.
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    canonical_raster: CanonicalRaster = Field(
        ..., description="Canonical normalized raster"
    )
    original_color_mode: str = Field(
        ..., description="Original color mode before normalization"
    )
    transformations_applied: List[str] = Field(
        default_factory=list,
        description="List of normalization transformations applied",
    )


class Stage1CanonicalNormalization(BaseStage[Stage1Input, Stage1Output]):
    """
    Stage 1: Canonical Normalization
    
    Orchestrates linear pipeline of normalization sub-modules.
    
    PROCESSING PIPELINE:
    1. Load image from InputDescriptor.image_path
    2. OrientationNormalizer: Apply EXIF rotation, clear flags
    3. ColorSpaceNormalizer: Convert to RGB, resolve alpha, strip ICC
    4. DPICanonicalizer: Rescale pixels to canonical DPI
    5. GridNormalizer: Validate repeat grid integrity
    6. RasterEmitter: Convert to NumPy, apply hybrid storage
    7. Validate: Check all post-execution invariants
    """
    
    def __init__(self):
        super().__init__()
        self._load_config()
    
    def _load_config(self) -> None:
        """
        Load canonical raster standards from pipeline.yaml.
        
        Loads configuration values for:
        - canonical_dpi: Target DPI (enforced via rescaling)
        - memory_threshold_mb: Hybrid storage threshold
        - alpha_policy: Alpha channel handling policy
        - strip_icc_profile: Whether to strip ICC profiles
        - resampling_method: DPI rescaling algorithm
        """
        config_path = Path("config/pipeline.yaml")
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            self._set_default_config()
            return
        
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            
            # Extract canonical raster config
            canon_config = config.get("canonical_raster", {})
            
            self.canonical_dpi = canon_config.get("canonical_dpi", 300)
            self.memory_threshold_mb = canon_config.get("memory_threshold_mb", 50)
            self.alpha_policy = AlphaPolicy(canon_config.get("alpha_policy", "FLATTEN_WHITE"))
            self.strip_icc_profile = canon_config.get("strip_icc_profile", True)
            self.resampling_method = canon_config.get("resampling_method", "LANCZOS")
            
            logger.debug(
                f"Loaded config: canonical_dpi={self.canonical_dpi}, "
                f"memory_threshold={self.memory_threshold_mb}MB, "
                f"alpha_policy={self.alpha_policy.value}, "
                f"resampling={self.resampling_method}"
            )
            
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            self._set_default_config()
    
    def _set_default_config(self) -> None:
        """Set default configuration values."""
        self.canonical_dpi = 300
        self.memory_threshold_mb = 50
        self.alpha_policy = AlphaPolicy.FLATTEN_WHITE
        self.strip_icc_profile = True
        self.resampling_method = "LANCZOS"
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=1,
            name="Canonical Normalization",
            description="Converts validated input into deterministic canonical raster via modular pipeline",
            version="2.0.0",  # Version 2.0: Modular architecture with DPI rescaling
            author="Weaver AI Team",
        )
    
    def pre_execute(self, input_data: Stage1Input) -> None:
        """
        Validate input preconditions.
        
        Ensures:
        - Image file exists and is readable
        - Pipeline workspace directory exists
        """
        image_path = Path(input_data.image_path)
        if not image_path.exists():
            raise CanonicalizationError(
                message=f"Input image not found: {input_data.image_path}",
                stage_number=1,
                details={
                    "image_path": input_data.image_path,
                    "pipeline_id": input_data.pipeline_id,
                },
            )
        
        if not image_path.is_file():
            raise CanonicalizationError(
                message=f"Input path is not a file: {input_data.image_path}",
                stage_number=1,
                details={
                    "image_path": input_data.image_path,
                    "pipeline_id": input_data.pipeline_id,
                },
            )
    
    def post_execute(self, output_data: Stage1Output) -> None:
        """
        Validate output postconditions using raster_emitter validation.
        
        Delegates to validate_canonical_raster() which checks:
        - Color mode is RGB
        - Bit depth is 8
        - Pixel array is loadable
        - Array shape matches (H, W, 3)
        - Array dtype is uint8
        - Repeat grid integrity maintained
        """
        validate_canonical_raster(output_data.canonical_raster)
    
    def execute(self, input_data: Stage1Input) -> Stage1Output:
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
            input_data: Stage 1 input with validated image metadata
        
        Returns:
            Stage 1 output with canonical raster
        """
        start_time = time.time()
        transformations: List[str] = []
        
        logger.info(f"Starting Stage 1 normalization: {input_data.image_path}")
        
        # ===================================================================
        # STEP 1: Load image from validated path
        # ===================================================================
        try:
            img = Image.open(input_data.image_path)
            logger.debug(f"Loaded image: {img.size}, mode={img.mode}")
        except Exception as e:
            raise CanonicalizationError(
                message=f"Failed to load image: {e}",
                stage_number=1,
                details={
                    "image_path": input_data.image_path,
                    "error": str(e),
                },
            )
        
        load_time_ms = int((time.time() - start_time) * 1000)
        pipeline_start = time.time()
        
        original_size = img.size
        original_mode = img.mode
        
        # ===================================================================
        # STEP 2: Normalize orientation (OrientationNormalizer)
        # ===================================================================
        img = normalize_orientation(img)
        if img.size != original_size:
            transformations.append("EXIF_orientation_applied")
        
        # ===================================================================
        # STEP 3: Normalize color space (ColorSpaceNormalizer)
        # ===================================================================
        img, color_transforms = normalize_color_space(img, self.alpha_policy)
        transformations.extend(color_transforms)
        
        # ===================================================================
        # STEP 4: Canonicalize DPI (DPICanonicalizer)
        # ===================================================================
        # Calculate new repeat unit after DPI rescaling
        input_repeat_w = input_data.repeat_unit_px["width"]
        input_repeat_h = input_data.repeat_unit_px["height"]
        
        img, dpi_metadata = canonicalize_dpi(
            img=img,
            input_dpi=input_data.dpi,
            canonical_dpi=self.canonical_dpi,
            repeat_width_px=input_repeat_w,
            repeat_height_px=input_repeat_h,
            resampling_method=self.resampling_method
        )
        
        if dpi_metadata["rescaled"]:
            transformations.append(
                f"DPI_rescaled_{input_data.dpi}to{self.canonical_dpi}_"
                f"{dpi_metadata['resampling_method']}"
            )
        
        # Update repeat unit to canonical dimensions
        canonical_repeat_unit = {
            "width": dpi_metadata["canonical_repeat"][0],
            "height": dpi_metadata["canonical_repeat"][1]
        }
        
        # ===================================================================
        # STEP 5: Validate repeat grid (GridNormalizer)
        # ===================================================================
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
        
        # ===================================================================
        # STEP 6: Emit canonical raster (RasterEmitter)
        # ===================================================================
        storage_dir = Path("storage") / input_data.pipeline_id
        
        canonical_raster = emit_canonical_raster(
            img=img,
            pipeline_id=input_data.pipeline_id,
            storage_dir=storage_dir,
            dpi=self.canonical_dpi,
            repeat_unit_px=canonical_repeat_unit,
            memory_threshold_mb=self.memory_threshold_mb
        )
        
        total_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Stage 1 complete: {original_size} -> {img.size}, "
            f"{original_mode} -> RGB, "
            f"{input_data.dpi}dpi -> {self.canonical_dpi}dpi "
            f"({total_time_ms}ms)"
        )
        
        # ===================================================================
        # STEP 7: Return Stage 1 output
        # ===================================================================
        return Stage1Output(
            stage_number=1,
            status=StageStatus.COMPLETED,
            message=(
                f"Image normalized to canonical RGB raster "
                f"({canonical_raster.width_px}x{canonical_raster.height_px} @ {self.canonical_dpi}dpi)"
            ),
            canonical_raster=canonical_raster,
            original_color_mode=original_mode,
            transformations_applied=transformations,
            metrics={
                "load_time_ms": load_time_ms,
                "pipeline_time_ms": pipeline_time_ms,
                "total_time_ms": total_time_ms,
                "original_size": f"{original_size[0]}x{original_size[1]}",
                "canonical_size": f"{canonical_raster.width_px}x{canonical_raster.height_px}",
                "original_dpi": input_data.dpi,
                "canonical_dpi": self.canonical_dpi,
                "dpi_scale_factor": dpi_metadata["scale_factor"],
                "tiles_horizontal": tile_metrics["tiles_horizontal"],
                "tiles_vertical": tile_metrics["tiles_vertical"],
                "total_tiles": tile_metrics["total_tiles"],
                "storage_type": "in_memory" if canonical_raster.pixel_array is not None else "file",
            },
        )
