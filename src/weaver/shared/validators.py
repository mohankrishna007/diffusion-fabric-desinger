"""
Shared Validation Utilities

PURPOSE:
Centralized validation logic for image configuration detection and validation.
Eliminates duplication between UI (ConfigDetector) and Pipeline (Stage 0).

USAGE:
- UI layer: Pre-flight validation and smart defaults
- API layer: Validation endpoint for remote frontends
- Service layer: Pre-execution validation
- Stage 0: Strict validation before pipeline execution

DESIGN:
Simple, extensible functions that can be composed for different use cases.
Returns structured errors for API/UI consumption.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from PIL import Image
import logging
from dataclasses import dataclass, field

from weaver.shared.constants import (
    DEFAULT_DPI, MIN_DPI, MAX_DPI,
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT,
    VALID_COLOR_MODES, MAX_MEGAPIXELS
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Structured validation error."""
    field: str
    error: str
    value: Any = None


@dataclass
class ValidationResult:
    """Complete validation result with detection, suggestions, and errors."""
    valid: bool
    detected: Dict[str, Any] = field(default_factory=dict)
    suggestions: Dict[str, Any] = field(default_factory=dict)
    errors: List[ValidationError] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'valid': self.valid,
            'detected': self.detected,
            'suggestions': self.suggestions,
            'errors': [{'field': e.field, 'error': e.error, 'value': e.value} for e in self.errors]
        }


def detect_dpi(image: Image.Image) -> int:
    """
    Detect DPI from image metadata or return intelligent default.
    
    Args:
        image: PIL Image object
    
    Returns:
        Detected or default DPI value (clamped to valid range)
    
    Examples:
        >>> img = Image.open("design.png")
        >>> dpi = detect_dpi(img)
        >>> assert MIN_DPI <= dpi <= MAX_DPI
    """
    dpi_info = image.info.get('dpi', None)
    
    if dpi_info:
        x_dpi, y_dpi = dpi_info
        
        # Use X DPI if both are the same, otherwise use average
        if x_dpi == y_dpi:
            detected_dpi = int(round(x_dpi))
        else:
            detected_dpi = int(round((x_dpi + y_dpi) / 2))
            logger.warning(f"Different X and Y DPI: {x_dpi}, {y_dpi}. Using average: {detected_dpi}")
        
        # Clamp to valid range
        if MIN_DPI <= detected_dpi <= MAX_DPI:
            logger.debug(f"Detected DPI: {detected_dpi}")
            return detected_dpi
        else:
            logger.warning(f"Detected DPI {detected_dpi} out of range [{MIN_DPI}, {MAX_DPI}]. Using default: {DEFAULT_DPI}")
            return DEFAULT_DPI
    
    # No DPI info found, use default
    logger.debug(f"No DPI metadata found. Using default: {DEFAULT_DPI}")
    return DEFAULT_DPI


def detect_color_mode(image: Image.Image) -> str:
    """
    Detect color mode from image and suggest valid alternative if needed.
    
    Args:
        image: PIL Image object
    
    Returns:
        Valid color mode string (one of VALID_COLOR_MODES)
    
    Examples:
        >>> img = Image.open("design.png")
        >>> mode = detect_color_mode(img)
        >>> assert mode in VALID_COLOR_MODES
    """
    mode = image.mode
    
    # Check if mode is already valid
    if mode in VALID_COLOR_MODES:
        logger.debug(f"Detected valid color mode: {mode}")
        return mode
    
    # Handle forbidden modes with suggestions
    if mode == 'P':
        logger.warning("Palette mode (P) detected. Recommending conversion to RGB.")
        return 'RGB'
    
    if mode == '1':
        logger.warning("1-bit mode detected. Recommending conversion to L (grayscale).")
        return 'L'
    
    # For other modes, suggest RGB as safe default
    logger.warning(f"Unusual color mode {mode} detected. Recommending RGB.")
    return 'RGB'


def suggest_repeat_unit(width: int, height: int) -> Dict[str, int]:
    """
    Suggest repeat unit dimensions that create perfect tiling.
    
    Uses multiple strategies:
    1. Common pattern sizes (100, 200, 250, 500, 1000 pixels)
    2. Largest common divisors within reasonable range
    3. Percentage-based suggestions (25%, 33%, 50%)
    4. Fallback to entire image
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        Dictionary with 'width' and 'height' keys that divide image dimensions evenly
    
    Examples:
        >>> repeat = suggest_repeat_unit(1000, 1000)
        >>> assert 1000 % repeat['width'] == 0
        >>> assert 1000 % repeat['height'] == 0
    """
    # Strategy 1: Try common repeat sizes
    common_sizes = [100, 200, 250, 500, 1000]
    for size in common_sizes:
        if width % size == 0 and height % size == 0:
            logger.debug(f"Found common size repeat: {size}x{size}")
            return {'width': size, 'height': size}
    
    # Strategy 2: Find largest common divisor in reasonable range
    def find_divisors(n: int, min_size: int = 50, max_size: int = 2000) -> List[int]:
        """Find divisors of n within reasonable size range."""
        divisors = []
        for i in range(min_size, min(n + 1, max_size + 1)):
            if n % i == 0:
                divisors.append(i)
        return divisors
    
    width_divisors = set(find_divisors(width))
    height_divisors = set(find_divisors(height))
    
    # Find common divisors (square repeats preferred)
    common = width_divisors.intersection(height_divisors)
    if common:
        repeat_size = max(common)
        logger.debug(f"Found common divisor repeat: {repeat_size}x{repeat_size}")
        return {'width': repeat_size, 'height': repeat_size}
    
    # Try non-square repeats with separate divisors
    if width_divisors and height_divisors:
        repeat_width = max(width_divisors)
        repeat_height = max(height_divisors)
        logger.debug(f"Found non-square repeat: {repeat_width}x{repeat_height}")
        return {'width': repeat_width, 'height': repeat_height}
    
    # Strategy 3: Try percentage-based suggestions
    percentages = [0.25, 0.33, 0.5]
    for pct in percentages:
        repeat_width = int(width * pct)
        repeat_height = int(height * pct)
        
        if repeat_width > 0 and repeat_height > 0:
            if width % repeat_width == 0 and height % repeat_height == 0:
                logger.debug(f"Found percentage-based repeat ({pct*100}%): {repeat_width}x{repeat_height}")
                return {'width': repeat_width, 'height': repeat_height}
    
    # Strategy 4: Fallback to entire image
    logger.warning(f"Could not find optimal repeat unit. Using entire image: {width}x{height}")
    return {'width': width, 'height': height}


def validate_dpi(dpi: Optional[int]) -> List[ValidationError]:
    """
    Validate DPI value.
    
    Args:
        dpi: DPI value to validate
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if dpi is None:
        errors.append(ValidationError(
            field='dpi',
            error='DPI is required',
            value=None
        ))
    elif not isinstance(dpi, int):
        errors.append(ValidationError(
            field='dpi',
            error=f'DPI must be an integer',
            value=dpi
        ))
    elif not (MIN_DPI <= dpi <= MAX_DPI):
        errors.append(ValidationError(
            field='dpi',
            error=f'DPI must be between {MIN_DPI} and {MAX_DPI}',
            value=dpi
        ))
    
    return errors


def validate_color_mode(color_mode: Optional[str]) -> List[ValidationError]:
    """
    Validate color mode.
    
    Args:
        color_mode: Color mode to validate
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if color_mode is None:
        errors.append(ValidationError(
            field='color_mode',
            error='Color mode is required',
            value=None
        ))
    elif color_mode not in VALID_COLOR_MODES:
        errors.append(ValidationError(
            field='color_mode',
            error=f'Color mode must be one of {list(VALID_COLOR_MODES)}',
            value=color_mode
        ))
    
    return errors


def validate_repeat_unit(
    repeat_unit: Optional[Dict[str, int]],
    image_width: int,
    image_height: int
) -> List[ValidationError]:
    """
    Validate repeat unit dimensions and tiling.
    
    Args:
        repeat_unit: Dictionary with 'width' and 'height' keys
        image_width: Image width in pixels
        image_height: Image height in pixels
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if repeat_unit is None:
        errors.append(ValidationError(
            field='repeat_unit',
            error='Repeat unit is required',
            value=None
        ))
        return errors
    
    repeat_width = repeat_unit.get('width')
    repeat_height = repeat_unit.get('height')
    
    if repeat_width is None or repeat_height is None:
        errors.append(ValidationError(
            field='repeat_unit',
            error='Repeat unit must have both width and height',
            value=repeat_unit
        ))
        return errors
    
    if not isinstance(repeat_width, int) or not isinstance(repeat_height, int):
        errors.append(ValidationError(
            field='repeat_unit',
            error='Repeat unit width and height must be integers',
            value=repeat_unit
        ))
        return errors
    
    if repeat_width <= 0:
        errors.append(ValidationError(
            field='repeat_unit.width',
            error=f'Repeat width must be positive',
            value=repeat_width
        ))
    
    if repeat_height <= 0:
        errors.append(ValidationError(
            field='repeat_unit.height',
            error=f'Repeat height must be positive',
            value=repeat_height
        ))
    
    # Check perfect tiling
    if repeat_width > 0 and image_width % repeat_width != 0:
        errors.append(ValidationError(
            field='repeat_unit.width',
            error=f'Image width {image_width} is not divisible by repeat width {repeat_width}',
            value=repeat_width
        ))
    
    if repeat_height > 0 and image_height % repeat_height != 0:
        errors.append(ValidationError(
            field='repeat_unit.height',
            error=f'Image height {image_height} is not divisible by repeat height {repeat_height}',
            value=repeat_height
        ))
    
    # Check repeat doesn't exceed image dimensions
    if repeat_width > image_width:
        errors.append(ValidationError(
            field='repeat_unit.width',
            error=f'Repeat width {repeat_width} exceeds image width {image_width}',
            value=repeat_width
        ))
    
    if repeat_height > image_height:
        errors.append(ValidationError(
            field='repeat_unit.height',
            error=f'Repeat height {repeat_height} exceeds image height {image_height}',
            value=repeat_height
        ))
    
    return errors


def validate_dimensions(width: int, height: int) -> List[ValidationError]:
    """
    Validate image dimensions against manufacturing limits.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if width > MAX_IMAGE_WIDTH:
        errors.append(ValidationError(
            field='dimensions.width',
            error=f'Width {width:,}px exceeds maximum {MAX_IMAGE_WIDTH:,}px',
            value=width
        ))
    
    if height > MAX_IMAGE_HEIGHT:
        errors.append(ValidationError(
            field='dimensions.height',
            error=f'Height {height:,}px exceeds maximum {MAX_IMAGE_HEIGHT:,}px',
            value=height
        ))
    
    megapixels = (width * height) / 1_000_000
    if megapixels > MAX_MEGAPIXELS:
        errors.append(ValidationError(
            field='dimensions.megapixels',
            error=f'Image {megapixels:.1f}MP exceeds maximum {MAX_MEGAPIXELS}MP',
            value=megapixels
        ))
    
    return errors


def validate_image_config(
    image_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    image_data: Optional[bytes] = None
) -> ValidationResult:
    """
    Comprehensive validation of image and configuration.
    
    Detects configuration from image, validates provided config,
    and suggests optimal values. Can validate:
    - Image only (detect and suggest)
    - Config only (validate ranges/formats)
    - Both (detect, validate, check consistency)
    
    Args:
        image_path: Path to image file (optional)
        config: Configuration dictionary to validate (optional)
        image_data: Raw image bytes as alternative to image_path (optional)
    
    Returns:
        ValidationResult with detection, suggestions, and errors
    
    Examples:
        >>> # Detect from image
        >>> result = validate_image_config(image_path="design.png")
        >>> print(result.detected['dpi'])
        
        >>> # Validate config with image
        >>> result = validate_image_config(
        ...     image_path="design.png",
        ...     config={'dpi': 300, 'color_mode': 'RGB', 'repeat_unit': {'width': 100, 'height': 100}}
        ... )
        >>> if not result.valid:
        ...     for error in result.errors:
        ...         print(f"{error.field}: {error.error}")
    """
    result = ValidationResult(valid=True)
    config = config or {}
    
    # Load image if provided
    image = None
    width = height = None
    
    if image_path:
        path = Path(image_path)
        if not path.exists():
            result.errors.append(ValidationError(
                field='image_path',
                error=f'Image file not found: {image_path}',
                value=image_path
            ))
            result.valid = False
            return result
        
        try:
            image = Image.open(path)
            width, height = image.size
        except Exception as e:
            result.errors.append(ValidationError(
                field='image_path',
                error=f'Cannot load image: {str(e)}',
                value=image_path
            ))
            result.valid = False
            return result
    
    elif image_data:
        try:
            from io import BytesIO
            image = Image.open(BytesIO(image_data))
            width, height = image.size
        except Exception as e:
            result.errors.append(ValidationError(
                field='image_data',
                error=f'Cannot decode image: {str(e)}',
                value=None
            ))
            result.valid = False
            return result
    
    # Detect from image if available
    if image:
        result.detected['dpi'] = detect_dpi(image)
        result.detected['color_mode'] = detect_color_mode(image)
        result.detected['dimensions'] = {'width': width, 'height': height}
        result.detected['actual_color_mode'] = image.mode
        
        # Validate dimensions
        result.errors.extend(validate_dimensions(width, height))
        
        # Suggest repeat unit
        result.suggestions['repeat_unit'] = suggest_repeat_unit(width, height)
        
        # Calculate tile counts for suggestion
        repeat = result.suggestions['repeat_unit']
        tiles_x = width // repeat['width']
        tiles_y = height // repeat['height']
        result.suggestions['tiles'] = {'x': tiles_x, 'y': tiles_y, 'total': tiles_x * tiles_y}
    
    # Validate provided config
    if config:
        # Validate DPI
        dpi = config.get('dpi')
        result.errors.extend(validate_dpi(dpi))
        
        # Validate color mode
        color_mode = config.get('color_mode')
        result.errors.extend(validate_color_mode(color_mode))
        
        # Validate repeat unit (if dimensions available)
        if width and height:
            repeat_unit = config.get('repeat_unit')
            result.errors.extend(validate_repeat_unit(repeat_unit, width, height))
    
    # Set overall validity
    result.valid = len(result.errors) == 0
    
    return result
