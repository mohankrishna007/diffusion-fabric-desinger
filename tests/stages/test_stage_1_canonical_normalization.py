"""
Comprehensive Unit Tests for Stage 1: Canonical Normalization

Tests all 9 normalization steps and canonical raster invariants:
1. Orientation normalization (EXIF handling)
2. Color space conversion (RGB/RGBA/LA/L/P/1 → RGB)
3. Alpha channel policies (FLATTEN_WHITE, FLATTEN_BLACK, STRIP)
4. ICC profile stripping
5. DPI canonicalization (rescaling)
6. Bit depth normalization
7. Repeat grid integrity validation
8. Hybrid storage (in-memory vs file-based)
9. Post-execution invariant checks
"""

import pytest
import numpy as np
from PIL import Image, ImageOps
from pathlib import Path
import tempfile
import shutil

from weaver.diffusion.stages.stage_1_canonical_normalization.processor import (
    Stage1CanonicalNormalization,
    Stage1Input,
    Stage1Output,
)
from weaver.diffusion.stages.stage_1_canonical_normalization.orientation_normalizer import (
    normalize_orientation,
)
from weaver.diffusion.stages.stage_1_canonical_normalization.colorspace_normalizer import (
    normalize_color_space,
)
from weaver.diffusion.stages.stage_1_canonical_normalization.dpi_canonicalizer import (
    canonicalize_dpi,
)
from weaver.diffusion.stages.stage_1_canonical_normalization.grid_normalizer import (
    validate_repeat_grid,
)
from weaver.diffusion.stages.stage_1_canonical_normalization.raster_emitter import (
    emit_canonical_raster,
    load_canonical_raster,
)
from weaver.shared.schemas import AlphaPolicy, CanonicalRaster
from weaver.shared.exceptions import CanonicalizationError


@pytest.fixture
def temp_workspace():
    """Create temporary workspace for test files."""
    workspace = Path(tempfile.mkdtemp())
    yield workspace
    shutil.rmtree(workspace)


@pytest.fixture
def sample_rgb_image():
    """Create sample RGB image for testing."""
    # Create 600x600 RGB image (2x2 tiles of 300x300)
    img = Image.new("RGB", (600, 600), color=(128, 128, 128))
    return img


@pytest.fixture
def sample_rgba_image():
    """Create sample RGBA image for testing alpha handling."""
    img = Image.new("RGBA", (600, 600), color=(128, 128, 128, 255))
    # Add semi-transparent region
    for x in range(200, 400):
        for y in range(200, 400):
            img.putpixel((x, y), (255, 0, 0, 128))
    return img


class TestOrientationNormalization:
    """Test EXIF orientation handling."""
    
    def test_no_exif_orientation(self, sample_rgb_image):
        """Test image without EXIF orientation data."""
        img = normalize_orientation(sample_rgb_image)
        assert img.size == sample_rgb_image.size
        assert img.mode == "RGB"
    
    def test_exif_transpose_no_op(self, sample_rgb_image):
        """Test that images without rotation flags are unchanged."""
        original_size = sample_rgb_image.size
        img = normalize_orientation(sample_rgb_image)
        assert img.size == original_size


class TestColorSpaceNormalization:
    """Test color space conversion and ICC stripping."""
    
    def test_rgb_unchanged(self, sample_rgb_image):
        """Test that RGB images pass through unchanged."""
        img, transforms = normalize_color_space(sample_rgb_image, AlphaPolicy.FLATTEN_WHITE)
        assert img.mode == "RGB"
        assert "ICC_profile_stripped" in transforms
    
    def test_rgba_flatten_white(self, sample_rgba_image):
        """Test RGBA to RGB with white background."""
        img, transforms = normalize_color_space(sample_rgba_image, AlphaPolicy.FLATTEN_WHITE)
        assert img.mode == "RGB"
        assert any("RGBA_to_RGB" in t for t in transforms)
        # Check background color (should be white where alpha=0)
        pixel = img.getpixel((0, 0))  # Fully opaque region
        assert pixel == (128, 128, 128)
    
    def test_rgba_flatten_black(self, sample_rgba_image):
        """Test RGBA to RGB with black background."""
        img, transforms = normalize_color_space(sample_rgba_image, AlphaPolicy.FLATTEN_BLACK)
        assert img.mode == "RGB"
        assert any("FLATTEN_BLACK" in t for t in transforms)
    
    def test_rgba_strip_alpha(self, sample_rgba_image):
        """Test RGBA to RGB by stripping alpha."""
        img, transforms = normalize_color_space(sample_rgba_image, AlphaPolicy.STRIP)
        assert img.mode == "RGB"
        assert any("STRIP" in t for t in transforms)
    
    def test_grayscale_to_rgb(self):
        """Test L (grayscale) to RGB conversion."""
        gray_img = Image.new("L", (600, 600), color=128)
        img, transforms = normalize_color_space(gray_img, AlphaPolicy.FLATTEN_WHITE)
        assert img.mode == "RGB"
        assert "L_to_RGB" in transforms
        # Check that grayscale was replicated to all channels
        pixel = img.getpixel((0, 0))
        assert pixel[0] == pixel[1] == pixel[2]
    
    def test_palette_to_rgb(self):
        """Test P (palette) to RGB conversion."""
        palette_img = Image.new("P", (600, 600))
        img, transforms = normalize_color_space(palette_img, AlphaPolicy.FLATTEN_WHITE)
        assert img.mode == "RGB"
        assert "P_to_RGB" in transforms
    
    def test_binary_to_rgb(self):
        """Test 1-bit to RGB conversion."""
        binary_img = Image.new("1", (600, 600), color=1)
        img, transforms = normalize_color_space(binary_img, AlphaPolicy.FLATTEN_WHITE)
        assert img.mode == "RGB"
        assert "1_to_RGB" in transforms
    
    def test_icc_profile_stripped(self, sample_rgb_image):
        """Test that ICC profiles are removed."""
        # Add fake ICC profile
        sample_rgb_image.info["icc_profile"] = b"fake_icc_data"
        img, transforms = normalize_color_space(sample_rgb_image, AlphaPolicy.FLATTEN_WHITE)
        assert "icc_profile" not in img.info
        assert "ICC_profile_stripped" in transforms


class TestDPICanonicalization:
    """Test DPI rescaling logic."""
    
    def test_no_rescale_same_dpi(self, sample_rgb_image):
        """Test that same DPI doesn't rescale."""
        img, metadata = canonicalize_dpi(
            img=sample_rgb_image,
            input_dpi=300,
            canonical_dpi=300,
            repeat_width_px=300,
            repeat_height_px=300,
            resampling_method="LANCZOS"
        )
        assert metadata["rescaled"] is False
        assert metadata["scale_factor"] == 1.0
        assert img.size == sample_rgb_image.size
    
    def test_upscale_dpi(self, sample_rgb_image):
        """Test upscaling from 150 to 300 DPI."""
        img, metadata = canonicalize_dpi(
            img=sample_rgb_image,
            input_dpi=150,
            canonical_dpi=300,
            repeat_width_px=300,
            repeat_height_px=300,
            resampling_method="LANCZOS"
        )
        assert metadata["rescaled"] is True
        assert metadata["scale_factor"] == 2.0
        assert img.width == 1200  # 600 * 2
        assert img.height == 1200
    
    def test_downscale_dpi(self):
        """Test downscaling from 600 to 300 DPI."""
        # Create 1200x1200 image at 600 DPI (2x2 tiles of 600x600)
        large_img = Image.new("RGB", (1200, 1200), color=(128, 128, 128))
        img, metadata = canonicalize_dpi(
            img=large_img,
            input_dpi=600,
            canonical_dpi=300,
            repeat_width_px=600,
            repeat_height_px=600,
            resampling_method="LANCZOS"
        )
        assert metadata["rescaled"] is True
        assert metadata["scale_factor"] == 0.5
        assert img.width == 600  # 1200 * 0.5
        assert img.height == 600
    
    def test_repeat_grid_maintained(self, sample_rgb_image):
        """Test that repeat grid remains aligned after rescaling."""
        img, metadata = canonicalize_dpi(
            img=sample_rgb_image,
            input_dpi=150,
            canonical_dpi=300,
            repeat_width_px=300,
            repeat_height_px=300,
            resampling_method="LANCZOS"
        )
        new_repeat_w, new_repeat_h = metadata["canonical_repeat"]
        assert img.width % new_repeat_w == 0
        assert img.height % new_repeat_h == 0
    
    def test_repeat_grid_violation_raises_error(self):
        """Test that repeat grid violations raise CanonicalizationError."""
        # Create image that won't tile perfectly after rescaling
        img = Image.new("RGB", (601, 601), color=(128, 128, 128))
        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_dpi(
                img=img,
                input_dpi=300,
                canonical_dpi=150,
                repeat_width_px=300,
                repeat_height_px=300,
                resampling_method="LANCZOS"
            )
        assert "repeat grid alignment" in str(exc_info.value).lower()


class TestGridNormalization:
    """Test repeat grid validation."""
    
    def test_valid_repeat_grid(self, sample_rgb_image):
        """Test valid repeat grid passes validation."""
        # 600x600 image, 300x300 repeat = 2x2 tiles
        validate_repeat_grid(sample_rgb_image, 300, 300)  # Should not raise
    
    def test_invalid_width_raises_error(self, sample_rgb_image):
        """Test that non-divisible width raises error."""
        with pytest.raises(CanonicalizationError) as exc_info:
            validate_repeat_grid(sample_rgb_image, 400, 300)  # 600 % 400 != 0
        assert "width not divisible" in str(exc_info.value).lower()
    
    def test_invalid_height_raises_error(self, sample_rgb_image):
        """Test that non-divisible height raises error."""
        with pytest.raises(CanonicalizationError) as exc_info:
            validate_repeat_grid(sample_rgb_image, 300, 400)  # 600 % 400 != 0
        assert "height not divisible" in str(exc_info.value).lower()


class TestHybridStorage:
    """Test in-memory vs file-based storage."""
    
    def test_small_image_in_memory(self, temp_workspace, sample_rgb_image):
        """Test that small images are stored both in-memory AND as file."""
        # 600x600x3 = ~1MB < 50MB threshold
        raster = emit_canonical_raster(
            img=sample_rgb_image,
            pipeline_id="test-pipeline",
            storage_dir=temp_workspace,
            dpi=300,
            repeat_unit_px={"width": 300, "height": 300},
            memory_threshold_mb=50
        )
        # Small images have BOTH for performance
        assert raster.pixel_array is not None
        assert raster.pixel_array_path is not None
        assert raster.pixel_array.shape == (600, 600, 3)
        assert raster.pixel_array.dtype == np.uint8
        # File also exists
        assert Path(raster.pixel_array_path).exists()
    
    def test_large_image_file_based(self, temp_workspace):
        """Test that large images are saved to file only (no in-memory copy)."""
        # Create large image > 50MB
        large_img = Image.new("RGB", (5000, 5000), color=(128, 128, 128))
        raster = emit_canonical_raster(
            img=large_img,
            pipeline_id="test-pipeline",
            storage_dir=temp_workspace,
            dpi=300,
            repeat_unit_px={"width": 1000, "height": 1000},
            memory_threshold_mb=50
        )
        # Large images: file only (no in-memory to save RAM)
        assert raster.pixel_array is None
        assert raster.pixel_array_path is not None
        assert Path(raster.pixel_array_path).exists()
        
        # Test loading from file
        loaded_array = load_canonical_raster(raster)
        assert loaded_array.shape == (5000, 5000, 3)
        assert loaded_array.dtype == np.uint8
    
    def test_hybrid_threshold_boundary(self, temp_workspace):
        """Test threshold boundary behavior."""
        # Create image right at threshold (~50MB)
        # 50MB / 3 bytes per pixel ≈ 4082x4082 pixels
        boundary_img = Image.new("RGB", (4082, 4082), color=(128, 128, 128))
        raster = emit_canonical_raster(
            img=boundary_img,
            pipeline_id="test-pipeline",
            storage_dir=temp_workspace,
            dpi=300,
            repeat_unit_px={"width": 1000, "height": 1000},
            memory_threshold_mb=50
        )
        # At boundary: file only (above threshold)
        assert raster.pixel_array is None
        assert raster.pixel_array_path is not None


class TestEndToEndPipeline:
    """Test complete Stage 1 pipeline."""
    
    def test_rgb_image_normalization(self, temp_workspace, sample_rgb_image):
        """Test end-to-end normalization of RGB image."""
        # Save sample image
        image_path = temp_workspace / "test_image.png"
        sample_rgb_image.save(image_path)
        
        # Create Stage 1 input
        stage1_input = Stage1Input(
            pipeline_id="test-pipeline",
            stage_number=1,
            image_path=str(image_path),
            width_px=600,
            height_px=600,
            dpi=300,
            repeat_unit_px={"width": 300, "height": 300},
            color_mode="RGB",
            bit_depth=8,
            raw_hash="test_hash"
        )
        
        # Execute Stage 1
        processor = Stage1CanonicalNormalization()
        output = processor.run(stage1_input)
        
        # Validate output
        assert output.status.value == "completed"
        assert output.canonical_raster.color_mode == "RGB"
        assert output.canonical_raster.bit_depth == 8
        assert output.canonical_raster.dpi == 300
        assert output.canonical_raster.width_px == 600
        assert output.canonical_raster.height_px == 600
    
    def test_rgba_image_normalization(self, temp_workspace, sample_rgba_image):
        """Test end-to-end normalization of RGBA image with alpha."""
        # Save sample image
        image_path = temp_workspace / "test_rgba.png"
        sample_rgba_image.save(image_path)
        
        # Create Stage 1 input
        stage1_input = Stage1Input(
            pipeline_id="test-pipeline",
            stage_number=1,
            image_path=str(image_path),
            width_px=600,
            height_px=600,
            dpi=300,
            repeat_unit_px={"width": 300, "height": 300},
            color_mode="RGBA",
            bit_depth=8,
            raw_hash="test_hash"
        )
        
        # Execute Stage 1
        processor = Stage1CanonicalNormalization()
        output = processor.run(stage1_input)
        
        # Validate output
        assert output.status.value == "completed"
        assert output.canonical_raster.color_mode == "RGB"  # Converted from RGBA
        assert "RGBA_to_RGB" in str(output.transformations_applied)
    
    def test_dpi_rescaling_integration(self, temp_workspace, sample_rgb_image):
        """Test end-to-end DPI rescaling."""
        # Save sample image
        image_path = temp_workspace / "test_150dpi.png"
        sample_rgb_image.save(image_path, dpi=(150, 150))
        
        # Create Stage 1 input at 150 DPI
        stage1_input = Stage1Input(
            pipeline_id="test-pipeline",
            stage_number=1,
            image_path=str(image_path),
            width_px=600,
            height_px=600,
            dpi=150,
            repeat_unit_px={"width": 300, "height": 300},
            color_mode="RGB",
            bit_depth=8,
            raw_hash="test_hash"
        )
        
        # Execute Stage 1 (should rescale to 300 DPI)
        processor = Stage1CanonicalNormalization()
        output = processor.run(stage1_input)
        
        # Validate output
        assert output.canonical_raster.dpi == 300
        assert output.canonical_raster.width_px == 1200  # Doubled
        assert output.canonical_raster.height_px == 1200
        assert output.metrics["dpi_scale_factor"] == 2.0
        assert "DPI_rescaled" in str(output.transformations_applied)


class TestInvariantValidation:
    """Test post-execution invariant checks."""
    
    def test_color_mode_invariant(self, temp_workspace):
        """Test that non-RGB color mode fails validation."""
        # This should never happen in practice, but test validation logic
        raster = CanonicalRaster(
            schema_version="stage1.v1",
            width_px=600,
            height_px=600,
            dpi=300,
            color_mode="L",  # Invalid - not RGB
            bit_depth=8,
            pixel_array=np.zeros((600, 600, 3), dtype=np.uint8),
            pixel_array_path=str(temp_workspace / "test.npy"),
            repeat_unit_px={"width": 300, "height": 300}
        )
        
        from weaver.diffusion.stages.stage_1_canonical_normalization.raster_emitter import validate_canonical_raster
        with pytest.raises(CanonicalizationError) as exc_info:
            validate_canonical_raster(raster)
        assert "color mode" in str(exc_info.value).lower()
    
    def test_bit_depth_invariant(self, temp_workspace):
        """Test that non-8-bit depth fails validation."""
        raster = CanonicalRaster(
            schema_version="stage1.v1",
            width_px=600,
            height_px=600,
            dpi=300,
            color_mode="RGB",
            bit_depth=16,  # Invalid - not 8
            pixel_array=np.zeros((600, 600, 3), dtype=np.uint8),
            pixel_array_path=str(temp_workspace / "test.npy"),
            repeat_unit_px={"width": 300, "height": 300}
        )
        
        from weaver.diffusion.stages.stage_1_canonical_normalization.raster_emitter import validate_canonical_raster
        with pytest.raises(CanonicalizationError) as exc_info:
            validate_canonical_raster(raster)
        assert "bit depth" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
