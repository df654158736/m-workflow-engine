"""Concrete NodeExecutor implementations (SPI plugins)."""

from backend.executors.approval import ApprovalExecutor
from backend.executors.condition import ConditionExecutor
from backend.executors.flink_sql import FlinkSQLExecutor
from backend.executors.function import FunctionExecutor
from backend.executors.llm import LLMExecutor
from backend.executors.tool import ToolExecutor
from backend.spi import ExecutorRegistry


def build_default_registry() -> ExecutorRegistry:
    """Create registry with all built-in executors."""
    registry = ExecutorRegistry()
    registry.register(LLMExecutor())
    registry.register(ConditionExecutor())
    registry.register(ToolExecutor())
    registry.register(FlinkSQLExecutor())
    registry.register(FunctionExecutor())
    registry.register(ApprovalExecutor())
    return registry
