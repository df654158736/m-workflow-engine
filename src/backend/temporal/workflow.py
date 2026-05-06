"""Temporal Workflow — DAG orchestration with multi-queue dispatch + human interaction.

Supports:
- Standard nodes: execute as Activity on target queue
- Approval nodes: pause workflow, wait for Signal from human
- Condition nodes: dynamic branching
- When clauses: conditional skip
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from backend.dsl_parser import topological_sort
    from backend.models import (
        EdgeSpec,
        NodeSpec,
        NodeType,
        OnError,
        StepStatus,
        WorkflowDefinition,
    )
    from backend.routing import get_queue_for_node

_REF_PATTERN = re.compile(r"\$\{(\w+)\.outputs\.(\w+)\}")

NODE_TIMEOUTS: dict[NodeType, timedelta] = {
    NodeType.LLM: timedelta(minutes=5),
    NodeType.TOOL: timedelta(minutes=10),
    NodeType.APPROVAL: timedelta(hours=24),
    NodeType.CONDITION: timedelta(seconds=30),
    NodeType.SANDBOX: timedelta(minutes=15),
    NodeType.FLINK_SQL: timedelta(minutes=60),
    NodeType.FUNCTION: timedelta(minutes=5),
}


@workflow.defn(name="WorkflowEngine")
class WorkflowEngineWorkflow:
    """Temporal Workflow that orchestrates a DAG of nodes across multiple Planes.

    Human interaction:
    - Approval nodes pause the workflow and wait for an "approval_signal"
    - The signal carries {node_id, decision, approver, comment}
    - UI/API sends the signal to resume the workflow
    """

    def __init__(self) -> None:
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._approval_decisions: dict[str, dict[str, Any]] = {}

    @workflow.signal(name="approval_signal")
    async def on_approval_signal(self, payload: dict[str, Any]) -> None:
        """Receive human approval/rejection decision."""
        node_id = payload.get("node_id", "")
        self._approval_decisions[node_id] = payload
        workflow.logger.info(f"Received approval signal for node '{node_id}': {payload.get('decision')}")

    @workflow.query(name="get_state")
    def get_state(self) -> dict[str, Any]:
        """Query current workflow state (pending approvals, completed nodes)."""
        return {
            "pending_approvals": self._pending_approvals,
            "decisions": self._approval_decisions,
        }

    @workflow.run
    async def run(self, definition_dict: dict[str, Any]) -> dict[str, Any]:
        definition = self._deserialize(definition_dict)
        execution_order = topological_sort(definition)
        node_map = {n.id: n for n in definition.nodes}
        edge_map = self._build_edge_map(definition.edges)
        override_queue = definition_dict.get("override_queue")

        results: dict[str, dict[str, Any]] = {}

        workflow.logger.info(
            f"Starting workflow '{definition.id}' with {len(execution_order)} nodes"
        )

        for node_id in execution_order:
            node = node_map[node_id]

            # Check conditional execution (when clause)
            if node.when and not self._evaluate_when(node.when, results):
                workflow.logger.info(f"Skipping node '{node_id}' (when condition not met)")
                results[node_id] = {
                    "node_id": node_id,
                    "status": StepStatus.SKIPPED.value,
                    "outputs": {},
                    "duration_ms": 0,
                    "error": "",
                }
                continue

            # Check edge conditions
            if not self._should_execute_by_edges(node_id, edge_map, results):
                workflow.logger.info(f"Skipping node '{node_id}' (edge condition not met)")
                results[node_id] = {
                    "node_id": node_id,
                    "status": StepStatus.SKIPPED.value,
                    "outputs": {},
                    "duration_ms": 0,
                    "error": "",
                }
                continue

            # --- Approval Node: Human Interaction ---
            if node.type == NodeType.APPROVAL:
                result = await self._handle_approval(node_id, node.config, results)
                results[node_id] = result
                # If rejected, stop workflow (or continue based on config)
                if result["outputs"].get("decision") == "REJECTED":
                    if node.on_error == OnError.FAIL:
                        workflow.logger.info(f"Approval rejected at '{node_id}', stopping workflow")
                        break
                continue

            # --- Standard Node: Execute as Activity ---
            resolved_inputs = self._resolve_inputs(node.inputs, results)
            task_queue = override_queue or get_queue_for_node(node.type)
            timeout = NODE_TIMEOUTS.get(node.type, timedelta(minutes=5))

            workflow.logger.info(
                f"Dispatching '{node_id}' ({node.type.value}) → '{task_queue}'"
            )

            activity_payload = {
                "node_id": node_id,
                "node_type": node.type.value,
                "config": node.config,
                "inputs": resolved_inputs,
                "task_queue": task_queue,
            }

            try:
                result = await workflow.execute_activity(
                    "execute_node",
                    activity_payload,
                    task_queue=task_queue,
                    start_to_close_timeout=timeout,
                    retry_policy=self._retry_policy(node.on_error),
                )
                results[node_id] = result
            except Exception as e:
                workflow.logger.error(f"Node '{node_id}' failed: {e}")
                if node.on_error == OnError.SKIP:
                    results[node_id] = {
                        "node_id": node_id,
                        "status": StepStatus.SKIPPED.value,
                        "outputs": {},
                        "error": str(e),
                        "duration_ms": 0,
                    }
                else:
                    results[node_id] = {
                        "node_id": node_id,
                        "status": StepStatus.FAILED.value,
                        "outputs": {},
                        "error": str(e),
                        "duration_ms": 0,
                    }
                    if node.on_error == OnError.FAIL:
                        break

        workflow.logger.info(f"Workflow '{definition.id}' completed")
        return results

    async def _handle_approval(
        self, node_id: str, config: dict, results: dict
    ) -> dict[str, Any]:
        """Handle Approval node: register pending approval, wait for signal."""
        approval_info = {
            "node_id": node_id,
            "title": config.get("title", f"Approval required: {node_id}"),
            "description": config.get("description", ""),
            "approvers": config.get("approvers", ["admin"]),
            "status": "WAITING",
        }
        self._pending_approvals[node_id] = approval_info

        workflow.logger.info(
            f"Approval node '{node_id}' waiting for human decision. "
            f"Send signal 'approval_signal' with {{node_id: '{node_id}', decision: 'APPROVED'|'REJECTED'}}"
        )

        # Wait for the approval signal (up to 24 hours)
        await workflow.wait_condition(
            lambda: node_id in self._approval_decisions,
            timeout=timedelta(hours=24),
        )

        decision = self._approval_decisions.get(node_id, {})
        del self._pending_approvals[node_id]

        return {
            "node_id": node_id,
            "status": StepStatus.COMPLETED.value,
            "outputs": {
                "decision": decision.get("decision", "TIMEOUT"),
                "approver": decision.get("approver", "unknown"),
                "comment": decision.get("comment", ""),
            },
            "duration_ms": 0,
            "error": "",
        }

    def _deserialize(self, data: dict) -> WorkflowDefinition:
        nodes = [
            NodeSpec(
                id=n["id"],
                type=NodeType(n["type"]),
                config=n.get("config", {}),
                inputs=n.get("inputs", {}),
                when=n.get("when"),
                on_error=OnError(n.get("on_error", "FAIL")),
            )
            for n in data.get("nodes", [])
        ]
        edges = [
            EdgeSpec(
                from_node=e["from_node"],
                to_node=e["to_node"],
                condition=e.get("condition"),
            )
            for e in data.get("edges", [])
        ]
        return WorkflowDefinition(
            id=data["id"],
            name=data.get("name", ""),
            nodes=nodes,
            edges=edges,
        )

    def _build_edge_map(self, edges: list[EdgeSpec]) -> dict[str, list[EdgeSpec]]:
        edge_map: dict[str, list[EdgeSpec]] = {}
        for e in edges:
            edge_map.setdefault(e.to_node, []).append(e)
        return edge_map

    def _should_execute_by_edges(
        self, node_id: str, edge_map: dict[str, list[EdgeSpec]], results: dict[str, dict]
    ) -> bool:
        incoming = edge_map.get(node_id, [])
        if not incoming:
            return True
        for edge in incoming:
            if edge.condition is None:
                return True
            parent_result = results.get(edge.from_node, {})
            parent_outputs = parent_result.get("outputs", {})
            try:
                if eval(edge.condition, {"__builtins__": {}}, parent_outputs):
                    return True
            except Exception:
                pass
        return False

    def _evaluate_when(self, expr: str, results: dict[str, dict]) -> bool:
        context: dict[str, Any] = {}
        for node_id, result in results.items():
            context[node_id] = result.get("outputs", {})
        try:
            return bool(eval(expr, {"__builtins__": {}}, context))
        except Exception:
            return True

    def _resolve_inputs(self, inputs: dict[str, str], results: dict[str, dict]) -> dict[str, Any]:
        resolved = {}
        for key, value in inputs.items():
            if isinstance(value, str):
                match = _REF_PATTERN.match(value)
                if match:
                    ref_node, ref_field = match.groups()
                    node_result = results.get(ref_node, {})
                    outputs = node_result.get("outputs", {})
                    resolved[key] = outputs.get(ref_field, value)
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _retry_policy(self, on_error: OnError):
        from temporalio.common import RetryPolicy
        if on_error == OnError.RETRY:
            return RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            )
        return RetryPolicy(maximum_attempts=1)
