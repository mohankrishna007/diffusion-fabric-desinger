"""
Pipeline execution engine - Orchestrates stage execution in strict sequential order.
"""

import uuid
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from weaver.diffusion.stage_loader import StageLoader
from weaver.diffusion.stages import STAGE_CLASSES
from weaver.shared.schemas import (
    PipelineContext, PipelineStatus
)
from weaver.shared.exceptions import (
    PipelineExecutionError
)


logger = logging.getLogger(__name__)


class DiffusionPipelineEngine:
    """
    Core pipeline execution engine.
    Executes stages in strict sequential order as defined in configuration.
    All stages are mandatory and must complete successfully.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the pipeline engine.
        
        Args:
            config: Pipeline configuration with stage definitions
        """
        self.stage_loader = StageLoader()
        self.config = config or {}
        self._execution_history: Dict[str, Dict[str, Any]] = {}
        self._stages: List[Dict[str, Any]] = []
        
        # Initialize stages from config
        self._initialize_stages()
    
    def _initialize_stages(self) -> None:
        """
        Initialize stages from configuration.
        Stages execute in strict sequential order as defined in config.
        """
        logger.debug(f"Initializing stages with config keys: {list(self.config.keys())}")
        
        # Load stages from diffusion module configuration
        if "diffusion" not in self.config:
            logger.warning(f"No 'diffusion' module in configuration. Available keys: {list(self.config.keys())}")
            return
        
        diffusion_config = self.config["diffusion"]
        if "stages" not in diffusion_config:
            logger.warning(f"No stages defined in diffusion module. Available keys: {list(diffusion_config.keys())}")
            return
        
        stages_config = diffusion_config["stages"]
        logger.info(f"Found {len(stages_config)} stages in configuration")
        
        # Get available stage classes
        available_classes = set(STAGE_CLASSES.keys())
        logger.info(f"Available stage classes: {list(available_classes)}")
        
        # Load stages in config order
        skipped_stages = []
        
        for stage_config in stages_config:
            class_name = stage_config.get("class_name")
            stage_id = stage_config.get("id")
            
            if not class_name:
                logger.warning(f"Stage configuration missing 'class_name' field, skipping")
                continue
            
            if class_name not in available_classes:
                skipped_stages.append(f"{stage_id} ({class_name})")
                logger.warning(
                    f"Stage class '{class_name}' not available. "
                    f"This may be due to import errors."
                )
                continue
            
            self._stages.append(stage_config)
        
        if skipped_stages:
            logger.warning(
                f"Skipped {len(skipped_stages)} stages: {skipped_stages}. "
                f"Pipeline will run with {len(self._stages)} stages."
            )
        
        if not self._stages:
            logger.error("No valid stages available. Pipeline cannot execute.")
            return
        
        stage_names = [s['id'] for s in self._stages]
        logger.info(f"Pipeline execution order: {' -> '.join(stage_names)}")
    
    def execute(self, source_file: str, source_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the pipeline with dynamically configured stages.
        
        Args:
            source_file: Path to input fabric design image
            source_data: Source data associated with the input fabric design
        
        Returns:
            Pipeline execution result containing final output and metadata
        
        Raises:
            PipelineExecutionError: If pipeline execution fails
        """
        # Generate unique pipeline ID
        pipeline_id = str(uuid.uuid4())
        
        # Extract global settings (shared across all stages)
        global_config = self.config.get('global', {})
        
        # Create pipeline context
        context = PipelineContext(
            pipeline_id=pipeline_id,
            source_file=source_file,
            source_data=source_data,
            config=global_config, 
            created_at=datetime.utcnow()
        )
        
        logger.info(f"Starting pipeline execution: {pipeline_id}")
        
        # Store execution record
        self._execution_history[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "status": PipelineStatus.RUNNING,
            "source_file": source_file,
            "created_at": context.created_at,
            "current_stage": None,
            "completed_stages": [],
            "stage_outputs": {},
            "errors": []
        }
        
        try:
            # Execute stages in sequential order
            # Each stage receives the result from the previous stage
            prev_result = None
            
            for stage_index, stage_config in enumerate(self._stages):
                prev_result = self._execute_stage(stage_config, stage_index, context, prev_result)
            
            # Mark pipeline as completed
            self._execution_history[pipeline_id]["status"] = PipelineStatus.COMPLETED
            self._execution_history[pipeline_id]["current_stage"] = None
            
            logger.info(f"Pipeline execution completed: {pipeline_id}")
            
            # Return final result
            return {
                "pipeline_id": pipeline_id,
                "status": PipelineStatus.COMPLETED,
                "source_file": source_file,
                "result": self._build_final_result(context),
                "stage_outputs": {k: v.model_dump() for k, v in context.stage_outputs.items()},
                "created_at": context.created_at,
                "completed_at": datetime.utcnow()
            }
            
        except Exception as e:
            # Mark pipeline as failed
            self._execution_history[pipeline_id]["status"] = PipelineStatus.FAILED
            self._execution_history[pipeline_id]["errors"].append(str(e))
            
            logger.error(f"Pipeline execution failed: {pipeline_id} - {str(e)}")
            
            raise PipelineExecutionError(
                f"Pipeline execution failed at stage {self._execution_history[pipeline_id].get('current_stage')}",
                details={
                    "pipeline_id": pipeline_id,
                    "error": str(e),
                    "completed_stages": self._execution_history[pipeline_id]["completed_stages"]
                }
            ) from e
    
    def _execute_stage(self, stage_config: Dict[str, Any], stage_index: int, context: PipelineContext, prev_result: Any) -> Any:
        """
        Execute a single stage, passing the previous stage's result.
        
        Args:
            stage_config: Stage configuration dict with id, class_name, config
            stage_index: Stage position in execution order (0-based)
            context: Pipeline context
            prev_result: Result from previous stage (None for first stage)
        
        Returns:
            Result from this stage to pass to next stage
        
        Raises:
            StageError: If stage execution fails
        """
        stage_id = stage_config["id"]
        class_name = stage_config["class_name"]
        stage_cfg = stage_config.get("config", {})
        
        logger.info(f"Executing stage {stage_index} ({stage_id}): {context.pipeline_id}")
        
        # Update current stage
        self._execution_history[context.pipeline_id]["current_stage"] = stage_id
        
        try:
            # Load the stage by class name
            stage = self.stage_loader.load_stage(class_name)
            
            # Build config for stage execution
            # Merge global config with stage-specific config
            execution_config = {
                **context.config,  # Global settings (manufacturing, logging)
                **stage_cfg  # Stage-specific config
            }
            
            # For first stage (stage 0), add source_file and merge source_data into config
            if stage_index == 0:
                execution_config["source_file"] = context.source_file
                if context.source_data:
                    # Merge source_data fields (dpi, color_mode, repeat_unit) into config
                    execution_config.update(context.source_data)
            
            # Execute stage with new pattern:
            # - execute() calls validate_input() automatically
            # - All stages use same signature: execute(prev_result, pipeline_id, config)
            result = stage.execute(
                prev_result=prev_result,
                pipeline_id=context.pipeline_id,
                config=execution_config
            )
            
            # Store result in context
            context.stage_outputs[stage_id] = result
            
            # Save stage metadata to JSON file
            storage_dir = Path("storage") / context.pipeline_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            metadata_file = storage_dir / f"{stage_id}_metadata.json"
            
            # stage_metadata is always a dict in StageResult
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(result.stage_metadata, f, indent=2, default=str)
            
            logger.debug(f"Saved stage metadata to {metadata_file}")
            
            # Update execution history
            self._execution_history[context.pipeline_id]["completed_stages"].append(stage_id)
            if hasattr(result, 'model_dump'):
                self._execution_history[context.pipeline_id]["stage_outputs"][stage_id] = result.model_dump()
            else:
                self._execution_history[context.pipeline_id]["stage_outputs"][stage_id] = str(result)
            
            logger.info(f"Stage {stage_id} completed successfully: {context.pipeline_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Stage {stage_id} failed: {context.pipeline_id} - {str(e)}")
            raise
    
    def _build_final_result(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Build final pipeline result from all stage outputs.
        
        Args:
            context: Pipeline context
        
        Returns:
            Final result dictionary
        """
        # Get the result from the last stage
        if self._stages and context.stage_outputs:
            final_stage_id = self._stages[-1]['id']
            if final_stage_id in context.stage_outputs:
                final_result = context.stage_outputs[final_stage_id]
                return {
                    "status": "COMPLETED",
                    "final_stage": final_stage_id,
                    "final_output": final_result
                }
        
        return {"status": "INCOMPLETE"}
    
    def get_execution_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution status for a pipeline.
        
        Args:
            pipeline_id: Pipeline execution ID
        
        Returns:
            Execution status or None if not found
        """
        return self._execution_history.get(pipeline_id)
    
    def list_executions(self) -> list[Dict[str, Any]]:
        """
        List all pipeline executions.
        
        Returns:
            List of execution records
        """
        return list(self._execution_history.values())
    
    def get_execution_order(self) -> List[str]:
        """
        Get the configured stage execution order.
        
        Returns:
            Ordered list of stage IDs
        """
        return [s['id'] for s in self._stages]

