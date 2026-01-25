# Diffusion Fabric Designer

An AI-powered, constraint-driven pipeline system for transforming fabric design images into loom-compatible, CAM-ready outputs using Stable Diffusion + ControlNet under strict manufacturing constraints.

## Overview

This system implements an 8-stage industrial transformation pipeline:

- **Stage 0**: Input Acquisition - Fast-fail validation of raw design input
- **Stage 1**: Canonical Normalization - Standardizing data for processing
- **Stage 2**: Structural Intent Definition - Encoding geometric invariants
- **Stage 3**: Controlled Diffusion Refinement - AI-powered geometry refinement
- **Stage 4**: Repeat & Boundary Enforcement - Guaranteeing perfect tiling
- **Stage 5**: Manufacturing Geometry Cleanup - Creating weaveable geometry
- **Stage 6**: Color & Thread Constraint Enforcement - Loom capacity compliance
- **Stage 7**: Pre-CAM Validation Firewall - Final hardware compliance audit

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI REST API                     │
│  POST /api/v1/pipeline/execute                          │
│  GET  /api/v1/pipeline/status/{id}                      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Pipeline Orchestrator                       │
│  - Stage loader                                         │
│  - Contract validator                                   │
│  - Sequential execution engine                          │
└────────────────────┬────────────────────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       │                           │
┌──────▼──────┐           ┌────────▼────────┐
│  Stage 0-7  │    ...    │    Stage 7      │
│  Processor  │           │    Processor    │
└─────────────┘           └─────────────────┘
```

## Project Structure

```
weaver-ai/
├── src/weaver/
│   ├── api/                    # FastAPI application
│   │   ├── main.py            # App entry point
│   │   └── routes/            # API endpoints
│   ├── orchestrator/          # Pipeline execution engine
│   │   ├── pipeline_engine.py # Main orchestrator
│   │   └── stage_loader.py    # Dynamic stage loading
│   ├── stages/                # Stage implementations
│   │   ├── base.py           # BaseStage contract
│   │   ├── stage_0_input_acquisition/
│   │   ├── stage_1_canonical_normalization/
│   │   ├── stage_2_structural_intent/
│   │   ├── stage_3_diffusion_refinement/
│   │   ├── stage_4_repeat_enforcement/
│   │   ├── stage_5_geometry_cleanup/
│   │   ├── stage_6_color_constraint/
│   │   └── stage_7_precam_validation/
│   └── shared/               # Shared utilities
│       ├── schemas.py        # Pydantic models
│       ├── exceptions.py     # Exception hierarchy
│       ├── logger.py         # Structured logging
│       └── utils.py          # Utility functions
├── config/                   # Configuration files
├── tests/                    # Test suite
└── docs/                     # Documentation
```

## Quick Start

### Automated Setup (Recommended)

**Windows PowerShell:**
```powershell
.\setup.ps1
```

**Unix/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup

**Prerequisites:**
- Python 3.10+
- [UV package manager](https://github.com/astral-sh/uv)

**Installation:**

```bash
# Install UV (if not already installed)
# Windows PowerShell:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Unix/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd diffusion-fabric-designer

# Install project with dependencies (UV handles venv automatically)
uv sync

# Or manually create venv and install:
uv venv
uv pip install -e .

# Activate virtual environment (optional - can use 'uv run' instead)
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Unix/macOS:
source .venv/bin/activate
```

**See [UV Setup Guide](docs/UV_SETUP.md) for detailed UV usage.**

**Note:** This project is already initialized. Use `uv init` only when creating new projects from scratch.

### Running the API

```bash
# Using UV run (recommended - no venv activation needed)
uv run python -m weaver.api.main

# Or with uvicorn
uv run uvicorn weaver.api.main:app --reload --host 0.0.0.0 --port 8000

# Or activate venv first, then run normally
python -m weaver.api.main
uvicorn weaver.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### API Usage

**Execute pipeline (async):**
```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "/path/to/design.bmp",
    "config": {}
  }'
```

**Check pipeline status:**
```bash
curl "http://localhost:8000/api/v1/pipeline/status/{pipeline_id}"
```

**List available stages:**
```bash
curl "http://localhost:8000/api/v1/pipeline/stages"
```

## For Stage Developers

### Implementing a Stage

Each stage must:

1. **Inherit from BaseStage**:
```python
from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput

class MyStage(BaseStage[MyInput, MyOutput]):
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=X,
            name="My Stage",
            description="What it does",
            version="1.0.0",
            author="Your Name"
        )
    
    def execute(self, input_data: MyInput) -> MyOutput:
        # Implementation here
        return MyOutput(...)
```

2. **Define input/output schemas** extending `StageInput` and `StageOutput`

3. **Implement validation hooks**:
   - `pre_execute()` - Input validation
   - `post_execute()` - Output validation

4. **Add tests** in `tests/stages/test_stage_X.py`

### Contract Rules

- Input/output must use Pydantic models
- Schemas must be frozen (immutable)
- No silent error handling - raise exceptions
- All failures must be explicit and logged
- Manufacturing constraints override all else

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific stage tests
uv run pytest tests/stages/test_stage_0.py

# Run with coverage
uv run pytest --cov=weaver tests/

# Or with activated venv:
pytest
pytest --cov=weaver tests/
```

## Configuration

Edit `config/pipeline.yaml` to adjust:
- Manufacturing constraints (min line width, max colors, etc.)
- Stage timeouts
- Image processing parameters
- AI model settings

## Development

### Code Quality

This project enforces:
- Type hints (mypy compatible)
- Pydantic validation
- Structured logging
- Exception hierarchies
- Contract-driven design

### Adding Dependencies

```bash
# Add to pyproject.toml dependencies, then:
uv pip install -e .

# Or add directly with UV and update pyproject.toml manually:
uv pip install package-name

# For development dependencies, add to [project.optional-dependencies.dev]
# then install with:
uv pip install -e ".[dev]"
```

## Architecture Principles

1. **Constraint Dominance**: Manufacturing requirements override aesthetics
2. **Explicit Contracts**: Stages communicate via defined schemas only
3. **AI as Operator**: Diffusion is a geometric tool, not a creator
4. **Loud Failures**: No silent error fixes - pipeline halts on violation
5. **Statelessness**: No implicit state sharing between stages

## License

[Your License]

## Contact

[Your Contact Information]
