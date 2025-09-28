import asyncio
import logging
from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime
from models.workflow import NodeResult
from node_handlers import handle_node
import time

logger = logging.getLogger("workflow_api")

class ParallelExecutionEngine:
    """
    Advanced workflow execution engine with parallel processing capabilities
    """
    
    def __init__(self, max_concurrent_nodes: int = 5):
        self.max_concurrent_nodes = max_concurrent_nodes
        self.node_semaphore = asyncio.Semaphore(max_concurrent_nodes)
    
    async def execute_workflow(
        self, 
        nodes: List[Dict[str, Any]], 
        edges: List[Dict[str, Any]], 
        initial_inputs: Dict[str, Any],
        workflow_data: Dict[str, Any],
        request: Any
    ) -> Dict[str, Any]:
        """
        Execute workflow with parallel processing of independent nodes
        """
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(nodes, edges)
        reverse_deps = self._build_reverse_dependencies(edges)
        
        # Track execution state
        completed_nodes = set()
        node_outputs = {}
        node_results = {}
        execution_tasks = {}
        
        # Metrics tracking
        start_time = time.time()
        execution_stats = {
            "total_nodes": len(nodes),
            "parallel_batches": 0,
            "max_concurrent": 0,
            "execution_path": []
        }
        
        logger.info(f"Starting parallel execution of {len(nodes)} nodes")
        
        while len(completed_nodes) < len(nodes):
            # Find nodes ready for execution (all dependencies satisfied)
            ready_nodes = self._get_ready_nodes(
                nodes, dependency_graph, completed_nodes, execution_tasks
            )
            
            if not ready_nodes and not execution_tasks:
                # Deadlock detection
                remaining_nodes = [n for n in nodes if n["id"] not in completed_nodes]
                logger.error(f"Execution deadlock detected. Remaining nodes: {[n['id'] for n in remaining_nodes]}")
                break
            
            # Execute ready nodes in parallel
            if ready_nodes:
                execution_stats["parallel_batches"] += 1
                batch_size = min(len(ready_nodes), self.max_concurrent_nodes)
                execution_stats["max_concurrent"] = max(execution_stats["max_concurrent"], batch_size)
                
                logger.info(f"Executing batch of {len(ready_nodes)} nodes: {[n['id'] for n in ready_nodes]}")
                
                # Start execution tasks for ready nodes
                for node in ready_nodes:
                    task = asyncio.create_task(
                        self._execute_single_node(
                            node, edges, node_outputs, initial_inputs, workflow_data, request
                        )
                    )
                    execution_tasks[node["id"]] = task
            
            # Wait for at least one task to complete
            if execution_tasks:
                completed_task_ids = []
                
                # Wait for first completion
                done, pending = await asyncio.wait(
                    execution_tasks.values(), 
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=300  # 5 minute timeout per batch
                )
                
                # Process completed tasks
                for task in done:
                    for node_id, node_task in execution_tasks.items():
                        if node_task == task:
                            completed_task_ids.append(node_id)
                            break
                
                # Collect results and update state
                for node_id in completed_task_ids:
                    task = execution_tasks.pop(node_id)
                    try:
                        result = await task
                        node_results[node_id] = result
                        if result.status == "success":
                            node_outputs[node_id] = result.output or result.data
                            completed_nodes.add(node_id)
                            execution_stats["execution_path"].append(node_id)
                            logger.info(f"Node {node_id} completed successfully")
                        else:
                            logger.error(f"Node {node_id} failed: {result.message}")
                            # Handle failure based on error policy
                            if not self._should_continue_on_error(node_id, nodes):
                                raise Exception(f"Critical node {node_id} failed: {result.message}")
                    except Exception as e:
                        logger.error(f"Node {node_id} execution error: {str(e)}")
                        node_results[node_id] = NodeResult(
                            output={"error": str(e)},
                            status="error",
                            error=str(e),
                            execution_time=0,
                            node_id=node_id
                        )
        
        # Cancel any remaining tasks
        for task in execution_tasks.values():
            task.cancel()
        
        execution_time = time.time() - start_time
        execution_stats["total_execution_time"] = execution_time
        
        logger.info(f"Workflow execution completed in {execution_time:.2f}s with {execution_stats['parallel_batches']} parallel batches")
        
        # Convert NodeResult objects to dicts for serialization
        serializable_node_results = {
            node_id: result.model_dump() if isinstance(result, NodeResult) else result 
            for node_id, result in node_results.items()
        }
        
        return {
            "node_outputs": node_outputs,
            "node_results": serializable_node_results,
            "execution_stats": execution_stats,
            "status": "success" if len(completed_nodes) == len(nodes) else "partial_failure"
        }
    
    def _build_dependency_graph(self, nodes: List[Dict], edges: List[Dict]) -> Dict[str, Set[str]]:
        """Build a dependency graph showing what each node depends on"""
        graph = {node["id"]: set() for node in nodes}
        
        for edge in edges:
            target = edge["target"]
            source = edge["source"]
            if target in graph:
                graph[target].add(source)
        
        return graph
    
    def _build_reverse_dependencies(self, edges: List[Dict]) -> Dict[str, Set[str]]:
        """Build reverse dependency graph showing what depends on each node"""
        reverse_deps = {}
        
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            if source not in reverse_deps:
                reverse_deps[source] = set()
            reverse_deps[source].add(target)
        
        return reverse_deps
    
    def _get_ready_nodes(
        self, 
        nodes: List[Dict], 
        dependency_graph: Dict[str, Set[str]], 
        completed_nodes: Set[str],
        execution_tasks: Dict[str, asyncio.Task]
    ) -> List[Dict]:
        """Get nodes that are ready for execution (all dependencies satisfied)"""
        ready_nodes = []
        
        for node in nodes:
            node_id = node["id"]
            
            # Skip if already completed or currently executing
            if node_id in completed_nodes or node_id in execution_tasks:
                continue
            
            # Check if all dependencies are satisfied
            dependencies = dependency_graph.get(node_id, set())
            if dependencies.issubset(completed_nodes):
                ready_nodes.append(node)
        
        return ready_nodes
    
    async def _execute_single_node(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        node_outputs: Dict[str, Any],
        initial_inputs: Dict[str, Any],
        workflow_data: Dict[str, Any],
        request: Any
    ) -> NodeResult:
        """Execute a single node with proper resource management"""
        
        async with self.node_semaphore:  # Limit concurrent executions
            node_id = node["id"]
            node_type = node["type"]
            node_data = node.get("data", {})
            
            # Gather inputs for this node
            inputs = self._get_node_inputs(node_id, edges, node_outputs, initial_inputs)
            
            # Add execution timestamp
            start_time = datetime.now().timestamp()
            
            logger.info(f"Starting execution of node {node_id} (type: {node_type})")
            
            try:
                # Execute the node using the existing handler
                result = await handle_node(
                    node_id=node_id,
                    node_type=node_type,
                    node_data=node_data,
                    inputs=inputs,
                    workflow_data=workflow_data,
                    request=request
                )
                
                logger.info(f"Node {node_id} executed successfully in {result.execution_time:.2f}s")
                return result
                
            except Exception as e:
                execution_time = datetime.now().timestamp() - start_time
                logger.error(f"Node {node_id} execution failed: {str(e)}")
                
                return NodeResult(
                    output={"error": str(e)},
                    status="error",
                    error=str(e),
                    execution_time=execution_time,
                    node_id=node_id
                )
    
    def _get_node_inputs(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        node_outputs: Dict[str, Any],
        initial_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gather inputs for a specific node from connected nodes and initial inputs"""
        
        inputs = {}
        
        # Get inputs from connected nodes
        for edge in edges:
            if edge["target"] == node_id:
                source_node_id = edge["source"]
                if source_node_id in node_outputs:
                    # Use the specific output port if specified
                    source_handle = edge.get("sourceHandle", "output")
                    target_handle = edge.get("targetHandle", "input")
                    
                    source_output = node_outputs[source_node_id]
                    if isinstance(source_output, dict) and source_handle in source_output:
                        inputs[target_handle] = source_output[source_handle]
                    else:
                        inputs[target_handle] = source_output
        
        # Add initial inputs for input nodes
        if not inputs and initial_inputs:
            inputs.update(initial_inputs)
        
        return inputs
    
    def _should_continue_on_error(self, node_id: str, nodes: List[Dict]) -> bool:
        """Determine if workflow should continue when a node fails"""
        
        # Find the node configuration
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return False
        
        # Check if node is marked as critical
        node_data = node.get("data", {})
        params = node_data.get("params", {})
        
        # Default behavior: continue unless marked as critical
        return not params.get("critical", False)


class WorkflowValidator:
    """Validate workflow structure before execution"""
    
    @staticmethod
    def validate_workflow(nodes: List[Dict], edges: List[Dict]) -> Dict[str, Any]:
        """Comprehensive workflow validation"""
        
        errors = []
        warnings = []
        
        # Check for circular dependencies
        try:
            WorkflowValidator._detect_cycles(nodes, edges)
        except ValueError as e:
            errors.append(str(e))
        
        # Check for orphaned nodes
        orphaned = WorkflowValidator._find_orphaned_nodes(nodes, edges)
        if orphaned:
            warnings.append(f"Orphaned nodes detected: {orphaned}")
        
        # Check for missing input connections
        missing_inputs = WorkflowValidator._find_missing_required_inputs(nodes, edges)
        if missing_inputs:
            errors.extend(missing_inputs)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    @staticmethod
    def _detect_cycles(nodes: List[Dict], edges: List[Dict]) -> None:
        """Detect circular dependencies using DFS"""
        
        graph = {node["id"]: [] for node in nodes}
        for edge in edges:
            graph[edge["source"]].append(edge["target"])
        
        white = set(graph.keys())  # Unvisited
        gray = set()  # Currently visiting
        black = set()  # Completed
        
        def dfs(node_id: str):
            if node_id in gray:
                raise ValueError(f"Circular dependency detected involving node: {node_id}")
            if node_id in black:
                return
            
            white.discard(node_id)
            gray.add(node_id)
            
            for neighbor in graph[node_id]:
                dfs(neighbor)
            
            gray.discard(node_id)
            black.add(node_id)
        
        while white:
            dfs(white.pop())
    
    @staticmethod
    def _find_orphaned_nodes(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Find nodes with no connections"""
        
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge["source"])
            connected_nodes.add(edge["target"])
        
        return [node["id"] for node in nodes if node["id"] not in connected_nodes]
    
    @staticmethod
    def _find_missing_required_inputs(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Find nodes missing required input connections"""
        
        errors = []
        
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]
            
            # Skip input nodes - they don't need input connections
            if node_type == "input":
                continue
            
            # Check if node has any input connections
            has_inputs = any(edge["target"] == node_id for edge in edges)
            
            # Some node types require inputs
            if node_type not in ["output"] and not has_inputs:
                errors.append(f"Node {node_id} ({node_type}) has no input connections")
        
        return errors 