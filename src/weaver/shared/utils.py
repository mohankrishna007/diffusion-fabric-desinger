"""
Shared utility functions.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


def generate_pipeline_id() -> str:
    """
    Generate a unique pipeline execution ID.
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def compute_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    Compute hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
    
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def ensure_directory(path: str) -> Path:
    """
    Ensure directory exists, create if not.
    
    Args:
        path: Directory path
    
    Returns:
        Path object
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def validate_file_exists(file_path: str) -> bool:
    """
    Check if file exists.
    
    Args:
        file_path: Path to file
    
    Returns:
        True if file exists, False otherwise
    """
    return Path(file_path).is_file()


def validate_file_extension(file_path: str, allowed_extensions: list[str]) -> bool:
    """
    Validate file extension.
    
    Args:
        file_path: Path to file
        allowed_extensions: List of allowed extensions (e.g., ['.bmp', '.png'])
    
    Returns:
        True if extension is allowed, False otherwise
    """
    file_ext = Path(file_path).suffix.lower()
    return file_ext in [ext.lower() for ext in allowed_extensions]


def merge_dicts(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge two dictionaries, with override taking precedence.
    
    Args:
        base: Base dictionary
        override: Override dictionary
    
    Returns:
        Merged dictionary
    """
    if override is None:
        return base.copy()
    
    result = base.copy()
    result.update(override)
    return result


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to file
    
    Returns:
        File size in bytes
    """
    return Path(file_path).stat().st_size


def get_stage_artifact_dir(pipeline_id: str, stage_number: int, base_dir: str = "storage") -> Path:
    """
    Get standardized artifact directory for a stage.
    
    Creates directory structure: storage/<pipeline_id>/stage_<N>/
    
    Args:
        pipeline_id: Pipeline execution ID
        stage_number: Stage number (0-7)
        base_dir: Base storage directory (default: "storage")
    
    Returns:
        Path to stage artifact directory
    """
    artifact_dir = Path(base_dir) / pipeline_id / f"stage_{stage_number}"
    ensure_directory(str(artifact_dir))
    return artifact_dir


def save_artifact_json(artifact_dir: Path, filename: str, data: Dict[str, Any]) -> Path:
    """
    Save artifact data as JSON file.
    
    Args:
        artifact_dir: Artifact directory path
        filename: Output filename (e.g., "metadata.json")
        data: Data to serialize
    
    Returns:
        Path to saved file
    """
    import json
    
    output_path = artifact_dir / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    
    return output_path


def copy_artifact_file(source_path: str, artifact_dir: Path, filename: str) -> Path:
    """
    Copy a file to the artifact directory.
    
    Args:
        source_path: Source file path
        artifact_dir: Artifact directory path
        filename: Destination filename
    
    Returns:
        Path to copied file
    """
    import shutil
    
    dest_path = artifact_dir / filename
    shutil.copy2(source_path, dest_path)
    
    return dest_path
