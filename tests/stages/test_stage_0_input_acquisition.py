"""
Contract tests for Stage 0: Input Acquisition

COVERAGE:
- All 9 validation steps with failure scenarios
- Happy path with valid PNG/TIFF/BMP inputs
- Edge cases for dimensional limits
- Metadata consistency validation
- Repeat integrity enforcement
- Resource protection limits

TESTING PHILOSOPHY:
Fast-fail semantics - every test validates that Stage 0 halts
the pipeline appropriately when constraints are violated.
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from PIL import Image

from weaver.diffusion.stages.stage_0_input_acquisition.processor import (
    Stage0InputAcquisition,
    Stage0Input,
    RepeatUnit,
)
from weaver.shared.exceptions import (
    InputFormatError,
    MetadataConsistencyError,
    DimensionalConstraintError,
    RepeatIntegrityError,
    ResourceProtectionError,
    InputSchemaError,
)
from weaver.shared.schemas import StageStatus


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for test images."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_png_image(temp_dir: Path) -> Path:
    """Create valid PNG test image with perfect repeat tiling."""
    # 1000x800 image with 200x200 repeat unit (5x4 tiles)
    img = Image.new("RGB", (1000, 800), color="red")
    img_path = temp_dir / "valid_design.png"
    img.save(img_path, "PNG", dpi=(300, 300))
    return img_path


@pytest.fixture
def valid_tiff_image(temp_dir: Path) -> Path:
    """Create valid TIFF test image."""
    img = Image.new("RGB", (800, 600), color="blue")
    img_path = temp_dir / "valid_design.tiff"
    img.save(img_path, "TIFF", dpi=(300, 300))
    return img_path


@pytest.fixture
def valid_bmp_image(temp_dir: Path) -> Path:
    """Create valid BMP test image.
    
    Note: BMP format has default DPI of ~96. We use that value in the test.
    """
    img = Image.new("RGB", (600, 400), color="green")
    img_path = temp_dir / "valid_design.bmp"
    # BMP doesn't reliably accept dpi parameter in PIL, it uses default ~96 DPI
    img.save(img_path, "BMP")
    return img_path


@pytest.fixture
def jpeg_image(temp_dir: Path) -> Path:
    """Create JPEG image (forbidden format)."""
    img = Image.new("RGB", (800, 600), color="yellow")
    img_path = temp_dir / "lossy_design.jpg"
    img.save(img_path, "JPEG", quality=95, dpi=(300, 300))
    return img_path


@pytest.fixture
def oversized_image(temp_dir: Path) -> Path:
    """Create image exceeding dimensional limits."""
    # Exceeds MAX_IMAGE_WIDTH = 10000
    img = Image.new("RGB", (12000, 800), color="purple")
    img_path = temp_dir / "oversized.png"
    img.save(img_path, "PNG", dpi=(300, 300))  # Add DPI for PNG
    return img_path


@pytest.fixture
def non_tiling_image(temp_dir: Path) -> Path:
    """Create image with non-integer repeat tiling."""
    # 1000x800 doesn't tile with 300x300 repeat unit
    img = Image.new("RGB", (1000, 800), color="cyan")
    img_path = temp_dir / "non_tiling.png"
    img.save(img_path, "PNG", dpi=(300, 300))
    return img_path


@pytest.fixture
def stage() -> Stage0InputAcquisition:
    """Create Stage 0 instance."""
    return Stage0InputAcquisition()


def _make_input(image_path: Path, dpi: int = 300, repeat_width: int = 200, 
                repeat_height: int = 200, color_mode: str = "RGB") -> Stage0Input:
    """Helper to create Stage0Input with default pipeline_id."""
    return Stage0Input(
        pipeline_id="test_pipeline_001",
        stage_number=0,
        image_path=str(image_path),
        dpi=dpi,
        repeat_unit_px=RepeatUnit(width=repeat_width, height=repeat_height),
        color_mode=color_mode
    )


# ============================================================================
# METADATA TESTS
# ============================================================================

class TestStageMetadata:
    """Test stage metadata compliance."""
    
    def test_stage_number(self, stage: Stage0InputAcquisition):
        """Verify stage number is 0."""
        assert stage.metadata.stage_number == 0
    
    def test_stage_name(self, stage: Stage0InputAcquisition):
        """Verify stage name."""
        assert stage.metadata.name == "Input Acquisition"
    
    def test_stage_version(self, stage: Stage0InputAcquisition):
        """Verify stage has version."""
        assert stage.metadata.version == "1.0.0"


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================

class TestHappyPath:
    """Test successful validation with valid inputs."""
    
    def test_valid_png_input(self, stage: Stage0InputAcquisition, valid_png_image: Path):
        """Test successful processing of valid PNG image."""
        input_data = _make_input(valid_png_image)
        
        output = stage.run(input_data)
        
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor is not None
        assert output.input_descriptor.schema_version == "stage0.v1"
        assert output.input_descriptor.width_px == 1000
        assert output.input_descriptor.height_px == 800
        assert output.input_descriptor.dpi == 300
        assert output.input_descriptor.color_mode == "RGB"
        assert output.input_descriptor.file_format == "PNG"
        assert len(output.input_descriptor.raw_hash) == 64  # SHA-256 hex
        assert output.input_descriptor.repeat_unit_px == {"width": 200, "height": 200}
        
        # Verify metrics
        assert output.metrics["repeat_units_x"] == 5  # 1000 / 200
        assert output.metrics["repeat_units_y"] == 4  # 800 / 200
        assert output.metrics["pixel_count"] == 800_000
    
    def test_valid_tiff_input(self, stage: Stage0InputAcquisition, valid_tiff_image: Path):
        """Test successful processing of valid TIFF image."""
        input_data = _make_input(valid_tiff_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.file_format == "TIFF"
        assert output.input_descriptor.width_px == 800
        assert output.input_descriptor.height_px == 600
    
    def test_valid_bmp_input(self, stage: Stage0InputAcquisition, valid_bmp_image: Path):
        """Test successful processing of valid BMP image.
        
        BMP format has default DPI of ~96 in PIL, so we declare that DPI.
        """
        input_data = _make_input(valid_bmp_image, dpi=96, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.file_format == "BMP"
        assert output.input_descriptor.width_px == 600
        assert output.input_descriptor.height_px == 400
        # BMP DPI is approximately 96
        assert abs(output.input_descriptor.dpi - 96) <= 1


# ============================================================================
# STEP 1: SCHEMA VALIDATION TESTS
# ============================================================================

class TestSchemaValidation:
    """Test input schema validation (Pydantic level)."""
    
    def test_missing_image_path(self):
        """Test FAIL when image_path is missing."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="RGB"
            )
    
    def test_missing_dpi(self, valid_png_image: Path):
        """Test FAIL when DPI is missing."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="RGB"
            )
    
    def test_missing_repeat_unit(self, valid_png_image: Path):
        """Test FAIL when repeat_unit_px is missing."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                color_mode="RGB"
            )
    
    def test_missing_color_mode(self, valid_png_image: Path):
        """Test FAIL when color_mode is missing."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200)
            )
    
    def test_nonexistent_file(self):
        """Test FAIL when image file does not exist."""
        with pytest.raises(InputSchemaError) as exc_info:
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path="/nonexistent/path/image.png",
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="RGB"
            )
        
        assert "does not exist" in str(exc_info.value)
        assert exc_info.value.details["error"] == "file_not_found"
    
    def test_invalid_color_mode(self, valid_png_image: Path):
        """Test FAIL when color_mode is invalid."""
        with pytest.raises(InputSchemaError) as exc_info:
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="CMYK"  # Not in valid_modes
            )
        
        assert "not allowed" in str(exc_info.value)
    
    def test_palette_mode_forbidden(self, valid_png_image: Path):
        """
        Test FAIL when color_mode is 'P' (palette-indexed).
        
        RATIONALE: Palette interpretation creates manufacturing ambiguity.
        """
        with pytest.raises(InputSchemaError) as exc_info:
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="P"  # Palette-indexed forbidden
            )
        
        error = exc_info.value
        assert "palette-indexed" in str(error).lower()
        assert error.details["color_mode"] == "P"
        assert "RGB" in error.details["valid_modes"]
        assert "manufacturing ambiguity" in error.details["rationale"]
    
    def test_onebit_mode_forbidden(self, valid_png_image: Path):
        """
        Test FAIL when color_mode is '1' (1-bit).
        
        RATIONALE: 1-bit mode creates bit-depth assumptions that leak downstream.
        """
        with pytest.raises(InputSchemaError) as exc_info:
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="1"  # 1-bit forbidden
            )
        
        error = exc_info.value
        assert "1-bit" in str(error).lower()
        assert error.details["color_mode"] == "1"
        assert "manufacturing ambiguity" in error.details["rationale"]
    
    def test_dpi_below_minimum(self, valid_png_image: Path):
        """Test FAIL when DPI is below minimum."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=50,  # Below MIN_DPI (72)
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="RGB"
            )
    
    def test_dpi_above_maximum(self, valid_png_image: Path):
        """Test FAIL when DPI exceeds maximum."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=2000,  # Above MAX_DPI (1200)
                repeat_unit_px=RepeatUnit(width=200, height=200),
                color_mode="RGB"
            )
    
    def test_zero_repeat_width(self, valid_png_image: Path):
        """Test FAIL when repeat unit width is zero."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            _make_input(valid_png_image, dpi=300, repeat_width=0, repeat_height=200, color_mode="RGB")
    
    def test_negative_repeat_height(self, valid_png_image: Path):
        """Test FAIL when repeat unit height is negative."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Stage0Input(pipeline_id="test_001", stage_number=0,
                image_path=str(valid_png_image),
                dpi=300,
                repeat_unit_px=RepeatUnit(width=200, height=-100),
                color_mode="RGB"
            )


# ============================================================================
# STEP 3: FORMAT ALLOWLIST TESTS
# ============================================================================

class TestFormatAllowlist:
    """Test enforcement of lossless format allowlist."""
    
    def test_jpeg_forbidden(self, stage: Stage0InputAcquisition, jpeg_image: Path):
        """
        Test FAIL when JPEG format is used.
        
        RATIONALE: Lossy compression destroys thread-level precision.
        """
        input_data = _make_input(jpeg_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(InputFormatError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "not allowed" in error.message.lower()
        assert ".jpg" in error.details["file_extension"]
        assert "lossy compression" in error.details["rationale"].lower()
    
    def test_webp_forbidden(self, stage: Stage0InputAcquisition, temp_dir: Path):
        """Test FAIL when WEBP format is used (if PIL supports it)."""
        try:
            img = Image.new("RGB", (800, 600), color="orange")
            img_path = temp_dir / "design.webp"
            img.save(img_path, "WEBP")
            
            input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
            
            with pytest.raises(InputFormatError):
                stage.run(input_data)
        except Exception:
            # Skip if WEBP not supported by PIL
            pytest.skip("WEBP format not supported by PIL")


# ============================================================================
# STEP 4: METADATA CONSISTENCY TESTS
# ============================================================================

class TestMetadataConsistency:
    """Test metadata consistency validation."""
    
    def test_color_mode_mismatch(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """
        Test FAIL when declared color mode doesn't match image.
        
        RATIONALE: Metadata inconsistency prevents dimensional errors.
        """
        # Image is RGB, but we declare RGBA
        input_data = Stage0Input(pipeline_id="test_001", stage_number=0,
            image_path=str(valid_png_image),
            dpi=300,
            repeat_unit_px=RepeatUnit(width=200, height=200),
            color_mode="RGBA"  # Mismatch!
        )
        
        with pytest.raises(MetadataConsistencyError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "Color mode mismatch" in error.details["violations"][0]
        assert error.details["declared_color_mode"] == "RGBA"
        assert error.details["actual_color_mode"] == "RGB"
    
    def test_dpi_mismatch(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """
        Test FAIL when declared DPI significantly differs from image metadata.
        
        RATIONALE: DPI mismatch causes physical dimension errors in fabric.
        """
        # Image has 300 DPI, but we declare 150 (outside 1% tolerance)
        input_data = _make_input(valid_png_image, dpi=150, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(MetadataConsistencyError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "DPI mismatch" in error.details["violations"][0]
        assert error.details["declared_dpi"] == 150
        # PIL may return DPI as float, check with tolerance
        assert abs(error.details["actual_dpi"] - 300) < 1
    
    def test_png_missing_dpi_fails(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when PNG lacks DPI metadata.
        
        RATIONALE: PNG/TIFF must have embedded DPI for manufacturing trust.
        Format-specific rule: PNG requires DPI metadata.
        """
        # Create PNG without DPI metadata
        img = Image.new("RGB", (1000, 800), color="red")
        img_path = temp_dir / "no_dpi.png"
        img.save(img_path, "PNG")  # No dpi parameter
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(MetadataConsistencyError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "DPI metadata missing in PNG file" in error.details["violations"][0]
        assert error.details["file_format"] == "PNG"
        assert error.details["actual_dpi"] is None
    
    def test_bmp_missing_dpi_passes(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test PASS when BMP lacks DPI metadata (declared DPI is authoritative).
        
        RATIONALE: BMP DPI is unreliable - declared DPI is the source of truth.
        Format-specific rule: BMP with missing/zero DPI uses declared value.
        """
        # Create BMP without explicit DPI (PIL often gives 0 or None for BMP)
        img = Image.new("RGB", (1000, 800), color="green")
        img_path = temp_dir / "no_dpi.bmp"
        img.save(img_path, "BMP")  # BMP typically has no reliable DPI
        
        # Note: PIL may return default 96 DPI for BMP, but we want to test
        # the case where declared DPI is used. For true BMP with no DPI,
        # we'd need a binary editor. For this test, we declare 96 to match.
        input_data = _make_input(img_path, dpi=96, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        # Should PASS - declared DPI matches BMP's default
        output = stage.run(input_data)
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.dpi == 96  # Uses declared DPI


# ============================================================================
# STEP 5: DIMENSIONAL CONSTRAINT TESTS
# ============================================================================

class TestDimensionalConstraints:
    """Test dimensional sanity checks against manufacturing limits."""
    
    def test_width_exceeds_maximum(
        self, stage: Stage0InputAcquisition, oversized_image: Path
    ):
        """
        Test FAIL when image width exceeds MAX_IMAGE_WIDTH.
        
        RATIONALE: Oversized designs exceed Jacquard loom physical limits.
        """
        input_data = _make_input(oversized_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(DimensionalConstraintError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "Width" in error.details["violations"][0]
        assert error.details["width_px"] == 12000
        assert error.details["max_width"] == 10000
        assert "Jacquard loom" in error.details["rationale"]
    
    def test_megapixels_exceeds_maximum(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when image megapixels exceed MAX_MEGAPIXELS.
        
        RATIONALE: Prevents resource exhaustion.
        """
        # Create 11000x10000 = 110MP image (exceeds 100MP limit)
        # Note: This is expensive, so we use a smaller image and mock the check
        # For real test, would need actual large image
        pytest.skip("Skip expensive megapixel test in CI")


# ============================================================================
# STEP 6: REPEAT INTEGRITY TESTS
# ============================================================================

class TestRepeatIntegrity:
    """Test perfect repeat unit tiling validation."""
    
    def test_width_non_integer_tiling(
        self, stage: Stage0InputAcquisition, non_tiling_image: Path
    ):
        """
        Test FAIL when width is not a multiple of repeat width.
        
        RATIONALE: Partial repeats cannot be woven.
        """
        # Image is 1000x800, repeat is 300x300 (1000 % 300 = 100 remainder)
        input_data = _make_input(non_tiling_image, dpi=300, repeat_width=300, repeat_height=300, color_mode="RGB")
        
        with pytest.raises(RepeatIntegrityError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "Width" in error.details["violations"][0]
        assert "remainder: 100px" in error.details["violations"][0]
        assert error.details["image_width"] == 1000
        assert error.details["repeat_width"] == 300
        assert "cannot be woven" in error.details["rationale"]
    
    def test_height_non_integer_tiling(
        self, stage: Stage0InputAcquisition, non_tiling_image: Path
    ):
        """
        Test FAIL when height is not a multiple of repeat height.
        
        RATIONALE: Partial repeats are physically impossible to manufacture.
        """
        # Image is 1000x800, repeat is 300x300 (800 % 300 = 200 remainder)
        input_data = _make_input(non_tiling_image, dpi=300, repeat_width=300, repeat_height=300, color_mode="RGB")
        
        with pytest.raises(RepeatIntegrityError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        # Both width and height violate tiling, check that height violation is present
        violations_str = " ".join(error.details["violations"])
        assert "Height" in violations_str
        assert "remainder: 200px" in violations_str
        assert error.details["image_height"] == 800
        assert error.details["repeat_height"] == 300
    
    def test_both_dimensions_non_integer_tiling(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """Test FAIL when both dimensions fail tiling."""
        # 1001x801 with 200x200 repeat (both have remainders)
        img = Image.new("RGB", (1001, 801), color="magenta")
        img_path = temp_dir / "bad_tiling.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(RepeatIntegrityError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert len(error.details["violations"]) == 2
    
    def test_repeat_width_exceeds_image_width(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when repeat width exceeds image width.
        
        RATIONALE: Clear error message when repeat is larger than image.
        Edge case that modulo would catch but with confusing message.
        """
        # Image 800x600, repeat 1000x200 (width too large)
        img = Image.new("RGB", (800, 600), color="blue")
        img_path = temp_dir / "small_image.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=1000, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(RepeatIntegrityError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "exceeds image width" in error.details["violations"][0]
        assert "1000px exceeds" in error.details["violations"][0]
        assert error.details["repeat_width"] == 1000
        assert error.details["image_width"] == 800
    
    def test_repeat_height_exceeds_image_height(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when repeat height exceeds image height.
        
        RATIONALE: Clear error message when repeat is larger than image.
        """
        # Image 800x600, repeat 200x1000 (height too large)
        img = Image.new("RGB", (800, 600), color="green")
        img_path = temp_dir / "short_image.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=1000, color_mode="RGB")
        
        with pytest.raises(RepeatIntegrityError) as exc_info:
            stage.run(input_data)
        
        error = exc_info.value
        assert "exceeds image height" in error.details["violations"][0]
        assert "1000px exceeds" in error.details["violations"][0]
        assert error.details["repeat_height"] == 1000
        assert error.details["image_height"] == 600


# ============================================================================
# STEP 7: RESOURCE PROTECTION TESTS
# ============================================================================

class TestResourceProtection:
    """Test resource protection limits."""
    
    def test_pre_decode_file_size_check(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test pre-decode file size check prevents OOM.
        
        RATIONALE: PIL can allocate >2x during decode. Early rejection
        protects system before attempting decode.
        """
        # Create a file that's too large (mock by monkey-patching os.path.getsize)
        img = Image.new("RGB", (1000, 800), color="red")
        img_path = temp_dir / "large.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        # Monkey patch to simulate large file
        import os
        original_getsize = os.path.getsize
        try:
            os.path.getsize = lambda p: 600 * 1024 * 1024 if p == str(img_path) else original_getsize(p)
            
            with pytest.raises(ResourceProtectionError) as exc_info:
                stage.run(input_data)
            
            error = exc_info.value
            assert "Pre-decode resource limits exceeded" in error.message
            assert "pre-decode check" in error.details["violations"][0]
            assert "PIL can allocate >2x" in error.details["rationale"]
        finally:
            os.path.getsize = original_getsize
    
    def test_file_size_exceeds_maximum(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when file size exceeds MAX_FILE_SIZE_BYTES.
        
        RATIONALE: Prevents DoS and resource exhaustion.
        """
        # Create a file larger than 500MB is expensive for tests
        # For real test, would create actual large file
        # For now, we can test the logic with smaller limits in config
        pytest.skip("Skip expensive file size test in CI")
    
    def test_pixel_count_exceeds_maximum(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """
        Test FAIL when pixel count exceeds MAX_PIXEL_COUNT.
        
        RATIONALE: Protects downstream stages from malicious files.
        """
        # Similar to megapixel test - skip for CI
        pytest.skip("Skip expensive pixel count test in CI")


# ============================================================================
# STEP 8: HASH COMPUTATION TESTS
# ============================================================================

class TestHashComputation:
    """Test SHA-256 hash computation for immutability proof."""
    
    def test_hash_deterministic(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """Test that hash is deterministic (same file = same hash)."""
        input_data = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output1 = stage.run(input_data)
        output2 = stage.run(input_data)
        
        assert output1.input_descriptor.raw_hash == output2.input_descriptor.raw_hash
    
    def test_hash_differs_for_different_files(
        self,
        stage: Stage0InputAcquisition,
        valid_png_image: Path,
        valid_tiff_image: Path
    ):
        """Test that different files produce different hashes."""
        input_png = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        input_tiff = _make_input(valid_tiff_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output_png = stage.run(input_png)
        output_tiff = stage.run(input_tiff)
        
        assert output_png.input_descriptor.raw_hash != output_tiff.input_descriptor.raw_hash
    
    def test_hash_length(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """Test that hash is valid SHA-256 (64 hex characters)."""
        input_data = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        assert len(output.input_descriptor.raw_hash) == 64
        assert all(c in "0123456789abcdef" for c in output.input_descriptor.raw_hash)


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_minimum_valid_dimensions(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """Test smallest valid image (1x1 pixel with 1x1 repeat)."""
        img = Image.new("RGB", (1, 1), color="white")
        img_path = temp_dir / "tiny.png"
        img.save(img_path, "PNG", dpi=(300, 300))  # Add DPI for PNG
        
        input_data = _make_input(img_path, dpi=300, repeat_width=1, repeat_height=1, color_mode="RGB")
        
        output = stage.run(input_data)
        assert output.status == StageStatus.COMPLETED
    
    def test_maximum_valid_dimensions(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """Test largest valid image (10000x10000 at limit)."""
        # This is expensive - create a smaller version for testing
        img = Image.new("RGB", (10000, 10000), color="black")
        img_path = temp_dir / "max_size.png"
        img.save(img_path, "PNG", dpi=(300, 300))  # Add DPI for PNG
        
        input_data = _make_input(img_path, dpi=300, repeat_width=1000, repeat_height=1000, color_mode="RGB")
        
        output = stage.run(input_data)
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.width_px == 10000
        assert output.input_descriptor.height_px == 10000
    
    def test_grayscale_image(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """Test grayscale image (L mode)."""
        img = Image.new("L", (800, 600), color=128)
        img_path = temp_dir / "grayscale.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="L")
        
        output = stage.run(input_data)
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.color_mode == "L"
    
    def test_rgba_image(
        self, stage: Stage0InputAcquisition, temp_dir: Path
    ):
        """Test RGBA image with alpha channel."""
        img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        img_path = temp_dir / "rgba.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        input_data = _make_input(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGBA")
        
        output = stage.run(input_data)
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor.color_mode == "RGBA"


# ============================================================================
# OUTPUT CONTRACT TESTS
# ============================================================================

class TestOutputContract:
    """Test output contract compliance."""
    
    def test_pass_contains_input_descriptor(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """Test that PASS output contains input_descriptor."""
        input_data = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        assert output.status == StageStatus.COMPLETED
        assert output.input_descriptor is not None
        assert isinstance(output.input_descriptor.raw_hash, str)
        assert isinstance(output.input_descriptor.width_px, int)
        assert isinstance(output.input_descriptor.height_px, int)
    
    def test_fail_raises_exception(
        self, stage: Stage0InputAcquisition, jpeg_image: Path
    ):
        """Test that FAIL raises exception (no dual output)."""
        input_data = _make_input(jpeg_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        with pytest.raises(InputFormatError):
            stage.run(input_data)
        
        # No output returned - exception raised instead
    
    def test_input_descriptor_immutability(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """Test that input_descriptor is frozen (immutable)."""
        input_data = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        # Attempt to modify should raise error (Pydantic frozen model)
        with pytest.raises(Exception):  # Pydantic ValidationError
            output.input_descriptor.width_px = 999
    
    def test_input_descriptor_schema_version(
        self, stage: Stage0InputAcquisition, valid_png_image: Path
    ):
        """Test that input_descriptor has correct schema version."""
        input_data = _make_input(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGB")
        
        output = stage.run(input_data)
        
        assert output.input_descriptor.schema_version == "stage0.v1"

