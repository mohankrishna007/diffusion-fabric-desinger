"""
Structured logging configuration using Python's logging module.
"""

import logging
import sys
from typing import Optional
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured log messages.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured data."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "pipeline_id"):
            log_data["pipeline_id"] = record.pipeline_id
        
        if hasattr(record, "stage_number"):
            log_data["stage_number"] = record.stage_number
        
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        # Format as key=value pairs
        parts = [f"{k}={v}" for k, v in log_data.items()]
        return " ".join(parts)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(StructuredFormatter())
    
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class PipelineLogger:
    """
    Logger wrapper with pipeline context.
    """
    
    def __init__(self, pipeline_id: str, logger: Optional[logging.Logger] = None):
        """
        Initialize pipeline logger.
        
        Args:
            pipeline_id: Pipeline execution ID
            logger: Base logger instance
        """
        self.pipeline_id = pipeline_id
        self.logger = logger or logging.getLogger("weaver.pipeline")
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method with context."""
        extra = {"pipeline_id": self.pipeline_id, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def stage_start(self, stage_number: int, stage_name: str):
        """Log stage start."""
        self.info(
            f"Stage {stage_number} ({stage_name}) started",
            stage_number=stage_number
        )
    
    def stage_complete(self, stage_number: int, stage_name: str, duration_ms: float):
        """Log stage completion."""
        self.info(
            f"Stage {stage_number} ({stage_name}) completed",
            stage_number=stage_number,
            duration_ms=duration_ms
        )
    
    def stage_error(self, stage_number: int, stage_name: str, error: str):
        """Log stage error."""
        self.error(
            f"Stage {stage_number} ({stage_name}) failed: {error}",
            stage_number=stage_number
        )
