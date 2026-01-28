# Artifact Storage Structure

## Overview

The Weaver AI pipeline stores artifacts from each stage in a standardized directory structure to ensure reproducibility, debugging, and audit trails for manufacturing validation.

## Directory Structure

```
storage/
└── <pipeline_id>/
    ├── stage_0/                    # Input Acquisition
    │   ├── input_descriptor.json   # Validated input metadata
    │   └── stage_metadata.json     # Complete stage execution record
    │
    ├── stage_1/                    # Canonical Normalization
    │   ├── canonical_raster.npy    # Normalized pixel array (H×W×3 RGB uint8)
    │   ├── canonical_raster_metadata.json  # Raster specifications
    │   ├── canonical_preview.png   # Visual preview of normalized image
    │   └── stage_metadata.json     # Normalization transformations & metrics
    │
    ├── stage_2/                    # Structural Intent Definition
    │   ├── edge_map.png           # Binary edge map
    │   ├── skeleton_map.png       # 1-pixel skeleton topology
    │   ├── repeat_boundary_mask.png  # Repeat unit boundaries
    │   ├── region_masks/          # Individual region masks
    │   │   ├── region_000.png
    │   │   ├── region_001.png
    │   │   └── ...
    │   ├── structural_metadata.json  # Geometry contract
    │   └── stage_metadata.json    # Complete structural analysis
    │
    └── stage_N/                   # Future stages (3-7)
        └── ...
```

## Stage 0: Input Acquisition

### Artifacts

- **`input_descriptor.json`**: Immutable source of truth
  - Raw image hash (SHA-256)
  - Validated dimensions, DPI, color mode
  - Repeat unit specifications
  - File format and bit depth

- **`stage_metadata.json`**: Execution record
  - All validation results (format, metadata, dimensions, repeat integrity)
  - Resource checks and constraints
  - Source seal cryptographic proof
  - Validation metrics

### Purpose
Establishes the immutable design source of truth. All downstream stages reference this descriptor for dimensional accuracy and manufacturing trust.

## Stage 1: Canonical Normalization

### Artifacts

- **`canonical_raster.npy`**: NumPy array (H×W×3)
  - Format: RGB uint8
  - DPI: Canonical (300 DPI default)
  - Color space: sRGB, ICC profiles stripped
  - Orientation: EXIF-corrected

- **`canonical_raster_metadata.json`**: Raster specifications
  - Dimensions (width, height)
  - Color mode and bit depth
  - Repeat unit at canonical DPI
  - Storage type (in-memory vs file)

- **`canonical_preview.png`**: Visual reference
  - Lossless PNG preview
  - Human-readable visualization

- **`stage_metadata.json`**: Transformation record
  - Original vs canonical dimensions
  - Applied transformations (DPI rescaling, color conversion, etc.)
  - Normalization config (alpha policy, ICC strip, resampling method)
  - Tile counts and metrics
  - Processing times

### Purpose
Provides deterministic, unambiguous representation for downstream geometric analysis. Eliminates orientation, color space, and DPI ambiguities.

## Stage 2: Structural Intent Definition

### Artifacts

- **`edge_map.png`**: Binary edge detection
  - Canny edges showing all motif boundaries
  - Black/white (0/255) binary format

- **`skeleton_map.png`**: Topological skeleton
  - 1-pixel wide medial axis
  - Validated graph connectivity

- **`repeat_boundary_mask.png`**: Repeat constraints
  - Immutable boundary edges
  - Locked for downstream stages

- **`region_masks/`**: Segmented regions
  - One PNG per closed region
  - Non-overlapping, fully enclosed

- **`structural_metadata.json`**: Geometry contract
  - Edge counts, skeleton topology stats
  - Region count and validation
  - Explicit guarantees for downstream stages

- **`stage_metadata.json`**: Analysis record
  - Input dimensions and DPI
  - Processing configuration (Canny thresholds, etc.)
  - Complete structural analysis
  - Artifact paths and metrics

### Purpose
Locks geometric invariants (edges, topology, regions) that must be preserved through all downstream transformations. Provides explicit contracts for manufacturing validation.

## Usage

### Accessing Artifacts

```python
from pathlib import Path

# Get stage artifacts
pipeline_id = "550e8400-e29b-41d4-a716-446655440000"
stage_0_dir = Path("storage") / pipeline_id / "stage_0"

# Load input descriptor
import json
with open(stage_0_dir / "input_descriptor.json") as f:
    descriptor = json.load(f)

# Load canonical raster
import numpy as np
stage_1_dir = Path("storage") / pipeline_id / "stage_1"
raster = np.load(stage_1_dir / "canonical_raster.npy")

# Load structural metadata
stage_2_dir = Path("storage") / pipeline_id / "stage_2"
with open(stage_2_dir / "structural_metadata.json") as f:
    structure = json.load(f)
```

### Artifact Guarantees

1. **Immutability**: Stage artifacts are never modified after creation
2. **Completeness**: All intermediate data preserved for debugging
3. **Traceability**: Pipeline ID links all stages
4. **Reproducibility**: Complete execution record in `stage_metadata.json`
5. **Manufacturing Trust**: Cryptographic hashes and validation proofs

## Storage Management

### Cleanup Policy

- **Development**: Retain all artifacts for debugging
- **Production**: Implement retention policy based on:
  - Manufacturing completion status
  - Audit requirements
  - Storage capacity

### Disk Usage

Typical storage per pipeline:
- Stage 0: ~10 KB (metadata only)
- Stage 1: ~Image size × 3 (RGB array + metadata + preview)
- Stage 2: ~Image size × 2 (edge maps + regions + metadata)

Example: 2000×2000 pixel image @ 300 DPI
- Raw input: ~12 MB (PNG)
- Stage 0: 10 KB
- Stage 1: ~40 MB (raster + preview)
- Stage 2: ~25 MB (maps + regions)
- **Total: ~77 MB per pipeline**

### Archival

For long-term storage, compress stage artifacts:
```bash
# Archive completed pipeline
tar -czf pipeline_${PIPELINE_ID}.tar.gz storage/${PIPELINE_ID}/

# Extract for analysis
tar -xzf pipeline_${PIPELINE_ID}.tar.gz
```

## Best Practices

1. **Always preserve Stage 0 artifacts**: Source of truth for manufacturing
2. **Include pipeline_id in all logs**: Enable artifact correlation
3. **Validate artifacts before deletion**: Ensure downstream stages completed
4. **Use stage_metadata.json for debugging**: Complete execution record
5. **Monitor storage growth**: Implement cleanup for failed/abandoned pipelines

## Future Enhancements

- Artifact compression (lossless)
- Cloud storage integration (S3, Azure Blob)
- Artifact versioning and rollback
- Distributed storage for large-scale manufacturing
- Real-time artifact streaming for monitoring
