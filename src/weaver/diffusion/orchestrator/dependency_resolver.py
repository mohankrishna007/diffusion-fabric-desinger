"""
Dependency Resolver for Pipeline Stages
Manages inter-stage dependencies and data flow.
"""

from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from weaver.shared.exceptions import ConfigurationError
from weaver.shared.schemas import StageOutput


@dataclass
class DependencyNode:
    """Represents a stage in the dependency graph."""
    stage_id: str
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.stage_id)


class DependencyResolver:
    """
    Resolves stage dependencies and determines execution order.
    Performs topological sorting to ensure stages execute in correct order.
    """
    
    def __init__(self):
        self._nodes: Dict[str, DependencyNode] = {}
    
    def add_stage(self, stage_id: str, dependencies: Optional[List[str]] = None) -> None:
        """
        Add a stage to the dependency graph.
        
        Args:
            stage_id: Unique stage identifier
            dependencies: List of stage IDs this stage depends on
        """
        if stage_id in self._nodes:
            raise ConfigurationError(
                f"Stage '{stage_id}' already added to dependency graph"
            )
        
        node = DependencyNode(
            stage_id=stage_id,
            dependencies=dependencies or []
        )
        self._nodes[stage_id] = node
        
        # Update dependents
        for dep_id in node.dependencies:
            if dep_id not in self._nodes:
                # Create placeholder node for dependency
                self._nodes[dep_id] = DependencyNode(stage_id=dep_id)
            self._nodes[dep_id].dependents.append(stage_id)
    
    def validate_dependencies(self) -> None:
        """
        Validate that all dependencies are satisfied and there are no cycles.
        
        Raises:
            ConfigurationError: If dependencies are invalid or circular
        """
        # Check for missing dependencies
        all_stages = set(self._nodes.keys())
        for stage_id, node in self._nodes.items():
            for dep_id in node.dependencies:
                if dep_id not in all_stages:
                    raise ConfigurationError(
                        f"Stage '{stage_id}' depends on '{dep_id}', "
                        f"but '{dep_id}' is not in the pipeline"
                    )
        
        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for dep_id in self._nodes[node_id].dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for stage_id in self._nodes:
            if stage_id not in visited:
                if has_cycle(stage_id):
                    raise ConfigurationError(
                        f"Circular dependency detected involving stage '{stage_id}'"
                    )
    
    def resolve_execution_order(self) -> List[str]:
        """
        Determine the execution order using topological sort.
        
        Returns:
            Ordered list of stage IDs
        
        Raises:
            ConfigurationError: If dependencies cannot be resolved
        """
        self.validate_dependencies()
        
        # Kahn's algorithm for topological sort
        in_degree = {
            stage_id: len(node.dependencies)
            for stage_id, node in self._nodes.items()
        }
        
        # Queue with stages that have no dependencies
        queue = [stage_id for stage_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            # Sort queue to ensure deterministic ordering when multiple stages have no deps
            queue.sort()
            stage_id = queue.pop(0)
            execution_order.append(stage_id)
            
            # Reduce in-degree for dependents
            for dependent_id in self._nodes[stage_id].dependents:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
        
        # If not all stages processed, there's a cycle (shouldn't happen after validation)
        if len(execution_order) != len(self._nodes):
            raise ConfigurationError(
                "Could not resolve execution order - possible circular dependency"
            )
        
        return execution_order
    
    def get_required_inputs(self, stage_id: str, stage_outputs: Dict[str, StageOutput]) -> Dict[str, Any]:
        """
        Get required inputs for a stage from previous stage outputs.
        
        Args:
            stage_id: Stage that needs inputs
            stage_outputs: Dictionary of completed stage outputs
        
        Returns:
            Dictionary of inputs from dependent stages
        
        Raises:
            ConfigurationError: If required dependencies not available
        """
        if stage_id not in self._nodes:
            raise ConfigurationError(f"Stage '{stage_id}' not found in dependency graph")
        
        node = self._nodes[stage_id]
        required_inputs = {}
        
        for dep_id in node.dependencies:
            if dep_id not in stage_outputs:
                raise ConfigurationError(
                    f"Stage '{stage_id}' requires output from '{dep_id}', "
                    f"but '{dep_id}' has not executed yet"
                )
            required_inputs[dep_id] = stage_outputs[dep_id]
        
        return required_inputs
    
    def get_dependencies(self, stage_id: str) -> List[str]:
        """
        Get direct dependencies for a stage.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            List of stage IDs this stage depends on
        """
        if stage_id not in self._nodes:
            return []
        return self._nodes[stage_id].dependencies.copy()
    
    def get_dependents(self, stage_id: str) -> List[str]:
        """
        Get stages that depend on this stage.
        
        Args:
            stage_id: Stage identifier
        
        Returns:
            List of stage IDs that depend on this stage
        """
        if stage_id not in self._nodes:
            return []
        return self._nodes[stage_id].dependents.copy()
    
    def clear(self) -> None:
        """Clear all nodes. Primarily for testing."""
        self._nodes.clear()


class StageInputBuilder:
    """
    Builds stage input from previous stage outputs.
    Handles data flow between stages.
    """
    
    @staticmethod
    def build_input(
        stage_id: str,
        pipeline_id: str,
        stage_number: Optional[int],
        dependencies: Dict[str, StageOutput],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build input dictionary for a stage.
        
        Args:
            stage_id: Current stage identifier
            pipeline_id: Pipeline execution ID
            stage_number: Stage execution order number (optional)
            dependencies: Outputs from dependent stages
            additional_data: Additional data to include
        
        Returns:
            Input dictionary ready for stage consumption
        """
        input_data = {
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "stage_number": stage_number,
            "metadata": {}
        }
        
        # Add dependency outputs
        if dependencies:
            input_data["dependencies"] = dependencies
        
        # Merge additional data
        if additional_data:
            input_data.update(additional_data)
        
        return input_data
