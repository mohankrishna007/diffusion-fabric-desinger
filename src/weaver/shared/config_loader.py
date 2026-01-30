"""
Configuration Loader
Loads pipeline configuration from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def load_pipeline_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load pipeline configuration from YAML file.
    
    Args:
        config_path: Path to pipeline.yaml file (default: config/pipeline.yaml)
    
    Returns:
        Loaded configuration dictionary
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    if config_path is None:
        # Default path
        config_path = Path("config/pipeline.yaml")
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    logger.info(f"Loading pipeline configuration from {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            raise ValueError("Configuration file is empty")
        
        # Validate required sections
        validate_config_structure(config)
        
        logger.info(f"Configuration loaded successfully: {len(config.get('stages', []))} stages defined")
        
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML configuration: {e}")
        raise


def validate_config_structure(config: Dict[str, Any]) -> None:
    """
    Validate that configuration has required structure.
    
    Args:
        config: Configuration dictionary
    
    Raises:
        ValueError: If configuration is invalid
    """
    # Check for diffusion module stages
    if 'diffusion' not in config:
        logger.warning("Configuration missing 'diffusion' module - pipeline may not execute")
        return
    
    diffusion_config = config['diffusion']
    if 'stages' not in diffusion_config:
        logger.warning("Diffusion module missing 'stages' section - pipeline may not execute")
        return
    
    stages = diffusion_config['stages']
    if not isinstance(stages, list):
        raise ValueError("'diffusion.stages' section must be a list")
    
    if not stages:
        logger.warning("'diffusion.stages' list is empty - no stages configured")
        return
    
    # Validate each stage has required fields
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError(f"Stage {i} must be a dictionary")
        
        required_fields = ['id', 'name', 'class_name']
        for field in required_fields:
            if field not in stage:
                raise ValueError(f"Stage {i} missing required field '{field}'")


def get_stage_config(config: Dict[str, Any], stage_id: str) -> Dict[str, Any]:
    """
    Get configuration for a specific stage.
    
    Args:
        config: Full pipeline configuration
        stage_id: Stage identifier
    
    Returns:
        Stage-specific configuration
    """
    stages = config.get('stages', [])
    
    for stage in stages:
        if stage.get('id') == stage_id:
            return stage.get('config', {})
    
    return {}
