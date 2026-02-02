# Stage Developer Guide

## Overview

**Version**: 2.0.0 - Modular Architecture

This guide explains how to implement a pipeline stage for the Weaver AI Diffusion Fabric Designer. Each stage is an independent module that processes design data according to specific manufacturing constraints.

**Architecture Evolution**: v2.0 introduces a modular, result-based pipeline where stages pass frozen Pydantic result objects (not mutable input schemas) and receive configuration as plain dictionaries.

## Development Environment Setup

### Installing UV Package Manager

This project uses [UV](https://github.com/astral-sh/uv), a fast Python package manager:

```bash
# On Unix/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Project Setup

**Note:** This project is already initialized with `pyproject.toml`. You don't need `uv init`.

```bash
# Clone the repository
git clone <repository-url>
cd weaver-ai

# Install project (UV reads pyproject.toml automatically)
uv sync

# Or manually:
# 1. Create virtual environment
uv venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Unix/macOS:
source .venv/bin/activate

# Install project with all dependencies
uv sync

# Or install with specific extras
uv pip install -e ".[dev]"

# Install everything (dev + ai + docs)
uv pip install -e ".[dev,ai,docs]"
```

## Stage Contract

Every stage must implement the `BaseStage` interface defined in `src/weaver/diffusion/stages/base_stage.py`.

### v2.0 Architecture: Result-Based Pipeline

**Key Changes from v1.0**:
- **No Input Schemas**: Stages accept `prev_result: Optional[StageResult]` and `config: dict`, not Pydantic input models
- **Frozen Result Objects**: Stages return immutable Pydantic result objects that freeze execution state
- **File-Based Storage**: Each result automatically saves to `storage/{pipeline_id}/stage_{N}_result.json`
- **Template Method Pattern**: Override `_execute()`, not `execute()` (automatic validation + saving)

### Required Components

1. **Stage Metadata** - Descriptive information (stage_id, name, description, version)
2. **Result Schema** - Pydantic model extending `StageResult` (frozen, immutable)
3. **`validate_input()` Method** - Validate prev_result and config before execution
4. **`_execute()` Method** - Core processing logic (template method pattern)
5. **`metadata` Property** - Returns StageMetadata instance

## Implementation Template

```python
from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages.stage_result import StageResult
from weaver.shared.exceptions import ValidationError
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Define your result schema (frozen, immutable)
class StageXResult(StageResult):
    """Result schema for Stage X."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    # Add stage-specific fields
    processed_data: dict = Field(..., description="Processed data")
    metrics: dict = Field(default_factory=dict, description="Processing metrics")

# Implement your stage
class StageXProcessor(BaseStage):
    """
    Stage X: Your Stage Name
    
    Brief description of what this stage does.
    
    VERSION: 2.0.0
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_id="stage_x_name",  # lowercase_with_underscores
            name="Your Stage Name",
            description="Detailed description",
            version="2.0.0"
        )
    
    def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
        """
        Validate previous result and config before execution.
        
        Args:
            prev_result: Result from previous stage (or None for Stage 0)
            config: Pipeline configuration dictionary
        
        Raises:
            TypeError: If prev_result is wrong type
            ValueError: If config is missing required keys
            ValidationError: If data validation fails
        """
        # For Stage 0, prev_result should be None
        if self.metadata.stage_id == "input_acquisition":
            if prev_result is not None:
                raise ValueError("Stage 0 expects prev_result=None")
            # Validate config has required fields
            if 'source_file' not in config:
                raise ValueError("Config missing 'source_file'")
        else:
            # For other stages, validate prev_result type
            if prev_result is None:
                raise ValueError(f"{self.metadata.name} requires previous stage result")
            # Add stage-specific validation here
    
    def _execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> StageXResult:
        """
        Execute stage processing (internal implementation).
        
        NOTE: This method is called by execute() after validation.
        Do not override execute() - override this method instead.
        
        Args:
            prev_result: Validated result from previous stage
            pipeline_id: Unique pipeline execution ID
            config: Pipeline configuration dictionary
        
        Returns:
            Stage result (automatically saved to JSON)
        
        Raises:
            ValidationError: If processing fails validation
            StageError: If execution fails
        """
        # Extract data from prev_result (if not Stage 0)
        if prev_result is not None:
            prev_data = prev_result.model_dump()
            # Access previous stage's output...
        
        # Extract config parameters
        param1 = config.get('param1', default_value)
        
        # Your implementation here
        processed_data = self._process_data(prev_result, config)
        
        # Return frozen result
        return StageXResult(
            stage_metadata={
                "stage_number": X,
                "stage_id": self.metadata.stage_id,
                "stage_name": self.metadata.name,
                "pipeline_id": pipeline_id
            },
            processed_data=processed_data,
            metrics={"duration_ms": 100}
        )
```

## Stage-Specific Guidelines

### Stage 0: Input Acquisition

**Version**: 2.0.0 - Modular Architecture

**Responsibility**: RAW DESIGN SOURCE OF TRUTH - Fast-fail validation of raw input

**Architecture**: 8 specialized sub-modules in linear pipeline:
1. `pre_decode_guard` - File size check (OOM protection)
2. `image_decoder` - PIL decode and metadata extraction
3. `format_validator` - Lossless format allowlist (PNG, TIFF, BMP)
4. `metadata_validator` - Declared vs actual consistency
5. `dimension_validator` - Manufacturing limit checks
6. `repeat_validator` - Perfect tiling verification
7. `resource_guard` - Post-decode resource protection
8. `source_sealer` - SHA-256 hash for immutability proof

**Config Parameters**:
- `source_file: str` - Path to design file (required)
- `dpi: int` - Declared DPI (default: 300)
- `repeat_unit: dict` - Repeat dimensions `{width: int, height: int}`
- `color_mode: str` - Color mode (default: 'RGB')

**Result Output** (`InputAcquisitionResult`):
- `input_descriptor: dict` - Complete input metadata bundle
- `source_seal: str` - SHA-256 hash of source image
- `validation_summary: dict` - Pass/fail status for each sub-module

**Failure Conditions** (ZERO TOLERANCE):
- Unsupported file format (no JPEG, WebP, HEIC)
- Metadata inconsistency (declared DPI ≠ actual DPI)
- Dimensions exceed manufacturing limits
- Non-integer tiling (partial repeats)
- File not found or corrupted
- OOM risk (file size > 50MB or pixel count > 100M)

---

### Stage 1: Canonical Normalization

**Version**: 2.0.0 - Modular Architecture

**Responsibility**: Standardize raster to canonical format for downstream processing

**Architecture**: 6 specialized sub-modules:
1. `OrientationNormalizer` - EXIF rotation correction
2. `ColorSpaceNormalizer` - RGB conversion (RGBA → RGB, P → RGB)
3. `DPICanonicalizer` - DPI resampling to canonical 300 DPI
4. `GridNormalizer` - Repeat-aware scaling to integer dimensions
5. `RasterEmitter` - Final raster packaging
6. `Post-Validation` - Output contract verification

**Config Parameters**:
- `canonical_dpi: int` - Target DPI (default: 300)
- `alpha_policy: str` - Alpha channel handling: 'discard' or 'flatten'
- `strip_icc_profile: bool` - Remove ICC color profiles (default: true)
- `resampling_method: str` - Pillow resampling method (default: 'LANCZOS')

**Result Output** (`CanonicalNormalizationResult`):
- `canonical_image: PIL.Image` - Normalized RGB image at 300 DPI
- `scaling_factors: dict` - Applied transformations `{dpi_scale, repeat_scale}`
- `normalization_log: dict` - Per-module execution log

**Guarantees** (Output Contract):
- RGB color mode (8-bit per channel)
- Canonical DPI (300 DPI)
- Integer repeat dimensions
- No ICC profiles
- Deterministic output (same input → same output)

**Failure Conditions**:
- Color space conversion failure
- Resampling produces non-integer dimensions
- Output validation fails

---

### Stage 2: Structural Intent Extraction

**Version**: 2.0.0 - Compiler IR Paradigm

**Responsibility**: Extract symbolic "Compiler IR" from raster - resolution-independent representation

**Paradigm Shift**: v2.0 outputs symbolic representation (motif graph), not pixel artifacts

**Symbolic IR Components**:
1. **Motif Graph** - Nodes (strokes, junctions, islands) + Edges (connectivity)
2. **Topology** - Connected component analysis with explicit 5-point contract:
   - `topology_well_formed=True` guarantees:
     - No self-loops in the graph
     - No duplicate edges between same node pairs
     - All non-NOISE_CANDIDATE nodes have degree >= 1
     - Graph connectivity matches component_count
     - Junction types are consistently classified
3. **Curve Intent** - Per-motif curve complexity `{low, medium, high}`
4. **Pattern Intent** - Discriminated pattern detection:
   - `pattern_type`: Literal["REFLECTION", "ROTATIONAL", "TRANSLATIONAL", "REPETITION", "NONE"]
   - Each pattern_type has specific required parameters (discriminated union)
   - Prevents incoherent pattern objects (e.g., REFLECTION with tile_size)
5. **Structural Masks** - Symbolic region descriptors (NOT raster masks):
   - `mask_type`: Literal["FOREGROUND_STRUCTURE", "ORNAMENTAL_FILL", "NEGATIVE_SPACE", "BORDER_EMPHASIS"]
   - `representation`: Literal["VECTOR_REGION", "PROBABILITY_FIELD"]
   - Debug visualizations may show raster, but IR is symbolic
6. **Constraints** - Repeat boundary conditions, closure validation
7. **Uncertainty** - Low-confidence elements (skeleton islands flagged as NOISE_CANDIDATE role)

**Config Parameters**:
- `canny_low: int` - Canny low threshold (default: 50)
- `canny_high: int` - Canny high threshold (default: 150)
- `min_island_size: int` - Minimum island pixels to keep (default: 10)
- `symmetry_detection: str` - Symmetry mode: 'full', 'basic', 'off'
- `topology_analysis: bool` - Enable topology graph (default: true)
- `curve_complexity_threshold: float` - Complexity classification threshold

**Result Output** (`StructuralIntentResult`):
- `motif_nodes: list[MotifNode]` - Symbolic nodes (TYPE, position, scale, confidence)
- `motif_edges: list[MotifEdge]` - Connectivity graph
- `topology: dict` - Graph topology metrics
- `curve_intents: dict` - Per-motif curve complexity
- `pattern_intents: dict` - Detected symmetries
- `structural_masks: dict` - Debugging masks (edge_map, skeleton_map, region_masks)
- `constraints: dict` - Boundary closure, repeat validation

**Key Features**:
- Resolution-independent output (no pixel coordinates as truth)
- Skeleton islands preserved as low-confidence nodes with NOISE_CANDIDATE role
- KD-tree spatial indexing for junction-stroke matching
- Explicit uncertainty tracking
- **CRITICAL CONTRACT**: No field represents absolute pixel geometry or raster truth - all spatial info normalized to [0,1]

**Failure Conditions**:
- Edge detection produces no edges
- Skeletonization fails
- Topology validation fails (non-closed boundaries)

---

### Stage 3: Controlled Diffusion Refinement

**Version**: 2.0.0 (Planned)

**Responsibility**: AI-powered geometry refinement with structural guidance

**Status**: Implementation in progress

**Key Tasks**:
- Initialize Stable Diffusion + ControlNet
- Apply structural guidance from Stage 2 symbolic IR
- Refine geometry while preserving topology
- Verify no motifs added/removed

**Config Parameters** (Planned):
- `model_id: str` - Diffusion model identifier
- `denoise_strength: float` - Refinement intensity (0.2-0.4)
- `controlnet_conditioning_scale: float` - Guidance strength
- `guidance_scale: float` - Classifier-free guidance

**Result Output** (Planned):
- Refined raster image
- Diffusion metrics (steps, guidance used)
- Topology preservation validation

**Constraints**:
- Motif topology unchanged (verified against Stage 2 motif graph)
- Low denoise strength (0.2-0.4) to preserve structural intent
- ControlNet guidance from Stage 2 structural masks

**Note**: This is the most complex stage and requires GPU resources.

---

### Stage 4: Repeat & Boundary Enforcement

**Version**: 2.0.0 (Planned)

**Responsibility**: Guarantee perfect infinite tiling

**Key Tasks**:
- Check left/right border equality (pixel-perfect)
- Check top/bottom border equality (pixel-perfect)
- Calculate XOR difference (must be 0)
- Fix wrap-around misalignments using blend/stitch algorithms

**Config Parameters** (Planned):
- `border_tolerance: int` - Maximum pixel difference (default: 0)
- `repair_method: str` - 'blend', 'stitch', or 'fail'
- `blend_width: int` - Blending zone width in pixels

**Result Output** (Planned):
- Tiling-validated image
- Border equality metrics
- Repair operations applied

**Invariant** (Mathematical):
- `XOR(left_border, right_border) == 0` (pixel-wise)
- `XOR(top_border, bottom_border) == 0` (pixel-wise)

**Failure Conditions**:
- Border mismatch exceeds tolerance
- Repair algorithm fails to achieve perfect tiling

---

### Stage 5: Manufacturing Geometry Cleanup

**Version**: 2.0.0 (Planned)

**Responsibility**: Create weaveable geometry conforming to loom constraints

**Key Tasks**:
- Apply minimum line width (2px minimum for jacquard looms)
- Remove isolated pixels (noise)
- Morphological operations (opening, closing)
- Thread-safe feature validation

**Config Parameters** (Planned):
- `min_line_width: int` - Minimum thread width in pixels (default: 2)
- `remove_isolated: bool` - Remove single-pixel islands (default: true)
- `morphology_operations: list[str]` - Cleanup operations to apply

**Result Output** (Planned):
- Cleaned geometry image
- Removed feature count
- Cleanup operation log

**Constraints**:
- All features ≥ minimum width
- No isolated islands (< min_island_size)
- Loom resolution compatible

---

### Stage 6: Color & Thread Constraint Enforcement

**Version**: 2.0.0 (Planned)

**Responsibility**: Lock design to loom capacity (color count, yarn mapping)

**Key Tasks**:
- Map to indexed color palette
- Remove anti-aliasing (convert to nearest palette color)
- Enforce max color count (16 for jacquard looms)
- Map colors to physical yarn palette

**Config Parameters** (Planned):
- `max_colors: int` - Maximum color count (default: 16)
- `yarn_palette: list[dict]` - Physical yarn specifications
- `dither_method: str` - Dithering algorithm (default: 'none')

**Result Output** (Planned):
- Indexed color image
- Color mapping table (palette index → yarn ID)
- Color reduction metrics

**Constraints**:
- Maximum 16 colors (jacquard loom limit)
- No gradients or anti-aliasing
- Colors map to physical yarns (RGB → yarn ID)

---

### Stage 7: Pre-CAM Validation Firewall

**Version**: 2.0.0 (Planned)

**Responsibility**: Final compliance audit (zero tolerance)

**Key Tasks**:
- Validate ALL manufacturing rules
- Check repeat dimensions (integer tiling)
- Verify color count ≤ max_colors
- Validate minimum feature sizes
- Generate diagnostic report
- Return PASS/FAIL verdict

**Config Parameters** (Planned):
- `validation_rules: list[str]` - Rules to enforce
- `tolerance: dict` - Per-rule tolerances
- `generate_report: bool` - Create detailed PDF report

**Result Output** (Planned):
- `verdict: Literal["PASS", "FAIL"]` - Final compliance verdict
- Detailed validation report (per-rule status)
- CAM-ready file (if PASS)
- Violation details (if FAIL)

**Invariant**:
- No violations allowed (zero tolerance)
- Detailed error reporting for any failure

**Output Artifacts** (if PASS):
- CAM-ready PNG/TIFF file
- Manufacturing specification JSON
- Compliance certificate

## Best Practices

### 1. Error Handling

```python
from weaver.shared.exceptions import ValidationError, StageError

def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
    """Validate inputs before execution."""
    # Validate prev_result type
    if prev_result is not None:
        if not isinstance(prev_result, ExpectedResultType):
            raise TypeError(
                f"Expected {ExpectedResultType.__name__}, got {type(prev_result).__name__}"
            )
    
    # Validate config has required keys
    required_keys = ['param1', 'param2']
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")

def _execute(self, prev_result, pipeline_id, config):
    """Execute with error handling."""
    try:
        result = self._process(prev_result, config)
    except Exception as e:
        raise StageError(
            f"Processing failed: {str(e)}",
            stage_id=self.metadata.stage_id
        ) from e
    
    return result
```

### 2. Logging

```python
from weaver.shared.logger import get_logger

logger = get_logger(__name__)

def _execute(self, prev_result, pipeline_id, config):
    """Execute with comprehensive logging."""
    logger.info(
        f"Stage {self.metadata.stage_id} starting",
        extra={
            "pipeline_id": pipeline_id,
            "stage_id": self.metadata.stage_id
        }
    )
    
    # Process with step logging
    logger.debug("Step 1/3: Preprocessing")
    # ...
    
    logger.info(
        f"Stage {self.metadata.stage_id} completed",
        extra={
            "pipeline_id": pipeline_id,
            "stage_id": self.metadata.stage_id,
            "duration_ms": duration
        }
    )
```

### 3. Configuration

Configuration is passed as a dictionary to `_execute()`. Load stage-specific config from `config/pipeline.yaml`:

```python
import yaml
from pathlib import Path

def _execute(self, prev_result, pipeline_id, config):
    """Extract config parameters."""
    # Get stage-specific config from pipeline.yaml
    stage_config = config.get(self.metadata.stage_id, {})
    
    # Extract parameters with defaults
    param1 = stage_config.get('param1', default_value)
    param2 = stage_config.get('param2', default_value)
    
    # Or extract from root config
    source_file = config.get('source_file')
    
    # Use parameters...
```

### 4. Testing

Create comprehensive tests in `tests/stages/test_{stage_name}.py`:

```python
import pytest
from pathlib import Path
from weaver.diffusion.stages.{stage_name}.processor import {StageProcessor}, {StageResult}
from weaver.diffusion.stages.stage_result import StageResult

def test_stage_x_basic_execution():
    """Test basic stage execution."""
    stage = StageXProcessor()
    
    # Mock previous result
    prev_result = MockPreviousResult(
        stage_metadata={"stage_number": X-1, "pipeline_id": "test-123"}
    )
    
    config = {
        'param1': 'value1',
        'param2': 100
    }
    
    result = stage.execute(prev_result, "test-123", config)
    
    assert isinstance(result, StageXResult)
    assert result.stage_metadata['stage_number'] == X
    assert result.stage_metadata['pipeline_id'] == "test-123"

def test_stage_x_validation_failure():
    """Test validation failure."""
    stage = StageXProcessor()
    
    # Invalid prev_result type
    invalid_prev = {"invalid": "data"}
    config = {'param1': 'value1'}
    
    with pytest.raises(TypeError):
        stage.execute(invalid_prev, "test-123", config)

def test_stage_x_missing_config():
    """Test missing config parameter."""
    stage = StageXProcessor()
    prev_result = MockPreviousResult()
    
    # Missing required config key
    config = {}  # Missing 'param1'
    
    with pytest.raises(ValueError, match="missing required keys"):
        stage.execute(prev_result, "test-123", config)
```

## Integration Checklist

Before submitting your stage implementation:

- [ ] Inherits from `BaseStage`
- [ ] Implements `metadata` property (returns `StageMetadata`)
- [ ] Defines result schema (extends `StageResult`, frozen=True)
- [ ] Implements `validate_input(prev_result, config)` method
- [ ] Implements `_execute(prev_result, pipeline_id, config)` method (not `execute()`)
- [ ] Returns frozen Pydantic result object
- [ ] Result includes `stage_metadata` dict with stage_number, stage_id, pipeline_id
- [ ] Includes comprehensive docstrings
- [ ] Handles errors properly (ValidationError, StageError)
- [ ] Includes logging (info, debug, error levels)
- [ ] Accepts config as plain dict (not Pydantic schema)
- [ ] Has unit tests (>80% coverage)
- [ ] Has integration tests
- [ ] Located in `src/weaver/diffusion/stages/{stage_name}/processor.py`
- [ ] Documents stage in `docs/STAGE_{N}_{NAME}.md`
- [ ] Passes mypy type checking
- [ ] Follows code style (black, isort)

## Common Issues

### Issue: Stage not loading

**Solution**: Ensure class name matches the expected pattern in stage loader. Check:
```python
# Class should be named: {StageName}Stage or {StageName}Processor
# Example:
class InputAcquisitionStage(BaseStage):  # Correct
    pass

class Stage0InputAcquisition(BaseStage):  # Also correct
    pass
```

### Issue: Contract validation failing

**Solution**: Ensure result extends `StageResult` and is frozen:
```python
from weaver.diffusion.stages.stage_result import StageResult
from pydantic import ConfigDict

class StageXResult(StageResult):
    model_config = ConfigDict(frozen=True, extra="forbid")  # Must be frozen
    # ... fields
```

### Issue: Pipeline halts at stage

**Solution**: Check logs for exceptions. Ensure:
- `_execute()` returns a proper result object (not None)
- Result includes `stage_metadata` dict
- No unhandled exceptions raised
- Result is a frozen Pydantic model
- Result saved to `storage/{pipeline_id}/stage_{N}_result.json`

### Issue: "AttributeError: 'dict' object has no attribute 'model_dump'"

**Solution**: You're passing a dict instead of a StageResult. Ensure previous stage returns proper result object:
```python
# Wrong:
return {"data": "value"}  # Plain dict

# Correct:
return StageXResult(
    stage_metadata={...},
    data="value"
)  # Pydantic model
```

### Issue: "TypeError: execute() takes 2 positional arguments but 4 were given"

**Solution**: You overrode `execute()` instead of `_execute()`. The template method pattern requires:
```python
# Wrong:
def execute(self, input_data):  # Old v1.0 signature
    pass

# Correct:
def _execute(self, prev_result, pipeline_id, config):  # v2.0 signature
    pass
```

## Questions?

See the architecture document or contact the orchestrator maintainer.
