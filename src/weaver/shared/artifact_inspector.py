"""
Artifact Inspector - Utility for examining pipeline stage artifacts

Usage:
    python -m weaver.shared.artifact_inspector <pipeline_id> [--stage STAGE]
    
Examples:
    # Inspect all stages
    python -m weaver.shared.artifact_inspector 550e8400-e29b-41d4-a716-446655440000
    
    # Inspect specific stage
    python -m weaver.shared.artifact_inspector 550e8400-e29b-41d4-a716-446655440000 --stage 1
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
import sys

from weaver.shared.utils import format_file_size, get_file_size


class ArtifactInspector:
    """Inspect and summarize pipeline stage artifacts."""
    
    def __init__(self, pipeline_id: str, storage_dir: str = "storage"):
        """
        Initialize artifact inspector.
        
        Args:
            pipeline_id: Pipeline execution ID
            storage_dir: Base storage directory
        """
        self.pipeline_id = pipeline_id
        self.storage_dir = Path(storage_dir)
        self.pipeline_dir = self.storage_dir / pipeline_id
        
        if not self.pipeline_dir.exists():
            raise FileNotFoundError(f"Pipeline directory not found: {self.pipeline_dir}")
    
    def inspect_all(self) -> Dict[str, Any]:
        """
        Inspect all available stages.
        
        Returns:
            Complete artifact summary
        """
        summary = {
            "pipeline_id": self.pipeline_id,
            "storage_path": str(self.pipeline_dir),
            "stages": {}
        }
        
        # Find all stage directories
        for stage_dir in sorted(self.pipeline_dir.glob("stage_*")):
            stage_num = int(stage_dir.name.split("_")[1])
            summary["stages"][stage_num] = self.inspect_stage(stage_num)
        
        return summary
    
    def inspect_stage(self, stage_number: int) -> Dict[str, Any]:
        """
        Inspect specific stage artifacts.
        
        Args:
            stage_number: Stage number (0-7)
        
        Returns:
            Stage artifact summary
        """
        stage_dir = self.pipeline_dir / f"stage_{stage_number}"
        
        if not stage_dir.exists():
            return {"error": f"Stage {stage_number} not found"}
        
        stage_info = {
            "stage_number": stage_number,
            "stage_path": str(stage_dir),
            "artifacts": [],
            "total_size": 0
        }
        
        # Load stage metadata if available
        metadata_path = stage_dir / "stage_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                stage_info["metadata"] = json.load(f)
        
        # List all artifacts
        for artifact in sorted(stage_dir.rglob("*")):
            if artifact.is_file():
                size = get_file_size(str(artifact))
                stage_info["artifacts"].append({
                    "name": artifact.name,
                    "path": str(artifact.relative_to(stage_dir)),
                    "size": size,
                    "size_formatted": format_file_size(size),
                    "type": artifact.suffix
                })
                stage_info["total_size"] += size
        
        stage_info["total_size_formatted"] = format_file_size(stage_info["total_size"])
        stage_info["artifact_count"] = len(stage_info["artifacts"])
        
        return stage_info
    
    def print_summary(self, summary: Dict[str, Any], verbose: bool = False):
        """
        Print human-readable summary.
        
        Args:
            summary: Summary dict from inspect_all()
            verbose: Show detailed artifact listings
        """
        print(f"\n{'='*80}")
        print(f"PIPELINE ARTIFACTS: {summary['pipeline_id']}")
        print(f"{'='*80}\n")
        print(f"Location: {summary['storage_path']}\n")
        
        if not summary["stages"]:
            print("No stage artifacts found.")
            return
        
        total_size = 0
        
        for stage_num, stage_info in sorted(summary["stages"].items()):
            if "error" in stage_info:
                print(f"Stage {stage_num}: {stage_info['error']}")
                continue
            
            stage_name = "Unknown"
            if "metadata" in stage_info:
                stage_name = stage_info["metadata"].get("stage_name", "Unknown")
            
            print(f"Stage {stage_num}: {stage_name}")
            print(f"  Path: {stage_info['stage_path']}")
            print(f"  Artifacts: {stage_info['artifact_count']}")
            print(f"  Total Size: {stage_info['total_size_formatted']}")
            
            total_size += stage_info["total_size"]
            
            if verbose and stage_info["artifacts"]:
                print(f"  Files:")
                for artifact in stage_info["artifacts"]:
                    print(f"    - {artifact['path']:<40} {artifact['size_formatted']:>10}")
            
            # Print key metadata
            if "metadata" in stage_info:
                metadata = stage_info["metadata"]
                if "metrics" in metadata:
                    print(f"  Metrics:")
                    for key, value in metadata["metrics"].items():
                        print(f"    {key}: {value}")
            
            print()
        
        print(f"{'='*80}")
        print(f"TOTAL STORAGE: {format_file_size(total_size)}")
        print(f"{'='*80}\n")
    
    def export_json(self, summary: Dict[str, Any], output_path: Optional[str] = None):
        """
        Export summary as JSON.
        
        Args:
            summary: Summary dict from inspect_all()
            output_path: Optional output file path
        """
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"Summary exported to: {output_path}")
        else:
            print(json.dumps(summary, indent=2))


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Inspect Weaver AI pipeline stage artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "pipeline_id",
        help="Pipeline execution ID"
    )
    
    parser.add_argument(
        "--stage", "-s",
        type=str,
        help="Inspect specific stage only (use stage ID like 'input_acquisition')"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed artifact listings"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Export JSON to file"
    )
    
    parser.add_argument(
        "--storage-dir",
        default="storage",
        help="Base storage directory (default: storage)"
    )
    
    args = parser.parse_args()
    
    try:
        inspector = ArtifactInspector(args.pipeline_id, args.storage_dir)
        
        if args.stage is not None:
            # Inspect single stage
            summary = {
                "pipeline_id": args.pipeline_id,
                "stages": {args.stage: inspector.inspect_stage(args.stage)}
            }
        else:
            # Inspect all stages
            summary = inspector.inspect_all()
        
        if args.json or args.output:
            inspector.export_json(summary, args.output)
        else:
            inspector.print_summary(summary, args.verbose)
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
