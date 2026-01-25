"""
Tests for the pipeline orchestrator.
"""

import pytest
from weaver.orchestrator.pipeline_engine import PipelineEngine
from weaver.orchestrator.stage_loader import StageLoader
from weaver.shared.exceptions import StageNotFoundError


class TestStageLoader:
    """Test suite for StageLoader."""
    
    def test_load_stage_0(self):
        """Test loading Stage 0."""
        loader = StageLoader()
        stage = loader.load_stage(0)
        
        assert stage is not None
        assert stage.metadata.stage_number == 0
        assert stage.metadata.name == "Input Acquisition"
    
    def test_load_all_stages(self):
        """Test loading all stages."""
        loader = StageLoader()
        stages = loader.load_all_stages()
        
        assert len(stages) == 8
        for i in range(8):
            assert i in stages
            assert stages[i].metadata.stage_number == i
    
    def test_load_invalid_stage(self):
        """Test loading invalid stage number."""
        loader = StageLoader()
        
        with pytest.raises(StageNotFoundError):
            loader.load_stage(99)
    
    def test_stage_caching(self):
        """Test that stages are cached."""
        loader = StageLoader()
        
        stage1 = loader.load_stage(0)
        stage2 = loader.load_stage(0)
        
        # Should be the same instance
        assert stage1 is stage2


class TestPipelineEngine:
    """Test suite for PipelineEngine."""
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = PipelineEngine()
        
        assert engine.stage_loader is not None
        assert engine.config == {}
    
    def test_engine_with_config(self):
        """Test engine with custom config."""
        config = {"test": "value"}
        engine = PipelineEngine(config=config)
        
        assert engine.config == config
    
    # TODO: Add more integration tests once stages are implemented
    # def test_full_pipeline_execution(self):
    #     """Test complete pipeline execution."""
    #     pass
