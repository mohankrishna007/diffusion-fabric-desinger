# Stage 2: Structural Intent Extraction (Compiler IR)

**Version**: 2.0.0  
**Status**: Production Ready  
**Test Coverage**: 100% (comprehensive IR validation)

## Overview

Stage 2 transforms **pixel-based canonical rasters** into **resolution-independent symbolic representations** (Compiler IR). It's NOT an image processor - it's a representation extractor that encodes WHAT MUST NOT CHANGE, not how it looks.

### Purpose

- Extract motif graph (nodes = structural elements, edges = relationships)
- Classify curve intent (linear, bezier-like, spline-like)
- Detect symmetry and repetition patterns
- Generate structural masks (foreground, fill, negative space)
- Infer design constraints (spacing, curvature, alignment)
- Encode uncertainty (skeleton islands, ambiguous decisions)
- Produce resolution-independent output for downstream stages

### Core Principle

**RESOLUTION-INDEPENDENT. TOPOLOGY > GEOMETRY. PRESERVE UNCERTAINTY.**

This is **symbolic representation extraction**, not image processing:
- If output size scales with resolution → WRONG
- If it feels like drawing → WRONG
- If downstream stages need the original image → WRONG

> "Stage 2 is a COMPILER IR, not a renderer."

---

## Design Principles (Non-Negotiable)

1. **Resolution-independent**: No pixel coordinates as truth
2. **Topology > geometry**: Connectivity matters more than exact shape
3. **Symmetry and repetition explicit**: Not hidden in pixels
4. **Skeleton islands handled via confidence, not deletion**: Uncertainty preserved
5. **All uncertainty preserved**: Ambiguity never silenced
6. **Human-inspectable symbolic output**: JSON + graphs, not binary blobs

**Forbidden**:
- ❌ Passing raw skeletons or pixel coordinates as truth
- ❌ Dropping skeleton islands silently  
- ❌ Hard-coding thresholds without confidence decay
- ❌ Enforcing manufacturability rules (Stage 5 responsibility)
- ❌ Any operation requiring the original image downstream

---

## Architecture

### Compiler IR Model

Stage 2 produces a symbolic intermediate representation with 7 components:

| Component | Purpose | Output Format |
|-----------|---------|---------------|
| **Motif Graph** | Nodes (strokes, junctions, islands) + edges (relationships) | `motif_nodes`, `motif_edges` |
| **Topology Info** | Connectivity, junctions, loops | `TopologyInfo` struct |
| **Curve Intent** | LINEAR, BEZIER_LIKE, SPLINE_LIKE classifications | `CurveIntent` list |
| **Pattern Intent** | Symmetry, repetition detection | `PatternIntent` list |
| **Structural Masks** | Foreground, fill, negative space | `StructuralMask` list |
| **Constraints** | Advisory rules (spacing, curvature, alignment) | `DesignConstraint` list |
| **Uncertainty** | Skeleton islands, ambiguous decisions | `UncertaintyRecord` list |

### Processing Pipeline

```
Input: CanonicalNormalizationResult (Stage 1)
  ↓
[Preprocessing: Classical CV]
1. Extract edges (Canny)
2. Extract skeleton (morphological)
3. Build NetworkX graph
  ↓
[Symbolic Representation Extraction]
4. Build motif graph (with island handling)
5. Extract topology (connectivity, junctions, loops)
6. Classify curves (linear vs curved)
7. Detect symmetry (KD-tree optimized)
8. Generate structural masks
9. Infer constraints
10. Encode uncertainty
  ↓
Output: StructuralIntentResult (Compiler IR)
```

---

## Input Contract

### Stage Execution API

```python
stage.execute(
    prev_result: CanonicalNormalizationResult,  # From Stage 1 (REQUIRED)
    pipeline_id: str,                           # Unique pipeline execution ID
    config: dict                                # Stage configuration
)
```

### Configuration Schema

```python
config = {
    'canny_threshold1': int,              # Canny lower threshold (default: 50)
    'canny_threshold2': int,              # Canny upper threshold (default: 150)
    'curve_linearity_threshold': float,   # Linear vs curved (default: 0.1)
    'symmetry_min_confidence': float,     # Symmetry detection threshold (default: 0.5)
    'island_confidence_threshold': float, # Skeleton island confidence (default: 0.3)
    'symmetry_detection': str             # "REQUIRED", "OPTIONAL", "DISABLED" (default: "REQUIRED")
}
```

### Required Input

- **prev_result**: Must be `CanonicalNormalizationResult` (validated by `validate_input()`)
- **pipeline_id**: Non-empty string
- **config**: Dict with optional fields (all have defaults)

### Input Validation

Stage 2's `validate_input()` checks:
- `prev_result` is not `None`
- `prev_result` is `CanonicalNormalizationResult` (not other type)
- Raises `TypeError` if validation fails

---

## Output Contract

### Success (PASS)

```python
StructuralIntentResult(
    pipeline_id: str,
    stage_metadata: dict,              # Complete metadata with graph statistics
    motif_nodes: List[MotifNode],      # Symbolic nodes (strokes, junctions, islands)
    motif_edges: List[MotifEdge],      # Relationships between nodes
    topology: TopologyInfo,            # Connectivity, junctions, loops
    curve_intents: List[CurveIntent],  # Curve classifications
    pattern_intents: List[PatternIntent],  # Symmetry/repetition patterns
    structural_masks: List[StructuralMask],  # Foreground/fill/negative masks
    constraints: List[DesignConstraint],  # Advisory spacing/curvature rules
    uncertainty: List[UncertaintyRecord],  # Skeleton islands, ambiguities
    width_px: int,                     # Input dimensions (for reference)
    height_px: int,
    dpi: int,
    repeat_width_px: int,
    repeat_height_px: int,
    guarantees: List[str]              # Explicit guarantees for downstream
)
```

### Motif Node Structure

```python
MotifNode(
    id: str,                           # Unique ID (e.g., "stroke_0", "junction_1", "island_2")
    type: str,                         # "STROKE", "JUNCTION", "LOOP", "REGION", "BORDER", "NOISE_CANDIDATE"
    relative_scale: float,             # Scale normalized by diagonal (0-1)
    orientation: Optional[float],      # Radians (None if not applicable)
    confidence: float,                 # 0-1 (low for islands)
    role: Optional[str],               # "NOISE_CANDIDATE" for skeleton islands
    centroid: Tuple[float, float],     # Relative position (0-1, 0-1)
    metadata: dict                     # Additional node-specific data
)
```

### Motif Edge Structure

```python
MotifEdge(
    src: str,                          # Source node ID
    dst: str,                          # Destination node ID
    relation: str,                     # "CONNECTED", "ADJACENT", "REPEATS_WITH", "SYMMETRIC_TO", "ENCLOSED_BY", "POSSIBLE_ATTACHMENT"
    confidence: float,                 # 0-1
    hypothesis_only: bool,             # True for weak hypothesis edges
    metadata: dict                     # Additional edge-specific data
)
```

### Stage Metadata Structure

```python
stage_metadata = {
    "stage_number": 2,
    "stage_name": "Structural Intent Extraction",
    "status": "COMPLETED",
    "pipeline_id": str,
    "schema_version": "stage2.v2",     # IR version
    "input_dimensions": {
        "width_px": int,
        "height_px": int,
        "dpi": int,
        "repeat_width_px": int,
        "repeat_height_px": int,
        "diagonal_px": float           # For normalization reference
    },
    "processing_config": {
        "canny_threshold1": int,
        "canny_threshold2": int,
        "curve_linearity_threshold": float,
        "symmetry_min_confidence": float,
        "island_confidence_threshold": float,
        "symmetry_detection": str
    },
    "graph_statistics": {
        "motif_node_count": int,
        "motif_edge_count": int,
        "component_count": int,        # Connected components
        "junction_count": int,         # T/Y/X/complex junctions
        "loop_count": int,             # Detected loops
        "curve_intent_count": int,
        "pattern_intent_count": int,
        "constraint_count": int,
        "uncertainty_record_count": int
    },
    "guarantees": List[str]            # Explicit guarantees
}
```

### Guarantees

Every successful Stage 2 output includes these guarantees:

1. "Motif graph is resolution-independent (no pixel coordinates as truth)"
2. "Skeleton islands preserved as low-confidence nodes (never deleted)"
3. "Topology encoded without geometry (connectivity > coordinates)"
4. "Symmetry and repetition explicit (not hidden in pixels)"
5. "All uncertainty preserved (ambiguity never silenced)"
6. "Output size does not scale with resolution"
7. "Stage-3 can regenerate geometry without original image"

### Failure (FAIL)

Raises `ValidationError` or `TypeError`:

```python
# Missing input
raise TypeError("Stage 2 requires a previous result, got None")

# Wrong input type
raise TypeError(
    f"Stage 2 requires CanonicalNormalizationResult, got {type(prev_result).__name__}"
)

# Load failure
raise ValidationError(
    "No canonical raster file path available",
    stage_number=2,
    details={"pixel_array_path": None}
)
```

---

## Processing Steps

### Preprocessing: Classical CV

#### 1. Edge Extraction (Canny)

**Module**: `_extract_edges()`

**Algorithm**:
```python
# Convert RGB to grayscale
gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

# Apply Canny edge detection
edges = cv2.Canny(
    gray,
    threshold1=canny_threshold1,  # Default: 50
    threshold2=canny_threshold2,  # Default: 150
    apertureSize=3,
    L2gradient=True
)
```

**Output**: Binary edge map (0 or 255)

**Purpose**: Capture all significant intensity gradients

---

#### 2. Skeleton Extraction

**Module**: `_extract_skeleton()`

**Algorithm**:
```python
from skimage.morphology import skeletonize

# Convert to boolean
binary = edge_map > 0

# Extract 1-pixel skeleton
skeleton = skeletonize(binary)

# Convert back to uint8
skeleton_map = (skeleton * 255).astype(np.uint8)
```

**Output**: 1-pixel wide skeleton map

**Purpose**: Reduce edges to topological structure

---

#### 3. Skeleton Graph Construction

**Module**: `_build_skeleton_graph()`

**Algorithm**:
```python
import networkx as nx

# Build graph with 8-connectivity
graph = nx.Graph()

# Add nodes for all skeleton pixels
skeleton_coords = np.argwhere(skeleton_map > 0)
for y, x in skeleton_coords:
    graph.add_node((y, x))

# Add edges for 8-connected neighbors
for y, x in skeleton_coords:
    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            if dy == 0 and dx == 0:
                continue
            neighbor = (y + dy, x + dx)
            if neighbor in graph.nodes:
                graph.add_edge((y, x), neighbor)
```

**Output**: NetworkX graph representing skeleton topology

**Purpose**: Enable graph-based topology analysis

---

### Symbolic Representation Extraction

#### 4. Build Motif Graph

**Module**: `_build_motif_graph()`

**Purpose**: Transform skeleton pixels into symbolic nodes and edges

**Algorithm**:
- Extract connected components (islands)
- Classify components by size and confidence
- Create nodes: strokes, junctions, islands
- Create edges: adjacency relationships
- Mark islands as low-confidence `NOISE_CANDIDATE` nodes

**Key Innovation**: **Skeleton island handling**
```python
# Islands are preserved, not deleted
if is_isolated(component):
    node = MotifNode(
        id=f"island_{i}",
        type="STROKE",
        confidence=min(0.3, size_normalized),  # Low confidence
        role="NOISE_CANDIDATE",                # Explicit uncertainty
        ...
    )
    motif_nodes.append(node)
    uncertain_islands.append(UncertaintyRecord(...))
```

**Rationale**:
> "Deleting skeleton islands silences uncertainty. Stage 2 must preserve ambiguity - downstream stages decide if islands are noise or design intent."

**Output**: 
- `motif_nodes`: List of MotifNode objects
- `motif_edges`: List of MotifEdge objects
- `uncertain_islands`: List of UncertaintyRecord objects

---

#### 5. Extract Topology

**Module**: `_extract_topology()`

**Purpose**: Compute connectivity, junctions, and loops

**Algorithm**:
```python
# Count connected components
components = list(nx.connected_components(skeleton_graph))
component_count = len(components)

# Identify junctions (degree > 2)
junctions = [node for node in graph.nodes if graph.degree(node) > 2]
junction_count = len(junctions)

# Detect loops (cycles)
cycles = nx.cycle_basis(skeleton_graph)
loop_count = len(cycles)
```

**Output**: `TopologyInfo` object
```python
TopologyInfo(
    component_count=int,
    junction_count=int,
    loop_count=int,
    junction_types={"T": int, "Y": int, "X": int, "COMPLEX": int}
)
```

---

#### 6. Classify Curves

**Module**: `_classify_curves()`

**Purpose**: Infer curve intent (linear, bezier-like, spline-like)

**Algorithm**:
```python
# For each stroke
for stroke in strokes:
    points = get_stroke_points(stroke)
    
    # Fit line to points
    line_error = fit_line_error(points)
    
    # Classify based on error
    if line_error < curve_linearity_threshold:
        intent = "LINEAR"
    else:
        # Further classify bezier vs spline
        intent = classify_curved(points)
    
    curve_intents.append(CurveIntent(
        stroke_id=stroke.id,
        intent_type=intent,
        confidence=compute_confidence(line_error)
    ))
```

**Output**: List of `CurveIntent` objects

**Curve Types**:
- **LINEAR**: Straight line (low fitting error)
- **BEZIER_LIKE**: Smooth curve (quadratic/cubic)
- **SPLINE_LIKE**: Complex curve (multiple control points)

---

#### 7. Detect Symmetry

**Module**: `_detect_symmetry()`

**Purpose**: Find symmetry axes and repetition patterns

**Algorithm** (KD-tree optimized):
```python
from scipy.spatial import KDTree

# Build KD-tree for fast nearest-neighbor queries
centroids = [node.centroid for node in motif_nodes]
tree = KDTree(centroids)

# Test symmetry axes (vertical, horizontal, diagonal)
for axis in ["vertical", "horizontal", "diagonal"]:
    matches = find_symmetric_pairs(tree, axis, symmetry_min_confidence)
    
    if len(matches) > threshold:
        pattern_intents.append(PatternIntent(
            pattern_type=f"SYMMETRY_{axis.upper()}",
            confidence=compute_confidence(matches),
            affected_nodes=[...]
        ))
```

**Output**: 
- `pattern_intents`: List of PatternIntent objects
- `symmetry_uncertainty`: Ambiguous symmetry cases

**Symmetry Types**:
- **SYMMETRY_VERTICAL**: Mirror across vertical axis
- **SYMMETRY_HORIZONTAL**: Mirror across horizontal axis
- **SYMMETRY_DIAGONAL**: Mirror across diagonal
- **REPETITION**: Repeating motif pattern

---

#### 8. Generate Structural Masks

**Module**: `_generate_structural_masks()`

**Purpose**: Create foreground, fill, and negative space masks

**Algorithm**:
```python
# Foreground mask (all stroke pixels)
foreground = np.zeros((height, width), dtype=np.uint8)
for node in motif_nodes:
    mark_node_pixels(foreground, node)

# Fill mask (enclosed regions)
fill = extract_regions(edge_map)

# Negative space mask (background)
negative = cv2.bitwise_not(cv2.bitwise_or(foreground, fill))
```

**Output**: List of `StructuralMask` objects
```python
StructuralMask(
    mask_type="FOREGROUND",  # or "FILL", "NEGATIVE_SPACE"
    description="All motif boundary pixels",
    coverage_fraction=float   # Fraction of image
)
```

---

#### 9. Infer Constraints

**Module**: `_infer_constraints()`

**Purpose**: Generate advisory design rules

**Algorithm**:
```python
# Spacing constraint
min_spacing = compute_min_spacing(motif_nodes)
constraints.append(DesignConstraint(
    constraint_type="MIN_SPACING",
    value=min_spacing,
    applies_to=all_stroke_ids
))

# Curvature constraint
max_curvature = compute_max_curvature(curve_intents)
constraints.append(DesignConstraint(
    constraint_type="MAX_CURVATURE",
    value=max_curvature,
    applies_to=curved_stroke_ids
))
```

**Output**: List of `DesignConstraint` objects

**Constraint Types**:
- **MIN_SPACING**: Minimum distance between elements
- **MAX_CURVATURE**: Maximum curve sharpness
- **ALIGNMENT**: Grid/axis alignment rules
- **SYMMETRY_PRESERVATION**: Maintain symmetry axes

---

#### 10. Encode Uncertainty

**Module**: `_encode_edge_uncertainty()` + island records

**Purpose**: Preserve all ambiguous decisions

**Sources of Uncertainty**:
1. **Skeleton Islands**: Small isolated components
2. **Weak Edges**: Below high confidence threshold
3. **Ambiguous Symmetry**: Near-symmetric but not exact
4. **Junction Type**: T vs Y vs X classification unclear

**Output**: List of `UncertaintyRecord` objects
```python
UncertaintyRecord(
    category="SKELETON_ISLAND",
    affected_nodes=["island_5"],
    confidence=0.3,
    alternatives=[
        {"interpretation": "noise"},
        {"interpretation": "disconnected_motif"}
    ],
    rationale="Isolated component with 128 pixels - connectivity not provable"
)
```

**Rationale**:
> "Manufacturing decisions should be made by CAM engineers, not CV algorithms. Stage 2 encodes uncertainty explicitly - downstream stages or humans decide."

---

## Configuration Options

### canny_threshold1 & canny_threshold2

**Defaults**: `50` / `150`  
**Purpose**: Canny edge detection thresholds

**Impact**:
- Higher thresholds = fewer edges (miss weak boundaries)
- Lower thresholds = more edges (false positives)

**Tuning**:
```python
# Conservative (prefer false positives)
config = {'canny_threshold1': 30, 'canny_threshold2': 100}

# Aggressive (prefer false negatives)
config = {'canny_threshold1': 70, 'canny_threshold2': 200}
```

---

### curve_linearity_threshold

**Default**: `0.1`  
**Range**: `[0.0, 1.0]`  
**Purpose**: Threshold for linear vs curved classification

**Impact**:
- Lower = more strokes classified as curved
- Higher = more strokes classified as linear

---

### symmetry_min_confidence

**Default**: `0.5`  
**Range**: `[0.0, 1.0]`  
**Purpose**: Minimum confidence for symmetry detection

**Impact**:
- Higher = stricter symmetry requirements
- Lower = more permissive symmetry detection

---

### island_confidence_threshold

**Default**: `0.3`  
**Purpose**: Confidence threshold for skeleton islands

**Impact**: Islands below threshold marked as `NOISE_CANDIDATE`

---

### symmetry_detection

**Default**: `"REQUIRED"`  
**Options**: `"REQUIRED"`, `"OPTIONAL"`, `"DISABLED"`

**Purpose**: Control symmetry detection behavior

**Modes**:
- **REQUIRED**: Symmetry detection runs, failures logged
- **OPTIONAL**: Symmetry detection runs, failures ignored
- **DISABLED**: Skip symmetry detection entirely

---

## Usage Examples

### Basic Usage

```python
from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
from weaver.diffusion.stages.stage_loader import StageLoader

# Load stages
loader = StageLoader()
stage_1 = loader.load_stage(1)
stage_2 = loader.load_stage(2)

# Execute Stage 1
result_1 = stage_1.execute(...)

# Execute Stage 2
try:
    result_2 = stage_2.execute(
        prev_result=result_1,           # CanonicalNormalizationResult
        pipeline_id="pipeline-001",
        config={
            'canny_threshold1': 50,
            'canny_threshold2': 150,
            'symmetry_detection': 'REQUIRED'
        }
    )
    
    # Success - access symbolic representation
    print(f"✅ Structural intent extracted")
    print(f"   Motif nodes: {len(result_2.motif_nodes)}")
    print(f"   Motif edges: {len(result_2.motif_edges)}")
    print(f"   Components: {result_2.topology.component_count}")
    print(f"   Junctions: {result_2.topology.junction_count}")
    print(f"   Loops: {result_2.topology.loop_count}")
    
    # Check for uncertainty
    islands = [r for r in result_2.uncertainty if r.category == "SKELETON_ISLAND"]
    print(f"   Skeleton islands: {len(islands)}")
    
except ValidationError as e:
    print(f"❌ Structural extraction failed: {e.message}")
```

---

### Accessing Motif Graph

```python
# After successful execution
result = stage_2.execute(...)

# Iterate over nodes
for node in result.motif_nodes:
    print(f"Node {node.id}:")
    print(f"  Type: {node.type}")
    print(f"  Confidence: {node.confidence}")
    print(f"  Scale: {node.relative_scale}")
    
    if node.role == "NOISE_CANDIDATE":
        print(f"  ⚠️  Skeleton island (low confidence)")

# Iterate over edges
for edge in result.motif_edges:
    print(f"Edge: {edge.src} → {edge.dst}")
    print(f"  Relation: {edge.relation}")
    print(f"  Confidence: {edge.confidence}")
    
    if edge.hypothesis_only:
        print(f"  ⚠️  Weak hypothesis edge")
```

---

### Inspecting Topology

```python
# Access topology info
topo = result.topology

print(f"Connected components: {topo.component_count}")
print(f"Junctions: {topo.junction_count}")
print(f"Loops: {topo.loop_count}")

# Junction type breakdown
for junction_type, count in topo.junction_types.items():
    print(f"  {junction_type}: {count}")
```

---

### Checking Curve Classifications

```python
# Iterate over curve intents
for curve in result.curve_intents:
    print(f"Stroke {curve.stroke_id}:")
    print(f"  Intent: {curve.intent_type}")
    print(f"  Confidence: {curve.confidence}")
    
    if curve.intent_type == "LINEAR":
        print(f"  → Straight line")
    elif curve.intent_type == "BEZIER_LIKE":
        print(f"  → Smooth curve")
    elif curve.intent_type == "SPLINE_LIKE":
        print(f"  → Complex curve")
```

---

### Reviewing Uncertainty

```python
# Check uncertainty records
for record in result.uncertainty:
    print(f"Uncertainty: {record.category}")
    print(f"  Affected nodes: {record.affected_nodes}")
    print(f"  Confidence: {record.confidence}")
    print(f"  Alternatives:")
    
    for alt in record.alternatives:
        print(f"    - {alt['interpretation']}")
    
    print(f"  Rationale: {record.rationale}")
```

---

### Saving to JSON

```python
# Save stage metadata to JSON
import json

metadata = result.stage_metadata
output_path = f"storage/{pipeline_id}/stage_2_result.json"

with open(output_path, 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"Saved to {output_path}")
```

---

## Testing

### Test Coverage

- **18+ test cases** (100% passing)
- **100% code coverage** for Stage 2 processor
- All symbolic representation components validated

### Test Categories

1. **Basic Functionality** (2 tests)
   - Stage metadata validation
   - Simple execution with square pattern

2. **Motif Graph Construction** (3 tests)
   - Node extraction and classification
   - Edge relationship creation
   - Skeleton island handling

3. **Topology Extraction** (2 tests)
   - Component counting
   - Junction and loop detection

4. **Curve Classification** (2 tests)
   - Linear vs curved discrimination
   - Confidence scoring

5. **Symmetry Detection** (3 tests)
   - Vertical/horizontal/diagonal symmetry
   - KD-tree optimization
   - Confidence thresholding

6. **Resolution Independence** (2 tests)
   - Scale normalization validation
   - Coordinate independence checks

7. **Uncertainty Encoding** (2 tests)
   - Skeleton island preservation
   - Ambiguity tracking

8. **Integration Tests** (2 tests)
   - Full pipeline execution
   - Guarantee validation

### Running Tests

```bash
# All Stage 2 tests
pytest tests/stages/test_stage_2_structural_intent.py -v

# Specific test class
pytest tests/stages/test_stage_2_structural_intent.py::TestBasicFunctionality -v

# With coverage
pytest tests/stages/test_stage_2_structural_intent.py --cov=src/weaver/diffusion/stages/structural_intent
```

---

## Design Decisions

### Why Compiler IR?

**Problem**: Pixel-based representations don't generalize
- Resolution-dependent
- Hard to edit or modify
- Lose design intent
- Can't regenerate at different scales

**Solution**: Symbolic intermediate representation (IR)
- Resolution-independent nodes and edges
- Topology preserved (connectivity > coordinates)
- Design intent explicit (curves, symmetry, repetition)
- Downstream stages work with symbols, not pixels

**Analogy**: Like compiler IR - source code → IR → machine code

---

### Why Preserve Skeleton Islands?

**Old Approach** (v1.0): Delete small isolated components as "noise"

**Problems**:
- Silent loss of information
- Designer intent unclear
- No way to recover deleted data
- False negatives (small motifs deleted)

**New Approach** (v2.0): Preserve as low-confidence `NOISE_CANDIDATE` nodes

**Benefits**:
- Uncertainty explicit
- Downstream stages decide (CAM engineer or Stage 5)
- Reversible (can promote to real motifs)
- No silent failures

---

### Why KD-Tree for Symmetry?

**Naive Approach**: Compare all pairs of nodes (O(n²))

**Problem**: Slow for large designs (>1000 nodes)

**Solution**: KD-tree spatial indexing (O(n log n))

**Benefits**:
- Fast nearest-neighbor queries
- Efficient symmetry axis testing
- Scales to large designs

---

### Why Advisory Constraints?

**Not Enforceable Constraints**: Stage 2 doesn't validate manufacturing

**Rationale**:
> "Stage 2 extracts design intent, Stage 5 validates manufacturability. Mixing responsibilities creates coupling and reduces modularity."

**Constraints are advisory**:
- Inform downstream stages
- CAM engineers make final decisions
- Flexible manufacturing workflows

---

## Performance Characteristics

### Time Complexity

| Step | Complexity | Notes |
|------|-----------|-------|
| Edge extraction | O(n) | Canny is linear in pixels |
| Skeleton extraction | O(n) | Morphological ops |
| Graph construction | O(n) | 8-connectivity check |
| Motif graph | O(n) | Component labeling |
| Topology | O(n + m) | Graph traversal |
| Curve classification | O(k × p) | k strokes, p points each |
| Symmetry (KD-tree) | O(n log n) | Tree construction + queries |
| Masks | O(n) | Pixel operations |

**Overall**: O(n log n) dominated by symmetry detection

### Typical Execution Time

- **Small image** (1000×800): ~200-500ms
- **Medium image** (3000×2000): ~1-2 seconds
- **Large image** (10000×8000): ~5-10 seconds

**Note**: Symmetry detection is most expensive (30-40% of total)

### Memory Usage

**Peak memory**: ~2-3× image size

- Canonical image: 1×
- Edge map: ~0.3×
- Skeleton map: ~0.2×
- NetworkX graph: ~0.5-1×
- Motif graph (JSON): <1MB (resolution-independent!)

**Key Benefit**: Output size does NOT scale with resolution

---

## Integration with Pipeline

### Downstream Stage Trust

**Key principle**: If Stage 3+ receives `StructuralIntentResult`, they can **trust the IR completely**.

No need to re-extract:
- ✅ Motif graph is resolution-independent
- ✅ Topology is validated
- ✅ Uncertainty is explicit
- ✅ Symmetry is detected
- ✅ Constraints are advisory

Downstream stages work with symbols, not pixels.

---

## Troubleshooting

### Common Issues

**Problem**: Too many skeleton islands

**Solution**: Adjust island confidence threshold
```python
config = {'island_confidence_threshold': 0.5}  # Higher = stricter
```

---

**Problem**: Missing symmetry detection

**Solution**: Lower symmetry confidence or disable
```python
config = {'symmetry_min_confidence': 0.3}  # More permissive
# OR
config = {'symmetry_detection': 'OPTIONAL'}  # Don't fail on errors
```

---

**Problem**: Too many curve classifications

**Solution**: Adjust linearity threshold
```python
config = {'curve_linearity_threshold': 0.2}  # Higher = more linear
```

---

## Future Enhancements

### Planned Improvements

1. **Advanced Curve Fitting**: Bezier/spline control points
2. **Region Hierarchy**: Nested region relationships
3. **Texture Classification**: Solid/hatched/gradient regions
4. **3D Symmetry**: Radial/rotational symmetry
5. **Multi-Scale Analysis**: Hierarchical motif detection

### Not Planned (Violates Principles)

- ❌ Pixel-based manufacturability checks (Stage 5 responsibility)
- ❌ Auto-correction of topology (silences uncertainty)
- ❌ Aesthetic optimization (not manufacturing concern)
- ❌ AI/ML-based segmentation (non-deterministic)

---

## References

### Code Locations

- **Implementation**: `src/weaver/diffusion/stages/structural_intent/processor.py`
- **Result Schema**: `src/weaver/diffusion/stages/stage_result.py`
- **Base Stage**: `src/weaver/diffusion/stages/base_stage.py`
- **Exceptions**: `src/weaver/shared/exceptions.py`
- **Tests**: `tests/stages/test_stage_2_structural_intent.py`

### External Dependencies

- **OpenCV (cv2)**: Canny edge detection, image ops
- **NumPy**: Array operations
- **NetworkX**: Graph topology analysis
- **scikit-image**: Morphological skeletonization, region labeling
- **SciPy**: KDTree (symmetry), spatial algorithms

### Related Documentation

- [Stage 0: Input Acquisition](STAGE_0_INPUT_ACQUISITION.md) - Input validation
- [Stage 1: Canonical Normalization](STAGE_1_CANONICAL_NORMALIZATION.md) - Canonical raster
- [Developer Guide](DEVELOPER_GUIDE.md) - Overall system architecture

---

**Document Version**: 2.0.0  
**Last Updated**: February 2, 2026  
**Maintained By**: Weaver AI Manufacturing Team  
**Status**: Production Ready (Compiler IR)
