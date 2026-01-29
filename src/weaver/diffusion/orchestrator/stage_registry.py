"""
Dynamic Stage Registry System
Provides decorator-based auto-registration for pipeline stages.
Eliminates hardcoded stage mappings and enables plugin-like stage discovery.
"""

from typing import Dict, Type, Optional, List, Callable
from dataclasses import dataclass, field
from weaver.diffusion.stages.base import BaseStage
from weaver.shared.exceptions import StageNotFoundError, ConfigurationError


@dataclass
class StageRegistration:
    """
    Registration information for a pipeline stage.
    """
    stage_id: str  # Unique identifier (e.g., "input_acquisition")
    stage_class: Type[BaseStage]  # The stage class
    module_path: str  # Module path for import
    display_name: str  # Human-readable name
    description: str = ""  # Stage description
    dependencies: List[str] = field(default_factory=list)  # Stage IDs this stage depends on
    version: str = "1.0.0"  # Stage version
    enabled: bool = True  # Whether stage is enabled
    
    def __post_init__(self):
        """Validate registration."""
        if not self.stage_id:
            raise ValueError("stage_id cannot be empty")
        if not self.stage_class:
            raise ValueError("stage_class cannot be None")


class StageRegistry:
    """
    Global registry for pipeline stages.
    Provides decorator-based registration and lookup.
    """
    
    def __init__(self):
        self._stages: Dict[str, StageRegistration] = {}
        self._execution_order: List[str] = []
    
    def register(
        self,
        stage_id: str,
        display_name: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        version: str = "1.0.0",
        enabled: bool = True
    ) -> Callable:
        """
        Decorator to register a stage class.
        
        Usage:
            @stage_registry.register(
                stage_id="input_acquisition",
                display_name="Input Acquisition",
                description="Load and validate input image",
                dependencies=[]
            )
            class InputAcquisitionStage(BaseStage):
                ...
        
        Args:
            stage_id: Unique identifier for the stage
            display_name: Human-readable name
            description: Stage description
            dependencies: List of stage IDs this stage depends on
            version: Stage version
            enabled: Whether stage is enabled
        
        Returns:
            Decorator function
        """
        def decorator(stage_class: Type[BaseStage]) -> Type[BaseStage]:
            # Get module path from class
            module_path = stage_class.__module__
            
            registration = StageRegistration(
                stage_id=stage_id,
                stage_class=stage_class,
                module_path=module_path,
                display_name=display_name,
                description=description,
                dependencies=dependencies or [],
                version=version,
                enabled=enabled
            )
            
            if stage_id in self._stages:
                raise ConfigurationError(
                    f"Stage '{stage_id}' is already registered. "
                    f"Existing: {self._stages[stage_id].stage_class.__name__}, "
                    f"New: {stage_class.__name__}"
                )
            
            self._stages[stage_id] = registration
            return stage_class
        
        return decorator
    
    def get_stage_class(self, stage_id: str) -> Type[BaseStage]:
        """
        Get stage class by ID.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            Stage class
        
        Raises:
            StageNotFoundError: If stage not found
        """
        if stage_id not in self._stages:
            available = ", ".join(self._stages.keys())
            raise StageNotFoundError(
                f"Stage '{stage_id}' not found in registry. "
                f"Available stages: {available}"
            )
        
        registration = self._stages[stage_id]
        
        if not registration.enabled:
            raise StageNotFoundError(
                f"Stage '{stage_id}' is registered but disabled"
            )
        
        return registration.stage_class
    
    def get_registration(self, stage_id: str) -> StageRegistration:
        """
        Get full registration information for a stage.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            Stage registration
        
        Raises:
            StageNotFoundError: If stage not found
        """
        if stage_id not in self._stages:
            available = ", ".join(self._stages.keys())
            raise StageNotFoundError(
                f"Stage '{stage_id}' not found. Available: {available}"
            )
        
        return self._stages[stage_id]
    
    def get_all_registrations(self) -> Dict[str, StageRegistration]:
        """
        Get all registered stages.
        
        Returns:
            Dictionary mapping stage IDs to registrations
        """
        return self._stages.copy()
    
    def get_enabled_stages(self) -> List[str]:
        """
        Get list of enabled stage IDs.
        
        Returns:
            List of stage IDs that are enabled
        """
        return [
            stage_id 
            for stage_id, reg in self._stages.items() 
            if reg.enabled
        ]
    
    def set_execution_order(self, stage_ids: List[str]) -> None:
        """
        Set the execution order for stages.
        This is typically called after loading configuration.
        
        Args:
            stage_ids: Ordered list of stage IDs
        
        Raises:
            ConfigurationError: If stage IDs are invalid
        """
        # Validate all stage IDs exist
        for stage_id in stage_ids:
            if stage_id not in self._stages:
                available = ", ".join(self._stages.keys())
                raise ConfigurationError(
                    f"Cannot set execution order: stage '{stage_id}' not registered. "
                    f"Available: {available}"
                )
        
        self._execution_order = stage_ids.copy()
    
    def get_execution_order(self) -> List[str]:
        """
        Get the configured execution order.
        
        Returns:
            Ordered list of stage IDs to execute
        """
        return self._execution_order.copy()
    
    def validate_dependencies(self) -> None:
        """
        Validate that all stage dependencies are satisfied.
        
        Raises:
            ConfigurationError: If dependencies are invalid
        """
        for stage_id, registration in self._stages.items():
            for dep_id in registration.dependencies:
                if dep_id not in self._stages:
                    raise ConfigurationError(
                        f"Stage '{stage_id}' depends on '{dep_id}', "
                        f"but '{dep_id}' is not registered"
                    )
    
    def clear(self) -> None:
        """Clear all registrations. Primarily for testing."""
        self._stages.clear()
        self._execution_order.clear()


# Global registry instance
stage_registry = StageRegistry()
