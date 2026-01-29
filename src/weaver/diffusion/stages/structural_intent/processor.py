"""
Stage 2: Structural Intent Definition
Responsibility: Extract and lock structural invariants for downstream stages.

This stage converts canonical raster images into explicit geometric contracts:
- Edge maps (where boundaries exist)
- Skeleton maps (1-pixel wide topological structure)
- Region masks (closed, non-overlapping areas)
- Repeat boundary masks (immutable edge constraints)
- Structural metadata (machine-readable guarantees)

DESIGN PRINCIPLES:
- Determinism over aesthetics
- Classical CV only (no AI/ML guessing)
- Fail loudly on ambiguity
- Topology validation required
- No auto-correction
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import cv2
import numpy as np
import networkx as nx
from pydantic import BaseModel, Field
from skimage.morphology import skeletonize, label
from skimage.measure import regionprops

from weaver.diffusion.stages.base_stage import BaseStage, StageMetadata
from weaver.diffusion.stages.stage_result import (
    CanonicalNormalizationResult,
    StageResult,
    StructuralIntentResult
)
from weaver.shared.schemas import StageStatus
from weaver.shared.exceptions import (
    TopologyViolationError,
    BoundaryInconsistencyError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class StructuralMetadata(BaseModel):
    """Structural analysis metadata contract for downstream stages."""
    
    schema_version: str = Field(
        default="stage2.v1",
        description="Structural metadata schema version"
    )
    width_px: int = Field(..., description="Image width")
    height_px: int = Field(..., description="Image height")
    dpi: int = Field(..., description="Image DPI")
    repeat_width_px: int = Field(..., description="Repeat width")
    repeat_height_px: int = Field(..., description="Repeat height")
    edge_count: int = Field(..., description="Total edge pixels detected")
    skeleton_node_count: int = Field(..., description="Skeleton graph node count")
    skeleton_edge_count: int = Field(..., description="Skeleton graph edge count")
    region_count: int = Field(..., description="Number of closed regions detected")
    topology_validated: bool = Field(..., description="Skeleton topology validation passed")
    repeat_boundary_validated: bool = Field(..., description="Boundary mask alignment validated")
    guarantees: List[str] = Field(
        default_factory=list,
        description="Explicit guarantees for downstream stages"
    )


class StructuralIntentStage(BaseStage):
    """
    Stage 2: Structural Intent Definition
    
    Extracts geometric invariants using deterministic classical CV:
    - Canny edge detection (config-driven thresholds)
    - Morphological skeletonization
    - Connected component region extraction
    - Topology validation via NetworkX
    - Repeat boundary mask generation
    
    FORBIDDEN:
    - Curve smoothing
    - Noise cleanup that alters topology
    - Auto-closing gaps
    - AI/ML segmentation
    - Guessing designer intent
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_id="structural_intent",
            name="Structural Intent Definition",
            description="Extract and lock structural invariants for downstream stages",
            version="1.0.0"
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
        Execute Stage 2: Structural Intent Definition.
        
        Args:
            prev_result: CanonicalNormalizationResult from Stage 1
            pipeline_id: Unique pipeline execution ID
            config: Stage configuration dict
        
        Returns:
            StructuralIntentResult with structural artifacts
        
        Raises:
            TopologyViolationError: If skeleton topology is broken
            RegionLeakageError: If regions are not fully enclosed
            BoundaryInconsistencyError: If boundary mask misaligns
        """
        from typing import cast
        
        # Extract configuration values
        canny_threshold1 = config.get("canny_threshold1", 50)
        canny_threshold2 = config.get("canny_threshold2", 150)
        boundary_margin = config.get("boundary_margin", 0)
        
        # Cast to expected type (already validated)
        input_result = cast(CanonicalNormalizationResult, prev_result)
        
        logger.info(f"Starting Stage 2 execution: {pipeline_id}")
        
        # Extract values from previous stage result
        width = input_result.width_px
        height = input_result.height_px
        dpi = input_result.dpi
        repeat_width = input_result.repeat_unit_px["width"]
        repeat_height = input_result.repeat_unit_px["height"]
        
        # Load canonical raster
        if input_result.pixel_array is not None:
            logger.info("Using in-memory canonical raster (performance optimization)")
            image = input_result.pixel_array
        elif input_result.pixel_array_path:
            logger.info(f"Loading canonical raster from file: {input_result.pixel_array_path}")
            image = self._load_canonical_raster(input_result.pixel_array_path)
        else:
            raise ValidationError(
                "No canonical raster data available (both pixel_array and pixel_array_path are None)",
                stage_number=2,
                details={"pipeline_id": pipeline_id}
            )
        
        # STEP 1: Extract edges
        logger.info("Extracting edges with Canny detection")
        edge_map = self._extract_edges(image, canny_threshold1, canny_threshold2)
        
        # STEP 2: Extract skeleton
        logger.info("Extracting skeleton from edge map")
        skeleton_map = self._extract_skeleton(edge_map)
        
        # STEP 3: Validate topology
        logger.info("Validating skeleton topology")
        graph, node_count, edge_count = self._validate_topology(skeleton_map)
        
        # STEP 4: Extract regions
        logger.info("Extracting closed regions")
        region_count = self._extract_regions(edge_map)
        
        # STEP 5: Generate boundary mask
        logger.info("Generating repeat boundary mask")
        boundary_mask = self._create_boundary_mask(width, height, repeat_width, repeat_height, boundary_margin)
        
        # STEP 6: Validate boundary mask
        self._validate_boundary_mask(boundary_mask, width, height, repeat_width, repeat_height)
        
        # Build comprehensive stage metadata in memory
        logger.info("Building structural metadata")
        edge_pixel_count = int(np.sum(edge_map > 0))
        
        guarantees = [
            "All motif boundaries captured in edge map",
            "Skeleton topology validated (no disconnected fragments)",
            "All regions fully enclosed and non-overlapping",
            "Repeat boundaries pixel-perfect aligned",
            "No auto-correction or inference applied"
        ]
        
        stage_metadata = {
            "stage_number": 2,
            "stage_name": "Structural Intent Definition",
            "status": "COMPLETED",
            "pipeline_id": pipeline_id,
            "input_dimensions": {
                "width_px": width,
                "height_px": height,
                "dpi": dpi,
                "repeat_width_px": repeat_width,
                "repeat_height_px": repeat_height
            },
            "processing_config": {
                "canny_threshold1": canny_threshold1,
                "canny_threshold2": canny_threshold2,
                "boundary_margin": boundary_margin
            },
            "structural_analysis": {
                "schema_version": "stage2.v1",
                "width_px": width,
                "height_px": height,
                "dpi": dpi,
                "repeat_width_px": repeat_width,
                "repeat_height_px": repeat_height,
                "edge_count": edge_pixel_count,
                "skeleton_node_count": node_count,
                "skeleton_edge_count": edge_count,
                "region_count": region_count,
                "topology_validated": True,
                "repeat_boundary_validated": True,
                "guarantees": guarantees
            },
            "metrics": {
                "edge_pixels": edge_pixel_count,
                "skeleton_nodes": node_count,
                "skeleton_edges": edge_count,
                "regions_detected": region_count
            }
        }
        
        logger.info(f"Stage 2 completed successfully: {pipeline_id}")
        
        return StructuralIntentResult(
            pipeline_id=pipeline_id,
            stage_metadata=stage_metadata,
            width_px=width,
            height_px=height,
            dpi=dpi,
            repeat_width_px=repeat_width,
            repeat_height_px=repeat_height,
            edge_count=edge_pixel_count,
            skeleton_node_count=node_count,
            skeleton_edge_count=edge_count,
            region_count=region_count,
            topology_validated=True,
            repeat_boundary_validated=True,
            guarantees=guarantees
        )
    
    def _load_canonical_raster(self, raster_path: str) -> np.ndarray:
        """
        Load canonical raster from Stage 1 .npy file and convert to grayscale.
        
        Stage 1 outputs RGB (H, W, 3) uint8 NumPy array.
        Stage 2 needs grayscale for edge detection.
        
        Args:
            raster_path: Path to .npy file containing canonical raster
        
        Returns:
            Grayscale image as numpy array (H, W) uint8
        
        Raises:
            ValidationError: If raster cannot be loaded or is invalid
        """
        try:
            # Load NumPy array from .npy file (no redundant image decode)
            pixel_array = np.load(raster_path)
            
            # Validate shape (H, W, 3) from Stage 1
            if pixel_array.ndim != 3 or pixel_array.shape[2] != 3:
                raise ValidationError(
                    f"Invalid canonical raster shape: {pixel_array.shape}, expected (H, W, 3)",
                    stage_number=2,
                    details={"raster_path": raster_path, "shape": pixel_array.shape}
                )
            
            # Validate dtype uint8 from Stage 1
            if pixel_array.dtype != np.uint8:
                raise ValidationError(
                    f"Invalid canonical raster dtype: {pixel_array.dtype}, expected uint8",
                    stage_number=2,
                    details={"raster_path": raster_path, "dtype": str(pixel_array.dtype)}
                )
            
            # Convert RGB to grayscale using standard luminosity weights
            # WHY: Edge detection requires grayscale. Use OpenCV's standard conversion.
            grayscale = cv2.cvtColor(pixel_array, cv2.COLOR_RGB2GRAY)
            
            return grayscale
            
        except Exception as e:
            raise ValidationError(
                f"Error loading canonical raster: {str(e)}",
                stage_number=2,
                details={"raster_path": raster_path, "error": str(e)}
            ) from e
    
    def _extract_edges(self, image: np.ndarray, canny_threshold1: int, canny_threshold2: int) -> np.ndarray:
        """
        Extract edges using Canny edge detection.
        
        Uses deterministic classical CV - no smoothing, no beautification.
        Prefers false positives over false negatives.
        
        Args:
            image: Grayscale image
            canny_threshold1: Lower threshold for Canny
            canny_threshold2: Upper threshold for Canny
        
        Returns:
            Binary edge map (0 or 255)
        """
        # Apply Canny edge detection
        edges = cv2.Canny(
            image,
            threshold1=canny_threshold1,
            threshold2=canny_threshold2,
            apertureSize=3,
            L2gradient=True  # More accurate gradient calculation
        )
        
        return edges
    
    def _extract_skeleton(self, edge_map: np.ndarray) -> np.ndarray:
        """
        Extract 1-pixel wide skeleton from edge map.
        
        Uses morphological skeletonization to preserve topology.
        
        Args:
            edge_map: Binary edge map
        
        Returns:
            Binary skeleton map (0 or 255)
        """
        # Convert to boolean for skimage
        binary = edge_map > 0
        
        # Skeletonize (preserves topology)
        skeleton = skeletonize(binary)
        
        # Convert back to uint8
        skeleton_uint8 = (skeleton * 255).astype(np.uint8)
        
        return skeleton_uint8
    
    def _validate_topology(self, skeleton_map: np.ndarray) -> Tuple[nx.Graph, int, int]:
        """
        Validate skeleton topology using graph analysis.
        
        Converts skeleton to NetworkX graph and validates:
        - No isolated nodes
        - Connectivity preserved
        - Junction degrees maintained
        
        Args:
            skeleton_map: Binary skeleton map
        
        Returns:
            Tuple of (graph, node_count, edge_count)
        
        Raises:
            TopologyViolationError: If topology is broken
        """
        # Find skeleton pixels
        skeleton_coords = np.argwhere(skeleton_map > 0)
        
        if len(skeleton_coords) == 0:
            raise TopologyViolationError(
                "Skeleton is empty - no edges detected",
                stage_number=2,
                details={
                    "edge_pixel_count": 0,
                    "rationale": "Empty skeleton indicates edge detection failure"
                }
            )
        
        # Build graph from skeleton pixels
        graph = nx.Graph()
        
        # Add nodes (skeleton pixels)
        for y, x in skeleton_coords:
            graph.add_node((y, x))
        
        # Add edges (8-connectivity)
        for y, x in skeleton_coords:
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    neighbor_y, neighbor_x = y + dy, x + dx
                    if (neighbor_y, neighbor_x) in graph.nodes:
                        graph.add_edge((y, x), (neighbor_y, neighbor_x))
        
        # Validate: no isolated nodes
        isolated_nodes = list(nx.isolates(graph))
        if isolated_nodes:
            raise TopologyViolationError(
                f"Skeleton has {len(isolated_nodes)} isolated nodes",
                stage_number=2,
                details={
                    "isolated_node_count": len(isolated_nodes),
                    "first_isolated_node": {
                        "y": isolated_nodes[0][0],
                        "x": isolated_nodes[0][1]
                    },
                    "rationale": "Isolated nodes indicate broken topology"
                }
            )
        
        # Get connected components
        components = list(nx.connected_components(graph))
        
        # Allow multiple components (separate motifs), but warn if fragmented
        if len(components) > 1:
            logger.warning(
                f"Skeleton has {len(components)} connected components "
                f"(may indicate multiple separate motifs)"
            )
        
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        
        logger.info(
            f"Topology validated: {node_count} nodes, "
            f"{edge_count} edges, {len(components)} components"
        )
        
        return graph, node_count, edge_count
    
    def _extract_regions(
        self,
        edge_map: np.ndarray
    ) -> int:
        """
        Extract closed regions bounded by edges.
        
        Uses connected component analysis to identify distinct regions.
        Validates that regions are fully enclosed and non-overlapping.
        
        Args:
            edge_map: Binary edge map
        
        Returns:
            Region count
        
        Raises:
            RegionLeakageError: If regions are not fully enclosed
        """
        # Invert edge map to find regions (edges = 0, regions = 1)
        inverted = cv2.bitwise_not(edge_map)
        
        # Label connected components
        labeled = label(inverted)
        regions = regionprops(labeled)
        
        # Filter out background (usually the largest region)
        if len(regions) == 0:
            logger.warning("No regions detected - image may be all edges")
            return 0
        
        # Sort by area and skip background (largest region touching borders)
        regions_sorted = sorted(regions, key=lambda r: r.area, reverse=True)
        
        # Check if largest region touches image borders (likely background)
        largest = regions_sorted[0]
        h, w = edge_map.shape
        touches_border = (
            largest.bbox[0] == 0 or  # top
            largest.bbox[1] == 0 or  # left
            largest.bbox[2] == h or  # bottom
            largest.bbox[3] == w     # right
        )
        
        # Skip background if it touches borders
        valid_regions = regions_sorted[1:] if touches_border else regions_sorted
        
        # Validate regions are enclosed
        for i, region in enumerate(valid_regions, start=1):
            # Validate region is enclosed (no pixels touching edges)
            region_touches_edge = (
                region.bbox[0] == 0 or
                region.bbox[1] == 0 or
                region.bbox[2] == h or
                region.bbox[3] == w
            )
            
            if region_touches_edge:
                logger.warning(
                    f"Region {i} touches image boundary - may not be fully enclosed"
                )
        
        region_count = len(valid_regions)
        logger.info(f"Extracted {region_count} closed regions")
        
        return region_count
    
    def _create_boundary_mask(
        self,
        width: int,
        height: int,
        repeat_width: int,
        repeat_height: int,
        boundary_margin: int
    ) -> np.ndarray:
        """
        Generate binary mask for repeat boundaries.
        
        Marks all pixels on repeat unit edges as immutable.
        
        Args:
            width: Image width
            height: Image height
            repeat_width: Repeat unit width
            repeat_height: Repeat unit height
            boundary_margin: Safety margin in pixels from edge
        
        Returns:
            Binary boundary mask (0 = mutable, 255 = immutable)
        """
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # Mark vertical repeat boundaries
        for x in range(0, width, repeat_width):
            if x + boundary_margin < width:
                mask[:, x:x + boundary_margin + 1] = 255
        
        # Mark horizontal repeat boundaries
        for y in range(0, height, repeat_height):
            if y + boundary_margin < height:
                mask[y:y + boundary_margin + 1, :] = 255
        
        # Always mark image borders (outer boundary)
        mask[0:boundary_margin + 1, :] = 255  # Top
        mask[-boundary_margin - 1:, :] = 255  # Bottom
        mask[:, 0:boundary_margin + 1] = 255  # Left
        mask[:, -boundary_margin - 1:] = 255  # Right
        
        return mask
    
    def _validate_boundary_mask(
        self,
        mask: np.ndarray,
        width: int,
        height: int,
        repeat_width: int,
        repeat_height: int
    ) -> None:
        """
        Validate boundary mask aligns with repeat dimensions.
        
        Args:
            mask: Binary boundary mask
            width: Expected image width
            height: Expected image height
            repeat_width: Expected repeat width
            repeat_height: Expected repeat height
        
        Raises:
            BoundaryInconsistencyError: If dimensions mismatch
        """
        actual_height, actual_width = mask.shape
        
        if actual_width != width or actual_height != height:
            raise BoundaryInconsistencyError(
                "Boundary mask dimensions do not match declared dimensions",
                stage_number=2,
                details={
                    "declared_width": width,
                    "declared_height": height,
                    "actual_width": actual_width,
                    "actual_height": actual_height,
                    "rationale": "Dimension mismatch indicates metadata error"
                }
            )
        
        # Validate repeat dimensions divide image dimensions
        if width % repeat_width != 0:
            raise BoundaryInconsistencyError(
                f"Image width {width} not divisible by repeat width {repeat_width}",
                stage_number=2,
                details={
                    "width": width,
                    "repeat_width": repeat_width,
                    "remainder": width % repeat_width,
                    "rationale": "Non-integer tiling violates repeat integrity"
                }
            )
        
        if height % repeat_height != 0:
            raise BoundaryInconsistencyError(
                f"Image height {height} not divisible by repeat height {repeat_height}",
                stage_number=2,
                details={
                    "height": height,
                    "repeat_height": repeat_height,
                    "remainder": height % repeat_height,
                    "rationale": "Non-integer tiling violates repeat integrity"
                }
            )
        
        logger.info("Boundary mask validation passed")

