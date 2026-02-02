"""
Result classes for pipeline stages.
Each stage produces a Result that the next stage consumes.
"""

import json
import numpy as np
from pydantic import BaseModel, Field, model_serializer
from typing import Optional, Dict, Any, Literal
from pathlib import Path

class StageResult(BaseModel):
    """Base class for all stage results."""
    pipeline_id: str
    stage_metadata: Dict[str, Any] = Field(..., description="Metadata about the stage that produced this result")
    
    def _save_numpy_arrays(self, data: Dict[str, Any], base_path: Path) -> Dict[str, Any]:
        """
        Recursively find numpy arrays in data and save them to .npy files.
        Replace array values with file paths.
        
        Args:
            data: Dictionary to process
            base_path: Base directory for saving .npy files
        
        Returns:
            Modified dictionary with file paths instead of arrays
        """
        import numpy as np
        
        result = {}
        for key, value in data.items():
            if value is None:
                # Preserve None values
                result[key] = None
            elif isinstance(value, np.ndarray):
                # Save numpy array to .npy file
                npy_filename = f"{key}.npy"
                npy_path = base_path / npy_filename
                np.save(npy_path, value)
                # Store just the filename (will be resolved relative to JSON file directory)
                result[key] = npy_filename
            elif isinstance(value, dict):
                result[key] = self._save_numpy_arrays(value, base_path)
            elif isinstance(value, list):
                result[key] = [
                    self._save_numpy_arrays(item, base_path) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def to_json(self, indent: int = 2, save_arrays: bool = False, array_dir: Optional[Path] = None) -> str:
        """
        Serialize the entire result to a JSON string.
        
        Args:
            indent: Indentation level for pretty printing (default: 2)
            save_arrays: If True, save numpy arrays to files (default: False)
            array_dir: Directory to save numpy arrays (required if save_arrays=True)
        
        Returns:
            JSON string representation of the result
        """
        data = self.model_dump(mode='python', exclude_none=False)
        
        if save_arrays and array_dir:
            data = self._save_numpy_arrays(data, array_dir)
        
        return json.dumps(data, indent=indent)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the result to a dictionary.
        
        Returns:
            Dictionary representation of the result
        """
        return self.model_dump(mode='python', exclude_none=False)
    
    def save_json(self, filepath: str | Path, indent: int = 2) -> None:
        """
        Save the entire result to a JSON file.
        Automatically saves numpy arrays to separate .npy files in the same directory.
        
        Args:
            filepath: Path where JSON file will be saved
            indent: Indentation level for pretty printing (default: 2)
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Use the same directory for numpy arrays
        array_dir = filepath.parent
        
        json_str = self.to_json(indent=indent, save_arrays=True, array_dir=array_dir)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_str)
    
    @classmethod
    def _load_numpy_arrays(cls, data: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
        """
        Recursively find file paths that point to .npy files and load them.
        
        Args:
            data: Dictionary to process
            base_dir: Base directory for resolving relative paths (the directory containing the JSON file)
        
        Returns:
            Modified dictionary with loaded numpy arrays
        """
        import numpy as np
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value.endswith('.npy'):
                # Load numpy array from file (relative to JSON directory)
                npy_path = base_dir / value
                if npy_path.exists():
                    result[key] = np.load(npy_path)
                else:
                    result[key] = value  # Keep path if file doesn't exist
            elif isinstance(value, dict):
                result[key] = cls._load_numpy_arrays(value, base_dir)
            elif isinstance(value, list):
                result[key] = [
                    cls._load_numpy_arrays(item, base_dir) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def from_json(cls, json_str: str, load_arrays: bool = False, base_dir: Optional[Path] = None) -> 'StageResult':
        """
        Load a result from a JSON string.
        
        Args:
            json_str: JSON string representation
            load_arrays: If True, load numpy arrays from file paths (default: False)
            base_dir: Base directory for resolving array paths (required if load_arrays=True)
        
        Returns:
            Deserialized result object
        """
        data = json.loads(json_str)
        
        if load_arrays and base_dir:
            data = cls._load_numpy_arrays(data, base_dir)
        
        return cls.model_validate(data)
    
    @classmethod
    def load_json(cls, filepath: str | Path, load_arrays: bool = True) -> 'StageResult':
        """
        Load a result from a JSON file.
        Automatically loads numpy arrays from .npy files if they exist.
        
        Args:
            filepath: Path to JSON file
            load_arrays: If True, load numpy arrays from file paths (default: True)
        
        Returns:
            Deserialized result object
        """
        filepath = Path(filepath)
        base_dir = filepath.parent  # Same directory as JSON file
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read(), load_arrays=load_arrays, base_dir=base_dir)

class InputAcquisitionResult(StageResult):
    """Result from Stage 0: Input Acquisition"""
    raw_hash: str = Field(..., description="SHA-256 hash of raw input file")
    source_seal: Dict[str, Any] = Field(..., description="Immutability proof")
    
    # Input descriptor fields
    image_path: str
    width_px: int
    height_px: int
    dpi: int
    repeat_unit_px: Dict[str, int]  # {"width": int, "height": int}
    color_mode: str
    bit_depth: int


class CanonicalNormalizationResult(StageResult):
    """Result from Stage 1: Canonical Normalization"""
    
    # Canonical raster data
    pixel_array_path: Optional[str] = Field(None, description="Path to .npy file if hybrid storage")
    pixel_array: Optional[Any] = Field(None, description="In-memory array if small")
    width_px: int
    height_px: int
    dpi: int
    repeat_unit_px: Dict[str, int]
    color_mode: str


class MotifNode(BaseModel):
    """Node in the motif graph representing a structural element."""
    id: str = Field(..., description="Unique node identifier")
    type: Literal["STROKE", "LOOP", "JUNCTION", "REGION", "BORDER"] = Field(..., description="Structural ontology type")
    relative_scale: float = Field(..., description="Scale normalized by image diagonal (0-1)")
    orientation: Optional[float] = Field(None, description="Orientation in radians (None if not applicable)")
    confidence: float = Field(..., description="Confidence score (0-1)")
    role: Optional[Literal["NOISE_CANDIDATE"]] = Field(None, description="Interpretation overlay: NOISE_CANDIDATE for low-confidence skeleton islands")
    centroid: Optional[tuple[float, float]] = Field(None, description="Relative centroid position (0-1, 0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional node metadata")

class MotifEdge(BaseModel):
    """Edge in the motif graph representing a relationship."""
    src: str = Field(..., description="Source node ID")
    dst: str = Field(..., description="Destination node ID")
    relation: str = Field(..., description="Relation type: CONNECTED, ADJACENT, REPEATS_WITH, SYMMETRIC_TO, ENCLOSED_BY, POSSIBLE_ATTACHMENT")
    confidence: float = Field(..., description="Confidence score (0-1)")
    hypothesis_only: bool = Field(default=False, description="True if this is a weak hypothesis edge")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional edge metadata")

class TopologyInfo(BaseModel):
    """Topology information extracted from skeleton.
    
    topology_well_formed=True guarantees:
    - No self-loops in the graph
    - No duplicate edges between same node pairs
    - All non-NOISE_CANDIDATE nodes have degree >= 1
    - Graph connectivity matches component_count
    - Junction types are consistently classified
    
    This does NOT imply manufacturability or design correctness.
    """
    component_count: int = Field(..., description="Number of connected components")
    junction_count: int = Field(..., description="Number of junction nodes")
    loop_count: int = Field(..., description="Number of detected loops")
    junction_types: Dict[str, int] = Field(default_factory=dict, description="Junction type counts: T, Y, X, COMPLEX")
    topology_well_formed: bool = Field(..., description="Graph structure internally consistent per contract above")

class CurveIntent(BaseModel):
    """Curve classification and intent for a stroke."""
    stroke_id: str = Field(..., description="Associated stroke node ID")
    curve_class: str = Field(..., description="Curve classification: LINEAR, BEZIER_LIKE, SPLINE_LIKE, ARC_LIKE")
    curvature_mean: float = Field(..., description="Mean curvature")
    curvature_max: float = Field(..., description="Maximum curvature")
    curvature_variance: float = Field(..., description="Curvature variance")
    continuity: str = Field(..., description="Continuity class: C0, C1, C2")
    confidence: float = Field(..., description="Classification confidence (0-1)")

class PatternIntent(BaseModel):
    """Symmetry and repetition pattern information.
    
    Discriminated pattern detection - pattern_type determines which parameters are valid.
    This prevents partial/incoherent pattern objects and makes Stage 3 consumption deterministic.
    """
    pattern_type: Literal["REFLECTION", "ROTATIONAL", "TRANSLATIONAL", "REPETITION", "NONE"] = Field(
        ..., 
        description="Pattern classification - determines valid parameter set"
    )
    # Pattern-specific parameters (validated by pattern_type)
    order: Optional[int] = Field(None, description="Symmetry order (required for ROTATIONAL: k-fold)")
    axis_angle: Optional[float] = Field(None, description="Reflection axis angle in radians (required for REFLECTION)")
    tile_size_relative: Optional[tuple[float, float]] = Field(None, description="Relative tile size (required for TRANSLATIONAL/REPETITION: 0-1, 0-1)")
    offset_vector: Optional[tuple[float, float]] = Field(None, description="Relative offset vector (required for TRANSLATIONAL)")
    confidence: float = Field(..., description="Pattern detection confidence (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional pattern-specific data")

class StructuralMask(BaseModel):
    """Soft mask for structural regions (symbolic representation only).
    
    CRITICAL: StructuralMask is NOT a raster mask. It references symbolic regions
    via region_ids. Any raster visualizations are debug-only and must not be
    serialized or treated as IR truth.
    
    representation types:
    - VECTOR_REGION: References to MotifNode region IDs (symbolic)
    - PROBABILITY_FIELD: Confidence distribution over symbolic regions (not pixels)
    """
    mask_type: Literal["FOREGROUND_STRUCTURE", "ORNAMENTAL_FILL", "NEGATIVE_SPACE", "BORDER_EMPHASIS"] = Field(
        ..., 
        description="Structural mask classification"
    )
    representation: Literal["VECTOR_REGION", "PROBABILITY_FIELD"] = Field(
        ..., 
        description="Symbolic representation type (not raster)"
    )
    region_ids: list[str] = Field(default_factory=list, description="Associated region node IDs from motif graph")
    confidence: float = Field(..., description="Mask confidence (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional symbolic mask metadata (not pixel data)")

class DesignConstraint(BaseModel):
    """Inferred design-level constraint (advisory, not enforced)."""
    constraint_type: str = Field(..., description="Constraint type: MIN_SPACING, MIN_CURVATURE_RADIUS, MAX_JUNCTION_DEGREE, ALIGNMENT_RULE")
    value: float = Field(..., description="Constraint value (relative units)")
    applies_to: list[str] = Field(default_factory=list, description="Node IDs this constraint applies to")
    confidence: float = Field(..., description="Constraint confidence (0-1)")
    description: str = Field(..., description="Human-readable constraint description")

class UncertaintyRecord(BaseModel):
    """Record of ambiguous or uncertain decisions."""
    category: str = Field(..., description="Uncertainty category: SKELETON_ISLAND, AMBIGUOUS_SYMMETRY, LOW_CONFIDENCE_EDGE, WEAK_ATTACHMENT")
    affected_nodes: list[str] = Field(default_factory=list, description="Affected node IDs")
    confidence: float = Field(..., description="Confidence of the decision made (0-1)")
    alternatives: list[Dict[str, Any]] = Field(default_factory=list, description="Alternative interpretations considered")
    rationale: str = Field(..., description="Explanation of the uncertainty")

class StructuralIntentResult(StageResult):
    """Result from Stage 2: Structural Intent Extraction (Compiler IR)
    
    Resolution-independent symbolic representation of design structure.
    No pixel coordinates, no raster data - pure topology and constraints.
    
    CRITICAL CONTRACT: No field in this IR represents absolute pixel geometry or raster truth.
    All spatial information is normalized to [0, 1] relative coordinates.
    Downstream stages must not assume pixel-level precision from this IR.
    """
    # Graph representation (serialized)
    motif_nodes: list[MotifNode] = Field(default_factory=list, description="Motif graph nodes")
    motif_edges: list[MotifEdge] = Field(default_factory=list, description="Motif graph edges")
    
    # Topology (resolution-independent)
    topology: TopologyInfo = Field(..., description="Topology statistics")
    
    # Geometry intent (curve classifications)
    geometry_intent: list[CurveIntent] = Field(default_factory=list, description="Curve intent for all strokes")
    
    # Pattern intent (symmetry/repetition)
    pattern_intent: list[PatternIntent] = Field(default_factory=list, description="Detected symmetries and patterns")
    
    # Structural masks (soft regions)
    structural_masks: list[StructuralMask] = Field(default_factory=list, description="Structural region masks")
    
    # Constraints (advisory)
    constraints: list[DesignConstraint] = Field(default_factory=list, description="Inferred design constraints")
    
    # Uncertainty (explicit ambiguity)
    uncertainty: list[UncertaintyRecord] = Field(default_factory=list, description="Uncertain decisions and ambiguities")
    
    # Metadata (dimensional reference only)
    width_px: int = Field(..., description="Original image width (reference only)")
    height_px: int = Field(..., description="Original image height (reference only)")
    dpi: int = Field(..., description="Original image DPI (reference only)")
    repeat_width_px: int = Field(..., description="Repeat unit width (reference only)")
    repeat_height_px: int = Field(..., description="Repeat unit height (reference only)")
    
    # Contract guarantees
    guarantees: list[str] = Field(default_factory=list, description="Explicit guarantees for downstream stages")


class DiffusionRefinementResult(StageResult):
    """Result from Stage 3: Diffusion Refinement
    
    TODO: Implement diffusion refinement stage
    - Apply diffusion-based smoothing while preserving structural intent
    - Maintain topology from Stage 2
    - Return refined raster data
    """
    pass  # TODO: Add fields for diffusion refinement results


class RepeatEnforcementResult(StageResult):
    """Result from Stage 4: Repeat Enforcement
    
    TODO: Implement repeat enforcement stage
    - Validate perfect tiling across repeat boundaries
    - Detect and correct boundary misalignments
    - Ensure seamless repeat unit continuity
    """
    pass  # TODO: Add fields for repeat enforcement results


class GeometryCleanupResult(StageResult):
    """Result from Stage 5: Geometry Cleanup
    
    TODO: Implement geometry cleanup stage
    - Remove features below minimum manufacturable width
    - Simplify geometry while preserving intent
    - Apply manufacturing constraints
    """
    pass  # TODO: Add fields for geometry cleanup results


class ColorConstraintResult(StageResult):
    """Result from Stage 6: Color Constraint
    
    TODO: Implement color constraint stage
    - Apply thread palette constraints
    - Quantize colors to available threads
    - Generate color-constrained output
    """
    pass  # TODO: Add fields for color constraint results


class PreCAMValidationResult(StageResult):
    """Result from Stage 7: Pre-CAM Validation
    
    TODO: Implement pre-CAM validation stage
    - Final validation before CAM generation
    - Verify all manufacturing constraints met
    - Produce CAM-ready output
    """
    pass  # TODO: Add fields for pre-CAM validation results
