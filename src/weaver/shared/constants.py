"""
Shared constants for the pipeline system.
"""

from typing import Final

# Pipeline configuration
MAX_STAGES: Final[int] = 8
STAGE_NUMBERS: Final[list[int]] = list(range(8))

# Stage names
STAGE_NAMES: Final[dict[int, str]] = {
    0: "Input Acquisition",
    1: "Canonical Normalization",
    2: "Structural Intent Definition",
    3: "Controlled Diffusion Refinement",
    4: "Repeat & Boundary Enforcement",
    5: "Manufacturing Geometry Cleanup",
    6: "Color & Thread Constraint Enforcement",
    7: "Pre-CAM Validation Firewall"
}

# File formats
SUPPORTED_INPUT_FORMATS: Final[list[str]] = [".bmp", ".png", ".tiff", ".tif", ".jpg", ".jpeg"]
CAM_OUTPUT_FORMAT: Final[str] = ".bmp"

# Image processing defaults
DEFAULT_DPI: Final[int] = 300
DEFAULT_COLOR_SPACE: Final[str] = "RGB"

# Manufacturing constraints (example values - should be loaded from config)
MIN_LINE_WIDTH_PIXELS: Final[int] = 2
MAX_COLOR_COUNT: Final[int] = 16
MAX_IMAGE_WIDTH: Final[int] = 10000
MAX_IMAGE_HEIGHT: Final[int] = 10000

# Validation
BORDER_TOLERANCE_PIXELS: Final[int] = 0  # Zero tolerance for repeat boundaries

# Timeouts (seconds)
DEFAULT_STAGE_TIMEOUT: Final[float] = 300.0  # 5 minutes
DIFFUSION_STAGE_TIMEOUT: Final[float] = 1800.0  # 30 minutes for Stage 3

# API
API_VERSION: Final[str] = "v1"
DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 100

# Logging
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
