"""
Stage 0: Input Acquisition
Responsibility: RAW DESIGN SOURCE OF TRUTH - Fast-fail input validation

VERSION: 2.0.0 - Modularized Architecture
- Extracted 8 specialized sub-modules for single-responsibility validation
- Linear pipeline with fail-fast semantics
- Enhanced maintainability and testability

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

from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator

from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput, StageStatus
from weaver.shared.exceptions import InputSchemaError
from weaver.shared.constants import MIN_DPI, MAX_DPI
from weaver.shared.logger import get_logger

# Import sub-module validators
from weaver.stages.stage_0_input_acquisition.pre_decode_guard import (
    validate_pre_decode_resources
)
from weaver.stages.stage_0_input_acquisition.image_decoder import (
    decode_image,
    validate_image_decoded
)
from weaver.stages.stage_0_input_acquisition.format_validator import (
    validate_format_allowlist
)
from weaver.stages.stage_0_input_acquisition.metadata_validator import (
    validate_metadata_consistency
)
from weaver.stages.stage_0_input_acquisition.dimension_validator import (
    validate_dimensions
)
from weaver.stages.stage_0_input_acquisition.repeat_validator import (
    validate_repeat_integrity,
    calculate_tile_counts
)
from weaver.stages.stage_0_input_acquisition.resource_guard import (
    validate_resource_limits
)
from weaver.stages.stage_0_input_acquisition.source_sealer import (
    compute_image_hash,
    create_source_seal
)

logger = get_logger(__name__)


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
        """Validate color mode is unambiguous for manufacturing.
        
        FORBIDDEN MODES:
        - "P" (palette-indexed): Requires palette interpretation, ambiguous for CAM
        - "1" (1-bit): Bit-depth assumptions leak into downstream stages
        
        RATIONALE: Stage 0 establishes source of truth. Only unambiguous color
        representations allowed. Convert P/1 to RGB/L before pipeline entry.
        """
        valid_modes = {"RGB", "RGBA", "L", "LA"}
        if v not in valid_modes:
            forbidden_modes = {"P": "palette-indexed (convert to RGB before pipeline entry)",
                             "1": "1-bit (convert to L or RGB before pipeline entry)"}
            rationale = forbidden_modes.get(v, "not a recognized mode")
            raise InputSchemaError(
                message=f"Color mode '{v}' not allowed: {rationale}",
                stage_number=0,
                details={
                    "color_mode": v,
                    "valid_modes": list(valid_modes),
                    "rationale": "Stage 0 requires unambiguous color representations. Palette-indexed (P) and 1-bit (1) modes create manufacturing ambiguity."
                }
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
    Stage 0: Input Acquisition - v2.0.0 Modularized
    
    RESPONSIBILITY: Establish raw design as immutable source of truth.
    
    ARCHITECTURE: Linear pipeline of 8 specialized validation modules
    1. pre_decode_guard: File size check (OOM protection)
    2. image_decoder: PIL decode and metadata extraction
    3. format_validator: Lossless format allowlist enforcement
    4. metadata_validator: Declared vs actual consistency
    5. dimension_validator: Manufacturing limit checks
    6. repeat_validator: Perfect tiling verification
    7. resource_guard: Post-decode resource protection
    8. source_sealer: SHA-256 hash for immutability proof
    
    Each module is SINGLE-RESPONSIBILITY and FAIL-FAST.
    
    MANUFACTURING RATIONALE:
    - JPEG forbidden: Lossy compression destroys thread-level precision
    - No inference: CAM systems require explicit, validated metadata
    - Perfect tiling: Partial repeats cannot be woven
    - Dimensional limits: Jacquard loom physical constraints
    - Fast-fail: Prevent resource waste on invalid designs
    - OOM protection: Pre-decode guard prevents memory exhaustion
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=0,
            name="Input Acquisition",
            description="RAW DESIGN SOURCE OF TRUTH - Fast-fail input validation",
            version="2.0.0",
            author="Weaver AI Manufacturing Team"
        )
    
    def execute(self, input_data: Stage0Input) -> Stage0Output:
        """
        Execute Stage 0: Input Acquisition (Modularized v2.0).
        
        ARCHITECTURE: Sequential validation with FAIL-FAST semantics.
        Each sub-module validates one aspect. Any failure raises exception immediately.
        
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
        logger.info(f"Starting Stage 0 execution (v2.0): {input_data.pipeline_id}")
        
        # STEP 1: Schema validation (already done by Pydantic)
        logger.debug("Schema validation passed (Pydantic)")
        
        # STEP 2: Pre-decode resource check (OOM protection)
        logger.info("Step 2/8: Pre-decode resource guard")
        pre_decode_result = validate_pre_decode_resources(input_data.image_path)
        
        # STEP 3: Decode image using lossless decoder
        logger.info("Step 3/8: Image decoder")
        image, image_info = decode_image(input_data.image_path)
        validate_image_decoded(image, image_info)
        
        # STEP 4: Enforce format allowlist (LOSSLESS ONLY)
        logger.info("Step 4/8: Format validator")
        format_result = validate_format_allowlist(
            input_data.image_path,
            image_info["format"]
        )
        
        # STEP 5: Metadata consistency validation
        logger.info("Step 5/8: Metadata validator")
        metadata_result = validate_metadata_consistency(
            declared_dpi=input_data.dpi,
            declared_color_mode=input_data.color_mode,
            image=image,
            image_info=image_info
        )
        
        # STEP 6: Dimensional sanity checks
        logger.info("Step 6/8: Dimension validator")
        dimension_result = validate_dimensions(
            image_info["width"],
            image_info["height"]
        )
        
        # STEP 7: Repeat integrity check (perfect tiling)
        logger.info("Step 7/8: Repeat validator")
        repeat_result = validate_repeat_integrity(
            image_width=image_info["width"],
            image_height=image_info["height"],
            repeat_width=input_data.repeat_unit_px.width,
            repeat_height=input_data.repeat_unit_px.height
        )
        
        # STEP 8: Resource protection (post-decode)
        logger.info("Step 8/8: Resource guard")
        resource_result = validate_resource_limits(
            input_data.image_path,
            image_info["width"],
            image_info["height"]
        )
        
        # STEP 9: Source-of-truth sealing (hash computation)
        logger.info("Computing source seal (SHA-256 hash)")
        source_seal = create_source_seal(input_data.image_path)
        raw_hash = source_seal["raw_hash"]
        
        # STEP 10: Emit canonical Input Descriptor
        logger.info("Creating canonical Input Descriptor")
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
                "validation_steps_passed": 10,
                "pixel_count": image_info["width"] * image_info["height"],
                "repeat_units_x": repeat_result["tiles_x"],
                "repeat_units_y": repeat_result["tiles_y"],
                "total_repeat_units": repeat_result["total_tiles"],
            }
        )
        
        logger.info(
            f"Stage 0 completed successfully: {input_data.pipeline_id} - "
            f"{image_info['width']}x{image_info['height']} @ {input_data.dpi}DPI, "
            f"{repeat_result['tiles_x']}x{repeat_result['tiles_y']} tiles"
        )
        
        return Stage0Output(
            stage_number=0,
            status=StageStatus.COMPLETED,
            message="Input acquisition successful - design sealed as source of truth",
            input_descriptor=input_descriptor,
            data={"raw_hash": raw_hash, "source_seal": source_seal},
            metrics=input_descriptor.metrics
        )
    
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
