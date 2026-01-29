# Diffusion Fabric Designer

> **Transform creative fabric designs into loom-ready manufacturing files using AI-powered constraint validation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![UV](https://img.shields.io/badge/uv-package%20manager-orange.svg)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 What Is This?

**Diffusion Fabric Designer** is an industrial-grade pipeline that bridges the gap between creative fabric design and manufacturing reality. It takes your design images and transforms them into loom-compatible, CAM-ready outputs while enforcing strict manufacturing constraints.

### The Problem We Solve

Traditional fabric design workflows have a critical gap:
- **Designers** create beautiful patterns in Photoshop/Illustrator
- **Manufacturing** requires precise, constraint-compliant raster files
- **Manual conversion** is time-consuming, error-prone, and inconsistent
- **AI tools** (Stable Diffusion) produce beautiful but non-manufacturable outputs

### Our Solution

A **constraint-first AI pipeline** that:
- ✅ Validates designs against loom specifications (color limits, line widths, tiling)
- ✅ Uses **Stable Diffusion + ControlNet** as a refinement tool (not a creator)
- ✅ Guarantees **pixel-perfect tiling** for seamless fabric repeats
- ✅ Enforces **zero-tolerance validation** before CAM export
- ✅ Provides **REST API** for integration with existing design tools

---

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

**Windows:**
```powershell
.\setup.ps1
```

**macOS/Linux:**
```bash
chmod +x setup.sh && ./setup.sh
```

### Option 2: Manual Setup

```bash
# 1. Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# OR
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# 2. Clone and install
git clone <your-repo-url>
cd diffusion-fabric-designer
uv sync  # Creates venv + installs everything

# 3. Run the API
uv run python -m weaver.api.main
```

**📖 API Documentation:** http://localhost:8000/docs

---

## 🎨 Streamlit UI (NEW!)

We now provide an **interactive web UI** for easy fabric design processing!

### Launch the UI

**Windows:**
```powershell
.\run_ui.ps1
```

**Linux/Mac:**
```bash
chmod +x run_ui.sh
./run_ui.sh
```

**Manual Launch:**
```bash
streamlit run src/weaver/ui/streamlit_app.py
```

### Features
- 📤 **Drag-and-drop image upload** with instant preview
- 🔍 **Auto-detect Stage 0 configs** (DPI, color mode, repeat units)
- ⚙️ **Interactive configuration editor** with real-time validation
- 🚀 **One-click pipeline execution** with progress tracking
- 📊 **Results visualization** with stage-by-stage outputs

**📘 Full UI Guide:** [docs/UI_GUIDE.md](docs/UI_GUIDE.md)

---

## ⚙️ How It Works

The pipeline processes designs through **8 sequential stages**, each enforcing specific manufacturing constraints:

```
Design Image → Stage 0 → Stage 1 → ... → Stage 7 → CAM-Ready Output
                 ↓         ↓              ↓           ↓
              Validate  Normalize    AI Refine   Final Check
```

### Pipeline Stages

| Stage | Name | Purpose |
|-------|------|---------|
| **0** | Input Acquisition | Fast-fail validation of raw design (format, metadata, dimensions) |
| **1** | Canonical Normalization | Standardize DPI, color space, and dimensions |
| **2** | Structural Intent | Extract geometric invariants (edges, skeletons, masks) |
| **3** | Diffusion Refinement | AI-powered smoothing via Stable Diffusion + ControlNet |
| **4** | Repeat Enforcement | Guarantee pixel-perfect seamless tiling |
| **5** | Geometry Cleanup | Ensure weaveable features (min line width, no islands) |
| **6** | Color Constraints | Map to loom's color palette (max 16 colors) |
| **7** | Pre-CAM Validation | Zero-tolerance manufacturing compliance check |

**Design Philosophy:**
- 🔒 **Manufacturing constraints override aesthetics** - No silent fixes
- 🎨 **AI as a tool, not a creator** - Preserves design intent
- ⚡ **Fail-fast validation** - Catches issues early
- 🔗 **Contract-driven** - Stages communicate via strict schemas

---

## 📡 API Usage

### Execute Pipeline (Asynchronous)

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "/path/to/design.bmp",
    "config": {}
  }'

# Response:
{
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Pipeline queued for execution"
}
```

### Check Pipeline Status

```bash
curl "http://localhost:8000/api/v1/pipeline/status/{pipeline_id}"

# Response:
{
  "pipeline_id": "550e8400...",
  "status": "completed",
  "current_stage": null,
  "completed_stages": [0, 1, 2, 3, 4, 5, 6, 7],
  "result": {
    "status": "PASS",
    "final_output": {...},
    "validation_report": []
  }
}
```

### List Available Stages

```bash
curl "http://localhost:8000/api/v1/pipeline/stages"
```

**📚 Full API Documentation:** http://localhost:8000/docs

---

## 👨‍💻 For Developers

### Architecture Overview

```
┌────────────────────────────────────────┐
│         FastAPI REST API               │
│  POST /execute  GET /status/{id}       │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│      Pipeline Orchestrator             │
│  • Loads stages dynamically            │
│  • Validates contracts                 │
│  • Sequential execution                │
└──────────────┬─────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼───────┐           ┌────▼───────┐
│Stage 0    │    ...    │Stage 7     │
└───────────┘           └────────────┘
```

### Project Structure

```
diffusion-fabric-designer/
├── src/weaver/
│   ├── api/                       # 🌐 REST API Layer
│   │   ├── main.py               # FastAPI app
│   │   └── routes/               # API endpoints
│   ├── ui/                       # 🎨 Streamlit UI (NEW!)
│   │   ├── streamlit_app.py     # Main UI app
│   │   ├── config_detector.py   # Auto-detect Stage 0 configs
│   │   └── pipeline_service.py  # Pipeline integration
│   ├── orchestrator/             # 🎭 Pipeline Engine
│   │   ├── pipeline_engine.py    # Sequential executor
│   │   └── stage_loader.py       # Dynamic stage loading
│   ├── stages/                   # 🔧 Processing Stages
│   │   ├── base.py              # BaseStage contract
│   │   ├── stage_0_input_acquisition/
│   │   ├── stage_1_canonical_normalization/
│   │   ├── stage_2_structural_intent/
│   │   ├── stage_3_diffusion_refinement/
│   │   ├── stage_4_repeat_enforcement/
│   │   ├── stage_5_geometry_cleanup/
│   │   ├── stage_6_color_constraint/
│   │   └── stage_7_precam_validation/
│   └── shared/                   # 📦 Shared Utilities
│       ├── schemas.py           # Pydantic models
│       ├── exceptions.py        # Error hierarchy
│       ├── logger.py            # Structured logging
│       └── utils.py             # Helper functions
├── config/
│   └── pipeline.yaml            # ⚙️ Manufacturing constraints
├── tests/                       # 🧪 Test suite
├── docs/
│   ├── UI_GUIDE.md              # 📘 Streamlit UI documentation
│   └── DEVELOPER_GUIDE.md       # 📖 Stage implementation guide
├── pyproject.toml               # 📦 Dependencies & metadata
├── run_ui.ps1 / run_ui.sh       # 🚀 Launch Streamlit UI
└── setup.ps1 / setup.sh         # 🚀 Quick setup scripts
```

---

## 🛠️ Implementing a Stage

**Each stage is developed independently** by different developers. Here's what you need:

### 1. Inherit from `BaseStage`

```python
from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput, StageStatus

class MyStageInput(StageInput):
    # Add your input fields
    image_data: bytes
    dpi: int

class MyStageOutput(StageOutput):
    # Add your output fields
    processed_data: bytes

class MyStage(BaseStage[MyStageInput, MyStageOutput]):
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=0,  # Your stage number (0-7)
            name="My Stage",
            description="What this stage does",
            version="1.0.0",
            author="Your Name"
        )
    
    def execute(self, input_data: MyStageInput) -> MyStageOutput:
        # Your implementation here
        result = process_image(input_data.image_data)
        
        return MyStageOutput(
            stage_number=0,
            status=StageStatus.COMPLETED,
            message="Processing complete",
            data={"result": result}
        )
```

### 2. Add Validation (Optional)

```python
def pre_execute(self, input_data: MyStageInput) -> None:
    """Validate input before processing."""
    if input_data.dpi < 72:
        raise ValidationError("DPI must be at least 72", stage_number=0)

def post_execute(self, output_data: MyStageOutput) -> None:
    """Validate output after processing."""
    if not output_data.data.get("result"):
        raise ValidationError("No result generated", stage_number=0)
```

### 3. Write Tests

```python
# tests/stages/test_my_stage.py
import pytest
from weaver.stages.stage_0.processor import MyStage, MyStageInput

def test_my_stage_basic():
    stage = MyStage()
    input_data = MyStageInput(
        pipeline_id="test-123",
        stage_number=0,
        image_data=b"...",
        dpi=300
    )
    output = stage.execute(input_data)
    assert output.status == StageStatus.COMPLETED
```

### 4. Update Configuration

Edit `config/pipeline.yaml`:
```yaml
stages:
  stage_0:
    name: "My Stage"
    timeout_seconds: 60
    custom_setting: value
```

**📖 Full Guide:** [Developer Documentation](docs/DEVELOPER_GUIDE.md)

---

## ⚡ Key Features

- ✅ **REST API** - Integrate with any design tool
- ✅ **Async Execution** - Queue multiple pipelines
- ✅ **Type-Safe** - Pydantic schemas + mypy validation
- ✅ **Contract-Driven** - Strict input/output validation
- ✅ **Modular** - Each stage is independently developed
- ✅ **Structured Logging** - Track every step
- ✅ **Zero-Tolerance Validation** - Manufacturing compliance guaranteed
- ✅ **UV Package Manager** - Fast, reliable dependency management

---

## 📋 Configuration

Edit `config/pipeline.yaml` to customize:

```yaml
manufacturing:
  min_line_width_pixels: 2      # Minimum weaveable line width
  max_color_count: 16           # Loom color capacity
  border_tolerance_pixels: 0    # Zero tolerance for tiling

stages:
  stage_3:  # AI Diffusion
    denoise_strength: 0.3       # Low = preserve structure
    model: "stable-diffusion-v1.5"
```

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=weaver tests/

# Run specific stage
uv run pytest tests/stages/test_stage_0.py

# Type checking
uv run mypy src/weaver
```

---

## 🏗️ Architecture Principles

1. **Constraint Dominance** - Manufacturing rules override aesthetics
2. **Explicit Contracts** - Stages communicate only via defined schemas  
3. **AI as Operator** - Diffusion refines geometry, doesn't create it
4. **Loud Failures** - No silent fixes; pipeline halts on violations
5. **Statelessness** - No implicit state sharing between stages

---

## 🤝 Contributing

1. **Fork the repository**
2. **Claim a stage** - Open an issue for stage assignment
3. **Implement** - Follow the contract in `src/weaver/stages/base.py`
4. **Test** - Write tests achieving >80% coverage
5. **Submit PR** - Include stage documentation

**See:** [Developer Guide](docs/DEVELOPER_GUIDE.md) for detailed instructions

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file

---

## 💬 Support

- **Documentation:** [Developer Guide](docs/DEVELOPER_GUIDE.md)
- **API Docs:** http://localhost:8000/docs (when running)
- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)

---

<div align="center">
  <strong>Built for Industrial Fabric Manufacturing 🧵</strong>
</div>
