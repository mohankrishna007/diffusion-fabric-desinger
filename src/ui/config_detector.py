"""
Configuration Detector for Streamlit UI
Thin wrapper over shared validators for embedded Streamlit deployment
"""

from pathlib import Path
from typing import Dict, Any, List
import logging

from weaver.shared.validators import (
    validate_image_config,
    ValidationResult
)

logger = logging.getLogger(__name__)


class ConfigDetector:
    """
    Detects and validates Stage 0 configuration parameters.
    
    Thin wrapper over shared validators (weaver.shared.validators).
    For embedded Streamlit deployment that can import Python modules.
    
    Future: When UI becomes separate frontend, it will call
    POST /api/v1/pipeline/validate endpoint instead.
    """
    
    def detect_and_validate(
        self,
        image_path: str,
        config: Dict[str, Any] = None
    ) -> ValidationResult:
        """
        Detect configuration from image and validate provided config.
        
        Args:
            image_path: Path to the image file
            config: Optional configuration to validate (if None, only detect)
        
        Returns:
            ValidationResult with detection, suggestions, and errors
        
        Examples:
            >>> detector = ConfigDetector()
            >>> result = detector.detect_and_validate("design.png")
            >>> print(result.detected['dpi'])
            >>> print(result.suggestions['repeat_unit'])
            
            >>> # With config validation
            >>> config = {'dpi': 300, 'color_mode': 'RGB', 'repeat_unit': {'width': 100, 'height': 100}}
            >>> result = detector.detect_and_validate("design.png", config)
            >>> if not result.valid:
            ...     for error in result.errors:
            ...         print(f"{error.field}: {error.error}")
        """
        logger.debug(f"Detecting config for {image_path}")
        
        # Delegate to shared validators
        result = validate_image_config(
            image_path=image_path,
            config=config
        )
        
        if result.valid:
            logger.info(
                f"Validation passed for {Path(image_path).name}: "
                f"DPI={result.detected.get('dpi')}, "
                f"Mode={result.detected.get('color_mode')}, "
                f"Repeat={result.suggestions.get('repeat_unit')}"
            )
        else:
            logger.warning(
                f"Validation failed for {Path(image_path).name}: "
                f"{len(result.errors)} errors"
            )
        
        return result
    
    # Backward compatibility methods (deprecated)
    
    def detect_config(self, image_path: str) -> Dict[str, Any]:
        """
        DEPRECATED: Use detect_and_validate() instead.
        
        Detect configuration from image (old interface for compatibility).
        """
        logger.warning("detect_config() is deprecated, use detect_and_validate()")
        result = self.detect_and_validate(image_path)
        
        return {
            'dpi': result.detected.get('dpi'),
            'color_mode': result.detected.get('color_mode'),
            'repeat_unit': result.suggestions.get('repeat_unit'),
            'image_width': result.detected.get('dimensions', {}).get('width'),
            'image_height': result.detected.get('dimensions', {}).get('height'),
            'suggestions': self._format_legacy_suggestions(result)
        }
    
    def validate_config(self, config: Dict[str, Any], image_path: str) -> Dict[str, Any]:
        """
        DEPRECATED: Use detect_and_validate() instead.
        
        Validate configuration (old interface for compatibility).
        """
        logger.warning("validate_config() is deprecated, use detect_and_validate()")
        result = self.detect_and_validate(image_path, config)
        
        return {
            'valid': result.valid,
            'errors': [f"{e.field}: {e.error}" for e in result.errors]
        }
    
    def _format_legacy_suggestions(self, result: ValidationResult) -> List[str]:
        """Format suggestions for old detect_config() interface."""
        suggestions = []
        
        # DPI info
        detected_dpi = result.detected.get('dpi')
        if detected_dpi:
            suggestions.append(f"✅ DPI {detected_dpi} detected from image metadata")
        
        # Color mode info
        color_mode = result.detected.get('color_mode')
        actual_mode = result.detected.get('actual_color_mode')
        if color_mode == actual_mode:
            suggestions.append(f"✅ Color mode {color_mode} matches image")
        elif actual_mode:
            suggestions.append(
                f"⚠️ Image color mode {actual_mode} differs from suggested {color_mode}"
            )
        
        # Repeat unit tiling info
        repeat = result.suggestions.get('repeat_unit', {})
        tiles = result.suggestions.get('tiles', {})
        if repeat and tiles:
            suggestions.append(
                f"✅ Suggested repeat creates {tiles.get('x')}x{tiles.get('y')} tiles "
                f"({tiles.get('total')} total repeats)"
            )
        
        # Dimension warnings
        for error in result.errors:
            if 'dimensions' in error.field:
                suggestions.append(f"⚠️ {error.error}")
        
        return suggestions
