# Stage Developer Guide

## Overview

This guide explains how to implement a pipeline stage for the Diffusion Fabric Designer. Each stage is an independent module that processes design data according to specific manufacturing constraints.

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

Every stage must implement the `BaseStage` interface defined in `weaver/stages/base.py`.

### Required Components

1. **Stage Metadata** - Descriptive information
2. **Input Schema** - Pydantic model extending `StageInput`
3. **Output Schema** - Pydantic model extending `StageOutput`
4. **Execute Method** - Core processing logic
5. **Validation Hooks** - Pre/post execution validation

## Implementation Template

```python
from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput, StageStatus
from weaver.shared.exceptions import ValidationError
from pydantic import Field

# Define your input schema
class StageXInput(StageInput):
    """Input schema for Stage X."""
    # Add stage-specific fields
    image_data: bytes = Field(..., description="Raw image data")
    dpi: int = Field(..., ge=1, description="Image DPI")

# Define your output schema
class StageXOutput(StageOutput):
    """Output schema for Stage X."""
    # Add stage-specific fields
    processed_image: bytes = Field(..., description="Processed image")
    metrics: dict = Field(default_factory=dict, description="Processing metrics")

# Implement your stage
class StageXProcessor(BaseStage[StageXInput, StageXOutput]):
    """
    Stage X: Your Stage Name
    
    Brief description of what this stage does.
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=X,  # 0-7
            name="Your Stage Name",
            description="Detailed description",
            version="1.0.0",
            author="Your Name"
        )
    
    def execute(self, input_data: StageXInput) -> StageXOutput:
        """
        Execute stage processing.
        
        Args:
            input_data: Validated input
        
        Returns:
            Processing output
        
        Raises:
            ValidationError: If processing fails validation
            StageError: If execution fails
        """
        # Your implementation here
        
        return StageXOutput(
            stage_number=X,
            status=StageStatus.COMPLETED,
            message="Processing complete",
            data={"result": "..."},
            metrics={"duration_ms": 100}
        )
    
    def pre_execute(self, input_data: StageXInput) -> None:
        """Pre-execution validation."""
        super().pre_execute(input_data)
        # Add custom input validation
    
    def post_execute(self, output_data: StageXOutput) -> None:
        """Post-execution validation."""
        super().post_execute(output_data)
        # Add custom output validation
```

## Stage-Specific Guidelines

### Stage 0: Input Acquisition

**Responsibility**: Fast-fail validation of raw input

**Key Tasks**:
- Load image from file
- Validate file format (BMP, PNG, TIFF)
- Extract metadata (DPI, dimensions)
- Check file size limits
- Verify image dimensions within bounds

**Input**:
- `file_path: str` - Path to design file

**Output**:
- `image_data: bytes` - Raw image bytes
- `width: int` - Image width
- `height: int` - Image height
- `dpi: int` - Image DPI
- `format: str` - File format

**Failure Conditions**:
- Unsupported file format
- Missing metadata
- Dimensions exceed limits
- File not found or corrupted

---

### Stage 1: Canonical Normalization

**Responsibility**: Standardize data for processing pipeline

**Key Tasks**:
- Convert to fixed DPI (300)
- Scale to integer repeat dimensions
- Convert to RGB color space
- Ensure deterministic output

**Input**:
- Image data from Stage 0
- Target DPI setting

**Output**:
- Normalized image data
- Scaling factors applied

**Failure Conditions**:
- Non-integer scaling required
- Color space conversion failure

---

### Stage 2: Structural Intent Definition

**Responsibility**: Encode geometric invariants

**Key Tasks**:
- Generate edge maps (Canny detection)
- Create line/skeleton maps
- Generate repeat masks
- Verify boundary closure

**Input**:
- Normalized image from Stage 1

**Output**:
- Edge map
- Skeleton map
- Repeat masks
- Structural metadata

**Constraints**:
- All motifs must be captured
- Boundaries must be closed
- No information loss

---

### Stage 3: Controlled Diffusion Refinement

**Responsibility**: AI-powered geometry refinement

**Key Tasks**:
- Initialize Stable Diffusion + ControlNet
- Apply structural guidance from Stage 2
- Refine geometry while preserving topology
- Verify no motifs added/removed

**Input**:
- Canonical image
- Structural guidance bundle

**Output**:
- Refined raster image
- Diffusion metrics

**Constraints**:
- Motif topology unchanged
- Low denoise strength (0.2-0.4)
- Preserve structural intent

**Note**: This is the most complex stage and may require GPU resources.

---

### Stage 4: Repeat & Boundary Enforcement

**Responsibility**: Guarantee perfect infinite tiling

**Key Tasks**:
- Check left/right border equality
- Check top/bottom border equality
- Calculate XOR difference (must be 0)
- Fix wrap-around misalignments

**Input**:
- Refined image from Stage 3

**Output**:
- Tiling-validated image
- Border equality metrics

**Invariant**:
- `XOR(left_border, right_border) == 0`
- `XOR(top_border, bottom_border) == 0`

---

### Stage 5: Manufacturing Geometry Cleanup

**Responsibility**: Create weaveable geometry

**Key Tasks**:
- Apply minimum line width (2px)
- Remove isolated pixels
- Morphological operations
- Thread-safe feature validation

**Input**:
- Tiled image from Stage 4
- Manufacturing constraints from config

**Output**:
- Cleaned geometry
- Removed feature count

**Constraints**:
- All features ≥ minimum width
- No isolated islands
- Loom resolution compatible

---

### Stage 6: Color & Thread Constraint Enforcement

**Responsibility**: Lock design to loom capacity

**Key Tasks**:
- Map to indexed color palette
- Remove anti-aliasing
- Enforce max color count (16)
- Map to yarn palette

**Input**:
- Cleaned geometry from Stage 5
- Yarn palette from config

**Output**:
- Indexed color image
- Color mapping table

**Constraints**:
- Maximum 16 colors
- No gradients or anti-aliasing
- Colors map to physical yarns

---

### Stage 7: Pre-CAM Validation Firewall

**Responsibility**: Final compliance audit (zero tolerance)

**Key Tasks**:
- Validate all manufacturing rules
- Check repeat dimensions
- Verify color count
- Validate minimum features
- Generate diagnostic report
- Return PASS/FAIL verdict

**Input**:
- Final design from Stage 6
- All manufacturing constraints

**Output**:
- `verdict: Literal["PASS", "FAIL"]`
- Detailed validation report
- CAM-ready file (if PASS)

**Invariant**:
- No violations allowed
- Detailed error reporting

## Best Practices

### 1. Error Handling

```python
from weaver.shared.exceptions import ValidationError, StageError

def execute(self, input_data):
    # Validate input
    if not self._validate_input(input_data):
        raise ValidationError(
            "Input validation failed",
            stage_number=self.metadata.stage_number,
            details={"reason": "..."}
        )
    
    # Process with error handling
    try:
        result = self._process(input_data)
    except Exception as e:
        raise StageError(
            f"Processing failed: {str(e)}",
            stage_number=self.metadata.stage_number
        ) from e
    
    return result
```

### 2. Logging

```python
from weaver.shared.logger import get_logger

logger = get_logger(__name__)

def execute(self, input_data):
    logger.info(f"Stage {self.metadata.stage_number} starting", 
                extra={"pipeline_id": input_data.pipeline_id})
    
    # Process...
    
    logger.info(f"Stage {self.metadata.stage_number} completed",
                extra={"pipeline_id": input_data.pipeline_id, 
                       "duration_ms": duration})
```

### 3. Configuration

Load stage config from `config/pipeline.yaml`:

```python
import yaml
from pathlib import Path

def __init__(self):
    config_path = Path("config/pipeline.yaml")
    with open(config_path) as f:
        pipeline_config = yaml.safe_load(f)
    self.config = pipeline_config["stages"][f"stage_{self.metadata.stage_number}"]
```

### 4. Testing

Create comprehensive tests in `tests/stages/test_stage_X.py`:

```python
import pytest
from weaver.stages.stage_X.processor import StageXProcessor, StageXInput

def test_stage_x_basic_execution():
    """Test basic stage execution."""
    stage = StageXProcessor()
    
    input_data = StageXInput(
        pipeline_id="test-123",
        stage_number=X,
        # ... add required fields
    )
    
    output = stage.execute(input_data)
    
    assert output.status == StageStatus.COMPLETED
    assert output.stage_number == X

def test_stage_x_validation_failure():
    """Test validation failure."""
    stage = StageXProcessor()
    
    invalid_input = StageXInput(
        pipeline_id="test-123",
        stage_number=X,
        # ... invalid data
    )
    
    with pytest.raises(ValidationError):
        stage.execute(invalid_input)
```

## Integration Checklist

Before submitting your stage implementation:

- [ ] Inherits from `BaseStage`
- [ ] Implements `metadata` property
- [ ] Defines input/output schemas
- [ ] Implements `execute()` method
- [ ] Implements validation hooks
- [ ] Includes comprehensive docstrings
- [ ] Handles errors properly
- [ ] Includes logging
- [ ] Loads config from YAML
- [ ] Has unit tests (>80% coverage)
- [ ] Has integration tests
- [ ] Documents in README
- [ ] Passes mypy type checking
- [ ] Follows code style (black, isort)

## Common Issues

### Issue: Stage not loading

**Solution**: Ensure class name matches the pattern in `stage_loader.py`:
```python
# For Stage 0
class Stage0InputAcquisition(BaseStage):
    pass
```

### Issue: Contract validation failing

**Solution**: Ensure schemas extend base classes:
```python
class StageXInput(StageInput):  # Must extend StageInput
    pass

class StageXOutput(StageOutput):  # Must extend StageOutput
    pass
```

### Issue: Pipeline halts at stage

**Solution**: Check logs for exceptions. Ensure:
- Output status is `StageStatus.COMPLETED`
- No exceptions raised
- Output schema is valid

## Questions?

See the architecture document or contact the orchestrator maintainer.
