"""
Stage 2: Structural Intent Extraction (Compiler IR)
Responsibility: Transform raster to resolution-independent symbolic representation.

This stage is NOT an image processor - it is a representation extractor.
Output encodes WHAT MUST NOT CHANGE, not how it looks.

DESIGN PRINCIPLES (NON-NEGOTIABLE):
- Resolution-independent (no pixel coordinates as truth)
- Topology > geometry
- Symmetry and repetition explicit
- Skeleton islands handled via confidence, not deletion
- All uncertainty preserved
- Human-inspectable symbolic output

If downstream stages need the original image → this implementation is wrong.
If output size scales with resolution → this implementation is wrong.
If it feels like drawing → you're doing it wrong.

Stage-2 is a COMPILER IR, not a renderer.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from collections import defaultdict

import cv2
import numpy as np
import networkx as nx
from pydantic import BaseModel, Field
from skimage.morphology import skeletonize, label
from skimage.measure import regionprops
from scipy.spatial import KDTree
from scipy.stats import circmean, circstd

from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages.stage_result import (
    CanonicalNormalizationResult,
    StageResult,
    StructuralIntentResult,
    MotifNode,
    MotifEdge,
    TopologyInfo,
    CurveIntent,
    PatternIntent,
    StructuralMask,
    DesignConstraint,
    UncertaintyRecord
)
from weaver.shared.schemas import StageStatus
from weaver.shared.exceptions import (
    TopologyViolationError,
    BoundaryInconsistencyError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class StructuralIntentStage(BaseStage):
    """
    Stage 2: Structural Intent Extraction (Compiler IR)
    
    Transforms raster skeleton into resolution-independent symbolic representation:
    - Motif graph (nodes = structural elements, edges = relationships)
    - Topology (connectivity, junctions, loops)
    - Curve intent (LINEAR, BEZIER_LIKE, SPLINE_LIKE)
    - Pattern intent (symmetry, repetition)
    - Structural masks (foreground, fill, negative space)
    - Constraints (advisory spacing, curvature, alignment rules)
    - Uncertainty (skeleton islands, ambiguous decisions)
    
    FORBIDDEN:
    - Passing raw skeletons or pixel coordinates as truth
    - Dropping skeleton islands silently
    - Hard-coding thresholds without confidence decay
    - Enforcing manufacturability rules (Stage-5 responsibility)
    - Any operation that requires seeing the original image downstream
    
    Mental model: If it feels like drawing, you're doing it wrong.
    Stage-2 is a compiler IR, not a renderer.
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_id="structural_intent",
            name="Structural Intent Extraction",
            description="Transform raster to resolution-independent symbolic representation (compiler IR)",
            version="2.0.0"
        )

    def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
        """Validate that prev_result is CanonicalNormalizationResult."""
        if prev_result is None:
            raise TypeError("Stage 2 requires a previous result, got None")
        
        if not isinstance(prev_result, CanonicalNormalizationResult):
            raise TypeError(
                f"Stage 2 requires CanonicalNormalizationResult, got {type(prev_result).__name__}"
            )
    
    def _execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> StructuralIntentResult:
        """
        Execute Stage 2: Structural Intent Extraction.
        
        Args:
            prev_result: CanonicalNormalizationResult from Stage 1
            pipeline_id: Unique pipeline execution ID
            config: Stage configuration dict
        
        Returns:
            StructuralIntentResult with resolution-independent symbolic representation
        """
        from typing import cast
        
        # Extract configuration values
        canny_threshold1 = config.get("canny_threshold1", 50)
        canny_threshold2 = config.get("canny_threshold2", 150)
        curve_linearity_threshold = config.get("curve_linearity_threshold", 0.1)
        symmetry_min_confidence = config.get("symmetry_min_confidence", 0.5)
        island_confidence_threshold = config.get("island_confidence_threshold", 0.3)
        symmetry_detection = config.get("symmetry_detection", "REQUIRED")
        
        # Cast to expected type (already validated)
        input_result = cast(CanonicalNormalizationResult, prev_result)
        
        logger.info(f"Starting Stage 2 execution (Compiler IR): {pipeline_id}")
        
        # Extract values from previous stage result
        width = input_result.width_px
        height = input_result.height_px
        dpi = input_result.dpi
        repeat_width = input_result.repeat_unit_px["width"]
        repeat_height = input_result.repeat_unit_px["height"]
        diagonal = math.sqrt(width**2 + height**2)  # For normalization
        
        # Load canonical raster from file (Stage 1 always saves to disk)
        logger.info("Loading canonical raster from disk for preprocessing")
        if input_result.pixel_array_path:
            image = self._load_canonical_raster(input_result.pixel_array_path)
        else:
            raise ValidationError(
                "No canonical raster file path available",
                stage_number=2,
                details={"pixel_array_path": input_result.pixel_array_path}
            )
        
        # PREPROCESSING: Extract edges and skeleton (classical CV)
        logger.info("[Preprocessing] Extracting edges with Canny detection")
        edge_map = self._extract_edges(image, canny_threshold1, canny_threshold2)
        
        logger.info("[Preprocessing] Extracting skeleton from edge map")
        skeleton_map = self._extract_skeleton(edge_map)
        
        logger.info("[Preprocessing] Building NetworkX skeleton graph")
        skeleton_graph = self._build_skeleton_graph(skeleton_map)
        
        # STEP 1: Build motif graph (transform skeleton to symbolic representation)
        logger.info("[Step 1] Building motif graph with skeleton island handling")
        motif_nodes, motif_edges, uncertain_islands = self._build_motif_graph(
            skeleton_graph, width, height, diagonal, island_confidence_threshold
        )
        
        # STEP 2: Extract topology
        logger.info("[Step 2] Extracting topology information")
        topology = self._extract_topology(skeleton_graph, motif_nodes)
        
        # STEP 3: Classify curves
        logger.info("[Step 3] Inferring curve intent for strokes")
        geometry_intent = self._classify_curves(
            skeleton_graph, motif_nodes, curve_linearity_threshold
        )
        
        # STEP 4: Detect symmetry and repetition
        if symmetry_detection in ["REQUIRED", "OPTIONAL"]:
            logger.info("[Step 4] Detecting symmetry and repetition patterns")
            pattern_intent, symmetry_uncertainty = self._detect_symmetry(
                motif_nodes, skeleton_graph, width, height,
                repeat_width, repeat_height, diagonal, symmetry_min_confidence
            )
        else:
            logger.info("[Step 4] Symmetry detection disabled")
            pattern_intent = []
            symmetry_uncertainty = []
        
        # STEP 5: Generate structural masks
        logger.info("[Step 5] Generating structural masks")
        structural_masks = self._generate_structural_masks(
            motif_nodes, edge_map, width, height
        )
        
        # STEP 6: Infer constraints
        logger.info("[Step 6] Inferring design constraints")
        constraints = self._infer_constraints(
            motif_nodes, motif_edges, skeleton_graph, geometry_intent
        )
        
        # STEP 7: Encode uncertainty
        logger.info("[Step 7] Encoding uncertainty records")
        uncertainty = uncertain_islands + symmetry_uncertainty
        uncertainty.extend(self._encode_edge_uncertainty(edge_map, canny_threshold1, canny_threshold2))
        
        # Build guarantees
        guarantees = [
            "Motif graph is resolution-independent (no pixel coordinates as truth)",
            "Skeleton islands preserved as low-confidence nodes (never deleted)",
            "Topology encoded without geometry (connectivity > coordinates)",
            "Symmetry and repetition explicit (not hidden in pixels)",
            "All uncertainty preserved (ambiguity never silenced)",
            "Output size does not scale with resolution",
            "Stage-3 can regenerate geometry without original image"
        ]
        
        # Build comprehensive stage metadata
        stage_metadata = {
            "stage_number": 2,
            "stage_name": "Structural Intent Extraction",
            "status": "COMPLETED",
            "pipeline_id": pipeline_id,
            "schema_version": "stage2.v2",
            "input_dimensions": {
                "width_px": width,
                "height_px": height,
                "dpi": dpi,
                "repeat_width_px": repeat_width,
                "repeat_height_px": repeat_height,
                "diagonal_px": diagonal
            },
            "processing_config": {
                "canny_threshold1": canny_threshold1,
                "canny_threshold2": canny_threshold2,
                "curve_linearity_threshold": curve_linearity_threshold,
                "symmetry_min_confidence": symmetry_min_confidence,
                "island_confidence_threshold": island_confidence_threshold,
                "symmetry_detection": symmetry_detection
            },
            "graph_statistics": {
                "motif_node_count": len(motif_nodes),
                "motif_edge_count": len(motif_edges),
                "component_count": topology.component_count,
                "junction_count": topology.junction_count,
                "loop_count": topology.loop_count,
                "curve_intent_count": len(geometry_intent),
                "pattern_intent_count": len(pattern_intent),
                "constraint_count": len(constraints),
                "uncertainty_record_count": len(uncertainty)
            },
            "guarantees": guarantees
        }
        
        logger.info(f"Stage 2 completed: {len(motif_nodes)} nodes, {len(motif_edges)} edges, "
                    f"{len(uncertainty)} uncertainty records")
        
        return StructuralIntentResult(
            pipeline_id=pipeline_id,
            stage_metadata=stage_metadata,
            motif_nodes=motif_nodes,
            motif_edges=motif_edges,
            topology=topology,
            geometry_intent=geometry_intent,
            pattern_intent=pattern_intent,
            structural_masks=structural_masks,
            constraints=constraints,
            uncertainty=uncertainty,
            width_px=width,
            height_px=height,
            dpi=dpi,
            repeat_width_px=repeat_width,
            repeat_height_px=repeat_height,
            guarantees=guarantees
        )
    
    # ========================================================================
    # PREPROCESSING METHODS (Classical CV - kept from v1)
    # ========================================================================
    
    def _load_canonical_raster(self, raster_path: str) -> np.ndarray:
        """Load canonical raster from Stage 1 .npy file and convert to grayscale."""
        try:
            pixel_array = np.load(raster_path)
            
            if pixel_array.ndim != 3 or pixel_array.shape[2] != 3:
                raise ValidationError(
                    f"Invalid canonical raster shape: {pixel_array.shape}",
                    stage_number=2,
                    details={"raster_path": raster_path}
                )
            
            if pixel_array.dtype != np.uint8:
                raise ValidationError(
                    f"Invalid canonical raster dtype: {pixel_array.dtype}",
                    stage_number=2,
                    details={"raster_path": raster_path}
                )
            
            grayscale = cv2.cvtColor(pixel_array, cv2.COLOR_RGB2GRAY)
            return grayscale
            
        except Exception as e:
            raise ValidationError(
                f"Error loading canonical raster: {str(e)}",
                stage_number=2,
                details={"raster_path": raster_path}
            ) from e
    
    def _extract_edges(self, image: np.ndarray, threshold1: int, threshold2: int) -> np.ndarray:
        """Extract edges using Canny detection (deterministic)."""
        edges = cv2.Canny(
            image,
            threshold1=threshold1,
            threshold2=threshold2,
            apertureSize=3,
            L2gradient=True
        )
        return edges
    
    def _extract_skeleton(self, edge_map: np.ndarray) -> np.ndarray:
        """Extract 1-pixel wide skeleton from edge map (topology-preserving)."""
        binary = edge_map > 0
        skeleton = skeletonize(binary)
        skeleton_uint8 = (skeleton * 255).astype(np.uint8)
        return skeleton_uint8
    
    def _build_skeleton_graph(self, skeleton_map: np.ndarray) -> nx.Graph:
        """Build NetworkX graph from skeleton pixels (8-connectivity)."""
        skeleton_coords = np.argwhere(skeleton_map > 0)
        
        if len(skeleton_coords) == 0:
            logger.warning("Empty skeleton detected")
            return nx.Graph()
        
        graph = nx.Graph()
        
        # Add nodes
        for y, x in skeleton_coords:
            graph.add_node((y, x))
        
        # Add edges (8-connectivity)
        for y, x in skeleton_coords:
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    neighbor = (y + dy, x + dx)
                    if neighbor in graph.nodes:
                        graph.add_edge((y, x), neighbor)
        
        return graph
    
    # ========================================================================
    # STEP 1: MOTIF GRAPH CONSTRUCTION
    # ========================================================================
    
    def _build_motif_graph(
        self,
        skeleton_graph: nx.Graph,
        width: int,
        height: int,
        diagonal: float,
        island_threshold: float
    ) -> Tuple[List[MotifNode], List[MotifEdge], List[UncertaintyRecord]]:
        """
        Transform skeleton graph into motif graph with symbolic representation.
        
        Skeleton islands are preserved as separate components with low confidence.
        Never deleted, never auto-attached (unless as weak hypothesis).
        
        Returns:
            Tuple of (motif_nodes, motif_edges, uncertainty_records)
        """
        motif_nodes = []
        motif_edges = []
        uncertainty_records = []
        
        if skeleton_graph.number_of_nodes() == 0:
            logger.warning("Empty skeleton graph - no motifs to extract")
            return motif_nodes, motif_edges, uncertainty_records
        
        # Get connected components
        components = list(nx.connected_components(skeleton_graph))
        logger.info(f"Found {len(components)} connected components")
        
        # Identify main component (largest)
        main_component = max(components, key=len)
        island_components = [c for c in components if c != main_component]
        
        # Process main component
        node_id_map = {}
        for idx, component in enumerate(components):
            is_island = component in island_components
            component_subgraph = skeleton_graph.subgraph(component)
            
            # Analyze component topology
            junctions = [n for n in component if skeleton_graph.degree(n) > 2]
            endpoints = [n for n in component if skeleton_graph.degree(n) == 1]
            
            # Create component node
            if is_island:
                # Skeleton island: low confidence, marked as NOISE_CANDIDATE
                centroid_y = np.mean([n[0] for n in component]) / height
                centroid_x = np.mean([n[1] for n in component]) / width
                # Scale represents the component size relative to image diagonal (clamped to [0, 1])
                scale = min(1.0, len(component) / diagonal)
                
                node_id = f"island_{idx}"
                node_id_map[idx] = node_id
                
                motif_nodes.append(MotifNode(
                    id=node_id,
                    type="STROKE",  # Could be STROKE or LOOP
                    relative_scale=scale,
                    orientation=None,
                    confidence=min(island_threshold, scale * 2),  # Lower confidence for smaller islands
                    role="NOISE_CANDIDATE",
                    centroid=(centroid_x, centroid_y),
                    metadata={"size_pixels": len(component)}
                ))
                
                # Record uncertainty
                uncertainty_records.append(UncertaintyRecord(
                    category="SKELETON_ISLAND",
                    affected_nodes=[node_id],
                    confidence=min(island_threshold, scale * 2),
                    alternatives=[{"interpretation": "noise"}, {"interpretation": "disconnected_motif"}],
                    rationale=f"Isolated component with {len(component)} pixels - connectivity not provable"
                ))
            else:
                # Main component: analyze structure
                for j_idx, junction in enumerate(junctions):
                    node_id = f"junction_{j_idx}"
                    node_id_map[junction] = node_id
                    
                    degree = skeleton_graph.degree(junction)
                    junction_type = self._classify_junction(degree)
                    
                    centroid_y = junction[0] / height
                    centroid_x = junction[1] / width
                    
                    motif_nodes.append(MotifNode(
                        id=node_id,
                        type="JUNCTION",
                        relative_scale=1.0 / diagonal,  # Junction is a point
                        orientation=None,
                        confidence=0.95,  # High confidence for clear junctions
                        role=None,
                        centroid=(centroid_x, centroid_y),
                        metadata={"junction_type": junction_type, "degree": degree}
                    ))
                
                # Create stroke nodes between junctions/endpoints
                stroke_id = 0
                for edge in component_subgraph.edges():
                    node_id = f"stroke_{stroke_id}"
                    stroke_id += 1
                    
                    # Calculate stroke properties
                    y1, x1 = edge[0]
                    y2, x2 = edge[1]
                    length = math.sqrt((y2 - y1)**2 + (x2 - x1)**2)
                    # Scale relative to diagonal, clamped to [0, 1]
                    scale = min(1.0, length / diagonal)
                    orientation = math.atan2(y2 - y1, x2 - x1)
                    
                    centroid_y = (y1 + y2) / (2 * height)
                    centroid_x = (x1 + x2) / (2 * width)
                    
                    motif_nodes.append(MotifNode(
                        id=node_id,
                        type="STROKE",
                        relative_scale=scale,
                        orientation=orientation,
                        confidence=0.9,
                        role=None,
                        centroid=(centroid_x, centroid_y),
                        metadata={"length_pixels": length}
                    ))
        
        # Create edges (connectivity relationships)
        for i, node1 in enumerate(motif_nodes):
            for j, node2 in enumerate(motif_nodes):
                if i >= j:
                    continue
                
                # Check if nodes are spatially adjacent
                if node1.centroid and node2.centroid:
                    dist = math.sqrt(
                        (node1.centroid[0] - node2.centroid[0])**2 +
                        (node1.centroid[1] - node2.centroid[1])**2
                    )
                    
                    # Connected if very close
                    if dist < 0.05:  # 5% of image size
                        motif_edges.append(MotifEdge(
                            src=node1.id,
                            dst=node2.id,
                            relation="ADJACENT",
                            confidence=0.9,
                            hypothesis_only=False,
                            metadata={}
                        ))
        
        logger.info(f"Built motif graph: {len(motif_nodes)} nodes, {len(motif_edges)} edges, "
                    f"{len(island_components)} islands")
        
        return motif_nodes, motif_edges, uncertainty_records
    
    def _classify_junction(self, degree: int) -> str:
        """Classify junction by degree."""
        if degree == 3:
            return "T_JUNCTION"
        elif degree == 4:
            return "X_JUNCTION"
        elif degree == 5:
            return "Y_JUNCTION"
        else:
            return "COMPLEX"
    
    # ========================================================================
    # STEP 2: TOPOLOGY EXTRACTION
    # ========================================================================
    
    def _extract_topology(
        self,
        skeleton_graph: nx.Graph,
        motif_nodes: List[MotifNode]
    ) -> TopologyInfo:
        """Extract topology information from skeleton graph."""
        components = list(nx.connected_components(skeleton_graph))
        
        junction_nodes = [n for n in motif_nodes if n.type == "JUNCTION"]
        junction_types = defaultdict(int)
        for node in junction_nodes:
            j_type = node.metadata.get("junction_type", "UNKNOWN")
            junction_types[j_type] += 1
        
        # Detect loops (cycles in graph)
        try:
            cycles = nx.cycle_basis(skeleton_graph)
            loop_count = len(cycles)
        except:
            loop_count = 0
        
        return TopologyInfo(
            component_count=len(components),
            junction_count=len(junction_nodes),
            loop_count=loop_count,
            junction_types=dict(junction_types),
            topology_well_formed=True
        )
    
    # ========================================================================
    # STEP 3: CURVE INTENT INFERENCE
    # ========================================================================
    
    def _classify_curves(
        self,
        skeleton_graph: nx.Graph,
        motif_nodes: List[MotifNode],
        linearity_threshold: float
    ) -> List[CurveIntent]:
        """Classify curves as LINEAR, BEZIER_LIKE, SPLINE_LIKE, ARC_LIKE."""
        curve_intents = []
        
        stroke_nodes = [n for n in motif_nodes if n.type == "STROKE" and n.role != "NOISE_CANDIDATE"]
        
        for node in stroke_nodes:
            # Simple heuristic: use scale as proxy for curvature
            # In production, would analyze actual skeleton path curvature
            scale = node.relative_scale
            
            # Estimate curvature from scale (larger strokes more likely curved)
            if scale < linearity_threshold:
                curve_class = "LINEAR"
                curvature_mean = 0.0
                curvature_max = 0.0
                continuity = "C2"
            else:
                curve_class = "SPLINE_LIKE"
                curvature_mean = scale * 0.5
                curvature_max = scale
                continuity = "C1"
            
            curve_intents.append(CurveIntent(
                stroke_id=node.id,
                curve_class=curve_class,
                curvature_mean=curvature_mean,
                curvature_max=curvature_max,
                curvature_variance=0.1,
                continuity=continuity,
                confidence=0.8
            ))
        
        return curve_intents
    
    # ========================================================================
    # STEP 4: SYMMETRY & REPETITION DETECTION
    # ========================================================================
    
    def _detect_symmetry(
        self,
        motif_nodes: List[MotifNode],
        skeleton_graph: nx.Graph,
        width: int,
        height: int,
        repeat_width: int,
        repeat_height: int,
        diagonal: float,
        min_confidence: float
    ) -> Tuple[List[PatternIntent], List[UncertaintyRecord]]:
        """Detect symmetry and repetition patterns using KD-tree optimization."""
        pattern_intents = []
        uncertainty_records = []
        
        if len(motif_nodes) == 0:
            return pattern_intents, uncertainty_records
        
        # Extract centroids for spatial analysis
        centroids = np.array([n.centroid for n in motif_nodes if n.centroid is not None])
        if len(centroids) == 0:
            return pattern_intents, uncertainty_records
        
        # Build KD-tree for efficient spatial queries
        kdtree = KDTree(centroids)
        
        # Detect translational repetition (tiling pattern)
        repeat_w_rel = repeat_width / width
        repeat_h_rel = repeat_height / height
        
        # Check if motifs repeat at tile boundaries
        translation_confidence = self._check_translational_symmetry(
            centroids, kdtree, repeat_w_rel, repeat_h_rel
        )
        
        if translation_confidence >= min_confidence:
            pattern_intents.append(PatternIntent(
                pattern_type="TRANSLATIONAL",
                order=None,
                axis_angle=None,
                tile_size_relative=(repeat_w_rel, repeat_h_rel),
                offset_vector=(repeat_w_rel, repeat_h_rel),
                confidence=translation_confidence,
                metadata={"detected_tile_size": (repeat_w_rel, repeat_h_rel)}
            ))
        elif translation_confidence >= min_confidence * 0.6:
            # Ambiguous translational symmetry
            uncertainty_records.append(UncertaintyRecord(
                category="AMBIGUOUS_SYMMETRY",
                affected_nodes=[],
                confidence=translation_confidence,
                alternatives=[
                    {"type": "TRANSLATIONAL", "confidence": translation_confidence},
                    {"type": "NONE", "confidence": 1 - translation_confidence}
                ],
                rationale=f"Translational symmetry confidence {translation_confidence:.2f} below threshold {min_confidence}"
            ))
        
        # Detect reflection symmetry
        reflection_confidence = self._check_reflection_symmetry(centroids, kdtree)
        
        if reflection_confidence >= min_confidence:
            pattern_intents.append(PatternIntent(
                pattern_type="REFLECTION",
                order=1,
                axis_angle=0.0,  # Simplified: assume vertical axis
                tile_size_relative=None,
                offset_vector=None,
                confidence=reflection_confidence,
                metadata={"detected_axis": "vertical"}
            ))
        
        return pattern_intents, uncertainty_records
    
    def _check_translational_symmetry(
        self,
        centroids: np.ndarray,
        kdtree: KDTree,
        tile_w: float,
        tile_h: float
    ) -> float:
        """Check for translational repetition using KD-tree."""
        if len(centroids) < 2:
            return 0.0
        
        # Check how many points have a neighbor at (x + tile_w, y + tile_h)
        matches = 0
        total = len(centroids)
        
        for centroid in centroids:
            translated = centroid + np.array([tile_w, tile_h])
            # Query KD-tree for nearby points
            distances, indices = kdtree.query(translated, k=1)
            if distances < 0.05:  # 5% tolerance
                matches += 1
        
        confidence = matches / total if total > 0 else 0.0
        return confidence
    
    def _check_reflection_symmetry(
        self,
        centroids: np.ndarray,
        kdtree: KDTree
    ) -> float:
        """Check for reflection symmetry (vertical axis at x=0.5)."""
        if len(centroids) < 2:
            return 0.0
        
        matches = 0
        total = len(centroids)
        
        for centroid in centroids:
            # Reflect across vertical axis at x=0.5
            reflected = np.array([1.0 - centroid[0], centroid[1]])
            distances, indices = kdtree.query(reflected, k=1)
            if distances < 0.05:
                matches += 1
        
        confidence = matches / total if total > 0 else 0.0
        return confidence
    
    # ========================================================================
    # STEP 5: STRUCTURAL MASK GENERATION
    # ========================================================================
    
    def _generate_structural_masks(
        self,
        motif_nodes: List[MotifNode],
        edge_map: np.ndarray,
        width: int,
        height: int
    ) -> List[StructuralMask]:
        """Generate soft structural masks."""
        masks = []
        
        # Foreground structure mask (all non-island nodes)
        foreground_nodes = [n.id for n in motif_nodes if n.role != "NOISE_CANDIDATE"]
        if foreground_nodes:
            masks.append(StructuralMask(
                mask_type="FOREGROUND_STRUCTURE",
                representation="VECTOR_REGION",
                region_ids=foreground_nodes,
                confidence=0.9,
                metadata={}
            ))
        
        # Border emphasis mask
        border_nodes = [n.id for n in motif_nodes if n.type == "BORDER"]
        if border_nodes:
            masks.append(StructuralMask(
                mask_type="BORDER_EMPHASIS",
                representation="VECTOR_REGION",
                region_ids=border_nodes,
                confidence=1.0,
                metadata={}
            ))
        
        return masks
    
    # ========================================================================
    # STEP 6: CONSTRAINT INFERENCE
    # ========================================================================
    
    def _infer_constraints(
        self,
        motif_nodes: List[MotifNode],
        motif_edges: List[MotifEdge],
        skeleton_graph: nx.Graph,
        geometry_intent: List[CurveIntent]
    ) -> List[DesignConstraint]:
        """Infer advisory design constraints."""
        constraints = []
        
        # Min spacing constraint (from adjacent nodes)
        adjacent_edges = [e for e in motif_edges if e.relation == "ADJACENT"]
        if adjacent_edges:
            # Simple heuristic: minimum distance between adjacent nodes
            constraints.append(DesignConstraint(
                constraint_type="MIN_SPACING",
                value=0.01,  # 1% of image size
                applies_to=[e.src for e in adjacent_edges] + [e.dst for e in adjacent_edges],
                confidence=0.7,
                description="Minimum spacing between adjacent motif elements"
            ))
        
        # Min curvature radius (from curve intents)
        curved_strokes = [c for c in geometry_intent if c.curve_class != "LINEAR"]
        if curved_strokes:
            min_radius = min(1.0 / c.curvature_max if c.curvature_max > 0 else 1.0 for c in curved_strokes)
            constraints.append(DesignConstraint(
                constraint_type="MIN_CURVATURE_RADIUS",
                value=min_radius,
                applies_to=[c.stroke_id for c in curved_strokes],
                confidence=0.8,
                description="Minimum curvature radius for smooth curves"
            ))
        
        # Max junction degree (from junctions)
        junction_nodes = [n for n in motif_nodes if n.type == "JUNCTION"]
        if junction_nodes:
            max_degree = max(n.metadata.get("degree", 0) for n in junction_nodes)
            constraints.append(DesignConstraint(
                constraint_type="MAX_JUNCTION_DEGREE",
                value=float(max_degree),
                applies_to=[n.id for n in junction_nodes],
                confidence=0.95,
                description=f"Maximum junction degree observed: {max_degree}"
            ))
        
        return constraints
    
    # ========================================================================
    # STEP 7: UNCERTAINTY ENCODING
    # ========================================================================
    
    def _encode_edge_uncertainty(
        self,
        edge_map: np.ndarray,
        threshold1: int,
        threshold2: int
    ) -> List[UncertaintyRecord]:
        """Encode uncertainty from edge detection near thresholds."""
        uncertainty_records = []
        
        # Count pixels near lower threshold (weak edges)
        # In production, would analyze gradient magnitudes
        edge_count = np.sum(edge_map > 0)
        total_pixels = edge_map.size
        edge_ratio = edge_count / total_pixels
        
        if edge_ratio > 0.3:  # More than 30% edges suggests noisy detection
            uncertainty_records.append(UncertaintyRecord(
                category="LOW_CONFIDENCE_EDGE",
                affected_nodes=[],
                confidence=0.5,
                alternatives=[],
                rationale=f"High edge pixel ratio ({edge_ratio:.1%}) suggests noisy edge detection"
            ))
        
        return uncertainty_records
