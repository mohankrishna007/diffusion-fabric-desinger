"""
Base stage contract definition.
All pipeline stages must inherit from BaseStage and implement the execute method.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import TypeVar, Generic
from weaver.shared.schemas import StageInput, StageOutput


# Type variables for input and output
TInput = TypeVar('TInput', bound=StageInput)
TOutput = TypeVar('TOutput', bound=StageOutput)


class StageMetadata(BaseModel):
    """Metadata describing a stage."""
    stage_number: int = Field(..., ge=0, le=7, description="Stage number (0-7)")
    name: str = Field(..., description="Stage name")
    description: str = Field(..., description="Stage description")
    version: str = Field(default="1.0.0", description="Stage implementation version")
    author: str = Field(default="Unknown", description="Stage developer")


class BaseStage(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for all pipeline stages.
    
    Each stage must:
    1. Define its metadata (stage_number, name, description)
    2. Implement the execute() method
    3. Define input/output schemas that extend StageInput/StageOutput
    4. Validate contracts in pre_execute() and post_execute() hooks
    
    Example:
        class MyStage(BaseStage[MyInput, MyOutput]):
            def metadata(self) -> StageMetadata:
                return StageMetadata(
                    stage_number=0,
                    name="My Stage",
                    description="Does something"
                )
            
            def execute(self, input_data: MyInput) -> MyOutput:
                # Implementation here
                return MyOutput(...)
    """
    
    @property
    @abstractmethod
    def metadata(self) -> StageMetadata:
        """
        Return metadata describing this stage.
        Must be implemented by each stage.
        """
        pass
    
    @abstractmethod
    def execute(self, input_data: TInput) -> TOutput:
        """
        Execute the stage's core logic.
        
        Args:
            input_data: Validated input conforming to the stage's input schema
        
        Returns:
            Output conforming to the stage's output schema
        
        Raises:
            StageError: If execution fails
            ValidationError: If input is invalid
        """
        pass
    
    def pre_execute(self, input_data: TInput) -> None:
        """
        Pre-execution hook for validation and setup.
        Override to add custom validation logic.
        
        Args:
            input_data: Input to validate
        
        Raises:
            ValidationError: If input validation fails
        """
        pass
    
    def post_execute(self, output_data: TOutput) -> None:
        """
        Post-execution hook for output validation.
        Override to add custom validation logic.
        
        Args:
            output_data: Output to validate
        
        Raises:
            ValidationError: If output validation fails
        """
        pass
    
    def run(self, input_data: TInput) -> TOutput:
        """
        Complete execution flow with pre/post hooks.
        This method is called by the orchestrator.
        
        Args:
            input_data: Stage input
        
        Returns:
            Stage output
        """
        # Pre-execution validation
        self.pre_execute(input_data)
        
        # Execute core logic
        output_data = self.execute(input_data)
        
        # Post-execution validation
        self.post_execute(output_data)
        
        return output_data
