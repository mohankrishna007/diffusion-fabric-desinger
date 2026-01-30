# Stage Result JSON Serialization

## Overview

All pipeline stages now automatically save their complete results to JSON files. The result JSON includes all metadata, so there's no need for separate stage_metadata files.

## Features

### 1. Automatic JSON Saving
- **Where**: `storage/{pipeline_id}/stage_{stage_number}_result.json`
- **When**: After every stage execution (via `BaseStage.execute()`)
- **Format**: Pretty-printed JSON with 2-space indentation

### 2. Result Methods (All Stage Results)

```python
# Serialize to JSON string
json_str = result.to_json(indent=2)

# Convert to dictionary
data_dict = result.to_dict()

# Save to file
result.save_json('path/to/result.json', indent=2)

# Load from JSON string
result = StructuralIntentResult.from_json(json_str)

# Load from file
result = StructuralIntentResult.load_json('path/to/result.json')
```

### 3. Inspection Utility (`inspect_results.py`)

```bash
# List all pipeline results
python inspect_results.py

# Inspect specific stage result
python inspect_results.py <pipeline_id> <stage_number>

# Example
python inspect_results.py dd249e7e-bde5-4b73-b851-03f9faacbe06 2
```

## What's Included in JSON

Each stage result JSON contains:

### All Stages
- `pipeline_id`: Unique execution ID
- `stage_metadata`: Complete stage information
  - `stage_number`: Stage index (0-7)
  - `stage_name`: Human-readable name
  - `status`: Execution status
  - `pipeline_id`: Pipeline reference
  - Stage-specific configuration and statistics

### Stage 2 (Structural Intent) Specifics
- `motif_nodes[]`: All graph nodes with properties
- `motif_edges[]`: All graph edges with relationships
- `topology`: Component/junction/loop statistics
- `geometry_intent[]`: Curve classifications
- `pattern_intent[]`: Symmetry/repetition patterns
- `structural_masks[]`: Region masks
- `constraints[]`: Design constraints
- `uncertainty[]`: Ambiguous decisions
- `guarantees[]`: Contract promises
- Reference dimensions (width, height, dpi, repeat unit)

## Benefits

1. **Complete Traceability**: Every stage result is persisted
2. **Debugging**: Inspect intermediate results without re-running pipeline
3. **Human-Readable**: Pretty-printed JSON for easy inspection
4. **No Redundancy**: No separate metadata files needed
5. **Automatic**: No manual saving code in stage processors
6. **Universal**: Works for all stages via base class

## Example Output Structure

```
storage/
├── dd249e7e-bde5-4b73-b851-03f9faacbe06/
│   ├── stage_0_result.json    # Input Acquisition
│   ├── stage_1_result.json    # Canonical Normalization
│   └── stage_2_result.json    # Structural Intent
└── test-stage2-basic-001/
    └── stage_2_result.json
```

## File Sizes

Stage 2 results can be large due to the comprehensive graph representation:
- Simple test (512x512): ~6.5 MB
- Complex pattern (392x392): ~145 MB

This is expected because the JSON contains:
- Thousands of motif nodes with full properties
- Hundreds of thousands of edges with relationships
- Complete uncertainty records
- All curve intents and pattern data

## Implementation Notes

- **Base Class**: `BaseStage.execute()` handles automatic saving
- **Error Handling**: Failures to save JSON are logged as warnings (non-blocking)
- **Storage Location**: `storage/{pipeline_id}/` directory
- **File Naming**: `stage_{stage_number}_result.json`
- **Pydantic Models**: All results use Pydantic for validation and serialization
