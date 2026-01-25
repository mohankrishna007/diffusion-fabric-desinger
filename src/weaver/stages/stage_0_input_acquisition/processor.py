"""
Stage 0: Input Acquisition
Responsibility: RAW DESIGN SOURCE OF TRUTH - Fast-fail input validation

MANUFACTURING-FIRST MANDATE:
This stage establishes the raw design as the immutable source of truth.
It enforces ZERO TOLERANCE for invalid inputs. No inference, no auto-correction.

FORBIDDEN BEHAVIORS:
- Inferring DPI or repeat dimensions from image content
- Auto-resizing, cropping, or correcting images
- Guessing metadata from visual analysis
- Allowing lossy formats (JPEG, WEBP, HEIC)
- Passing with warnings
- Performing any AI/CV/image enhancement

INPUT CONTRACT:
Design Package must include:
- Raw image file (PNG, TIFF, or BMP ONLY)
- Explicit metadata: dpi, repeat_unit_px, color_mode

OUTPUT CONTRACT (exactly one):
- PASS: {status: PASS, input_descriptor: {...}}
- FAIL: {status: FAIL, error_code: ..., message: ..., details: {...}}

No partial success. No dual outputs.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any

from PIL import Image
from pydantic import BaseModel, Field, ConfigDict, field_validator

from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput, StageStatus
from weaver.shared.exceptions import (
    InputFormatError,
    MetadataConsistencyError,
    DimensionalConstraintError,
    RepeatIntegrityError,
    ResourceProtectionError,
    InputSchemaError,
)
from weaver.shared.constants import (
    LOSSLESS_INPUT_FORMATS,
    MAX_IMAGE_WIDTH,
    MAX_IMAGE_HEIGHT,
    MAX_MEGAPIXELS,
    MAX_FILE_SIZE_BYTES,
    MAX_PIXEL_COUNT,
    MIN_DPI,
    MAX_DPI,
)


class RepeatUnit(BaseModel):
    """Repeat unit dimensions in pixels - lightweight value object."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    width: int = Field(..., gt=0, description="Repeat unit width in pixels")
    height: int = Field(..., gt=0, description="Repeat unit height in pixels")


class Stage0Input(StageInput):
    """
    Input schema for Stage 0 - Design Package.
    
    STRICT CONTRACT: All fields are REQUIRED. No defaults, no inference.
    Missing metadata = FAIL immediately.
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    image_path: str = Field(
        ...,
        description="Absolute path to raw design image file"
    )
    dpi: int = Field(
        ...,
        ge=MIN_DPI,
        le=MAX_DPI,
        description="Declared DPI - must match image metadata if present"
    )
    repeat_unit_px: RepeatUnit = Field(
        ...,
        description="Explicit repeat unit dimensions in pixels"
    )
    color_mode: str = Field(
        ...,
        description="Declared color mode (e.g., 'RGB', 'RGBA', 'L')"
    )
    
    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, v: str) -> str:
        """Validate image path exists and is a file."""
        path = Path(v)
        if not path.exists():
            raise InputSchemaError(
                message=f"Image file does not exist: {v}",
                stage_number=0,
                details={"image_path": v, "error": "file_not_found"}
            )
        if not path.is_file():
            raise InputSchemaError(
                message=f"Image path is not a file: {v}",
                stage_number=0,
                details={"image_path": v, "error": "not_a_file"}
            )
        return v
    
    @field_validator("color_mode")
    @classmethod
    def validate_color_mode(cls, v: str) -> str:
        """Validate color mode is recognized."""
        valid_modes = {"RGB", "RGBA", "L", "LA", "1", "P"}
        if v not in valid_modes:
            raise InputSchemaError(
                message=f"Invalid color mode: {v}",
                stage_number=0,
                details={"color_mode": v, "valid_modes": list(valid_modes)}
            )
        return v


class InputDescriptor(StageOutput):
    """
    Canonical Input Descriptor - Source of Truth.
    
    This descriptor represents the VALIDATED, IMMUTABLE raw design.
    All downstream stages must trust this descriptor completely.
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    schema_version: str = Field(
        default="stage0.v1",
        description="Input descriptor schema version"
    )
    raw_hash: str = Field(
        ...,
        description="SHA-256 hash of raw image bytes (immutability proof)"
    )
    image_path: str = Field(
        ...,
        description="Path to immutable raw image"
    )
    width_px: int = Field(..., description="Image width in pixels")
    height_px: int = Field(..., description="Image height in pixels")
    dpi: int = Field(..., description="Validated DPI")
    repeat_unit_px: Dict[str, int] = Field(
        ...,
        description="Validated repeat unit {width, height}"
    )
    color_mode: str = Field(..., description="Validated color mode")
    file_format: str = Field(..., description="Validated file format")
    file_size_bytes: int = Field(..., description="File size in bytes")
    bit_depth: int = Field(..., description="Bit depth per channel")


class Stage0Output(StageOutput):
    """
    Output schema for Stage 0.
    
    PASS: Contains input_descriptor
    FAIL: Contains error details, no input_descriptor
    """
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    input_descriptor: Optional[InputDescriptor] = Field(
        default=None,
        description="Canonical input descriptor (present only on PASS)"
    )


class Stage0InputAcquisition(BaseStage[Stage0Input, Stage0Output]):
    """
    Stage 0: Input Acquisition
    
    RESPONSIBILITY: Establish raw design as immutable source of truth.
    
    VALIDATION STEPS (executed in order, FAIL-FAST):
    1. Schema validation (Pydantic pre-validates)
    2. Image decode (lossless formats only)
    3. Format allowlist enforcement
    4. Metadata consistency check
    5. Dimensional sanity checks
    6. Repeat integrity verification
    7. Resource protection
    8. Source-of-truth sealing (hash + persist)
    9. Emit canonical Input Descriptor
    
    MANUFACTURING RATIONALE:
    - JPEG forbidden: Lossy compression destroys thread-level precision
    - No inference: CAM systems require explicit, validated metadata
    - Perfect tiling: Partial repeats cannot be woven
    - Dimensional limits: Jacquard loom physical constraints
    - Fast-fail: Prevent resource waste on invalid designs
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=0,
            name="Input Acquisition",
            description="RAW DESIGN SOURCE OF TRUTH - Fast-fail input validation",
            version="1.0.0",
            author="Weaver AI Manufacturing Team"
        )
    
    def execute(self, input_data: Stage0Input) -> Stage0Output:
        """
        Execute Stage 0: Input Acquisition.
        
        ARCHITECTURE: Sequential validation with FAIL-FAST semantics.
        Any validation failure raises an exception - no recovery, no warnings.
        
        Args:
            input_data: Design package with image path and explicit metadata
        
        Returns:
            Stage0Output with PASS status and input_descriptor
        
        Raises:
            InputFormatError: File format not on lossless allowlist
            MetadataConsistencyError: Declared metadata conflicts with image
            DimensionalConstraintError: Dimensions exceed manufacturing limits
            RepeatIntegrityError: Non-integer tiling detected
            ResourceProtectionError: File size or pixel count exceeds limits
        """
        
        # STEP 1: Schema validation (already done by Pydantic)
        # If we reach here, schema is valid
        
        # STEP 2: Decode image using lossless decoder
        image, image_info = self._decode_image(input_data.image_path)
        
        # STEP 3: Enforce format allowlist (LOSSLESS ONLY)
        self._validate_format_allowlist(input_data.image_path, image_info["format"])
        
        # STEP 4: Metadata consistency validation
        self._validate_metadata_consistency(
            input_data, image, image_info
        )
        
        # STEP 5: Dimensional sanity checks
        self._validate_dimensions(image_info["width"], image_info["height"])
        
        # STEP 6: Repeat integrity check (perfect tiling)
        self._validate_repeat_integrity(
            image_info["width"],
            image_info["height"],
            input_data.repeat_unit_px
        )
        
        # STEP 7: Resource protection
        self._validate_resource_limits(
            input_data.image_path,
            image_info["width"],
            image_info["height"]
        )
        
        # STEP 8: Source-of-truth sealing
        raw_hash = self._compute_image_hash(input_data.image_path)
        
        # STEP 9: Emit canonical Input Descriptor
        input_descriptor = InputDescriptor(
            stage_number=0,
            status=StageStatus.COMPLETED,
            message="Input validated and sealed as source of truth",
            schema_version="stage0.v1",
            raw_hash=raw_hash,
            image_path=str(Path(input_data.image_path).resolve()),
            width_px=image_info["width"],
            height_px=image_info["height"],
            dpi=input_data.dpi,
            repeat_unit_px={
                "width": input_data.repeat_unit_px.width,
                "height": input_data.repeat_unit_px.height
            },
            color_mode=image_info["mode"],
            file_format=image_info["format"],
            file_size_bytes=image_info["file_size"],
            bit_depth=image_info["bit_depth"],
            data={},
            metrics={
                "validation_steps_passed": 9,
                "pixel_count": image_info["width"] * image_info["height"],
                "repeat_units_x": image_info["width"] // input_data.repeat_unit_px.width,
                "repeat_units_y": image_info["height"] // input_data.repeat_unit_px.height,
            }
        )
        
        return Stage0Output(
            stage_number=0,
            status=StageStatus.COMPLETED,
            message="Input acquisition successful - design sealed as source of truth",
            input_descriptor=input_descriptor,
            data={"raw_hash": raw_hash},
            metrics=input_descriptor.metrics
        )
    
    def _decode_image(self, image_path: str) -> tuple[Image.Image, Dict[str, Any]]:
        """
        Decode image and extract metadata.
        
        RATIONALE: Use PIL for lossless decoding. Extract actual image
        properties to validate against declared metadata.
        
        Raises:
            InputFormatError: If image cannot be decoded
        """
        try:
            img = Image.open(image_path)
            
            # Extract DPI if present in image metadata
            dpi_info = img.info.get("dpi", None)
            image_dpi = None
            if dpi_info:
                # DPI can be a tuple (x_dpi, y_dpi)
                image_dpi = dpi_info[0] if isinstance(dpi_info, tuple) else dpi_info
            
            # Determine bit depth
            mode_to_depth = {
                "1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8,
                "I": 32, "F": 32, "LA": 8, "I;16": 16
            }
            bit_depth = mode_to_depth.get(img.mode, 8)
            
            image_info = {
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "format": img.format,
                "dpi": image_dpi,
                "bit_depth": bit_depth,
                "file_size": os.path.getsize(image_path)
            }
            
            return img, image_info
            
        except Exception as e:
            raise InputFormatError(
                message=f"Failed to decode image: {str(e)}",
                stage_number=0,
                details={
                    "image_path": image_path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
    
    def _validate_format_allowlist(self, image_path: str, image_format: str) -> None:
        """
        Enforce lossless format allowlist.
        
        RATIONALE: JPEG and other lossy formats introduce compression artifacts
        that destroy thread-level precision. Only PNG, TIFF, BMP are allowed.
        
        Raises:
            InputFormatError: If format is not on allowlist
        """
        file_ext = Path(image_path).suffix.lower()
        
        if file_ext not in LOSSLESS_INPUT_FORMATS:
            raise InputFormatError(
                message=(
                    f"File format '{file_ext}' not allowed. "
                    f"Only lossless formats permitted: {LOSSLESS_INPUT_FORMATS}"
                ),
                stage_number=0,
                details={
                    "file_extension": file_ext,
                    "image_format": image_format,
                    "allowed_formats": LOSSLESS_INPUT_FORMATS,
                    "rationale": (
                        "Lossy compression destroys thread-level precision "
                        "needed for CAM export"
                    )
                }
            )
    
    def _validate_metadata_consistency(
        self,
        input_data: Stage0Input,
        image: Image.Image,
        image_info: Dict[str, Any]
    ) -> None:
        """
        Validate declared metadata matches actual image properties.
        
        RATIONALE: Metadata inconsistency indicates data corruption or manual
        error. CAM systems require perfect metadata trust.
        
        Raises:
            MetadataConsistencyError: If declared metadata conflicts with image
        """
        violations = []
        
        # Check color mode consistency
        if input_data.color_mode != image_info["mode"]:
            violations.append(
                f"Color mode mismatch: declared '{input_data.color_mode}' "
                f"but image is '{image_info['mode']}'"
            )
        
        # Check DPI consistency if image has DPI metadata
        if image_info["dpi"] is not None:
            # Allow 1% tolerance for floating point rounding
            tolerance = max(1, int(input_data.dpi * 0.01))
            # Compare as floats to handle rounding
            actual_dpi = float(image_info["dpi"])
            declared_dpi = float(input_data.dpi)
            if abs(declared_dpi - actual_dpi) > tolerance:
                violations.append(
                    f"DPI mismatch: declared {input_data.dpi} "
                    f"but image metadata is {image_info['dpi']}"
                )
        
        if violations:
            raise MetadataConsistencyError(
                message="Metadata consistency validation failed",
                stage_number=0,
                details={
                    "violations": violations,
                    "declared_dpi": input_data.dpi,
                    "declared_color_mode": input_data.color_mode,
                    "actual_dpi": image_info["dpi"],
                    "actual_color_mode": image_info["mode"],
                    "rationale": (
                        "Metadata inconsistency prevents dimensional errors "
                        "in physical fabric manufacturing"
                    )
                }
            )
    
    def _validate_dimensions(self, width: int, height: int) -> None:
        """
        Validate image dimensions against manufacturing limits.
        
        RATIONALE: Jacquard looms have fixed maximum dimensions. Oversized
        designs cannot be manufactured.
        
        Raises:
            DimensionalConstraintError: If dimensions exceed limits
        """
        violations = []
        
        if width > MAX_IMAGE_WIDTH:
            violations.append(
                f"Width {width}px exceeds maximum {MAX_IMAGE_WIDTH}px"
            )
        
        if height > MAX_IMAGE_HEIGHT:
            violations.append(
                f"Height {height}px exceeds maximum {MAX_IMAGE_HEIGHT}px"
            )
        
        megapixels = (width * height) / 1_000_000
        if megapixels > MAX_MEGAPIXELS:
            violations.append(
                f"Image {megapixels:.1f}MP exceeds maximum {MAX_MEGAPIXELS}MP"
            )
        
        if violations:
            raise DimensionalConstraintError(
                message="Dimensional constraints violated",
                stage_number=0,
                details={
                    "violations": violations,
                    "width_px": width,
                    "height_px": height,
                    "megapixels": megapixels,
                    "max_width": MAX_IMAGE_WIDTH,
                    "max_height": MAX_IMAGE_HEIGHT,
                    "max_megapixels": MAX_MEGAPIXELS,
                    "rationale": (
                        "Oversized designs exceed Jacquard loom physical limits "
                        "and cannot be manufactured"
                    )
                }
            )
    
    def _validate_repeat_integrity(
        self,
        width: int,
        height: int,
        repeat_unit: RepeatUnit
    ) -> None:
        """
        Validate perfect repeat unit tiling.
        
        RATIONALE: Non-integer tiling creates partial repeats at boundaries,
        which cannot be woven. Repeat must tile perfectly.
        
        Raises:
            RepeatIntegrityError: If non-integer tiling detected
        """
        violations = []
        
        if width % repeat_unit.width != 0:
            violations.append(
                f"Width {width}px is not a multiple of repeat width "
                f"{repeat_unit.width}px (remainder: {width % repeat_unit.width}px)"
            )
        
        if height % repeat_unit.height != 0:
            violations.append(
                f"Height {height}px is not a multiple of repeat height "
                f"{repeat_unit.height}px (remainder: {height % repeat_unit.height}px)"
            )
        
        if violations:
            raise RepeatIntegrityError(
                message="Repeat integrity validation failed - non-integer tiling",
                stage_number=0,
                details={
                    "violations": violations,
                    "image_width": width,
                    "image_height": height,
                    "repeat_width": repeat_unit.width,
                    "repeat_height": repeat_unit.height,
                    "rationale": (
                        "Partial repeats at boundaries cannot be woven - "
                        "design is physically impossible to manufacture"
                    )
                }
            )
    
    def _validate_resource_limits(
        self,
        image_path: str,
        width: int,
        height: int
    ) -> None:
        """
        Validate resource protection limits.
        
        RATIONALE: Prevents DoS and resource exhaustion. Protects downstream
        stages from maliciously large files.
        
        Raises:
            ResourceProtectionError: If resource limits exceeded
        """
        violations = []
        
        file_size = os.path.getsize(image_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            violations.append(
                f"File size {file_size / 1_048_576:.1f}MB exceeds maximum "
                f"{MAX_FILE_SIZE_BYTES / 1_048_576:.0f}MB"
            )
        
        pixel_count = width * height
        if pixel_count > MAX_PIXEL_COUNT:
            violations.append(
                f"Pixel count {pixel_count:,} exceeds maximum {MAX_PIXEL_COUNT:,}"
            )
        
        if violations:
            raise ResourceProtectionError(
                message="Resource protection limits exceeded",
                stage_number=0,
                details={
                    "violations": violations,
                    "file_size_bytes": file_size,
                    "pixel_count": pixel_count,
                    "max_file_size": MAX_FILE_SIZE_BYTES,
                    "max_pixel_count": MAX_PIXEL_COUNT,
                    "rationale": (
                        "Resource limits prevent DoS and protect downstream stages "
                        "from processing maliciously large files"
                    )
                }
            )
    
    def _compute_image_hash(self, image_path: str) -> str:
        """
        Compute SHA-256 hash of raw image bytes.
        
        RATIONALE: Cryptographic hash provides immutability proof.
        Any modification to source image will change hash.
        
        Returns:
            SHA-256 hash as hexadecimal string
        """
        sha256 = hashlib.sha256()
        with open(image_path, "rb") as f:
            # Read in 64KB chunks for memory efficiency
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def pre_execute(self, input_data: Stage0Input) -> None:
        """
        Pre-execution validation.
        
        Schema validation already performed by Pydantic.
        Additional fast-fail checks could be added here.
        """
        super().pre_execute(input_data)
    
    def post_execute(self, output_data: Stage0Output) -> None:
        """
        Post-execution validation.
        
        Ensure output contains input_descriptor on PASS.
        """
        super().post_execute(output_data)
        
        if output_data.status == StageStatus.COMPLETED:
            if output_data.input_descriptor is None:
                raise ValueError(
                    "Stage 0 PASS must include input_descriptor"
                )

