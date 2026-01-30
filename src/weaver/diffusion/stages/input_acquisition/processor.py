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

from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages.stage_result import InputAcquisitionResult, StageResult
from weaver.shared.schemas import StageStatus
from weaver.shared.exceptions import InputSchemaError
from weaver.shared.constants import MIN_DPI, MAX_DPI
from weaver.shared.logger import get_logger

# Import sub-module validators
from weaver.diffusion.stages.input_acquisition.pre_decode_guard import (
    validate_pre_decode_resources
)
from weaver.diffusion.stages.input_acquisition.image_decoder import (
    decode_image,
    validate_image_decoded
)
from weaver.diffusion.stages.input_acquisition.format_validator import (
    validate_format_allowlist
)
from weaver.diffusion.stages.input_acquisition.metadata_validator import (
    validate_metadata_consistency
)
from weaver.diffusion.stages.input_acquisition.dimension_validator import (
    validate_dimensions
)
from weaver.diffusion.stages.input_acquisition.repeat_validator import (
    validate_repeat_integrity,
    calculate_tile_counts
)
from weaver.diffusion.stages.input_acquisition.resource_guard import (
    validate_resource_limits
)
from weaver.diffusion.stages.input_acquisition.source_sealer import (
    compute_image_hash,
    create_source_seal
)

logger = get_logger(__name__)


class RepeatUnit(BaseModel):
    """Repeat unit dimensions in pixels - lightweight value object."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    width: int = Field(..., gt=0, description="Repeat unit width in pixels")
    height: int = Field(..., gt=0, description="Repeat unit height in pixels")


class InputAcquisitionStage(BaseStage):
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
            stage_id="input_acquisition",
            name="Input Acquisition",
            description="RAW DESIGN SOURCE OF TRUTH - Fast-fail input validation",
            version="2.0.0",
        )

    def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
        """Validate config has required fields for stage 0."""
        source_file = config.get('source_file')
        if not source_file:
            raise InputSchemaError(
                message="Config must include 'source_file' path",
                stage_number=0,
                details={"config_keys": list(config.keys())}
            )
        
        if not isinstance(source_file, (str, Path)):
            raise InputSchemaError(
                message="source_file must be a string or Path",
                stage_number=0,
                details={"source_file_type": type(source_file).__name__}
            )
        
        if not Path(source_file).exists():
            raise InputSchemaError(
                message=f"Source file does not exist: {source_file}",
                stage_number=0,
                details={"source_file": str(source_file)}
            )
    
    def _execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> InputAcquisitionResult:
        """
        Execute Stage 0: Input Acquisition (Modularized v2.0).
        
        ARCHITECTURE: Sequential validation with FAIL-FAST semantics.
        Each sub-module validates one aspect. Any failure raises exception immediately.
        
        Args:
            prev_result: None (first stage)
            pipeline_id: Pipeline execution ID
            config: Pipeline configuration with source_file and metadata
        
        Returns:
            InputAcquisitionResult with validated input descriptor
        
        Raises:
            InputFormatError: File format not on lossless allowlist
            MetadataConsistencyError: Declared metadata conflicts with image
            DimensionalConstraintError: Dimensions exceed manufacturing limits
            RepeatIntegrityError: Non-integer tiling detected
            ResourceProtectionError: File size or pixel count exceeds limits
        """
        # Extract input parameters from config (already validated)
        image_path: str = str(config['source_file'])  # Required by validate_input
        dpi: int = config.get('dpi', 300)
        repeat_unit: dict = config.get('repeat_unit', {'width': 100, 'height': 100})
        color_mode: str = config.get('color_mode', 'RGB')
        
        logger.info(f"Starting Stage 0 execution (v2.0): {pipeline_id}")
        
        # Extract repeat dimensions
        repeat_width = repeat_unit.get('width', 100)
        repeat_height = repeat_unit.get('height', 100)
        image_width = 0  # Will be set after decode
        image_height = 0
        
        # STEP 1: Pre-decode resource check
        logger.info("Step 1/8: Pre-decode resource guard")
        pre_decode_result = validate_pre_decode_resources(image_path)
        
        # STEP 2: Decode image
        logger.info("Step 2/8: Image decoder")
        image, image_info = decode_image(image_path)
        validate_image_decoded(image, image_info)
        
        image_width = image_info["width"]
        image_height = image_info["height"]
        
        # STEP 3: Enforce format allowlist
        logger.info("Step 3/8: Format validator")
        format_result = validate_format_allowlist(
            image_path,
            image_info["format"]
        )
        
        # STEP 4: Metadata consistency validation
        logger.info("Step 4/8: Metadata validator")
        metadata_result = validate_metadata_consistency(
            declared_dpi=dpi,
            declared_color_mode=color_mode,
            image=image,
            image_info=image_info
        )
        
        # STEP 5: Dimensional sanity checks
        logger.info("Step 5/8: Dimension validator")
        dimension_result = validate_dimensions(image_width, image_height)
        
        # STEP 6: Repeat integrity check
        logger.info("Step 6/8: Repeat validator")
        repeat_result = validate_repeat_integrity(
            image_width=image_width,
            image_height=image_height,
            repeat_width=repeat_width,
            repeat_height=repeat_height
        )
        
        # STEP 7: Resource protection
        logger.info("Step 7/8: Resource guard")
        resource_result = validate_resource_limits(
            image_path,
            image_width,
            image_height
        )
        
        # STEP 8: Source sealing
        logger.info("Step 8/8: Computing source seal")
        source_seal = create_source_seal(image_path)
        raw_hash = source_seal["raw_hash"]
        
        # Extract commonly used values for logging and metrics
        logger.info("Creating stage result")
        resolved_path = str(Path(image_path).resolve())
        pixel_count = image_width * image_height
        tiles_x = repeat_result["tiles_x"]
        tiles_y = repeat_result["tiles_y"]
        total_tiles = repeat_result["total_tiles"]
        size_str = f"{image_width}x{image_height}"
        tiles_str = f"{tiles_x}x{tiles_y}"
        
        logger.info(
            f"Stage 0 completed successfully: {pipeline_id} - "
            f"{size_str} @ {dpi}DPI, {tiles_str} tiles"
        )
        
        # Build stage metadata (saved by pipeline engine)
        stage_metadata = {
            "stage_number": 0,
            "stage_name": "Input Acquisition",
            "status": "COMPLETED",
            "pipeline_id": pipeline_id,
            "input_descriptor": {
                "stage_id": "input_acquisition",
                "stage_number": 0,
                "status": "COMPLETED",
                "message": "Input validated and sealed as source of truth",
                "schema_version": "stage0.v1",
                "raw_hash": raw_hash,
                "image_path": resolved_path,
                "width_px": image_width,
                "height_px": image_height,
                "dpi": dpi,
                "repeat_unit_px": {"width": repeat_width, "height": repeat_height},
                "color_mode": image_info["mode"],
                "bit_depth": image_info["bit_depth"]
            },
            "source_seal": source_seal,
            "validation_results": {
                "pre_decode_check": pre_decode_result,
                "format_validation": format_result,
                "metadata_validation": metadata_result,
                "dimension_validation": dimension_result,
                "repeat_validation": repeat_result,
                "resource_validation": resource_result
            },
            "metrics": {
                "validation_steps_passed": 8,
                "pixel_count": pixel_count,
                "repeat_units_x": tiles_x,
                "repeat_units_y": tiles_y,
                "total_repeat_units": total_tiles,
                "file_format": image_info["format"],
                "file_size_bytes": image_info["file_size"]
            }
        }
        
        return InputAcquisitionResult(
            pipeline_id=pipeline_id,
            stage_metadata=stage_metadata,
            raw_hash=raw_hash,
            source_seal=source_seal,
            image_path=resolved_path,
            width_px=image_width,
            height_px=image_height,
            dpi=dpi,
            repeat_unit_px={"width": repeat_width, "height": repeat_height},
            color_mode=image_info["mode"],
            bit_depth=image_info["bit_depth"]
        )

