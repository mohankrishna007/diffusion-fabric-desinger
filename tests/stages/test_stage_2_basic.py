"""
Basic tests for Stage 2: Structural Intent Extraction (Compiler IR)
Simple tests to validate the new resolution-independent implementation.
"""

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
from weaver.diffusion.stages.stage_result import (
    CanonicalNormalizationResult,
    StructuralIntentResult
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pipeline_id() -> str:
    """Generate sample pipeline ID."""
    return "test-stage2-basic-001"


@pytest.fixture
def simple_test_image(temp_dir: Path):
    """Create simple test image with a square."""
    img_rgb = np.zeros((512, 512, 3), dtype=np.uint8)
    img_rgb[:] = (255, 255, 255)  # White background
    
    # Draw black square
    cv2.rectangle(img_rgb, (128, 128), (384, 384), (0, 0, 0), thickness=8)
    
    # Draw black circle
    cv2.circle(img_rgb, (256, 256), 80, (0, 0, 0), thickness=6)
    
    # Add small island (skeleton island candidate)
    cv2.circle(img_rgb, (400, 100), 10, (0, 0, 0), thickness=2)
    
    return img_rgb


class TestStage2Basic:
    """Basic Stage 2 functionality tests."""
    
    def test_stage_metadata(self):
        """Test stage metadata is correct."""
        stage = StructuralIntentStage()
        
        assert stage.metadata.stage_id == "structural_intent"
        assert stage.metadata.name == "Structural Intent Extraction"
        assert stage.metadata.version == "2.0.0"
    
    def test_basic_execution(
        self,
        simple_test_image: np.ndarray,
        sample_pipeline_id: str,
        temp_dir: Path
    ):
        """Test basic execution with simple pattern."""
        stage = StructuralIntentStage()
        
        # Save pixel array to file (simulating Stage 1 behavior)
        storage_dir = temp_dir / sample_pipeline_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        npy_path = storage_dir / "canonical_raster.npy"
        np.save(str(npy_path), simple_test_image)
        
        # Create canonical result (Stage 1 output)
        canonical_result = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={"stage_number": 1},
            pixel_array=None,  # Stage 1 now always passes None
            pixel_array_path=str(npy_path),  # Only path
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={"width": 512, "height": 512},
            color_mode="RGB"
        )
        
        # Execute Stage 2 (using execute() to test automatic JSON saving)
        result = stage.execute(canonical_result, sample_pipeline_id, {})
        
        # Validate result structure
        assert isinstance(result, StructuralIntentResult)
        assert result.pipeline_id == sample_pipeline_id
        assert len(result.motif_nodes) > 0, "Should extract at least one motif node"
        assert result.topology.component_count >= 1, "Should have at least one component"
        
        # Validate resolution independence
        assert all(0 <= n.relative_scale <= 1 for n in result.motif_nodes), \
            "All node scales should be normalized to [0, 1]"
        assert all(0 <= n.confidence <= 1 for n in result.motif_nodes), \
            "All node confidences should be in [0, 1]"
        
        # Validate guarantees
        assert len(result.guarantees) > 0
        assert any("resolution-independent" in g.lower() for g in result.guarantees)
        
        print(f"✓ Extracted {len(result.motif_nodes)} motif nodes")
        print(f"✓ {result.topology.component_count} connected components")
        print(f"✓ {len(result.uncertainty)} uncertainty records")
    
    def test_skeleton_islands_preserved(
        self,
        simple_test_image: np.ndarray,
        sample_pipeline_id: str,
        temp_dir: Path
    ):
        """Test that skeleton islands are preserved with low confidence."""
        stage = StructuralIntentStage()
        
        # Save pixel array to file
        storage_dir = temp_dir / sample_pipeline_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        npy_path = storage_dir / "canonical_raster.npy"
        np.save(str(npy_path), simple_test_image)
        
        canonical_result = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array=None,
            pixel_array_path=str(npy_path),
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={"width": 512, "height": 512},
            color_mode="RGB"
        )
        
        result = stage.execute(canonical_result, sample_pipeline_id, {})
        
        # Check for skeleton islands (NOISE_CANDIDATE nodes)
        islands = [n for n in result.motif_nodes if n.role == "NOISE_CANDIDATE"]
        
        # All islands should have low confidence
        for island in islands:
            assert island.confidence < 0.5, \
                f"Island {island.id} has unexpectedly high confidence: {island.confidence}"
        
        # Islands should be recorded in uncertainty
        island_uncertainty = [u for u in result.uncertainty if u.category == "SKELETON_ISLAND"]
        assert len(island_uncertainty) == len(islands), \
            "All islands should be recorded in uncertainty"
        
        print(f"✓ Found {len(islands)} skeleton islands (preserved, not deleted)")
    
    def test_motif_graph_structure(
        self,
        simple_test_image: np.ndarray,
        sample_pipeline_id: str,
        temp_dir: Path
    ):
        """Test motif graph structure (nodes and edges)."""
        stage = StructuralIntentStage()
        
        # Save pixel array to file
        storage_dir = temp_dir / sample_pipeline_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        npy_path = storage_dir / "canonical_raster.npy"
        np.save(str(npy_path), simple_test_image)
        
        canonical_result = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array=None,
            pixel_array_path=str(npy_path),
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={"width": 512, "height": 512},
            color_mode="RGB"
        )
        
        result = stage.execute(canonical_result, sample_pipeline_id, {})
        
        # Validate node types
        valid_node_types = {"STROKE", "LOOP", "JUNCTION", "REGION", "BORDER", "NOISE_CANDIDATE"}
        for node in result.motif_nodes:
            assert node.type in valid_node_types, f"Invalid node type: {node.type}"
        
        # Validate edge relations
        valid_relations = {"CONNECTED", "ADJACENT", "REPEATS_WITH", "SYMMETRIC_TO", "ENCLOSED_BY", "POSSIBLE_ATTACHMENT"}
        for edge in result.motif_edges:
            assert edge.relation in valid_relations, f"Invalid edge relation: {edge.relation}"
            assert 0 <= edge.confidence <= 1, "Edge confidence out of range"
        
        print(f"✓ Motif graph structure is valid")
        print(f"  - {len(result.motif_nodes)} nodes")
        print(f"  - {len(result.motif_edges)} edges")
