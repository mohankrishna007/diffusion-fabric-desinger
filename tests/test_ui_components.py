"""
Unit tests for Streamlit UI components

Tests the ConfigDetector and PipelineService without requiring
a full pipeline execution.
"""

import pytest
from pathlib import Path
from PIL import Image
import tempfile
from weaver.ui.config_detector import ConfigDetector
from weaver.ui.pipeline_service import PipelineService


@pytest.fixture
def temp_image():
    """Create a temporary test image."""
    # Create a simple RGB image
    img = Image.new('RGB', (1000, 1000), color='red')
    
    # Add DPI metadata
    img.info['dpi'] = (300, 300)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name, dpi=(300, 300))
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def config_detector():
    """Create a ConfigDetector instance."""
    return ConfigDetector()


@pytest.fixture
def pipeline_service():
    """Create a PipelineService instance."""
    return PipelineService()


class TestConfigDetector:
    """Tests for ConfigDetector class."""
    
    def test_detect_config_success(self, config_detector, temp_image):
        """Test successful config detection."""
        config = config_detector.detect_config(temp_image)
        
        assert config is not None
        assert 'dpi' in config
        assert 'color_mode' in config
        assert 'repeat_unit' in config
        assert 'image_width' in config
        assert 'image_height' in config
        assert 'suggestions' in config
    
    def test_detect_dpi_from_metadata(self, config_detector, temp_image):
        """Test DPI detection from image metadata."""
        config = config_detector.detect_config(temp_image)
        
        # Should detect 300 DPI from metadata
        assert config['dpi'] == 300
    
    def test_detect_color_mode(self, config_detector, temp_image):
        """Test color mode detection."""
        config = config_detector.detect_config(temp_image)
        
        # Image is RGB
        assert config['color_mode'] == 'RGB'
    
    def test_suggest_repeat_unit(self, config_detector, temp_image):
        """Test repeat unit suggestion."""
        config = config_detector.detect_config(temp_image)
        
        repeat = config['repeat_unit']
        assert 'width' in repeat
        assert 'height' in repeat
        assert repeat['width'] > 0
        assert repeat['height'] > 0
        
        # Should be divisors of 1000
        assert 1000 % repeat['width'] == 0
        assert 1000 % repeat['height'] == 0
    
    def test_detect_config_missing_file(self, config_detector):
        """Test config detection with missing file."""
        with pytest.raises(FileNotFoundError):
            config_detector.detect_config('/nonexistent/file.png')
    
    def test_validate_config_valid(self, config_detector, temp_image):
        """Test validation of valid configuration."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 200, 'height': 200}
        }
        
        validation = config_detector.validate_config(config, temp_image)
        
        assert validation['valid'] is True
        assert len(validation['errors']) == 0
    
    def test_validate_config_invalid_dpi(self, config_detector, temp_image):
        """Test validation with invalid DPI."""
        config = {
            'dpi': 50,  # Too low (min is 72)
            'color_mode': 'RGB',
            'repeat_unit': {'width': 200, 'height': 200}
        }
        
        validation = config_detector.validate_config(config, temp_image)
        
        assert validation['valid'] is False
        assert len(validation['errors']) > 0
    
    def test_validate_config_invalid_color_mode(self, config_detector, temp_image):
        """Test validation with invalid color mode."""
        config = {
            'dpi': 300,
            'color_mode': 'P',  # Palette mode not allowed
            'repeat_unit': {'width': 200, 'height': 200}
        }
        
        validation = config_detector.validate_config(config, temp_image)
        
        assert validation['valid'] is False
        assert any('color mode' in err.lower() for err in validation['errors'])
    
    def test_validate_config_imperfect_tiling(self, config_detector, temp_image):
        """Test validation with imperfect tiling."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 300, 'height': 300}  # 1000 % 300 != 0
        }
        
        validation = config_detector.validate_config(config, temp_image)
        
        assert validation['valid'] is False
        assert any('divisible' in err.lower() for err in validation['errors'])
    
    def test_validate_config_missing_parameters(self, config_detector, temp_image):
        """Test validation with missing parameters."""
        config = {
            'dpi': 300
            # Missing color_mode and repeat_unit
        }
        
        validation = config_detector.validate_config(config, temp_image)
        
        assert validation['valid'] is False
        assert len(validation['errors']) > 0


class TestPipelineService:
    """Tests for PipelineService class."""
    
    def test_init(self, pipeline_service):
        """Test PipelineService initialization."""
        assert pipeline_service is not None
        assert pipeline_service.pipeline_engine is not None
        assert pipeline_service.workspace_base_dir.exists()
    
    def test_validate_stage_0_config_valid(self, pipeline_service, temp_image):
        """Test Stage 0 config validation with valid config."""
        config = {
            'dpi': 300,
            'color_mode': 'RGB',
            'repeat_unit': {'width': 200, 'height': 200}
        }
        
        validation = pipeline_service.validate_stage_0_config(temp_image, config)
        
        assert validation['valid'] is True
        assert len(validation['errors']) == 0
    
    def test_validate_stage_0_config_invalid(self, pipeline_service, temp_image):
        """Test Stage 0 config validation with invalid config."""
        config = {
            'dpi': 50,  # Invalid
            'color_mode': 'RGB',
            'repeat_unit': {'width': 200, 'height': 200}
        }
        
        validation = pipeline_service.validate_stage_0_config(temp_image, config)
        
        assert validation['valid'] is False
        assert len(validation['errors']) > 0
    
    def test_create_workspace(self, pipeline_service):
        """Test workspace creation."""
        pipeline_id = "test-pipeline-123"
        
        workspace = pipeline_service.create_workspace(pipeline_id)
        
        assert workspace.exists()
        assert workspace.is_dir()
        
        # Check stage directories
        for stage_num in range(8):
            stage_dir = workspace / f"stage_{stage_num}"
            assert stage_dir.exists()
        
        # Cleanup
        import shutil
        shutil.rmtree(workspace)
    
    def test_list_pipelines_empty(self, pipeline_service):
        """Test listing pipelines when none exist."""
        pipelines = pipeline_service.list_pipelines()
        
        # Should be empty initially (or only from other tests)
        assert isinstance(pipelines, list)


class TestDetectionStrategies:
    """Tests for specific detection strategies."""
    
    def test_detect_repeat_by_common_sizes(self, config_detector):
        """Test common size detection strategy."""
        # 1000x1000 should find 100, 200, 250, 500, or 1000
        result = config_detector._detect_repeat_by_common_sizes(1000, 1000)
        
        assert result is not None
        assert result['width'] in [100, 200, 250, 500, 1000]
        assert result['height'] in [100, 200, 250, 500, 1000]
    
    def test_detect_repeat_by_common_sizes_no_match(self, config_detector):
        """Test common size strategy with no matches."""
        # 777x777 doesn't match common sizes
        result = config_detector._detect_repeat_by_common_sizes(777, 777)
        
        assert result is None
    
    def test_detect_repeat_by_divisors(self, config_detector):
        """Test divisor detection strategy."""
        result = config_detector._detect_repeat_by_divisors(1000, 1000)
        
        assert result is not None
        assert result['width'] > 0
        assert result['height'] > 0
        assert 1000 % result['width'] == 0
        assert 1000 % result['height'] == 0
    
    def test_detect_repeat_by_percentage(self, config_detector):
        """Test percentage-based detection strategy."""
        result = config_detector._detect_repeat_by_percentage(1000, 1000)
        
        assert result is not None
        assert 1000 % result['width'] == 0
        assert 1000 % result['height'] == 0


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
