"""
Stage 1: Canonical Normalization

PURPOSE:
Converts a VALIDATED but REPRESENTATION-AMBIGUOUS image into a SINGLE,
DETERMINISTIC internal representation called the CANONICAL RASTER.

GUARANTEES:
- Color mode: RGB only (no RGBA, L, P, or exotic modes)
- Bit depth: 8-bit per channel
- Orientation: normalized (EXIF rotation applied)
- Pixel grid: unchanged geometry (no rescaling)
- Repeat grid: perfectly aligned (width % repeat_w == 0)
- Encoding: in-memory NumPy array stored as .npy file

FORBIDDEN:
- No AI or diffusion
- No geometry smoothing
- No motif creation/deletion
- No cropping or resizing
- No metadata inference
"""

import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from PIL import Image, ImageOps

from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import (
    StageInput,
    StageOutput,
    StageStatus,
    CanonicalRaster,
)
from weaver.shared.exceptions import CanonicalizationError
from pydantic import Field, ConfigDict


class Stage1Input(StageInput):
    """
    Input schema for Stage 1.
    
    Receives validated InputDescriptor fields from Stage 0.
    Stage 0 guarantees these fields are valid - do NOT re-validate.
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    # From InputDescriptor (Stage 0 output)
    image_path: str = Field(..., description="Path to immutable raw image")
    width_px: int = Field(..., description="Image width in pixels")
    height_px: int = Field(..., description="Image height in pixels")
    dpi: int = Field(..., description="Validated DPI from Stage 0")
    repeat_unit_px: Dict[str, int] = Field(
        ..., description="Repeat unit {width, height} in pixels"
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
    
    Converts validated input into deterministic canonical form.
    Removes ALL representational ambiguity for downstream stages.
    
    PROCESSING STEPS (IN ORDER):
    1. Load image from InputDescriptor.image_path
    2. Normalize orientation using EXIF transpose
    3. Normalize color space (RGB/RGBA/L/P → RGB)
    4. Normalize bit depth (enforce 8-bit per channel)
    5. Assert repeat grid integrity (fail if violated)
    6. Convert to NumPy array (H, W, 3) uint8
    7. Save to .npy file in storage/{pipeline_id}/
    8. Emit CanonicalRaster object
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=1,
            name="Canonical Normalization",
            description="Converts validated input into deterministic canonical raster",
            version="1.0.0",
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
        Validate output postconditions.
        
        Ensures canonical raster invariants:
        - Color mode is RGB
        - Bit depth is 8
        - Pixel array file exists and is loadable
        - Array shape matches (H, W, 3)
        - Array dtype is uint8
        - Repeat grid integrity maintained
        """
        raster = output_data.canonical_raster
        
        # Invariant: Color mode must be RGB
        if raster.color_mode != "RGB":
            raise CanonicalizationError(
                message=f"Post-normalization color mode is not RGB: {raster.color_mode}",
                stage_number=1,
                details={
                    "color_mode": raster.color_mode,
                    "expected": "RGB",
                },
            )
        
        # Invariant: Bit depth must be 8
        if raster.bit_depth != 8:
            raise CanonicalizationError(
                message=f"Post-normalization bit depth is not 8: {raster.bit_depth}",
                stage_number=1,
                details={
                    "bit_depth": raster.bit_depth,
                    "expected": 8,
                },
            )
        
        # Invariant: Pixel array file must exist
        pixel_array_path = Path(raster.pixel_array_path)
        if not pixel_array_path.exists():
            raise CanonicalizationError(
                message=f"Canonical raster file not found: {raster.pixel_array_path}",
                stage_number=1,
                details={"pixel_array_path": raster.pixel_array_path},
            )
        
        # Invariant: Pixel array must be loadable and have correct shape/dtype
        try:
            pixel_array = np.load(raster.pixel_array_path)
        except Exception as e:
            raise CanonicalizationError(
                message=f"Failed to load canonical raster: {e}",
                stage_number=1,
                details={
                    "pixel_array_path": raster.pixel_array_path,
                    "error": str(e),
                },
            )
        
        # Invariant: Shape must be (H, W, 3)
        if pixel_array.ndim != 3 or pixel_array.shape[2] != 3:
            raise CanonicalizationError(
                message=f"Canonical raster shape is not (H, W, 3): {pixel_array.shape}",
                stage_number=1,
                details={
                    "shape": pixel_array.shape,
                    "expected_channels": 3,
                },
            )
        
        # Invariant: Dtype must be uint8
        if pixel_array.dtype != np.uint8:
            raise CanonicalizationError(
                message=f"Canonical raster dtype is not uint8: {pixel_array.dtype}",
                stage_number=1,
                details={
                    "dtype": str(pixel_array.dtype),
                    "expected": "uint8",
                },
            )
        
        # Invariant: Dimensions must match declared values
        height, width, _ = pixel_array.shape
        if width != raster.width_px or height != raster.height_px:
            raise CanonicalizationError(
                message=f"Canonical raster dimensions mismatch: array={width}x{height}, declared={raster.width_px}x{raster.height_px}",
                stage_number=1,
                details={
                    "array_width": width,
                    "array_height": height,
                    "declared_width": raster.width_px,
                    "declared_height": raster.height_px,
                },
            )
        
        # Invariant: Repeat grid integrity (must tile perfectly)
        repeat_w = raster.repeat_unit_px["width"]
        repeat_h = raster.repeat_unit_px["height"]
        
        if raster.width_px % repeat_w != 0:
            raise CanonicalizationError(
                message=f"Repeat grid violation: width {raster.width_px} is not divisible by repeat width {repeat_w}",
                stage_number=1,
                details={
                    "width_px": raster.width_px,
                    "repeat_width": repeat_w,
                    "remainder": raster.width_px % repeat_w,
                },
            )
        
        if raster.height_px % repeat_h != 0:
            raise CanonicalizationError(
                message=f"Repeat grid violation: height {raster.height_px} is not divisible by repeat height {repeat_h}",
                stage_number=1,
                details={
                    "height_px": raster.height_px,
                    "repeat_height": repeat_h,
                    "remainder": raster.height_px % repeat_h,
                },
            )
    
    def execute(self, input_data: Stage1Input) -> Stage1Output:
        """
        Execute Stage 1: Canonical Normalization.
        
        Converts input image into canonical RGB 8-bit representation
        with perfect repeat grid alignment.
        
        Args:
            input_data: Stage 1 input with validated image metadata
        
        Returns:
            Stage 1 output with canonical raster
        """
        start_time = time.time()
        transformations: List[str] = []
        
        # Step 1: Load image from validated path
        # WHY: Start with raw image data from Stage 0
        try:
            img = Image.open(input_data.image_path)
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
        conversion_start = time.time()
        
        # Step 2: Normalize orientation using EXIF transpose
        # WHY: Remove EXIF rotation flags to get true pixel orientation.
        # Some formats (JPEG, TIFF) store rotation in metadata rather than
        # physically rotating pixels. This applies the rotation and clears flags.
        try:
            img_transposed = ImageOps.exif_transpose(img)
            if img_transposed is not None:
                if img_transposed.size != img.size:
                    transformations.append("EXIF_transpose_rotated")
                img = img_transposed
            else:
                img = img  # No EXIF orientation data
        except Exception as e:
            # If EXIF transpose fails, continue with original image
            # (this is non-critical for lossless formats from Stage 0)
            pass
        
        # Step 3: Normalize color space
        # WHY: Downstream stages require consistent RGB representation.
        # - RGBA → RGB with white background (manufacturing standard)
        # - L (grayscale) → RGB via channel replication
        # - P (palette) → RGB via palette lookup
        # - 1 (1-bit) → RGB via conversion
        original_mode = img.mode
        
        if img.mode == "RGBA":
            # Convert RGBA to RGB with WHITE background composite
            # WHY: Manufacturing equipment interprets absence of thread as white fabric.
            # Alpha channel must be resolved to concrete color before CAM export.
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            img = rgb_img
            transformations.append("RGBA_to_RGB_white_background")
        
        elif img.mode == "LA":
            # Convert grayscale+alpha to RGB with white background
            l_img = img.convert("L")
            alpha = img.split()[1]
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            gray_rgb = Image.merge("RGB", [l_img, l_img, l_img])
            rgb_img.paste(gray_rgb, mask=alpha)
            img = rgb_img
            transformations.append("LA_to_RGB_white_background")
        
        elif img.mode in ("L", "P", "1"):
            # Convert grayscale, palette, or 1-bit to RGB
            # WHY: Ensures consistent 3-channel representation
            img = img.convert("RGB")
            transformations.append(f"{original_mode}_to_RGB")
        
        elif img.mode == "RGB":
            # Already RGB - no conversion needed
            pass
        
        else:
            # Unsupported color mode (should never happen if Stage 0 validated)
            raise CanonicalizationError(
                message=f"Unsupported color mode: {img.mode}",
                stage_number=1,
                details={
                    "color_mode": img.mode,
                    "image_path": input_data.image_path,
                },
            )
        
        # Step 4: Normalize bit depth
        # WHY: Ensure 8-bit per channel for deterministic processing.
        # PIL's RGB mode is always 8-bit, but we explicitly verify this.
        if img.mode != "RGB":
            raise CanonicalizationError(
                message=f"Color mode is not RGB after conversion: {img.mode}",
                stage_number=1,
                details={
                    "mode_after_conversion": img.mode,
                    "original_mode": original_mode,
                },
            )
        
        # Step 5: Set DPI metadata (without rescaling pixels)
        # WHY: Preserve DPI information from Stage 0 for downstream reference.
        # This does NOT rescale the pixel grid - only sets metadata.
        img.info["dpi"] = (input_data.dpi, input_data.dpi)
        
        # Step 6: Assert repeat grid integrity
        # WHY: Repeat unit must tile perfectly into image dimensions.
        # If this fails, it indicates Stage 0 contract breach or data corruption.
        repeat_w = input_data.repeat_unit_px["width"]
        repeat_h = input_data.repeat_unit_px["height"]
        
        if img.width % repeat_w != 0:
            raise CanonicalizationError(
                message=f"Repeat grid violation: width {img.width} not divisible by repeat width {repeat_w}",
                stage_number=1,
                details={
                    "width_px": img.width,
                    "repeat_width": repeat_w,
                    "remainder": img.width % repeat_w,
                    "expected_stage": "Stage 0 should have caught this",
                },
            )
        
        if img.height % repeat_h != 0:
            raise CanonicalizationError(
                message=f"Repeat grid violation: height {img.height} not divisible by repeat height {repeat_h}",
                stage_number=1,
                details={
                    "height_px": img.height,
                    "repeat_height": repeat_h,
                    "remainder": img.height % repeat_h,
                    "expected_stage": "Stage 0 should have caught this",
                },
            )
        
        # Step 7: Convert to NumPy array
        # WHY: NumPy provides deterministic in-memory tensor representation
        # with explicit shape (H, W, 3) and dtype uint8.
        try:
            pixel_array = np.array(img, dtype=np.uint8)
        except Exception as e:
            raise CanonicalizationError(
                message=f"Failed to convert image to NumPy array: {e}",
                stage_number=1,
                details={"error": str(e)},
            )
        
        # Verify array shape
        if pixel_array.ndim != 3 or pixel_array.shape[2] != 3:
            raise CanonicalizationError(
                message=f"NumPy array shape is not (H, W, 3): {pixel_array.shape}",
                stage_number=1,
                details={"shape": pixel_array.shape},
            )
        
        # Step 8: Save to .npy file
        # WHY: Store canonical raster as file for consumption by downstream stages.
        # .npy format preserves exact array structure and dtype.
        storage_dir = Path("storage") / input_data.pipeline_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        pixel_array_path = storage_dir / "canonical_raster.npy"
        try:
            np.save(str(pixel_array_path), pixel_array)
        except Exception as e:
            raise CanonicalizationError(
                message=f"Failed to save canonical raster: {e}",
                stage_number=1,
                details={
                    "pixel_array_path": str(pixel_array_path),
                    "error": str(e),
                },
            )
        
        conversion_time_ms = int((time.time() - conversion_start) * 1000)
        
        # Step 9: Create CanonicalRaster object
        canonical_raster = CanonicalRaster(
            schema_version="stage1.v1",
            width_px=pixel_array.shape[1],
            height_px=pixel_array.shape[0],
            dpi=input_data.dpi,
            color_mode="RGB",
            bit_depth=8,
            pixel_array_path=str(pixel_array_path),
            repeat_unit_px=input_data.repeat_unit_px,
        )
        
        # Return Stage 1 output
        return Stage1Output(
            stage_number=1,
            status=StageStatus.COMPLETED,
            message=f"Image normalized to canonical RGB raster ({pixel_array.shape[1]}x{pixel_array.shape[0]})",
            canonical_raster=canonical_raster,
            original_color_mode=original_mode,
            transformations_applied=transformations,
            metrics={
                "load_time_ms": load_time_ms,
                "conversion_time_ms": conversion_time_ms,
                "total_time_ms": int((time.time() - start_time) * 1000),
                "width_px": pixel_array.shape[1],
                "height_px": pixel_array.shape[0],
                "repeat_tiles_horizontal": pixel_array.shape[1] // repeat_w,
                "repeat_tiles_vertical": pixel_array.shape[0] // repeat_h,
            },
        )
