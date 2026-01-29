"""
Configuration Detector for Stage 0
Automatically detects required Stage 0 configuration parameters from uploaded images
"""

from pathlib import Path
from PIL import Image
from typing import Dict, Any, Optional
import logging

from weaver.shared.constants import (
    DEFAULT_DPI, MIN_DPI, MAX_DPI,
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT,
    VALID_COLOR_MODES
)


logger = logging.getLogger(__name__)


class ConfigDetector:
    """
    Detects Stage 0 configuration parameters from uploaded images.
    
    Provides intelligent defaults and suggestions while maintaining
    Stage 0's strict validation requirements.
    """
    
    def __init__(self):
        """Initialize the configuration detector."""
        self._default_repeat_strategies = [
            self._detect_repeat_by_common_sizes,
            self._detect_repeat_by_divisors,
            self._detect_repeat_by_percentage
        ]
    
    def detect_config(self, image_path: str) -> Dict[str, Any]:
        """
        Detect all required Stage 0 configuration parameters from an image.
        
        Args:
            image_path: Path to the image file
        
        Returns:
            Dictionary containing detected configuration:
            - dpi: Detected or default DPI
            - color_mode: Detected color mode
            - repeat_unit: Suggested repeat dimensions {width, height}
            - image_width: Actual image width
            - image_height: Actual image height
            - suggestions: Additional suggestions and warnings
        
        Raises:
            FileNotFoundError: If image file doesn't exist
            ValueError: If image cannot be loaded
        """
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            img = Image.open(path)
        except Exception as e:
            raise ValueError(f"Cannot load image: {str(e)}")
        
        # Detect DPI
        dpi = self._detect_dpi(img)
        
        # Detect color mode
        color_mode = self._detect_color_mode(img)
        
        # Get image dimensions
        width, height = img.size
        
        # Suggest repeat unit dimensions
        repeat_unit = self._suggest_repeat_unit(width, height)
        
        # Generate suggestions and warnings
        suggestions = self._generate_suggestions(img, dpi, color_mode, repeat_unit)
        
        config = {
            'dpi': dpi,
            'color_mode': color_mode,
            'repeat_unit': repeat_unit,
            'image_width': width,
            'image_height': height,
            'suggestions': suggestions
        }
        
        logger.info(f"Detected config for {path.name}: DPI={dpi}, Mode={color_mode}, Repeat={repeat_unit}")
        
        return config
    
    def _detect_dpi(self, img: Image.Image) -> int:
        """
        Detect DPI from image metadata or use intelligent default.
        
        Args:
            img: PIL Image object
        
        Returns:
            Detected or default DPI value
        """
        # Try to get DPI from image metadata
        dpi_info = img.info.get('dpi', None)
        
        if dpi_info:
            # DPI info is a tuple (x_dpi, y_dpi)
            x_dpi, y_dpi = dpi_info
            
            # Use X DPI if both are the same, otherwise use average
            if x_dpi == y_dpi:
                detected_dpi = int(round(x_dpi))
            else:
                detected_dpi = int(round((x_dpi + y_dpi) / 2))
                logger.warning(f"Different X and Y DPI: {x_dpi}, {y_dpi}. Using average: {detected_dpi}")
            
            # Clamp to valid range
            if MIN_DPI <= detected_dpi <= MAX_DPI:
                return detected_dpi
            else:
                logger.warning(f"Detected DPI {detected_dpi} out of range. Using default: {DEFAULT_DPI}")
                return DEFAULT_DPI
        
        # No DPI info found, use default
        logger.info(f"No DPI metadata found. Using default: {DEFAULT_DPI}")
        return DEFAULT_DPI
    
    def _detect_color_mode(self, img: Image.Image) -> str:
        """
        Detect color mode from image.
        
        Args:
            img: PIL Image object
        
        Returns:
            Valid color mode string
        """
        mode = img.mode
        
        # Check if mode is valid for Stage 0
        if mode in VALID_COLOR_MODES:
            return mode
        
        # Handle forbidden modes
        if mode == 'P':
            logger.warning("Palette mode (P) detected. Recommending conversion to RGB.")
            return 'RGB'  # Suggest RGB for palette images
        
        if mode == '1':
            logger.warning("1-bit mode detected. Recommending conversion to L (grayscale).")
            return 'L'  # Suggest L for 1-bit images
        
        # For other modes, suggest RGB as safe default
        logger.warning(f"Unusual color mode {mode} detected. Recommending RGB.")
        return 'RGB'
    
    def _suggest_repeat_unit(self, width: int, height: int) -> Dict[str, int]:
        """
        Suggest repeat unit dimensions based on image size.
        
        Uses multiple strategies to find the best repeat unit that:
        1. Divides the image dimensions evenly (perfect tiling)
        2. Is reasonable in size (not too small, not too large)
        3. Follows common pattern design conventions
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
        
        Returns:
            Dictionary with 'width' and 'height' keys
        """
        # Try each strategy in order
        for strategy in self._default_repeat_strategies:
            repeat = strategy(width, height)
            if repeat is not None:
                # Validate that repeat divides evenly
                if width % repeat['width'] == 0 and height % repeat['height'] == 0:
                    return repeat
        
        # Fallback: use entire image as repeat unit
        logger.warning(f"Could not find good repeat unit. Using entire image: {width}x{height}")
        return {'width': width, 'height': height}
    
    def _detect_repeat_by_common_sizes(self, width: int, height: int) -> Optional[Dict[str, int]]:
        """
        Try common repeat sizes (100, 200, 250, 500 pixels).
        
        Args:
            width: Image width
            height: Image height
        
        Returns:
            Repeat unit if found, None otherwise
        """
        common_sizes = [100, 200, 250, 500, 1000]
        
        for size in common_sizes:
            if width % size == 0 and height % size == 0:
                return {'width': size, 'height': size}
        
        return None
    
    def _detect_repeat_by_divisors(self, width: int, height: int) -> Optional[Dict[str, int]]:
        """
        Find the largest common divisor that creates reasonable repeat sizes.
        
        Args:
            width: Image width
            height: Image height
        
        Returns:
            Repeat unit if found, None otherwise
        """
        def find_divisors(n: int, min_size: int = 50, max_size: int = 2000) -> list:
            """Find divisors of n within reasonable size range."""
            divisors = []
            for i in range(min_size, min(n + 1, max_size + 1)):
                if n % i == 0:
                    divisors.append(i)
            return divisors
        
        # Get divisors for both dimensions
        width_divisors = set(find_divisors(width))
        height_divisors = set(find_divisors(height))
        
        # Find common divisors
        common = width_divisors.intersection(height_divisors)
        
        if common:
            # Use the largest common divisor (creates fewer tiles)
            repeat_size = max(common)
            return {'width': repeat_size, 'height': repeat_size}
        
        # Try non-square repeats
        if width_divisors and height_divisors:
            repeat_width = max(width_divisors)
            repeat_height = max(height_divisors)
            return {'width': repeat_width, 'height': repeat_height}
        
        return None
    
    def _detect_repeat_by_percentage(self, width: int, height: int) -> Optional[Dict[str, int]]:
        """
        Use a percentage of image dimensions as repeat unit.
        Tries 25%, 33%, 50% of dimensions.
        
        Args:
            width: Image width
            height: Image height
        
        Returns:
            Repeat unit if found, None otherwise
        """
        percentages = [0.25, 0.33, 0.5]
        
        for pct in percentages:
            repeat_width = int(width * pct)
            repeat_height = int(height * pct)
            
            # Check if this creates perfect tiling
            if width % repeat_width == 0 and height % repeat_height == 0:
                return {'width': repeat_width, 'height': repeat_height}
        
        return None
    
    def _generate_suggestions(
        self,
        img: Image.Image,
        dpi: int,
        color_mode: str,
        repeat_unit: Dict[str, int]
    ) -> list[str]:
        """
        Generate helpful suggestions and warnings for the user.
        
        Args:
            img: PIL Image object
            dpi: Detected DPI
            color_mode: Detected color mode
            repeat_unit: Suggested repeat unit
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        width, height = img.size
        actual_mode = img.mode
        
        # Note if detected values match actual image
        if 'dpi' in img.info:
            actual_dpi = int(round(img.info['dpi'][0]))
            if actual_dpi == dpi:
                suggestions.append(f"✅ DPI {dpi} detected from image metadata")
            else:
                suggestions.append(f"ℹ️ Image has DPI metadata: {actual_dpi}")
        else:
            suggestions.append(
                f"ℹ️ No DPI metadata found in image. Using default {dpi} DPI. "
                "Consider embedding DPI in source file."
            )
        
        # Note actual color mode
        if actual_mode == color_mode:
            suggestions.append(f"✅ Color mode {color_mode} matches image")
        elif actual_mode not in VALID_COLOR_MODES:
            suggestions.append(
                f"⚠️ Image color mode {actual_mode} is not allowed by Stage 0. "
                f"Configuration suggests {color_mode}. Convert image before processing."
            )
        
        # Check for perfect tiling
        if width % repeat_unit['width'] != 0 or height % repeat_unit['height'] != 0:
            suggestions.append(
                f"⚠️ Repeat unit {repeat_unit['width']}x{repeat_unit['height']} "
                f"does not divide image evenly. Stage 0 requires perfect tiling."
            )
        
        # Check DPI source
        if 'dpi' not in img.info:
            suggestions.append(
                f"ℹ️ No DPI metadata found in image. Using default {dpi} DPI. "
                "Consider embedding DPI in source file."
            )
        
        # Check color mode compatibility
        if img.mode not in VALID_COLOR_MODES:
            suggestions.append(
                f"⚠️ Color mode {img.mode} is not allowed by Stage 0. "
                f"Recommending {color_mode}. Convert image before processing."
            )
        
        # Check image size
        if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
            suggestions.append(
                f"⚠️ Image dimensions ({width}x{height}) exceed maximum "
                f"({MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}). Stage 0 will reject this image."
            )
        
        # Suggest optimal repeat sizes
        tiles_x = width // repeat_unit['width']
        tiles_y = height // repeat_unit['height']
        suggestions.append(
            f"✅ Suggested repeat creates {tiles_x}x{tiles_y} tiles "
            f"({tiles_x * tiles_y} total repeats)"
        )
        
        # Check for transparency
        if color_mode in ['RGBA', 'LA']:
            suggestions.append(
                "ℹ️ Image contains alpha channel. Ensure transparency is intentional "
                "for manufacturing output."
            )
        
        return suggestions
    
    def validate_config(self, config: Dict[str, Any], image_path: str) -> Dict[str, Any]:
        """
        Validate a configuration against Stage 0 requirements.
        
        Args:
            config: Configuration dictionary to validate
            image_path: Path to image file
        
        Returns:
            Validation result with 'valid' bool and 'errors' list
        """
        errors = []
        
        # Load image for validation
        try:
            img = Image.open(image_path)
            width, height = img.size
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Cannot load image: {str(e)}"]
            }
        
        # Validate DPI
        dpi = config.get('dpi')
        if dpi is None:
            errors.append("DPI is required")
        elif not (MIN_DPI <= dpi <= MAX_DPI):
            errors.append(f"DPI must be between {MIN_DPI} and {MAX_DPI}, got {dpi}")
        
        # Validate color mode
        color_mode = config.get('color_mode')
        if color_mode is None:
            errors.append("Color mode is required")
        elif color_mode not in VALID_COLOR_MODES:
            errors.append(f"Color mode must be one of {VALID_COLOR_MODES}, got {color_mode}")
        
        # Validate repeat unit
        repeat_unit = config.get('repeat_unit')
        if repeat_unit is None:
            errors.append("Repeat unit is required")
        else:
            repeat_width = repeat_unit.get('width')
            repeat_height = repeat_unit.get('height')
            
            if repeat_width is None or repeat_height is None:
                errors.append("Repeat unit must have both width and height")
            else:
                if repeat_width <= 0:
                    errors.append(f"Repeat width must be positive, got {repeat_width}")
                if repeat_height <= 0:
                    errors.append(f"Repeat height must be positive, got {repeat_height}")
                
                # Check perfect tiling
                if width % repeat_width != 0:
                    errors.append(
                        f"Image width {width} is not divisible by repeat width {repeat_width}"
                    )
                if height % repeat_height != 0:
                    errors.append(
                        f"Image height {height} is not divisible by repeat height {repeat_height}"
                    )
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
