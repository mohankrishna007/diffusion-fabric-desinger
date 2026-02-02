# Stage 0: Input Acquisition

**Version**: 2.0.0  
**Status**: Production Ready  
**Test Coverage**: 93%

## Overview

Stage 0 establishes the **raw design as the immutable source of truth** for the fabric manufacturing pipeline. It enforces manufacturing-first validation with **zero tolerance** for invalid inputs.

### Purpose

- Fast-fail validation before any processing begins
- Guarantee that all downstream stages receive valid, trustworthy input
- Prevent resource waste on designs that cannot be manufactured
- Establish cryptographic proof of input immutability (SHA-256 hash)

### Core Principle

**NO INFERENCE. NO AUTO-CORRECTION. NO WARNINGS. ONLY PASS OR FAIL.**

If Stage 0 passes, the design is guaranteed to be:
- In a lossless format that preserves thread-level precision
- Dimensionally compatible with Jacquard loom capabilities
- Perfectly tileable with declared repeat units
- Metadata-consistent and verifiable

---

## Architecture

### Manufacturing-First Design

Stage 0 treats validation as **industrial infrastructure**, not experimental code. Every constraint exists because of physical manufacturing limitations:

| Constraint | Manufacturing Rationale |
|------------|------------------------|
| **Lossless formats only** | JPEG compression destroys thread-level precision needed for CAM export |
| **Perfect tiling** | Partial repeats at boundaries cannot be woven (physically impossible) |
| **Metadata consistency** | DPI/dimension mismatches cause errors in physical fabric dimensions |
| **Dimensional limits** | Jacquard looms have fixed maximum width/height (10,000px) |
| **Resource protection** | Prevents DoS and protects downstream stages from malformed files |

### Sequential Validation Steps

Stage 0 executes **8 validation steps** in strict order with **FAIL-FAST** semantics:

```
1. Pre-Decode Guard       → File size check (OOM protection)
2. Image Decode           → PIL decodes image, extracts metadata  
3. Format Allowlist       → Reject JPEG/WEBP (lossy formats)
4. Metadata Consistency   → Declared vs actual (DPI, color mode)
5. Dimensional Checks     → Width/height/megapixels within limits
6. Repeat Integrity       → Perfect tiling (width % repeat_w == 0)
7. Resource Protection    → Post-decode pixel count validation
8. Source-of-Truth Seal   → Compute SHA-256 hash + emit result
```

Any failure at any step **immediately halts** the pipeline with a detailed exception.

---

## Input Contract

### Stage Execution API

Stage 0 is executed via the `BaseStage.execute()` method:

```python
stage.execute(
    prev_result: None,                    # Stage 0 is first (no previous result)
    pipeline_id: str,                     # Unique pipeline execution ID
    config: dict                          # Pipeline configuration
)
```

### Configuration Schema

```python
config = {
    'source_file': str | Path,            # REQUIRED: Path to raw image file
    'dpi': int,                           # Declared DPI (default: 300)
    'repeat_unit': {                      # Repeat dimensions (default: 100x100)
        'width': int,                     # > 0
        'height': int                     # > 0
    },
    'color_mode': str                     # "RGB", "RGBA", "L", "LA" (default: "RGB")
}
```

### Required Fields

Only **source_file** is strictly REQUIRED. Other fields have defaults.

- **source_file**: Must exist and be a valid file path
- **dpi**: Integer in range [72, 1200] (default: 300)
- **repeat_unit**: Both width and height > 0 (default: {width: 100, height: 100})
- **color_mode**: Must be in {"RGB", "RGBA", "L", "LA"} (default: "RGB")

**Forbidden Color Modes**:
- **"P" (palette-indexed)**: Requires palette interpretation, creates CAM ambiguity
- **"1" (1-bit)**: Bit-depth assumptions leak into downstream stages

**Rationale**: Stage 0 establishes unambiguous source of truth. Convert palette/1-bit images to RGB/L before pipeline entry.

### Allowed File Formats

**LOSSLESS ONLY**:
- ✅ `.png` - Portable Network Graphics
- ✅ `.tiff` / `.tif` - Tagged Image File Format
- ✅ `.bmp` - Bitmap

**FORBIDDEN**:
- ❌ `.jpg` / `.jpeg` - Lossy compression destroys thread precision
- ❌ `.webp` - Lossy compression (even in "lossless" mode)
- ❌ `.heic` - Lossy compression

---

## Output Contract

### Success (PASS)

```python
InputAcquisitionResult(
    pipeline_id: str,
    stage_metadata: dict,           # Complete stage metadata with validation results
    raw_hash: str,                  # SHA-256 hash (64 hex chars)
    source_seal: dict,              # Immutability proof
    image_path: str,                # Absolute resolved path
    width_px: int,                  # Validated image width
    height_px: int,                 # Validated image height
    dpi: int,                       # Validated DPI
    repeat_unit_px: dict,           # {"width": int, "height": int}
    color_mode: str,                # Validated color mode
    bit_depth: int                  # Bit depth per channel
)
```

**Stage Metadata Structure:**
```python
stage_metadata = {
    "stage_number": 0,
    "stage_name": "Input Acquisition",
    "status": "COMPLETED",
    "pipeline_id": str,
    "validation_results": {...},    # Results from each validation step
    "metrics": {
        "validation_steps_passed": 8,
        "pixel_count": int,
        "repeat_units_x": int,
        "repeat_units_y": int,
        "file_format": str,
        "file_size_bytes": int
    }
}
```

### Failure (FAIL)

No output is returned. Instead, an exception is raised:

```python
raise InputFormatError(
    message="File format '.jpg' not allowed. Only lossless formats permitted: ['.bmp', '.png', '.tiff', '.tif']",
    stage_number=0,
    details={
        "file_extension": ".jpg",
        "image_format": "JPEG",
        "allowed_formats": [".bmp", ".png", ".tiff", ".tif"],
        "rationale": "Lossy compression destroys thread-level precision needed for CAM export"
    }
)
```

---

## Validation Details

### 1. Pre-Decode Resource Guard

**Performed by**: `pre_decode_guard.validate_pre_decode_resources()`

**Checks**:
- Source file path is provided in config
- Path exists and is a valid file
- File is readable

**Exceptions**: `InputSchemaError`

This validation happens in `validate_input()` before `_execute()` runs.

---

### 2. Image Decode

**Performed by**: `image_decoder.decode_image()`

**Purpose**: File size check before PIL decode (OOM protection).

**Why this matters**:
> "PIL can allocate more than 2× decoded image size during decoding, especially for TIFF. TIFF decompression buffers can spike memory usage to 4× or more. Checking file size BEFORE decode prevents system crashes from malicious or corrupted files."

**Check**: File size must not exceed `MAX_FILE_SIZE_BYTES` (500 MB)

**Fast-fail advantage**: Uses `Path.stat()` (no full file read). Rejects before allocating decode buffers.

**Exception**: `ResourceProtectionError`

```python
details = {
    "violations": ["File size 600.0MB exceeds maximum 500MB (pre-decode check)"],
    "file_size_bytes": 629145600,
    "max_file_size": 524288000,
    "rationale": "File size check prevents OOM during decode. PIL can allocate >2x decoded size (especially TIFF). Rejecting before decode protects system resources."
}
```

This is performed by the `pre_decode_guard` module in Step 1.

---

### 3. Format Allowlist

**Performed by**: `format_validator.validate_format_allowlist()`

**Check**: File extension and PIL format must be in `LOSSLESS_INPUT_FORMATS`

**Allowed**: `.bmp`, `.png`, `.tiff`, `.tif`

**Why JPEG is forbidden**:
> "Lossy compression introduces quantization artifacts that destroy thread-level precision. CAM systems require pixel-perfect accuracy for needle positioning. A single pixel error can cause thread misalignment in physical fabric."

**Exception**: `InputFormatError`

```python
details = {
    "file_extension": ".jpg",
    "allowed_formats": [".bmp", ".png", ".tiff", ".tif"],
    "rationale": "Lossy compression destroys thread-level precision needed for CAM export"
}
```

---

### 4. Metadata Consistency

**Performed by**: `metadata_validator.validate_metadata_consistency()`

**Check**: Declared metadata matches actual image properties

**Color Mode**: Declared must exactly match image mode (RGB != RGBA)

**DPI (Format-Specific Rules)**:

**PNG & TIFF**:
- DPI metadata **MUST** be present in image file
- If missing → **FAIL** (incomplete metadata)
- If present → must match declared DPI within 1% tolerance
- Formula: `abs(declared_dpi - actual_dpi) <= max(1, declared_dpi * 0.01)`

**BMP**:
- Declared DPI is **authoritative** (BMP DPI metadata is unreliable)
- If BMP header DPI exists AND non-zero → must match declared DPI
- If BMP header DPI missing or zero → trust declared DPI (no validation)
- Rationale: BMP format often stores zero or invalid DPI values

**Why format-specific rules matter**:
> "PNG and TIFF store reliable DPI metadata that CAM systems depend on for physical dimensions. BMP DPI fields are often zero, corrupted, or absent—making declared DPI the only trustworthy source. Treating all formats identically causes false failures (BMP) or false trust (missing PNG DPI)."

**Exception**: `MetadataConsistencyError`

```python
# PNG missing DPI example
details = {
    "violations": ["DPI metadata missing in PNG file. PNG/TIFF must have embedded DPI for manufacturing trust."],
    "file_format": "PNG",
    "declared_dpi": 300,
    "actual_dpi": None,
    "rationale": "Metadata inconsistency prevents dimensional errors in physical fabric manufacturing. Format-specific rules: PNG DPI trust enforced."
}

# Color mode mismatch example
details = {
    "violations": ["Color mode mismatch: declared 'RGBA' but image is 'RGB'"],
    "file_format": "PNG",
    "declared_color_mode": "RGBA",
    "actual_color_mode": "RGB",
    "rationale": "Metadata inconsistency prevents dimensional errors in physical fabric manufacturing."
}
```

---

### 5. Dimensional Constraints

**Performed by**: `dimension_validator.validate_dimensions()`

**Check**: Image dimensions within Jacquard loom physical limits

**Limits** (from `constants.py`):
- `MAX_IMAGE_WIDTH = 10000` pixels
- `MAX_IMAGE_HEIGHT = 10000` pixels
- `MAX_MEGAPIXELS = 100` (10000 × 10000)

**Why these limits exist**:
> "Jacquard looms have fixed maximum dimensions determined by the mechanical design of the loom head. Oversized designs cannot be manufactured and must be rejected at input to prevent downstream resource waste."

**Exception**: `DimensionalConstraintError`

```python
details = {
    "violations": ["Width 12000px exceeds maximum 10000px"],
    "width_px": 12000,
    "max_width": 10000,
    "rationale": "Oversized designs exceed Jacquard loom physical limits and cannot be manufactured"
}
```

---

### 6. Repeat Integrity

**Performed by**: `repeat_validator.validate_repeat_integrity()`

**Check**: Image dimensions are integer multiples of repeat unit

**Perfect Tiling**:
```python
width_px % repeat_unit.width == 0
height_px % repeat_unit.height == 0
```

**Example**:
- ✅ 1000×800 image with 200×200 repeat = 5×4 tiles (PASS)
- ❌ 1000×800 image with 300×300 repeat = non-integer (FAIL)

**Why this is non-negotiable**:
> "Non-integer tiling creates partial repeats at boundaries, which cannot be woven. The repeat unit must tile perfectly (width % repeat_w == 0) or the design is physically impossible to manufacture."

**Exception**: `RepeatIntegrityError`

```python
details = {
    "violations": [
        "Width 1000px is not a multiple of repeat width 300px (remainder: 100px)",
        "Height 800px is not a multiple of repeat height 300px (remainder: 200px)"
    ],
    "image_width": 1000,
    "repeat_width": 300,
    "rationale": "Partial repeats at boundaries cannot be woven - design is physically impossible to manufacture"
}
```

---

### 7. Resource Protection (Post-Decode)

**Performed by**: `resource_guard.validate_resource_limits()`

**Check**: Pixel count within safe limits after successful decode

**Limits**:
- `MAX_PIXEL_COUNT = 100,000,000` pixels

**Purpose**:
> "Post-decode validation confirms actual image size. Complements pre-decode file size check. Protects downstream stages from processing images that passed file size but have extreme dimensions."

**Exception**: `ResourceProtectionError`

```python
details = {
    "violations": ["File size 550.0MB exceeds maximum 500MB"],
    "file_size_bytes": 576716800,
    "max_file_size": 524288000,
    "rationale": "Resource limits prevent DoS and protect downstream stages from processing maliciously large files"
}
```

---

### 8. Source-of-Truth Sealing

**Action**: Compute SHA-256 hash of raw image bytes

**Purpose**: Cryptographic proof of immutability. Any modification to the source image will change the hash.

**Implementation**:
```python
def _compute_image_hash(self, image_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**Result**: 64-character hexadecimal string (256 bits)

**Usage**: Downstream stages can verify input hasn't changed by recomputing hash.

---

## Exception Hierarchy

All Stage 0 exceptions extend `ValidationError` with structured `details` dict:

```
ValidationError (base)
├── InputSchemaError       → Missing/invalid required fields
├── InputFormatError       → Lossy format or decode failure
├── MetadataConsistencyError → Declared vs actual mismatch
├── DimensionalConstraintError → Exceeds loom limits
├── RepeatIntegrityError   → Non-integer tiling
└── ResourceProtectionError → File size or pixel count exceeded
```

### Exception Details Structure

Every exception includes:
```python
{
    "violations": List[str],      # Human-readable violation messages
    "rationale": str,             # Manufacturing rationale
    # + specific fields relevant to the error
}
```

---

## Usage Examples

### Basic Usage

```python
from weaver.diffusion.stages.input_acquisition.processor import InputAcquisitionStage
from pathlib import Path

# Create stage instance
stage = InputAcquisitionStage()

# Prepare configuration
config = {
    'source_file': "/path/to/design.png",
    'dpi': 300,
    'repeat_unit': {'width': 200, 'height': 200},
    'color_mode': "RGB"
}

# Execute validation (prev_result is None for first stage)
try:
    result = stage.execute(
        prev_result=None,
        pipeline_id="fab-2026-001",
        config=config
    )
    
    # Success - access validated properties
    print(f"✅ Design validated: {result.raw_hash}")
    print(f"   Dimensions: {result.width_px}×{result.height_px}")
    print(f"   Tiling: {result.stage_metadata['metrics']['repeat_units_x']}×{result.stage_metadata['metrics']['repeat_units_y']}")
    
except InputFormatError as e:
    print(f"❌ Invalid format: {e.message}")
    print(f"   Allowed: {e.details['allowed_formats']}")
    
except RepeatIntegrityError as e:
    print(f"❌ Tiling error: {e.message}")
    for violation in e.details['violations']:
        print(f"   - {violation}")
        
except ValidationError as e:
    print(f"❌ Validation failed: {e.message}")
```

### Accessing Validated Properties

```python
# After successful validation
result = stage.execute(prev_result=None, pipeline_id=..., config=...)

# Image properties (direct fields on result)
width = result.width_px               # 1000
height = result.height_px             # 800
dpi = result.dpi                      # 300
mode = result.color_mode              # "RGB"
bit_depth = result.bit_depth          # 8

# Repeat tiling
repeat_w = result.repeat_unit_px["width"]       # 200
repeat_h = result.repeat_unit_px["height"]      # 200

# From stage metadata
metrics = result.stage_metadata["metrics"]
tiles_x = metrics["repeat_units_x"]            # 5
tiles_y = metrics["repeat_units_y"]            # 4
file_format = metrics["file_format"]           # "PNG"
file_size = metrics["file_size_bytes"]        # File size

# Immutability proof
hash = result.raw_hash                # SHA-256 (64 hex chars)
seal = result.source_seal             # Complete seal info

# File path
path = result.image_path              # Absolute resolved path
```

---

## Constants Reference

All manufacturing constraints defined in `src/weaver/shared/constants.py`:

```python
# Lossless formats only (JPEG forbidden)
LOSSLESS_INPUT_FORMATS: Final[list[str]] = [".bmp", ".png", ".tiff", ".tif"]

# Unambiguous color modes only (P and 1 forbidden)
VALID_COLOR_MODES: Final[set[str]] = {"RGB", "RGBA", "L", "LA"}
# P (palette-indexed) and 1 (1-bit) create manufacturing ambiguity

# Jacquard loom physical limits
MAX_IMAGE_WIDTH: Final[int] = 10000   # Loom maximum width
MAX_IMAGE_HEIGHT: Final[int] = 10000  # Loom maximum height

# Thread precision thresholds
MIN_DPI: Final[int] = 72              # Below this, thread precision is lost
MAX_DPI: Final[int] = 1200            # Above this, loom cannot resolve

# Resource protection
MAX_MEGAPIXELS: Final[int] = 100      # 10000 × 10000 = loom limit
MAX_FILE_SIZE_BYTES: Final[int] = 500 * 1024 * 1024  # 500 MB
MAX_PIXEL_COUNT: Final[int] = 100_000_000
```

**Note**: These are immutable manufacturing constraints, **not** configurable deployment settings.

---

## Testing

### Test Coverage

- **38 test cases** (35 passing, 3 skipped for expense)
- **93% code coverage** for Stage 0 processor
- All 8 validation steps covered with failure scenarios

### Test Categories

1. **Stage Metadata** (3 tests)
   - Stage number, name, version

2. **Happy Path** (3 tests)
   - Valid PNG, TIFF, BMP inputs

3. **Schema Validation** (10 tests)
   - Missing fields, invalid values, file not found

4. **Format Allowlist** (2 tests)
   - JPEG forbidden, WEBP forbidden

5. **Metadata Consistency** (2 tests)
   - Color mode mismatch, DPI mismatch

6. **Dimensional Constraints** (2 tests)
   - Width exceeds maximum, megapixels exceeded

7. **Repeat Integrity** (3 tests)
   - Width non-integer tiling, height non-integer, both

8. **Resource Protection** (2 tests, skipped)
   - File size exceeds maximum, pixel count exceeded

9. **Hash Computation** (3 tests)
   - Deterministic hash, different files differ, SHA-256 length

10. **Edge Cases** (4 tests)
    - Minimum dimensions (1×1), maximum (10000×10000), grayscale, RGBA

11. **Output Contract** (4 tests)
    - PASS contains descriptor, FAIL raises exception, immutability, schema version

### Running Tests

```bash
# All Stage 0 tests
pytest tests/stages/test_stage_0_input_acquisition.py -v

# Specific test class
pytest tests/stages/test_stage_0_input_acquisition.py::TestHappyPath -v

# With coverage
pytest tests/stages/test_stage_0_input_acquisition.py --cov=src/weaver/diffusion/stages/input_acquisition
```

---

## Design Decisions

### Why Pydantic for Schemas?

- **Immutability**: `frozen=True` prevents accidental modification
- **Validation**: Automatic field validation with clear error messages
- **Type Safety**: Runtime type checking with IDE support
- **Serialization**: Built-in JSON serialization for logging/storage

### Why PIL (Pillow)?

- **Standard**: Industry-standard Python image library
- **Lossless**: Proper support for PNG, TIFF, BMP without compression artifacts
- **Metadata**: Reliable extraction of DPI, color mode, dimensions
- **No GPU**: CPU-only processing (Stage 0 mandate)

### Why SHA-256?

- **Collision Resistance**: Virtually impossible to find two inputs with same hash
- **Speed**: Fast enough for large images (64KB chunks)
- **Standard**: Widely supported, well-tested cryptographic hash
- **Size**: 256 bits (64 hex chars) provides sufficient uniqueness

### Why No Auto-Correction?

**Design Philosophy**: Stage 0 is a **gatekeeper**, not a fixer.

If we auto-corrected issues:
- We'd hide problems that indicate deeper issues (corrupt files, bad tooling)
- We'd violate "source of truth" principle (modified input isn't the source)
- We'd risk introducing errors (inferring DPI from resolution is unreliable)
- We'd lose traceability (which designs were auto-corrected?)

**Better approach**: Reject invalid input and require upstream fix. This forces:
- Proper design tool configuration
- Explicit metadata capture
- Clear responsibility boundaries

---

## Performance Characteristics

### Time Complexity

| Step | Complexity | Notes |
|------|-----------|-------|
| Schema validation | O(1) | Pydantic field checks |
| Image decode | O(n) | Linear in file size |
| Format check | O(1) | String comparison |
| Metadata check | O(1) | Field comparisons |
| Dimension check | O(1) | Arithmetic comparisons |
| Repeat check | O(1) | Modulo operations |
| Resource check | O(1) | Size comparisons |
| Hash compute | O(n) | Linear in file size |
| Emit descriptor | O(1) | Object creation |

**Overall**: O(n) where n = file size (dominated by decode + hash)

### Typical Execution Time

- Small image (1MB, 1000×800): ~50-100ms
- Medium image (10MB, 3000×2000): ~200-500ms
- Large image (100MB, 10000×10000): ~2-5 seconds

**Note**: All processing is CPU-bound (no GPU, no network).

### Memory Usage

**WARNING**: Peak memory can significantly exceed 2× decoded size.

- **Theoretical minimum**: 1× decoded image size (width × height × channels × bytes_per_channel)
- **Typical PIL behavior**: 2-3× decoded size during operations
- **TIFF decoding spikes**: Can temporarily exceed 4× due to decompression buffers
- **Hash computation**: Memory-efficient (64KB chunks)

**Example** (10000×10000 RGB @ 8-bit):
- Decoded size: 300MB (10000 × 10000 × 3 bytes)
- Typical peak: 600-900MB
- TIFF worst-case: 1200MB+

**Protection**:
- Pre-decode file size check (MAX_FILE_SIZE_BYTES = 500MB)
- Post-decode pixel count check (MAX_PIXEL_COUNT = 100M)
- Early rejection prevents OOM before full decode

---

## Integration with Pipeline

### Orchestrator Flow

```python
from weaver.diffusion.pipeline_engine import DiffusionPipelineEngine
from weaver.diffusion.stages.stage_loader import StageLoader

# Load stages
loader = StageLoader()
stage_0 = loader.load_stage(0)
stage_1 = loader.load_stage(1)

try:
    # Execute Stage 0
    result_0 = stage_0.execute(
        prev_result=None,
        pipeline_id="pipeline-001",
        config={
            'source_file': "/path/to/design.png",
            'dpi': 300,
            'repeat_unit': {'width': 200, 'height': 200}
        }
    )
    
    # Pass Stage 0 result to Stage 1
    result_1 = stage_1.execute(
        prev_result=result_0,           # InputAcquisitionResult
        pipeline_id="pipeline-001",
        config=config
    )
    
except ValidationError as e:
    # Pipeline halts - Stage 0 failed
    logger.error(f"Stage 0 validation failed: {e.message}")
```

### Downstream Stage Trust

**Key principle**: If Stage 1+ receives `input_descriptor`, they can **trust it completely**.

No need to re-validate:
- ✅ Format is lossless
- ✅ Dimensions are within limits
- ✅ Repeat tiling is perfect
- ✅ Metadata is consistent
- ✅ File hasn't been modified (hash proof)

This allows downstream stages to focus on their transformations without redundant validation.

---

## Troubleshooting

### Common Issues

**Problem**: `InputSchemaError: Image file does not exist`

**Solution**: Check image_path is absolute and file exists
```python
from pathlib import Path
path = Path(image_path).resolve()  # Convert to absolute
assert path.exists(), f"File not found: {path}"
```

---

**Problem**: `InputFormatError: File format '.jpg' not allowed`

**Solution**: Convert JPEG to PNG using lossless conversion
```bash
# ImageMagick
magick convert design.jpg design.png

# PIL/Pillow
from PIL import Image
img = Image.open("design.jpg")
img.save("design.png", "PNG")
```

---

**Problem**: `MetadataConsistencyError: DPI mismatch`

**Solution**: Either fix DPI in image metadata or declare correct DPI
```python
# Option 1: Update image DPI
img = Image.open("design.png")
img.save("design_300dpi.png", "PNG", dpi=(300, 300))

# Option 2: Declare actual DPI
actual_dpi = img.info.get("dpi", (96, 96))[0]
input_data = Stage0Input(..., dpi=actual_dpi, ...)
```

---

**Problem**: `RepeatIntegrityError: Width 1000px is not a multiple of repeat width 300px`

**Solution**: Either crop image or adjust repeat unit
```python
# Option 1: Crop to nearest multiple
crop_width = (width // repeat_w) * repeat_w  # 900px
img_cropped = img.crop((0, 0, crop_width, height))

# Option 2: Adjust repeat unit to divide evenly
# Find GCD of width and desired repeat
import math
repeat_w = math.gcd(width, 300)  # Find valid repeat
```

---

**Problem**: `DimensionalConstraintError: Width 12000px exceeds maximum 10000px`

**Solution**: Resize image to fit loom limits
```python
from PIL import Image

img = Image.open("design.png")
max_dim = 10000

# Calculate scale factor
scale = min(max_dim / img.width, max_dim / img.height)

if scale < 1:
    new_size = (int(img.width * scale), int(img.height * scale))
    img_resized = img.resize(new_size, Image.LANCZOS)
    img_resized.save("design_resized.png", "PNG")
```

---

## Future Enhancements

### Potential Improvements (Post-MVP)

1. **Parallel Hash Computation**: Use multiprocessing for large files
2. **Format-Specific Validation**: TIFF tag validation, PNG chunk verification
3. **Color Profile Validation**: ICC profile checks for color consistency
4. **Preview Generation**: Generate thumbnail for UI preview
5. **Batch Validation**: Validate multiple designs in parallel
6. **Metadata Extraction**: EXIF data capture for audit trail
7. **Design Fingerprinting**: Perceptual hash for duplicate detection

### Not Planned (Violates Principles)

- ❌ Auto-DPI inference from resolution
- ❌ Automatic image cropping to fit repeat
- ❌ Lossy-to-lossless conversion (re-encoding doesn't recover lost data)
- ❌ Color mode auto-conversion (changes design intent)
- ❌ GPU acceleration (adds complexity, not needed for Stage 0)

---

## References

### Code Locations

- **Implementation**: `src/weaver/diffusion/stages/input_acquisition/processor.py`
- **Sub-modules**: `src/weaver/diffusion/stages/input_acquisition/` (8 specialized validators)
- **Result Schema**: `src/weaver/diffusion/stages/stage_result.py`
- **Base Stage**: `src/weaver/diffusion/stages/base_stage.py`
- **Exceptions**: `src/weaver/shared/exceptions.py`
- **Constants**: `src/weaver/shared/constants.py`
- **Tests**: `tests/stages/test_stage_0_input_acquisition.py`

### External Dependencies

- **Pillow (PIL)**: Image decoding and metadata extraction
- **Pydantic**: Schema validation and immutability
- **hashlib**: SHA-256 hash computation (Python standard library)

### Related Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - Overall system architecture
- [Pipeline Configuration](../config/pipeline.yaml) - Stage settings

---

## Appendix: Error Code Reference

| Error Code | Exception | Trigger Condition |
|------------|-----------|------------------|
| `file_not_found` | InputSchemaError | image_path doesn't exist |
| `not_a_file` | InputSchemaError | image_path is directory |
| `invalid_color_mode` | InputSchemaError | color_mode not in valid set |
| `format_not_allowed` | InputFormatError | File extension not in LOSSLESS_INPUT_FORMATS |
| `decode_failed` | InputFormatError | PIL cannot decode image |
| `color_mode_mismatch` | MetadataConsistencyError | Declared != actual color mode |
| `dpi_mismatch` | MetadataConsistencyError | Declared != actual DPI (beyond tolerance) |
| `width_exceeds_max` | DimensionalConstraintError | width > MAX_IMAGE_WIDTH |
| `height_exceeds_max` | DimensionalConstraintError | height > MAX_IMAGE_HEIGHT |
| `megapixels_exceeds_max` | DimensionalConstraintError | (width × height) / 1M > MAX_MEGAPIXELS |
| `width_non_integer_tiling` | RepeatIntegrityError | width % repeat_w != 0 |
| `height_non_integer_tiling` | RepeatIntegrityError | height % repeat_h != 0 |
| `file_size_exceeds_max` | ResourceProtectionError | file_size > MAX_FILE_SIZE_BYTES |
| `pixel_count_exceeds_max` | ResourceProtectionError | (width × height) > MAX_PIXEL_COUNT |

---

**Document Version**: 1.0.0  
**Last Updated**: January 26, 2026  
**Maintained By**: Weaver AI Manufacturing Team
