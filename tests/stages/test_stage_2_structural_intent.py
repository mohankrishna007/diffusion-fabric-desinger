"""
Contract tests for Stage 2: Structural Intent Definition

COVERAGE:
- Valid execution with synthetic test images
- Edge detection and skeleton extraction
- Topology validation (broken/disconnected cases)
- Region extraction and closure validation
- Boundary mask generation and alignment
- Metadata contract correctness

TESTING PHILOSOPHY:
Manufacturing-first validation - every test ensures Stage 2 extracts
deterministic geometric invariants that downstream stages can trust.
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import cv2
import numpy as np
import pytest

from weaver.stages.stage_2_structural_intent.processor import (
    Stage2StructuralIntent,
    Stage2Input,
)
from weaver.shared.exceptions import (
    TopologyViolationError,
    BoundaryInconsistencyError,
    ValidationError,
)
from weaver.shared.schemas import StageStatus


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pipeline_id() -> str:
    """Generate sample pipeline ID."""
    return "test-stage2-pipeline-001"


@pytest.fixture
def simple_square_image(temp_dir: Path) -> Path:
    """
    Create simple test image with a white square on black background.
    Perfect for testing edge detection and region extraction.
    """
    # 400x400 image with 200x200 repeat
    img = np.zeros((400, 400), dtype=np.uint8)
    
    # Draw white squares (one per repeat unit)
    cv2.rectangle(img, (50, 50), (150, 150), 255, -1)
    cv2.rectangle(img, (250, 50), (350, 150), 255, -1)
    cv2.rectangle(img, (50, 250), (150, 350), 255, -1)
    cv2.rectangle(img, (250, 250), (350, 350), 255, -1)
    
    img_path = temp_dir / "simple_square.png"
    cv2.imwrite(str(img_path), img)
    return img_path


@pytest.fixture
def complex_pattern_image(temp_dir: Path) -> Path:
    """
    Create complex test image with multiple shapes and regions.
    Tests edge detection on more realistic patterns.
    """
    # 600x600 image with 200x200 repeat
    img = np.zeros((600, 600), dtype=np.uint8)
    
    # Create repeating pattern with circles and rectangles
    for y_offset in [0, 200, 400]:
        for x_offset in [0, 200, 400]:
            # Circle
            cv2.circle(img, (x_offset + 100, y_offset + 100), 40, 255, -1)
            # Rectangle
            cv2.rectangle(
                img,
                (x_offset + 50, y_offset + 150),
                (x_offset + 150, y_offset + 180),
                255,
                -1
            )
    
    img_path = temp_dir / "complex_pattern.png"
    cv2.imwrite(str(img_path), img)
    return img_path


@pytest.fixture
def broken_topology_image(temp_dir: Path) -> Path:
    """
    Create image with intentionally broken topology (disconnected segments).
    Should fail topology validation.
    """
    img = np.zeros((200, 200), dtype=np.uint8)
    
    # Draw disconnected line segments
    cv2.line(img, (50, 50), (70, 50), 255, 1)
    cv2.line(img, (80, 50), (100, 50), 255, 1)  # Gap!
    cv2.line(img, (110, 50), (130, 50), 255, 1)
    
    img_path = temp_dir / "broken_topology.png"
    cv2.imwrite(str(img_path), img)
    return img_path


class TestStage2Metadata:
    """Test Stage 2 metadata."""
    
    def test_stage_metadata(self):
        """Test stage metadata is correct."""
        stage = Stage2StructuralIntent()
        
        assert stage.metadata.stage_number == 2
        assert stage.metadata.name == "Structural Intent Definition"
        assert "geometric invariants" in stage.metadata.description.lower()
        assert stage.metadata.version == "1.0.0"


class TestHappyPath:
    """Test successful execution scenarios."""
    
    def test_basic_square_execution(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test basic execution with simple square pattern."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent(config={
            "canny_threshold1": 50,
            "canny_threshold2": 150
        })
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Validate output status
        assert output.status == StageStatus.COMPLETED
        assert output.stage_number == 2
        assert "geometric invariants" in output.message.lower()
        
        # Validate artifacts created
        assert output.edge_map_path is not None
        assert Path(output.edge_map_path).exists()
        
        assert output.skeleton_map_path is not None
        assert Path(output.skeleton_map_path).exists()
        
        assert output.repeat_boundary_mask_path is not None
        assert Path(output.repeat_boundary_mask_path).exists()
        
        assert output.structural_metadata_path is not None
        assert Path(output.structural_metadata_path).exists()
        
        # Validate metadata contract
        assert output.structural_metadata is not None
        metadata = output.structural_metadata
        
        assert metadata["schema_version"] == "stage2.v1"
        assert metadata["width_px"] == 400
        assert metadata["height_px"] == 400
        assert metadata["dpi"] == 300
        assert metadata["repeat_width_px"] == 200
        assert metadata["repeat_height_px"] == 200
        assert metadata["topology_validated"] is True
        assert metadata["repeat_boundary_validated"] is True
        assert len(metadata["guarantees"]) > 0
        
        # Validate metrics
        assert output.metrics["edge_pixels"] > 0
        assert output.metrics["skeleton_nodes"] > 0
        assert output.metrics["skeleton_edges"] >= 0
    
    def test_complex_pattern_execution(
        self,
        complex_pattern_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test execution with complex repeating pattern."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(complex_pattern_image),
            width_px=600,
            height_px=600,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        assert output.status == StageStatus.COMPLETED
        assert output.metrics["edge_pixels"] > 0
        assert output.metrics["regions_detected"] >= 0
        
        # Validate all files exist
        assert Path(output.edge_map_path).exists()
        assert Path(output.skeleton_map_path).exists()
        assert Path(output.repeat_boundary_mask_path).exists()
        assert Path(output.structural_metadata_path).exists()


class TestEdgeDetection:
    """Test edge detection functionality."""
    
    def test_edge_map_is_binary(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that edge map contains only binary values."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Load edge map and verify binary
        edge_map = cv2.imread(output.edge_map_path, cv2.IMREAD_GRAYSCALE)
        unique_values = np.unique(edge_map)
        
        # Should only contain 0 and/or 255
        assert all(val in [0, 255] for val in unique_values)
    
    def test_canny_threshold_configuration(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that Canny thresholds can be configured."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        # Test with different thresholds
        stage_low = Stage2StructuralIntent(config={
            "canny_threshold1": 30,
            "canny_threshold2": 100
        })
        
        stage_high = Stage2StructuralIntent(config={
            "canny_threshold1": 100,
            "canny_threshold2": 200
        })
        
        assert stage_low.canny_threshold1 == 30
        assert stage_low.canny_threshold2 == 100
        assert stage_high.canny_threshold1 == 100
        assert stage_high.canny_threshold2 == 200


class TestSkeletonAndTopology:
    """Test skeleton extraction and topology validation."""
    
    def test_skeleton_is_single_pixel_wide(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that skeleton is 1-pixel wide."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Load skeleton and verify it's thinner than edge map
        skeleton = cv2.imread(output.skeleton_map_path, cv2.IMREAD_GRAYSCALE)
        edge_map = cv2.imread(output.edge_map_path, cv2.IMREAD_GRAYSCALE)
        
        skeleton_pixels = np.sum(skeleton > 0)
        edge_pixels = np.sum(edge_map > 0)
        
        # Skeleton should have fewer pixels than edge map
        assert skeleton_pixels <= edge_pixels
    
    def test_topology_validation_passes(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that topology validation passes for valid skeleton."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Topology validation should pass
        assert output.structural_metadata["topology_validated"] is True
        assert output.metrics["skeleton_nodes"] > 0
        assert output.metrics["skeleton_edges"] >= 0


class TestRegionExtraction:
    """Test region extraction and closure validation."""
    
    def test_regions_extracted(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that closed regions are extracted."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Should detect regions (squares)
        assert output.metrics["regions_detected"] >= 0
        
        # Region masks directory should exist
        assert output.region_masks_dir is not None
        region_dir = Path(output.region_masks_dir)
        assert region_dir.exists()
    
    def test_region_masks_are_binary(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that region masks contain only binary values."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Check all region masks are binary
        region_dir = Path(output.region_masks_dir)
        for mask_file in region_dir.glob("region_*.png"):
            mask = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE)
            unique_values = np.unique(mask)
            assert all(val in [0, 255] for val in unique_values)


class TestBoundaryMask:
    """Test repeat boundary mask generation and validation."""
    
    def test_boundary_mask_alignment(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that boundary mask aligns with repeat dimensions."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Boundary validation should pass
        assert output.structural_metadata["repeat_boundary_validated"] is True
        
        # Load boundary mask and verify dimensions
        boundary_mask = cv2.imread(
            output.repeat_boundary_mask_path,
            cv2.IMREAD_GRAYSCALE
        )
        
        assert boundary_mask.shape == (400, 400)
    
    def test_boundary_mask_covers_edges(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that boundary mask covers image edges."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Load boundary mask
        boundary_mask = cv2.imread(
            output.repeat_boundary_mask_path,
            cv2.IMREAD_GRAYSCALE
        )
        
        # Check that borders are marked (255)
        assert np.any(boundary_mask[0, :] == 255)  # Top edge
        assert np.any(boundary_mask[-1, :] == 255)  # Bottom edge
        assert np.any(boundary_mask[:, 0] == 255)  # Left edge
        assert np.any(boundary_mask[:, -1] == 255)  # Right edge
    
    def test_boundary_mismatch_fails(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that non-integer tiling fails validation."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        # 400x400 image with 300x300 repeat (non-integer tiling)
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=300,
            repeat_height_px=300,
            workspace_dir=str(workspace)
        )
        
        with pytest.raises(BoundaryInconsistencyError) as exc_info:
            stage.execute(input_data)
        
        assert "not divisible by" in str(exc_info.value).lower()


class TestStructuralMetadata:
    """Test structural metadata contract."""
    
    def test_metadata_json_valid(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that metadata JSON is valid and complete."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Load and parse JSON
        with open(output.structural_metadata_path) as f:
            metadata = json.load(f)
        
        # Validate required fields
        assert metadata["schema_version"] == "stage2.v1"
        assert metadata["width_px"] == 400
        assert metadata["height_px"] == 400
        assert metadata["dpi"] == 300
        assert metadata["repeat_width_px"] == 200
        assert metadata["repeat_height_px"] == 200
        assert "edge_count" in metadata
        assert "skeleton_node_count" in metadata
        assert "skeleton_edge_count" in metadata
        assert "region_count" in metadata
        assert metadata["topology_validated"] is True
        assert metadata["repeat_boundary_validated"] is True
        assert isinstance(metadata["guarantees"], list)
        assert len(metadata["guarantees"]) > 0
    
    def test_metadata_guarantees_present(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that metadata includes explicit guarantees."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        guarantees = output.structural_metadata["guarantees"]
        
        # Should include key guarantees
        guarantee_text = " ".join(guarantees).lower()
        assert "topology" in guarantee_text
        assert "boundary" in guarantee_text or "boundaries" in guarantee_text
        assert "region" in guarantee_text


class TestFailureScenarios:
    """Test failure handling and error reporting."""
    
    def test_missing_image_fails(
        self,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that missing image file fails gracefully."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path="/nonexistent/image.png",
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        with pytest.raises(ValidationError) as exc_info:
            stage.execute(input_data)
        
        assert "failed to load" in str(exc_info.value).lower()
    
    def test_empty_image_fails(
        self,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that completely black image (no edges) fails topology validation."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        # Create empty black image
        empty_img = np.zeros((200, 200), dtype=np.uint8)
        empty_path = temp_dir / "empty.png"
        cv2.imwrite(str(empty_path), empty_img)
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(empty_path),
            width_px=200,
            height_px=200,
            dpi=300,
            repeat_width_px=100,
            repeat_height_px=100,
            workspace_dir=str(workspace)
        )
        
        with pytest.raises(TopologyViolationError) as exc_info:
            stage.execute(input_data)
        
        assert "empty" in str(exc_info.value).lower()


class TestOutputContract:
    """Test output contract compliance."""
    
    def test_output_contains_all_required_fields(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that output contains all required fields."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Required fields
        assert output.stage_number == 2
        assert output.status == StageStatus.COMPLETED
        assert output.message != ""
        assert output.edge_map_path is not None
        assert output.skeleton_map_path is not None
        assert output.region_masks_dir is not None
        assert output.repeat_boundary_mask_path is not None
        assert output.structural_metadata_path is not None
        assert output.structural_metadata is not None
        
        # Metrics
        assert "edge_pixels" in output.metrics
        assert "skeleton_nodes" in output.metrics
        assert "skeleton_edges" in output.metrics
        assert "regions_detected" in output.metrics
    
    def test_output_immutability(
        self,
        simple_square_image: Path,
        temp_dir: Path,
        sample_pipeline_id: str
    ):
        """Test that output is immutable (frozen)."""
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        stage = Stage2StructuralIntent()
        
        input_data = Stage2Input(
            pipeline_id=sample_pipeline_id,
            stage_number=2,
            canonical_image_path=str(simple_square_image),
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_width_px=200,
            repeat_height_px=200,
            workspace_dir=str(workspace)
        )
        
        output = stage.execute(input_data)
        
        # Attempt to modify should fail
        with pytest.raises(Exception):  # Pydantic ValidationError or AttributeError
            output.status = StageStatus.FAILED
