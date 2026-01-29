"""
Base stage contract definition.
All pipeline stages must inherit from BaseStage and implement the execute method.
Each stage produces a Result that the next stage consumes.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Optional, Any

from weaver.diffusion.stages.stage_result import StageResult


class StageMetadata(BaseModel):
    """Metadata describing a stage."""
    stage_id: str = Field(..., description="Unique stage identifier (e.g., 'input_acquisition')")
    name: str = Field(..., description="Stage name")
    description: str = Field(..., description="Stage description")
    version: str = Field(default="1.0.0", description="Stage implementation version")


class BaseStage(ABC):
    """
    Abstract base class for all pipeline stages.
    
    Each stage:
    1. Accepts the Result from the previous stage (or initial input for first stage)
    2. Processes the data
    3. Returns its own Result for the next stage
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
    def validate_input(self, prev_result: Optional[StageResult], config: dict) -> None:
        """
        Validate the previous stage's result before execution.
        
        Must be implemented by each stage to perform type checking and validation
        of the input result. Raise TypeError or ValueError if validation fails.
        
        Args:
            prev_result: Result from previous stage or None for first stage
            config: Pipeline configuration dictionary
        Raises:
            TypeError: If prev_result is not the expected type
            ValueError: If prev_result contains invalid data
        """
        pass

    def execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> StageResult:
        """
        Execute the stage's core logic with automatic input validation.
        
        This is a template method that:
        1. Calls validate_input() to verify prev_result
        2. Calls _execute() to perform the actual stage logic
        
        Do not override this method. Override _execute() instead.
        
        Args:
            prev_result: Result from previous stage
            pipeline_id: Unique pipeline execution ID
            config: Pipeline configuration dictionary
        
        Returns:
            Result for this stage
        
        Raises:
            StageError: If execution fails
        """
        self.validate_input(prev_result, config)
        return self._execute(prev_result, pipeline_id, config)

    @abstractmethod
    def _execute(self, prev_result: Optional[StageResult], pipeline_id: str, config: dict) -> StageResult:
        """
        Internal execution method to be implemented by child stages.
        
        Args:
            prev_result: Result from previous stage (already validated)
            pipeline_id: Unique pipeline execution ID
            config: Pipeline configuration dictionary
        
        Returns:
            Result for this stage
        
        Raises:
            StageError: If execution fails
        """
        pass