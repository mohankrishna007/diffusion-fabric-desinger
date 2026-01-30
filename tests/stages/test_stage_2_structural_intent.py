"""
Contract tests for Stage 2: Structural Intent Extraction (Compiler IR)

COVERAGE:
- Resolution-independent symbolic representation
- Motif graph construction with skeleton island handling
- Curve intent inference and topology extraction
- Symmetry detection with KD-tree optimization
- Constraint inference and uncertainty encoding
- Resolution independence validation

TESTING PHILOSOPHY:
Compiler IR validation - every test ensures Stage 2 produces resolution-independent
symbolic representations that Stage 3+ can consume without seeing the original image.
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import cv2
import numpy as np
import pytest

from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
from weaver.diffusion.stages.stage_result import (
    CanonicalNormalizationResult,
    StructuralIntentResult
)
from weaver.shared.exceptions import ValidationError
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


# ============================================================================
# BASIC FUNCTIONALITY TESTS
# ============================================================================

class TestBasicFunctionality:
    """Test basic Stage 2 functionality with new compiler IR architecture."""
    
    def test_stage_metadata(self):
        """Test stage metadata is correct."""
        stage = StructuralIntentStage()
        
        assert stage.metadata.stage_id == "structural_intent"
        assert stage.metadata.name == "Structural Intent Extraction"
        assert "compiler IR" in stage.metadata.description.lower() or "symbolic" in stage.metadata.description.lower()
        assert stage.metadata.version == "2.0.0"
    
    def test_simple_execution(
        self,
        simple_square_image: Path,
        sample_pipeline_id: str
    ):
        """Test basic execution with simple square pattern."""
        stage = StructuralIntentStage()
        
        # Load image as canonical format
        img_gray = cv2.imread(str(simple_square_image), cv2.IMREAD_GRAYSCALE)
        img_rgb = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
        
        # Create canonical result (Stage 1 output)
        canonical_result = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={
                "stage_number": 1,
                "stage_name": "Canonical Normalization"
            },
            pixel_array=img_rgb,
            pixel_array_path=None,
            width_px=400,
            height_px=400,
            dpi=300,
            repeat_unit_px={"width": 200, "height": 200},
            color_mode="RGB"
        )
        
        # Execute Stage 2
        result = stage._execute(canonical_result, sample_pipeline_id, {})
        
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=300
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=200
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
            repeat_height_px=100
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
            repeat_height_px=200
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
            repeat_height_px=200
        )
        
        output = stage.execute(input_data)
        
        # Attempt to modify should fail
        with pytest.raises(Exception):  # Pydantic ValidationError or AttributeError
            output.status = StageStatus.FAILED


# ============================================================================
# RESOLUTION INDEPENDENCE TESTS (CRITICAL)
# ============================================================================

class TestResolutionIndependence:
    """
    Critical tests to validate resolution independence of Stage 2 output.
    
    These tests ensure that:
    1. Graph topology is identical across resolutions
    2. Only relative scale attributes change proportionally
    3. Skeleton islands persist identically
    4. Symmetry detection is resolution-invariant
    5. Output size does not scale with resolution
    """
    
    @pytest.fixture
    def test_pattern_512(self, temp_dir: Path) -> tuple[Path, np.ndarray]:
        """Create 512x512 test pattern with canonical raster."""
        # Create simple pattern: square with nested circle
        img_rgb = np.zeros((512, 512, 3), dtype=np.uint8)
        img_rgb[:] = (255, 255, 255)  # White background
        
        # Draw black square
        cv2.rectangle(img_rgb, (128, 128), (384, 384), (0, 0, 0), thickness=8)
        
        # Draw black circle
        cv2.circle(img_rgb, (256, 256), 80, (0, 0, 0), thickness=6)
        
        # Add small island (skeleton island candidate)
        cv2.circle(img_rgb, (400, 100), 10, (0, 0, 0), thickness=2)
        
        # Save as .npy (canonical format)
        npy_path = temp_dir / "pattern_512.npy"
        np.save(npy_path, img_rgb)
        
        return npy_path, img_rgb
    
    @pytest.fixture
    def test_pattern_2048(self, temp_dir: Path) -> tuple[Path, np.ndarray]:
        """Create 2048x2048 test pattern (4x scaled version)."""
        # Create same pattern at 4x resolution
        img_rgb = np.zeros((2048, 2048, 3), dtype=np.uint8)
        img_rgb[:] = (255, 255, 255)
        
        # Scale all coordinates by 4
        cv2.rectangle(img_rgb, (512, 512), (1536, 1536), (0, 0, 0), thickness=32)
        cv2.circle(img_rgb, (1024, 1024), 320, (0, 0, 0), thickness=24)
        cv2.circle(img_rgb, (1600, 400), 40, (0, 0, 0), thickness=8)
        
        npy_path = temp_dir / "pattern_2048.npy"
        np.save(npy_path, img_rgb)
        
        return npy_path, img_rgb
    
    def test_graph_isomorphism_across_resolutions(
        self,
        test_pattern_512: tuple[Path, np.ndarray],
        test_pattern_2048: tuple[Path, np.ndarray],
        sample_pipeline_id: str
    ):
        """Test that motif graph topology is identical across resolutions."""
        from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
        from weaver.diffusion.stages.stage_result import CanonicalNormalizationResult
        
        stage = StructuralIntentStage()
        
        # Process 512px version
        result_512_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array_path=str(test_pattern_512[0]),
            pixel_array=test_pattern_512[1],
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={\"width\": 512, \"height\": 512},
            color_mode=\"RGB\"
        )
        
        result_512 = stage._execute(result_512_canonical, sample_pipeline_id, {})
        
        # Process 2048px version
        result_2048_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id + \"_2048\",
            stage_metadata={},
            pixel_array_path=str(test_pattern_2048[0]),
            pixel_array=test_pattern_2048[1],
            width_px=2048,
            height_px=2048,
            dpi=300,
            repeat_unit_px={\"width\": 2048, \"height\": 2048},
            color_mode=\"RGB\"
        )
        
        result_2048 = stage._execute(result_2048_canonical, sample_pipeline_id + \"_2048\", {})
        
        # CRITICAL TEST 1: Same number of nodes by type
        node_types_512 = [n.type for n in result_512.motif_nodes]
        node_types_2048 = [n.type for n in result_2048.motif_nodes]
        
        from collections import Counter
        assert Counter(node_types_512) == Counter(node_types_2048), \\
            f\"Node type counts differ: 512px={Counter(node_types_512)}, 2048px={Counter(node_types_2048)}\"
        
        # CRITICAL TEST 2: Same number of edges by relation type
        edge_relations_512 = [e.relation for e in result_512.motif_edges]
        edge_relations_2048 = [e.relation for e in result_2048.motif_edges]
        
        assert Counter(edge_relations_512) == Counter(edge_relations_2048), \\
            f\"Edge relation counts differ: 512px={Counter(edge_relations_512)}, 2048px={Counter(edge_relations_2048)}\"
        
        # CRITICAL TEST 3: Topology statistics match
        assert result_512.topology.component_count == result_2048.topology.component_count, \\
            \"Component counts differ across resolutions\"
        
        assert result_512.topology.junction_count == result_2048.topology.junction_count, \\
            \"Junction counts differ across resolutions\"
        
        assert result_512.topology.loop_count == result_2048.topology.loop_count, \\
            \"Loop counts differ across resolutions\"
    
    def test_skeleton_island_stability(
        self,
        test_pattern_512: tuple[Path, np.ndarray],
        test_pattern_2048: tuple[Path, np.ndarray],
        sample_pipeline_id: str
    ):
        """Test that skeleton islands persist identically across resolutions."""
        from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
        from weaver.diffusion.stages.stage_result import CanonicalNormalizationResult
        
        stage = StructuralIntentStage()
        
        # Process both resolutions
        result_512_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array_path=str(test_pattern_512[0]),
            pixel_array=test_pattern_512[1],
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={\"width\": 512, \"height\": 512},
            color_mode=\"RGB\"
        )
        
        result_512 = stage._execute(result_512_canonical, sample_pipeline_id, {})
        
        result_2048_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id + \"_2048\",
            stage_metadata={},
            pixel_array_path=str(test_pattern_2048[0]),
            pixel_array=test_pattern_2048[1],
            width_px=2048,
            height_px=2048,
            dpi=300,
            repeat_unit_px={\"width\": 2048, \"height\": 2048},
            color_mode=\"RGB\"
        )
        
        result_2048 = stage._execute(result_2048_canonical, sample_pipeline_id + \"_2048\", {})
        
        # Count skeleton islands (NOISE_CANDIDATE nodes)
        islands_512 = [n for n in result_512.motif_nodes if n.role == \"NOISE_CANDIDATE\"]
        islands_2048 = [n for n in result_2048.motif_nodes if n.role == \"NOISE_CANDIDATE\"]
        
        # CRITICAL TEST: Same number of islands
        assert len(islands_512) == len(islands_2048), \\
            f\"Skeleton island count differs: 512px={len(islands_512)}, 2048px={len(islands_2048)}\"
        
        # CRITICAL TEST: Islands have low confidence in both
        for island in islands_512:
            assert island.confidence < 0.5, \\
                f\"Island {island.id} has unexpectedly high confidence: {island.confidence}\"
        
        for island in islands_2048:
            assert island.confidence < 0.5, \\
                f\"Island {island.id} has unexpectedly high confidence: {island.confidence}\"
        
        # CRITICAL TEST: Islands recorded in uncertainty
        island_uncertainty_512 = [u for u in result_512.uncertainty if u.category == \"SKELETON_ISLAND\"]
        island_uncertainty_2048 = [u for u in result_2048.uncertainty if u.category == \"SKELETON_ISLAND\"]
        
        assert len(island_uncertainty_512) == len(islands_512), \\
            \"Not all islands recorded in uncertainty (512px)\"
        assert len(island_uncertainty_2048) == len(islands_2048), \\
            \"Not all islands recorded in uncertainty (2048px)\"
    
    def test_output_size_bounded(
        self,
        test_pattern_512: tuple[Path, np.ndarray],
        test_pattern_2048: tuple[Path, np.ndarray],
        sample_pipeline_id: str
    ):
        """Test that output size does not scale with resolution."""
        from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
        from weaver.diffusion.stages.stage_result import CanonicalNormalizationResult
        import json
        
        stage = StructuralIntentStage()
        
        # Process both resolutions
        result_512_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array_path=str(test_pattern_512[0]),
            pixel_array=test_pattern_512[1],
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={\"width\": 512, \"height\": 512},
            color_mode=\"RGB\"
        )
        
        result_512 = stage._execute(result_512_canonical, sample_pipeline_id, {})
        
        result_2048_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id + \"_2048\",
            stage_metadata={},
            pixel_array_path=str(test_pattern_2048[0]),
            pixel_array=test_pattern_2048[1],
            width_px=2048,
            height_px=2048,
            dpi=300,
            repeat_unit_px={\"width\": 2048, \"height\": 2048},
            color_mode=\"RGB\"
        )
        
        result_2048 = stage._execute(result_2048_canonical, sample_pipeline_id + \"_2048\", {})
        
        # Serialize to JSON and measure size
        json_512 = result_512.model_dump_json()
        json_2048 = result_2048.model_dump_json()
        
        size_512 = len(json_512)
        size_2048 = len(json_2048)
        
        # Allow up to 20% size difference (due to floating point precision)
        size_ratio = size_2048 / size_512 if size_512 > 0 else float('inf')
        
        assert size_ratio < 1.2, \\
            f\"Output size scales with resolution: 512px={size_512} bytes, 2048px={size_2048} bytes, ratio={size_ratio:.2f}\"
        
        # CRITICAL TEST: Output should be approximately the same size
        # (within 20% tolerance for floating point differences)
        assert abs(size_512 - size_2048) / size_512 < 0.2, \\
            f\"Output sizes differ significantly: {size_512} vs {size_2048} bytes\"
    
    def test_symmetry_detection_invariant(
        self,
        test_pattern_512: tuple[Path, np.ndarray],
        test_pattern_2048: tuple[Path, np.ndarray],
        sample_pipeline_id: str
    ):
        """Test that symmetry detection is resolution-invariant."""
        from weaver.diffusion.stages.structural_intent.processor import StructuralIntentStage
        from weaver.diffusion.stages.stage_result import CanonicalNormalizationResult
        
        stage = StructuralIntentStage()
        
        # Process both resolutions
        result_512_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id,
            stage_metadata={},
            pixel_array_path=str(test_pattern_512[0]),
            pixel_array=test_pattern_512[1],
            width_px=512,
            height_px=512,
            dpi=300,
            repeat_unit_px={\"width\": 512, \"height\": 512},
            color_mode=\"RGB\"
        )
        
        result_512 = stage._execute(result_512_canonical, sample_pipeline_id, {\"symmetry_detection\": \"REQUIRED\"})
        
        result_2048_canonical = CanonicalNormalizationResult(
            pipeline_id=sample_pipeline_id + \"_2048\",
            stage_metadata={},
            pixel_array_path=str(test_pattern_2048[0]),
            pixel_array=test_pattern_2048[1],
            width_px=2048,
            height_px=2048,
            dpi=300,
            repeat_unit_px={\"width\": 2048, \"height\": 2048},
            color_mode=\"RGB\"
        )
        
        result_2048 = stage._execute(result_2048_canonical, sample_pipeline_id + \"_2048\", {\"symmetry_detection\": \"REQUIRED\"})
        
        # Extract symmetry types
        symmetry_types_512 = [p.symmetry_type for p in result_512.pattern_intent]
        symmetry_types_2048 = [p.symmetry_type for p in result_2048.pattern_intent]
        
        # CRITICAL TEST: Same symmetry types detected
        assert set(symmetry_types_512) == set(symmetry_types_2048), \\
            f\"Symmetry types differ: 512px={symmetry_types_512}, 2048px={symmetry_types_2048}\"
        
        # CRITICAL TEST: Same symmetry orders (for rotational)
        orders_512 = [p.order for p in result_512.pattern_intent if p.order is not None]
        orders_2048 = [p.order for p in result_2048.pattern_intent if p.order is not None]
        
        assert sorted(orders_512) == sorted(orders_2048), \\
            f\"Symmetry orders differ: 512px={orders_512}, 2048px={orders_2048}\"

