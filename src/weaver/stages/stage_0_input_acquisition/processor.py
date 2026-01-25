"""
Stage 0: Input Acquisition
Responsibility: Intake of raw design and metadata; immediate structural validation.

TODO for Developer:
1. Implement the execute() method to:
   - Load the raw design image from file
   - Extract/validate DPI metadata
   - Extract/validate repeat unit metadata
   - Check file format (BMP, PNG, TIFF)
   - Validate image dimensions against operational bounds
   - Log the input as "source of truth"

2. Extend Stage0Input schema with required fields
3. Extend Stage0Output schema with validated design data
4. Implement pre_execute() for fast-fail validation
5. Add unit tests in tests/stages/test_stage_0.py
"""

from weaver.stages.base import BaseStage, StageMetadata
from weaver.shared.schemas import StageInput, StageOutput, StageStatus
from weaver.shared.exceptions import ValidationError
from pydantic import Field


class Stage0Input(StageInput):
    """Input schema for Stage 0."""
    # TODO: Add stage-specific fields
    # Example:
    # file_path: str = Field(..., description="Path to raw design file")
    pass


class Stage0Output(StageOutput):
    """Output schema for Stage 0."""
    # TODO: Add stage-specific fields
    # Example:
    # image_width: int = Field(..., description="Image width in pixels")
    # image_height: int = Field(..., description="Image height in pixels")
    # dpi: int = Field(..., description="Design DPI")
    pass


class Stage0InputAcquisition(BaseStage[Stage0Input, Stage0Output]):
    """
    Stage 0: Input Acquisition
    
    Fast-fail validation of raw input:
    - File format validation
    - Metadata presence check
    - Dimension bounds check
    """
    
    @property
    def metadata(self) -> StageMetadata:
        return StageMetadata(
            stage_number=0,
            name="Input Acquisition",
            description="Intake of raw design and metadata; immediate structural validation",
            version="1.0.0",
            author="TODO: Your Name"
        )
    
    def execute(self, input_data: Stage0Input) -> Stage0Output:
        """
        Execute Stage 0: Input Acquisition.
        
        TODO: Implement the following:
        1. Load image file
        2. Validate file format
        3. Extract metadata (DPI, repeat unit)
        4. Check dimensions
        5. Return validated data
        
        Args:
            input_data: Stage 0 input
        
        Returns:
            Stage 0 output with validated design data
        
        Raises:
            ValidationError: If input validation fails
        """
        # TODO: Implement stage logic
        # This is a placeholder implementation
        
        return Stage0Output(
            stage_number=0,
            status=StageStatus.COMPLETED,
            message="Stage 0 execution placeholder - awaiting implementation",
            data={},
            metrics={}
        )
    
    def pre_execute(self, input_data: Stage0Input) -> None:
        """
        Pre-execution validation.
        
        TODO: Add fast-fail checks:
        - File exists
        - File format supported
        - Basic metadata present
        """
        super().pre_execute(input_data)
        # Add custom validation here
    
    def post_execute(self, output_data: Stage0Output) -> None:
        """
        Post-execution validation.
        
        TODO: Validate output contains required data
        """
        super().post_execute(output_data)
        # Add custom validation here
