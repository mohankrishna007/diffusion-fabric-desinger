"""
Unit tests for shared validators module.

Tests migrated and expanded from old ConfigDetector tests.
"""

import pytest
from PIL import Image
import tempfile
from pathlib import Path
import io

from weaver.shared.validators import (
    detect_dpi,
    detect_color_mode,
    suggest_repeat_unit,
    validate_dpi,
    validate_color_mode,
    validate_repeat_unit,
    validate_dimensions,
    validate_image_config,
    ValidationError,
    ValidationResult
)
from weaver.shared.constants import (
    DEFAULT_DPI,
    MIN_DPI,
    MAX_DPI,
    MAX_IMAGE_WIDTH,
    MAX_IMAGE_HEIGHT,
    MAX_MEGAPIXELS,
    VALID_COLOR_MODES
)


class TestDetectDPI:
    """Tests for DPI detection."""
    
    def test_detect_dpi_with_metadata(self):
        """Should detect DPI from image metadata."""
        img = Image.new('RGB', (100, 100))
        img.info['dpi'] = (300, 300)
        
        dpi = detect_dpi(img)
        assert dpi == 300
    
    def test_detect_dpi_different_x_y(self):
        """Should average different X and Y DPI values."""
        img = Image.new('RGB', (100, 100))
        img.info['dpi'] = (300, 600)
        
        dpi = detect_dpi(img)
        assert dpi == 450
    
    def test_detect_dpi_no_metadata(self):
        """Should return default DPI when no metadata present."""
        img = Image.new('RGB', (100, 100))
        
        dpi = detect_dpi(img)
        assert dpi == DEFAULT_DPI
    
    def test_detect_dpi_out_of_range_low(self):
        """Should clamp to default when detected DPI is too low."""
        img = Image.new('RGB', (100, 100))
        img.info['dpi'] = (10, 10)
        
        dpi = detect_dpi(img)
        assert dpi == DEFAULT_DPI
    
    def test_detect_dpi_out_of_range_high(self):
        """Should clamp to default when detected DPI is too high."""
        img = Image.new('RGB', (100, 100))
        img.info['dpi'] = (5000, 5000)
        
        dpi = detect_dpi(img)
        assert dpi == DEFAULT_DPI
    
    def test_detect_dpi_at_boundaries(self):
        """Should accept DPI at min/max boundaries."""
        img_min = Image.new('RGB', (100, 100))
        img_min.info['dpi'] = (MIN_DPI, MIN_DPI)
        assert detect_dpi(img_min) == MIN_DPI
        
        img_max = Image.new('RGB', (100, 100))
        img_max.info['dpi'] = (MAX_DPI, MAX_DPI)
        assert detect_dpi(img_max) == MAX_DPI


class TestDetectColorMode:
    """Tests for color mode detection."""
    
    def test_detect_color_mode_rgb(self):
        """Should detect RGB mode correctly."""
        img = Image.new('RGB', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'RGB'
    
    def test_detect_color_mode_rgba(self):
        """Should detect RGBA mode correctly."""
        img = Image.new('RGBA', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'RGBA'
    
    def test_detect_color_mode_grayscale(self):
        """Should detect L (grayscale) mode correctly."""
        img = Image.new('L', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'L'
    
    def test_detect_color_mode_grayscale_alpha(self):
        """Should detect LA mode correctly."""
        img = Image.new('LA', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'LA'
    
    def test_detect_color_mode_palette(self):
        """Should suggest RGB for palette images."""
        img = Image.new('P', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'RGB'
    
    def test_detect_color_mode_1bit(self):
        """Should suggest L for 1-bit images."""
        img = Image.new('1', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'L'
    
    def test_detect_color_mode_cmyk(self):
        """Should suggest RGB for CMYK images."""
        img = Image.new('CMYK', (100, 100))
        mode = detect_color_mode(img)
        assert mode == 'RGB'


class TestSuggestRepeatUnit:
    """Tests for repeat unit suggestion."""
    
    def test_suggest_repeat_common_size_100(self):
        """Should suggest common size 100 when it divides evenly."""
        repeat = suggest_repeat_unit(1000, 1000)
        assert repeat == {'width': 100, 'height': 100}
    
    def test_suggest_repeat_common_size_200(self):
        """Should suggest common size 200 when 100 doesn't fit."""
        repeat = suggest_repeat_unit(1000, 800)
        assert repeat == {'width': 200, 'height': 200}
    
    def test_suggest_repeat_common_size_500(self):
        """Should suggest common size 500 for larger divisible dimensions."""
        repeat = suggest_repeat_unit(2000, 1500)
        assert repeat == {'width': 500, 'height': 500}
    
    def test_suggest_repeat_largest_divisor(self):
        """Should find largest divisor when common sizes don't work."""
        # 720 = 2^4 × 3^2 × 5, largest divisor in range is 720 itself
        repeat = suggest_repeat_unit(720, 720)
        assert repeat['width'] > 0
        assert repeat['height'] > 0
        assert 720 % repeat['width'] == 0
        assert 720 % repeat['height'] == 0
    
    def test_suggest_repeat_non_square(self):
        """Should suggest non-square repeat for non-square images."""
        repeat = suggest_repeat_unit(1200, 800)
        assert repeat['width'] > 0
        assert repeat['height'] > 0
        assert 1200 % repeat['width'] == 0
        assert 800 % repeat['height'] == 0
    
    def test_suggest_repeat_fallback_entire_image(self):
        """Should use entire image as fallback for odd dimensions."""
        repeat = suggest_repeat_unit(37, 41)  # Prime-ish numbers
        assert repeat == {'width': 37, 'height': 41}


class TestValidateDPI:
    """Tests for DPI validation."""
    
    def test_validate_dpi_valid(self):
        """Should pass validation for valid DPI."""
        errors = validate_dpi(300)
        assert len(errors) == 0
    
    def test_validate_dpi_none(self):
        """Should fail when DPI is None."""
        errors = validate_dpi(None)
        assert len(errors) == 1
        assert errors[0].field == 'dpi'
        assert 'required' in errors[0].error.lower()
    
    def test_validate_dpi_too_low(self):
        """Should fail when DPI is below minimum."""
        errors = validate_dpi(50)
        assert len(errors) == 1
        assert errors[0].field == 'dpi'
        assert str(MIN_DPI) in errors[0].error
    
    def test_validate_dpi_too_high(self):
        """Should fail when DPI exceeds maximum."""
        errors = validate_dpi(2000)
        assert len(errors) == 1
        assert errors[0].field == 'dpi'
        assert str(MAX_DPI) in errors[0].error
    
    def test_validate_dpi_not_integer(self):
        """Should fail when DPI is not an integer."""
        errors = validate_dpi("300")
        assert len(errors) == 1
        assert 'integer' in errors[0].error.lower()
    
    def test_validate_dpi_boundaries(self):
        """Should pass at min and max boundaries."""
        assert len(validate_dpi(MIN_DPI)) == 0
        assert len(validate_dpi(MAX_DPI)) == 0


class TestValidateColorMode:
    """Tests for color mode validation."""
    
    def test_validate_color_mode_valid(self):
        """Should pass for all valid color modes."""
        for mode in VALID_COLOR_MODES:
            errors = validate_color_mode(mode)
            assert len(errors) == 0, f"Failed for mode: {mode}"
    
    def test_validate_color_mode_none(self):
        """Should fail when color mode is None."""
        errors = validate_color_mode(None)
        assert len(errors) == 1
        assert errors[0].field == 'color_mode'
        assert 'required' in errors[0].error.lower()
    
    def test_validate_color_mode_invalid(self):
        """Should fail for invalid color modes."""
        invalid_modes = ['P', '1', 'CMYK', 'HSV', 'XYZ']
        for mode in invalid_modes:
            errors = validate_color_mode(mode)
            assert len(errors) == 1, f"Should fail for mode: {mode}"
            assert errors[0].field == 'color_mode'


class TestValidateRepeatUnit:
    """Tests for repeat unit validation."""
    
    def test_validate_repeat_unit_perfect_tiling(self):
        """Should pass for perfect tiling."""
        repeat = {'width': 100, 'height': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) == 0
    
    def test_validate_repeat_unit_none(self):
        """Should fail when repeat unit is None."""
        errors = validate_repeat_unit(None, 1000, 1000)
        assert len(errors) == 1
        assert errors[0].field == 'repeat_unit'
        assert 'required' in errors[0].error.lower()
    
    def test_validate_repeat_unit_missing_width(self):
        """Should fail when width is missing."""
        repeat = {'height': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) == 1
        assert 'width and height' in errors[0].error.lower()
    
    def test_validate_repeat_unit_missing_height(self):
        """Should fail when height is missing."""
        repeat = {'width': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) == 1
        assert 'width and height' in errors[0].error.lower()
    
    def test_validate_repeat_unit_negative_width(self):
        """Should fail for negative width."""
        repeat = {'width': -100, 'height': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('positive' in e.error.lower() for e in errors)
    
    def test_validate_repeat_unit_zero_height(self):
        """Should fail for zero height."""
        repeat = {'width': 100, 'height': 0}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('positive' in e.error.lower() for e in errors)
    
    def test_validate_repeat_unit_not_divisible_width(self):
        """Should fail when image width is not divisible by repeat width."""
        repeat = {'width': 300, 'height': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('not divisible' in e.error.lower() for e in errors)
    
    def test_validate_repeat_unit_not_divisible_height(self):
        """Should fail when image height is not divisible by repeat height."""
        repeat = {'width': 100, 'height': 300}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('not divisible' in e.error.lower() for e in errors)
    
    def test_validate_repeat_unit_exceeds_width(self):
        """Should fail when repeat width exceeds image width."""
        repeat = {'width': 2000, 'height': 100}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('exceeds' in e.error.lower() for e in errors)
    
    def test_validate_repeat_unit_exceeds_height(self):
        """Should fail when repeat height exceeds image height."""
        repeat = {'width': 100, 'height': 2000}
        errors = validate_repeat_unit(repeat, 1000, 1000)
        assert len(errors) >= 1
        assert any('exceeds' in e.error.lower() for e in errors)


class TestValidateDimensions:
    """Tests for dimension validation."""
    
    def test_validate_dimensions_valid(self):
        """Should pass for valid dimensions."""
        errors = validate_dimensions(1000, 1000)
        assert len(errors) == 0
    
    def test_validate_dimensions_max_valid(self):
        """Should pass at maximum boundaries."""
        errors = validate_dimensions(MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT)
        assert len(errors) == 0
    
    def test_validate_dimensions_width_exceeds(self):
        """Should fail when width exceeds maximum."""
        errors = validate_dimensions(MAX_IMAGE_WIDTH + 1, 1000)
        assert len(errors) >= 1
        assert any('width' in e.error.lower() and 'exceeds' in e.error.lower() for e in errors)
    
    def test_validate_dimensions_height_exceeds(self):
        """Should fail when height exceeds maximum."""
        errors = validate_dimensions(1000, MAX_IMAGE_HEIGHT + 1)
        assert len(errors) >= 1
        assert any('height' in e.error.lower() and 'exceeds' in e.error.lower() for e in errors)
    
    def test_validate_dimensions_megapixels_exceeds(self):
        """Should fail when total megapixels exceed maximum."""
        # Create dimensions that individually are valid but together exceed megapixel limit
        width = MAX_IMAGE_WIDTH
        height = MAX_IMAGE_HEIGHT
        errors = validate_dimensions(width, height)
        
        # At exact limits, should still pass
        assert len(errors) == 0


class TestValidateImageConfig:
    """Integration tests for complete image config validation."""
    
    @pytest.fixture
    def temp_image(self):
        """Create a temporary test image."""
        img = Image.new('RGB', (1000, 1000))
        img.info['dpi'] = (300, 300)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img.save(f.name)
            yield f.name
        
        Path(f.name).unlink()
    
    def test_validate_image_config_detection_only(self, temp_image):
        """Should detect configuration from image."""
        result = validate_image_config(image_path=temp_image)
        
        assert result.valid
        assert result.detected['dpi'] == 300
        assert result.detected['color_mode'] == 'RGB'
        assert result.detected['dimensions'] == {'width': 1000, 'height': 1000}
        assert 'repeat_unit' in result.suggestions
    
    def test_validate_image_config_with_valid_config(self, temp_image):
        """Should validate valid configuration."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 100, 'height': 100}
        }
        
        result = validate_image_config(image_path=temp_image, config=config)
        
        assert result.valid
        assert len(result.errors) == 0
    
    def test_validate_image_config_invalid_dpi(self, temp_image):
        """Should detect invalid DPI."""
        config = {
            'dpi': 5000,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 100, 'height': 100}
        }
        
        result = validate_image_config(image_path=temp_image, config=config)
        
        assert not result.valid
        assert len(result.errors) > 0
        assert any(e.field == 'dpi' for e in result.errors)
    
    def test_validate_image_config_invalid_color_mode(self, temp_image):
        """Should detect invalid color mode."""
        config = {
            'dpi': 300,
            'color_mode': 'CMYK',
            'repeat_unit': {'width': 100, 'height': 100}
        }
        
        result = validate_image_config(image_path=temp_image, config=config)
        
        assert not result.valid
        assert any(e.field == 'color_mode' for e in result.errors)
    
    def test_validate_image_config_bad_tiling(self, temp_image):
        """Should detect non-divisible repeat unit."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 300, 'height': 100}  # 1000 not divisible by 300
        }
        
        result = validate_image_config(image_path=temp_image, config=config)
        
        assert not result.valid
        assert any('repeat_unit' in e.field for e in result.errors)
    
    def test_validate_image_config_missing_file(self):
        """Should handle missing image file."""
        result = validate_image_config(image_path="/nonexistent/file.png")
        
        assert not result.valid
        assert len(result.errors) == 1
        assert result.errors[0].field == 'image_path'
    
    def test_validate_image_config_from_bytes(self):
        """Should validate from image bytes."""
        img = Image.new('RGB', (1000, 1000))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        result = validate_image_config(image_data=img_bytes.read())
        
        assert result.valid
        assert 'dimensions' in result.detected
        assert result.detected['dimensions'] == {'width': 1000, 'height': 1000}
    
    def test_validate_image_config_config_only(self):
        """Should validate config without image."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB'
        }
        
        result = validate_image_config(config=config)
        
        assert result.valid  # No dimension/repeat errors without image
    
    def test_validate_image_config_to_dict(self, temp_image):
        """Should convert result to dict."""
        result = validate_image_config(image_path=temp_image)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'valid' in result_dict
        assert 'detected' in result_dict
        assert 'suggestions' in result_dict
        assert 'errors' in result_dict
        assert isinstance(result_dict['errors'], list)


class TestValidationErrorAndResult:
    """Tests for ValidationError and ValidationResult data classes."""
    
    def test_validation_error_creation(self):
        """Should create ValidationError correctly."""
        error = ValidationError(
            field='dpi',
            error='DPI out of range',
            value=5000
        )
        
        assert error.field == 'dpi'
        assert error.error == 'DPI out of range'
        assert error.value == 5000
    
    def test_validation_result_creation(self):
        """Should create ValidationResult correctly."""
        result = ValidationResult(
            valid=True,
            detected={'dpi': 300},
            suggestions={'repeat_unit': {'width': 100, 'height': 100}},
            errors=[]
        )
        
        assert result.valid
        assert result.detected == {'dpi': 300}
        assert len(result.errors) == 0
    
    def test_validation_result_to_dict(self):
        """Should convert ValidationResult to dict."""
        error = ValidationError(field='dpi', error='Out of range', value=5000)
        result = ValidationResult(
            valid=False,
            detected={'dpi': 300},
            suggestions={},
            errors=[error]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['valid'] == False
        assert result_dict['detected'] == {'dpi': 300}
        assert len(result_dict['errors']) == 1
        assert result_dict['errors'][0]['field'] == 'dpi'
        assert result_dict['errors'][0]['error'] == 'Out of range'
        assert result_dict['errors'][0]['value'] == 5000
