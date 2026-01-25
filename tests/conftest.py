"""
Pytest configuration and fixtures.
"""

import pytest
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_pipeline_id():
    """Sample pipeline ID for testing."""
    return "test-pipeline-12345"


@pytest.fixture
def sample_config():
    """Sample pipeline configuration."""
    return {
        "stage_0": {"timeout_seconds": 60},
        "stage_1": {"timeout_seconds": 120},
        # Add more as needed
    }


@pytest.fixture
def mock_image_data():
    """Mock image data for testing."""
    # Create a simple 100x100 RGB image
    import numpy as np
    return np.zeros((100, 100, 3), dtype=np.uint8)
