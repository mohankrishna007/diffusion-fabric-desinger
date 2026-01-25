"""
Pipeline execution engine - Orchestrates sequential stage execution.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from weaver.orchestrator.stage_loader import StageLoader
from weaver.shared.schemas import (
    PipelineContext, StageInput, StageOutput, 
    StageStatus, PipelineStatus
)
from weaver.shared.exceptions import (
    PipelineExecutionError, StageError, ValidationError,
    ContractViolationError
)


logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    Core pipeline execution engine.
    Loads stages, validates contracts, and executes the pipeline sequentially.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the pipeline engine.
        
        Args:
            config: Optional pipeline configuration
        """
        self.stage_loader = StageLoader()
        self.config = config or {}
        self._execution_history: Dict[str, Dict[str, Any]] = {}
    
    def execute(self, source_file: str, config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the complete 8-stage pipeline.
        
        Args:
            source_file: Path to input fabric design image
            config_override: Optional configuration overrides
        
        Returns:
            Pipeline execution result containing final output and metadata
        
        Raises:
            PipelineExecutionError: If pipeline execution fails
        """
        # Generate unique pipeline ID
        pipeline_id = str(uuid.uuid4())
        
        # Merge configurations
        pipeline_config = {**self.config, **(config_override or {})}
        
        # Create pipeline context
        context = PipelineContext(
            pipeline_id=pipeline_id,
            source_file=source_file,
            config=pipeline_config,
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
            # Execute stages sequentially (0 -> 7)
            for stage_number in range(8):
                self._execute_stage(stage_number, context)
            
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
                "stage_outputs": context.stage_outputs,
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
    
    def _execute_stage(self, stage_number: int, context: PipelineContext) -> None:
        """
        Execute a single stage with contract validation.
        
        Args:
            stage_number: Stage number to execute
            context: Pipeline context
        
        Raises:
            StageError: If stage execution fails
            ValidationError: If contract validation fails
        """
        logger.info(f"Executing stage {stage_number}: {context.pipeline_id}")
        
        # Update current stage
        self._execution_history[context.pipeline_id]["current_stage"] = stage_number
        
        try:
            # Load the stage
            stage = self.stage_loader.load_stage(stage_number)
            
            # Prepare stage input
            stage_input = self._prepare_stage_input(stage_number, context)
            
            # Validate input contract
            self._validate_input_contract(stage_number, stage_input)
            
            # Execute the stage
            stage_output = stage.run(stage_input)
            
            # Validate output contract
            self._validate_output_contract(stage_number, stage_output)
            
            # Store output in context
            context.stage_outputs[stage_number] = stage_output
            
            # Update execution history
            self._execution_history[context.pipeline_id]["completed_stages"].append(stage_number)
            self._execution_history[context.pipeline_id]["stage_outputs"][stage_number] = stage_output.model_dump()
            
            logger.info(f"Stage {stage_number} completed successfully: {context.pipeline_id}")
            
        except Exception as e:
            logger.error(f"Stage {stage_number} failed: {context.pipeline_id} - {str(e)}")
            raise
    
    def _prepare_stage_input(self, stage_number: int, context: PipelineContext) -> StageInput:
        """
        Prepare input for a stage based on previous stage outputs.
        
        Args:
            stage_number: Stage number
            context: Pipeline context
        
        Returns:
            Stage input data
        """
        # For now, create a basic StageInput
        # Stage-specific implementations will extend this
        return StageInput(
            pipeline_id=context.pipeline_id,
            stage_number=stage_number,
            metadata={
                "source_file": context.source_file,
                "config": context.config,
                "previous_outputs": {k: v.model_dump() for k, v in context.stage_outputs.items()}
            }
        )
    
    def _validate_input_contract(self, stage_number: int, input_data: StageInput) -> None:
        """
        Validate stage input contract.
        
        Args:
            stage_number: Stage number
            input_data: Input to validate
        
        Raises:
            ContractViolationError: If validation fails
        """
        # Basic validation - Pydantic already validates schema
        # Additional business logic validation can be added here
        pass
    
    def _validate_output_contract(self, stage_number: int, output_data: StageOutput) -> None:
        """
        Validate stage output contract.
        
        Args:
            stage_number: Stage number
            output_data: Output to validate
        
        Raises:
            ContractViolationError: If validation fails
        """
        # Check for contract violations
        if output_data.status == StageStatus.FAILED:
            raise ContractViolationError(
                stage_number=stage_number,
                violations=output_data.errors
            )
        
        # Additional validation can be added here
        pass
    
    def _build_final_result(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Build final pipeline result from all stage outputs.
        
        Args:
            context: Pipeline context
        
        Returns:
            Final result dictionary
        """
        # Get the output from the final stage (Stage 7)
        if 7 in context.stage_outputs:
            final_stage_output = context.stage_outputs[7]
            return {
                "status": "PASS" if final_stage_output.status == StageStatus.COMPLETED else "FAIL",
                "final_output": final_stage_output.data,
                "validation_report": final_stage_output.errors,
                "metrics": {
                    stage_num: output.metrics 
                    for stage_num, output in context.stage_outputs.items()
                }
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
