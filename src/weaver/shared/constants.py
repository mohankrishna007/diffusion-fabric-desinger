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

# File formats - LOSSLESS ONLY (Stage 0 mandate)
# JPEG forbidden: lossy compression destroys thread-level precision for CAM
LOSSLESS_INPUT_FORMATS: Final[list[str]] = [".bmp", ".png", ".tiff", ".tif"]
SUPPORTED_INPUT_FORMATS: Final[list[str]] = LOSSLESS_INPUT_FORMATS  # Alias for backward compatibility
CAM_OUTPUT_FORMAT: Final[str] = ".bmp"

# Color modes - UNAMBIGUOUS ONLY (Stage 0 mandate)
# P (palette-indexed) and 1 (1-bit) forbidden: create manufacturing interpretation ambiguity
VALID_COLOR_MODES: Final[set[str]] = {"RGB", "RGBA", "L", "LA"}

# Image processing defaults
DEFAULT_DPI: Final[int] = 300
DEFAULT_COLOR_SPACE: Final[str] = "RGB"

# Manufacturing constraints - IMMUTABLE physical limits
# These represent Jacquard loom capabilities and CAM system requirements
# DO NOT make these configurable - they are engineering constraints
MIN_LINE_WIDTH_PIXELS: Final[int] = 2
MAX_COLOR_COUNT: Final[int] = 16
MAX_IMAGE_WIDTH: Final[int] = 10000  # Loom maximum width
MAX_IMAGE_HEIGHT: Final[int] = 10000  # Loom maximum height

# Stage 0 Input Acquisition - Manufacturing constraint thresholds
MAX_MEGAPIXELS: Final[int] = 100  # 10000 x 10000 = loom limit
MAX_FILE_SIZE_BYTES: Final[int] = 500 * 1024 * 1024  # 500 MB (resource protection)
MAX_PIXEL_COUNT: Final[int] = MAX_MEGAPIXELS * 1_000_000
MAX_DECODE_MEMORY_BYTES: Final[int] = 1024 * 1024 * 1024  # 1 GB max for image decode (OOM protection)
MIN_DPI: Final[int] = 72  # Below this, thread precision is lost
MAX_DPI: Final[int] = 1200  # Above this, loom cannot resolve

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
