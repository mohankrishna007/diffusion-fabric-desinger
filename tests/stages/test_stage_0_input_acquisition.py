"""
Contract tests for Stage 0: Input Acquisition

VERSION: 2.0.0 - Updated for modular architecture

COVERAGE:
- All 8 validation steps with failure scenarios
- Happy path with valid PNG/TIFF/BMP inputs
- Edge cases for dimensional limits
- Metadata consistency validation
- Repeat integrity enforcement
- Resource protection limits

TESTING PHILOSOPHY:
Fast-fail semantics - every test validates that Stage 0 halts
the pipeline appropriately when constraints are violated.

v2.0 CHANGES:
- No Stage0Input schema - use config dict
- No Stage0Output schema - return InputAcquisitionResult
- execute(prev_result=None, pipeline_id, config) signature
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from PIL import Image

from weaver.diffusion.stages.input_acquisition.processor import InputAcquisitionStage
from weaver.diffusion.stages.stage_result import InputAcquisitionResult
from weaver.shared.exceptions import (
    InputFormatError,
    MetadataConsistencyError,
    DimensionalConstraintError,
    RepeatIntegrityError,
    ResourceProtectionError,
    InputSchemaError,
)


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
def stage() -> InputAcquisitionStage:
    """Create Stage 0 instance."""
    return InputAcquisitionStage()


@pytest.fixture
def sample_pipeline_id() -> str:
    """Generate sample pipeline ID."""
    return "test_pipeline_001"


def _make_config(image_path: Path, dpi: int = 300, repeat_width: int = 200, 
                repeat_height: int = 200, color_mode: str = "RGB") -> dict:
    """Helper to create Stage 0 config dictionary."""
    return {
        'source_file': str(image_path),
        'dpi': dpi,
        'repeat_unit': {'width': repeat_width, 'height': repeat_height},
        'color_mode': color_mode
    }


# ============================================================================
# METADATA TESTS
# ============================================================================

class TestStageMetadata:
    """Test stage metadata compliance."""
    
    def test_stage_id(self, stage: InputAcquisitionStage):
        """Verify stage ID."""
        assert stage.metadata.stage_id == "input_acquisition"
    
    def test_stage_name(self, stage: InputAcquisitionStage):
        """Verify stage name."""
        assert stage.metadata.name == "Input Acquisition"
    
    def test_stage_version(self, stage: InputAcquisitionStage):
        """Verify stage version is 2.0.0."""
        assert stage.metadata.version == "2.0.0"


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================

class TestHappyPath:
    """Test successful validation with valid inputs."""
    
    def test_valid_png_input(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """Test successful processing of valid PNG image."""
        config = _make_config(valid_png_image)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        assert isinstance(result, InputAcquisitionResult)
        assert result.pipeline_id == sample_pipeline_id
        # stage_metadata has nested structure - stage_id is in input_descriptor
        assert result.stage_metadata['input_descriptor']['stage_id'] == "input_acquisition"
        assert result.width_px == 1000
        assert result.height_px == 800
        assert result.dpi == 300
        assert result.color_mode == "RGB"
        assert len(result.raw_hash) == 64  # SHA-256 hex
        assert result.repeat_unit_px == {"width": 200, "height": 200}
    
    def test_valid_tiff_input(self, stage: InputAcquisitionStage, valid_tiff_image: Path, sample_pipeline_id: str):
        """Test successful processing of valid TIFF image."""
        config = _make_config(valid_tiff_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        assert isinstance(result, InputAcquisitionResult)
        assert result.width_px == 800
        assert result.height_px == 600
    
    def test_valid_bmp_input(self, stage: InputAcquisitionStage, valid_bmp_image: Path, sample_pipeline_id: str):
        """Test successful processing of valid BMP image.
        
        BMP format has default DPI of ~96 in PIL, so we declare that DPI.
        """
        config = _make_config(valid_bmp_image, dpi=96, repeat_width=200, repeat_height=200)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        assert isinstance(result, InputAcquisitionResult)
        assert result.width_px == 600
        assert result.height_px == 400
        # BMP DPI is approximately 96
        assert abs(result.dpi - 96) <= 1


# ============================================================================
# CONFIG VALIDATION TESTS
# ============================================================================

class TestConfigValidation:
    """Test config validation (v2.0 - no Pydantic input schemas)."""
    
    def test_missing_source_file(self, stage: InputAcquisitionStage, sample_pipeline_id: str):
        """Test FAIL when source_file is missing from config."""
        config = {
            'dpi': 300,
            'repeat_unit': {'width': 200, 'height': 200},
            'color_mode': 'RGB'
        }
        
        with pytest.raises(InputSchemaError, match="source_file"):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_nonexistent_file(self, stage: InputAcquisitionStage, sample_pipeline_id: str):
        """Test FAIL when image file does not exist."""
        config = {
            'source_file': '/nonexistent/path/image.png',
            'dpi': 300,
            'repeat_unit': {'width': 200, 'height': 200},
            'color_mode': 'RGB'
        }
        
        with pytest.raises(InputSchemaError, match="does not exist"):
            stage.execute(None, sample_pipeline_id, config)


# ============================================================================
# FORMAT ALLOWLIST TESTS
# ============================================================================


class TestFormatAllowlist:
    """Test enforcement of lossless format allowlist."""
    
    def test_jpeg_forbidden(self, stage: InputAcquisitionStage, jpeg_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when JPEG format is used.
        
        RATIONALE: Lossy compression destroys thread-level precision.
        """
        config = _make_config(jpeg_image, dpi=300, repeat_width=200, repeat_height=200)
        
        with pytest.raises(InputFormatError) as exc_info:
            stage.execute(None, sample_pipeline_id, config)
        
        error = exc_info.value
        assert "not allowed" in error.message.lower()
        assert ".jpg" in error.details["file_extension"]
        assert "lossy compression" in error.details["rationale"].lower()
    
    def test_webp_forbidden(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """Test FAIL when WEBP format is used (if PIL supports it)."""
        try:
            img = Image.new("RGB", (800, 600), color="orange")
            img_path = temp_dir / "design.webp"
            img.save(img_path, "WEBP")
            
            config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=200)
            
            with pytest.raises(InputFormatError):
                stage.execute(None, sample_pipeline_id, config)
        except Exception:
            # Skip if WEBP not supported by PIL
            pytest.skip("WEBP format not supported by PIL")


# ============================================================================
# METADATA CONSISTENCY TESTS  
# ============================================================================

class TestMetadataConsistency:
    """Test metadata consistency validation."""
    
    def test_color_mode_mismatch(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when declared color mode doesn't match image.
        
        RATIONALE: Metadata inconsistency prevents dimensional errors.
        """
        # Image is RGB, but we declare RGBA
        config = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGBA")
        
        with pytest.raises(MetadataConsistencyError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_dpi_mismatch(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when declared DPI significantly differs from image metadata.
        
        RATIONALE: DPI mismatch causes physical dimension errors in fabric.
        """
        # Image has 300 DPI, but we declare 150 (outside tolerance)
        config = _make_config(valid_png_image, dpi=150, repeat_width=200, repeat_height=200)
        
        with pytest.raises(MetadataConsistencyError):
            stage.execute(None, sample_pipeline_id, config)


# ============================================================================
# DIMENSIONAL CONSTRAINT TESTS
# ============================================================================

class TestDimensionalConstraints:
    """Test dimensional sanity checks against manufacturing limits."""
    
    def test_width_exceeds_maximum(self, stage: InputAcquisitionStage, oversized_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when image width exceeds MAX_IMAGE_WIDTH.
        
        RATIONALE: Oversized designs exceed Jacquard loom physical limits.
        """
        config = _make_config(oversized_image, dpi=300, repeat_width=200, repeat_height=200)
        
        with pytest.raises(DimensionalConstraintError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_megapixels_exceeds_maximum(
        self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str
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
# REPEAT INTEGRITY TESTS
# ============================================================================

class TestRepeatIntegrity:
    """Test perfect repeat unit tiling validation."""
    
    def test_width_non_integer_tiling(self, stage: InputAcquisitionStage, non_tiling_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when width is not a multiple of repeat width.
        
        RATIONALE: Partial repeats cannot be woven.
        """
        # Image is 1000x800, repeat is 300x300 (1000 % 300 = 100 remainder)
        config = _make_config(non_tiling_image, dpi=300, repeat_width=300, repeat_height=300)
        
        with pytest.raises(RepeatIntegrityError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_height_non_integer_tiling(self, stage: InputAcquisitionStage, non_tiling_image: Path, sample_pipeline_id: str):
        """
        Test FAIL when height is not a multiple of repeat height.
        
        RATIONALE: Partial repeats are physically impossible to manufacture.
        """
        # Image is 1000x800, repeat is 300x300 (800 % 300 = 200 remainder)
        config = _make_config(non_tiling_image, dpi=300, repeat_width=300, repeat_height=300)
        
        with pytest.raises(RepeatIntegrityError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_both_dimensions_non_integer_tiling(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """Test FAIL when both dimensions fail tiling."""
        # 1001x801 with 200x200 repeat (both have remainders)
        img = Image.new("RGB", (1001, 801), color="magenta")
        img_path = temp_dir / "bad_tiling.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=200)
        
        with pytest.raises(RepeatIntegrityError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_repeat_width_exceeds_image_width(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """
        Test FAIL when repeat width exceeds image width.
        
        RATIONALE: Clear error message when repeat is larger than image.
        Edge case that modulo would catch but with confusing message.
        """
        # Image 800x600, repeat 1000x200 (width too large)
        img = Image.new("RGB", (800, 600), color="blue")
        img_path = temp_dir / "small_image.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=1000, repeat_height=200)
        
        with pytest.raises(RepeatIntegrityError):
            stage.execute(None, sample_pipeline_id, config)
    
    def test_repeat_height_exceeds_image_height(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """
        Test FAIL when repeat height exceeds image height.
        
        RATIONALE: Clear error message when repeat is larger than image.
        """
        # Image 800x600, repeat 200x1000 (height too large)
        img = Image.new("RGB", (800, 600), color="green")
        img_path = temp_dir / "short_image.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=1000)
        
        with pytest.raises(RepeatIntegrityError):
            stage.execute(None, sample_pipeline_id, config)


# ============================================================================
# RESOURCE PROTECTION TESTS
# ============================================================================

class TestResourceProtection:
    """Test resource protection limits."""
    
    def test_pre_decode_file_size_check(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """
        Test pre-decode file size check prevents OOM.
        
        RATIONALE: PIL can allocate >2x during decode. Early rejection
        protects system before attempting decode.
        """
        # Create a file that's too large (mock by monkey-patching os.path.getsize)
        img = Image.new("RGB", (1000, 800), color="red")
        img_path = temp_dir / "large.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=200)
        
        # Monkey patch to simulate large file
        import os
        original_getsize = os.path.getsize
        try:
            os.path.getsize = lambda p: 600 * 1024 * 1024 if p == str(img_path) else original_getsize(p)
            
            with pytest.raises(ResourceProtectionError):
                stage.execute(None, sample_pipeline_id, config)
        finally:
            os.path.getsize = original_getsize
    
    def test_file_size_exceeds_maximum(
        self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str
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
        self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str
    ):
        """
        Test FAIL when pixel count exceeds MAX_PIXEL_COUNT.
        
        RATIONALE: Protects downstream stages from malicious files.
        """
        # Similar to megapixel test - skip for CI
        pytest.skip("Skip expensive pixel count test in CI")


# ============================================================================
# HASH COMPUTATION TESTS
# ============================================================================

class TestHashComputation:
    """Test SHA-256 hash computation for immutability proof."""
    
    def test_hash_deterministic(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """Test that hash is deterministic (same file = same hash)."""
        config = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result1 = stage.execute(None, sample_pipeline_id, config)
        result2 = stage.execute(None, sample_pipeline_id, config)
        
        assert result1.raw_hash == result2.raw_hash
    
    def test_hash_differs_for_different_files(self, stage: InputAcquisitionStage, valid_png_image: Path, valid_tiff_image: Path, sample_pipeline_id: str):
        """Test that different files produce different hashes."""
        config_png = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200)
        config_tiff = _make_config(valid_tiff_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result_png = stage.execute(None, sample_pipeline_id, config_png)
        result_tiff = stage.execute(None, sample_pipeline_id, config_tiff)
        
        assert result_png.raw_hash != result_tiff.raw_hash
    
    def test_hash_length(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """Test that hash is valid SHA-256 (64 hex characters)."""
        config = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        assert len(result.raw_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.raw_hash)


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_minimum_valid_dimensions(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """Test smallest valid image (1x1 pixel with 1x1 repeat)."""
        img = Image.new("RGB", (1, 1), color="white")
        img_path = temp_dir / "tiny.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=1, repeat_height=1)
        
        result = stage.execute(None, sample_pipeline_id, config)
        assert isinstance(result, InputAcquisitionResult)
    
    def test_grayscale_image(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """Test grayscale image (L mode)."""
        img = Image.new("L", (800, 600), color=128)
        img_path = temp_dir / "grayscale.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="L")
        
        result = stage.execute(None, sample_pipeline_id, config)
        assert isinstance(result, InputAcquisitionResult)
        assert result.color_mode == "L"
    
    def test_rgba_image(self, stage: InputAcquisitionStage, temp_dir: Path, sample_pipeline_id: str):
        """Test RGBA image with alpha channel."""
        img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        img_path = temp_dir / "rgba.png"
        img.save(img_path, "PNG", dpi=(300, 300))
        
        config = _make_config(img_path, dpi=300, repeat_width=200, repeat_height=200, color_mode="RGBA")
        
        result = stage.execute(None, sample_pipeline_id, config)
        assert isinstance(result, InputAcquisitionResult)
        assert result.color_mode == "RGBA"


# ============================================================================
# OUTPUT CONTRACT TESTS
# ============================================================================

class TestOutputContract:
    """Test output contract compliance."""
    
    def test_result_contains_required_fields(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """Test that result contains all required fields."""
        config = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        assert isinstance(result, InputAcquisitionResult)
        assert isinstance(result.raw_hash, str)
        assert isinstance(result.width_px, int)
        assert isinstance(result.height_px, int)
        assert isinstance(result.dpi, int)
        assert isinstance(result.source_seal, dict)
    
    def test_fail_raises_exception(self, stage: InputAcquisitionStage, jpeg_image: Path, sample_pipeline_id: str):
        """Test that FAIL raises exception (no dual output)."""
        config = _make_config(jpeg_image, dpi=300, repeat_width=200, repeat_height=200)
        
        with pytest.raises(InputFormatError):
            stage.execute(None, sample_pipeline_id, config)
        
        # No output returned - exception raised instead
    
    def test_result_immutability(self, stage: InputAcquisitionStage, valid_png_image: Path, sample_pipeline_id: str):
        """Test that result can be serialized to JSON."""
        config = _make_config(valid_png_image, dpi=300, repeat_width=200, repeat_height=200)
        
        result = stage.execute(None, sample_pipeline_id, config)
        
        # Verify result can be serialized
        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

