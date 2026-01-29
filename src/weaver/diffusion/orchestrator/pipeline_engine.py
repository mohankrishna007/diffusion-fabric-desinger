"""
Pipeline execution engine - Orchestrates dynamic stage execution based on configuration.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from weaver.diffusion.orchestrator.stage_loader import StageLoader
from weaver.diffusion.orchestrator.stage_registry import stage_registry
from weaver.diffusion.orchestrator.dependency_resolver import DependencyResolver, StageInputBuilder
from weaver.shared.schemas import (
    PipelineContext, StageInput, StageOutput, 
    StageStatus, PipelineStatus
)
from weaver.shared.exceptions import (
    PipelineExecutionError, StageError, ValidationError,
    ContractViolationError, ConfigurationError
)


logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    Core pipeline execution engine.
    Loads stages dynamically based on configuration and executes them in dependency order.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the pipeline engine.
        
        Args:
            config: Pipeline configuration with stage definitions
        """
        self.stage_loader = StageLoader()
        self.config = config or {}
        self.dependency_resolver = DependencyResolver()
        self._execution_history: Dict[str, Dict[str, Any]] = {}
        self._execution_order: List[str] = []
        
        # Initialize execution order from config
        self._initialize_execution_order()
    
    def _initialize_execution_order(self) -> None:
        """
        Initialize stage execution order from configuration.
        """
        logger.debug(f"Initializing execution order with config keys: {list(self.config.keys())}")
        
        if "stages" not in self.config:
            logger.warning(f"No stages defined in configuration. Available keys: {list(self.config.keys())}")
            return
        
        stages_config = self.config["stages"]
        logger.info(f"Found {len(stages_config)} stages in configuration")
        
        # Get currently registered stages
        registered_stages = stage_registry.get_all_registrations()
        registered_ids = set(registered_stages.keys())
        logger.info(f"Currently registered stages: {list(registered_ids)}")
        
        # Filter to only stages that are both configured and registered
        valid_stages = []
        skipped_stages = []
        
        for stage_config in stages_config:
            stage_id = stage_config.get("id")
            
            if not stage_id:
                logger.warning(f"Stage configuration missing 'id' field, skipping")
                continue
            
            if stage_id not in registered_ids:
                skipped_stages.append(stage_id)
                logger.warning(
                    f"Stage '{stage_id}' configured but not registered, skipping. "
                    f"This may be due to import errors or missing decorators."
                )
                continue
            
            valid_stages.append(stage_config)
        
        if skipped_stages:
            logger.warning(
                f"Skipped {len(skipped_stages)} stages that are not registered: {skipped_stages}. "
                f"Pipeline will run with {len(valid_stages)} stages."
            )
        
        if not valid_stages:
            logger.error("No valid stages available after filtering. Pipeline cannot execute.")
            return
        
        # Build dependency graph with valid stages only
        for stage_config in valid_stages:
            stage_id = stage_config["id"]
            dependencies = stage_config.get("dependencies", [])
            
            # Filter dependencies to only include registered stages
            valid_deps = [dep for dep in dependencies if dep in registered_ids]
            if len(valid_deps) < len(dependencies):
                skipped_deps = set(dependencies) - set(valid_deps)
                logger.warning(
                    f"Stage '{stage_id}' has unregistered dependencies {skipped_deps}, "
                    f"they will be ignored"
                )
            
            self.dependency_resolver.add_stage(stage_id, valid_deps)
        
        # Validate dependencies
        self.dependency_resolver.validate_dependencies()
        
        # Resolve execution order
        self._execution_order = self.dependency_resolver.resolve_execution_order()
        
        # Set execution order in registry
        stage_registry.set_execution_order(self._execution_order)
        
        logger.info(f"Pipeline execution order: {' -> '.join(self._execution_order)}")
    
    def execute(self, source_file: str, config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the pipeline with dynamically configured stages.
        
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
            # Execute stages in dependency order
            for stage_index, stage_id in enumerate(self._execution_order):
                self._execute_stage(stage_id, stage_index, context)
            
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
    
    def _execute_stage(self, stage_id: str, stage_index: int, context: PipelineContext) -> None:
        """
        Execute a single stage with contract validation.
        
        Args:
            stage_id: Stage identifier
            stage_index: Stage position in execution order (0-based)
            context: Pipeline context
        
        Raises:
            StageError: If stage execution fails
            ValidationError: If contract validation fails
        """
        logger.info(f"Executing stage {stage_index} ({stage_id}): {context.pipeline_id}")
        
        # Update current stage
        self._execution_history[context.pipeline_id]["current_stage"] = stage_id
        
        try:
            # Load the stage
            stage = self.stage_loader.load_stage(stage_id)
            
            # Prepare stage input based on dependencies
            stage_input = self._prepare_stage_input(stage_id, stage_index, context)
            
            # Validate input contract
            self._validate_input_contract(stage_id, stage_input)
            
            # Execute the stage
            stage_output = stage.run(stage_input)
            
            # Validate output contract
            self._validate_output_contract(stage_id, stage_output)
            
            # Store output in context (keyed by stage_id)
            context.stage_outputs[stage_id] = stage_output
            
            # Update execution history
            self._execution_history[context.pipeline_id]["completed_stages"].append(stage_id)
            self._execution_history[context.pipeline_id]["stage_outputs"][stage_id] = stage_output.model_dump()
            
            logger.info(f"Stage {stage_id} completed successfully: {context.pipeline_id}")
            
        except Exception as e:
            logger.error(f"Stage {stage_id} failed: {context.pipeline_id} - {str(e)}")
            raise
    
    def _prepare_stage_input(self, stage_id: str, stage_index: int, context: PipelineContext) -> Any:
        """
        Prepare input for a stage based on dependencies.
        
        Args:
            stage_id: Stage identifier
            stage_index: Stage position in execution order
            context: Pipeline context
        
        Returns:
            Stage input data
        """
        # Get dependency outputs
        dependencies = self.dependency_resolver.get_dependencies(stage_id)
        dependency_outputs = self.dependency_resolver.get_required_inputs(
            stage_id, 
            context.stage_outputs
        )
        
        # Get stage-specific config
        stage_config = self._get_stage_config(stage_id)
        
        # Build base input dictionary with core StageInput fields
        base_input = {
            "pipeline_id": context.pipeline_id,
            "stage_id": stage_id,
            "stage_number": stage_index,
            "metadata": {}
        }
        
        # Add stage-specific fields based on stage_id
        # For stage 0 (input_acquisition), map from context
        if stage_id == "input_acquisition":
            # Map user config to Stage0Input fields
            user_config = context.config
            base_input.update({
                "image_path": context.source_file,
                "dpi": user_config.get("dpi", 300),
                "repeat_unit_px": user_config.get("repeat_unit", {"width": 100, "height": 100}),
                "color_mode": user_config.get("color_mode", "RGB")
            })
        elif stage_id == "canonical_normalization":
            # Stage 1 needs fields from Stage 0's InputDescriptor
            if "input_acquisition" in dependency_outputs:
                stage0_output = dependency_outputs["input_acquisition"]
                input_descriptor = stage0_output.input_descriptor
                base_input.update({
                    "image_path": input_descriptor.image_path,
                    "width_px": input_descriptor.width_px,
                    "height_px": input_descriptor.height_px,
                    "dpi": input_descriptor.dpi,
                    "repeat_unit_px": input_descriptor.repeat_unit_px,
                    "color_mode": input_descriptor.color_mode,
                    "bit_depth": input_descriptor.bit_depth,
                    "raw_hash": input_descriptor.raw_hash
                })
        elif stage_id == "structural_intent":
            # Stage 2 needs fields from Stage 1's CanonicalRaster
            if "canonical_normalization" in dependency_outputs:
                stage1_output = dependency_outputs["canonical_normalization"]
                canonical_raster = stage1_output.canonical_raster
                base_input.update({
                    "canonical_raster_path": canonical_raster.pixel_array_path,
                    "canonical_raster_array": canonical_raster.pixel_array,
                    "width_px": canonical_raster.width_px,
                    "height_px": canonical_raster.height_px,
                    "dpi": canonical_raster.dpi,
                    "repeat_width_px": canonical_raster.repeat_unit_px["width"],
                    "repeat_height_px": canonical_raster.repeat_unit_px["height"]
                })
        else:
            # For other stages, merge dependency outputs and config
            # This will be customized per stage as they are implemented
            base_input.update({
                **dependency_outputs,
                **stage_config
            })
        
        # Get stage class to determine expected input type
        stage = self.stage_loader.load_stage(stage_id)
        
        # Construct stage-specific input
        return self._construct_stage_specific_input(stage_id, base_input, context)
    
    def _construct_stage_specific_input(
        self, 
        stage_id: str, 
        base_input: Dict[str, Any], 
        context: PipelineContext
    ) -> Any:
        """
        Construct stage-specific input from base input.
        Each stage defines its own input schema that extends StageInput.
        
        Args:
            stage_id: Stage identifier
            base_input: Base input dictionary
            context: Pipeline context
        
        Returns:
            Stage-specific input instance
        """
        from typing import get_args, get_origin
        
        # Get stage registration to find the input schema
        registration = self.stage_loader.get_registration(stage_id)
        stage_class = registration.stage_class
        
        # Extract input class from BaseStage[TInput, TOutput] type parameters
        input_class = None
        for base in stage_class.__orig_bases__:
            origin = get_origin(base)
            if origin and hasattr(origin, '__name__') and 'BaseStage' in origin.__name__:
                type_args = get_args(base)
                if type_args:
                    input_class = type_args[0]
                    break
        
        if not input_class:
            logger.warning(f"Could not extract input class for stage {stage_id}, using base StageInput")
            # Fall back to base StageInput with only core fields
            core_fields = {k: v for k, v in base_input.items() 
                          if k in ['pipeline_id', 'stage_id', 'stage_number', 'metadata']}
            return StageInput(**core_fields)
        
        # Construct stage-specific input with only the fields it expects
        try:
            return input_class(**base_input)
        except Exception as e:
            logger.error(f"Failed to construct {input_class.__name__} for stage {stage_id}: {e}")
            logger.debug(f"Attempted input data: {base_input}")
            raise
    
    def _get_stage_config(self, stage_id: str) -> Dict[str, Any]:
        """
        Get configuration for a specific stage.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            Stage-specific configuration
        """
        if "stages" not in self.config:
            return {}
        
        for stage_config in self.config["stages"]:
            if stage_config.get("id") == stage_id:
                return stage_config.get("config", {})
        
        return {}
    
    def _validate_input_contract(self, stage_id: str, input_data: Any) -> None:
        """
        Validate stage input contract.
        
        Args:
            stage_id: Stage identifier
            input_data: Input to validate
        
        Raises:
            ContractViolationError: If validation fails
        """
        # Pydantic handles schema validation automatically
        # Additional business logic validation can be added here
        pass
    
    def _validate_output_contract(self, stage_id: str, output_data: StageOutput) -> None:
        """
        Validate stage output contract.
        
        Args:
            stage_id: Stage identifier
            output_data: Output to validate
        
        Raises:
            ContractViolationError: If validation fails
        """
        # Check for contract violations
        if output_data.status == StageStatus.FAILED:
            raise ContractViolationError(
                stage_id=stage_id,
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
        # Get the output from the last stage in execution order
        if self._execution_order:
            final_stage_id = self._execution_order[-1]
            if final_stage_id in context.stage_outputs:
                final_stage_output = context.stage_outputs[final_stage_id]
                return {
                    "status": "PASS" if final_stage_output.status == StageStatus.COMPLETED else "FAIL",
                    "final_stage": final_stage_id,
                    "final_output": final_stage_output.data,
                    "validation_report": final_stage_output.errors,
                    "metrics": {
                        stage_id: output.metrics 
                        for stage_id, output in context.stage_outputs.items()
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
    
    def get_execution_order(self) -> List[str]:
        """
        Get the configured stage execution order.
        
        Returns:
            Ordered list of stage IDs
        """
        return self._execution_order.copy()

