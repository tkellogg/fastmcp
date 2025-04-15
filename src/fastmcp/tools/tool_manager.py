from __future__ import annotations as _annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from mcp.shared.context import LifespanContextT

from fastmcp.exceptions import ToolError
from fastmcp.settings import DuplicateBehavior
from fastmcp.tools.tool import MCPTool, Tool
from fastmcp.utilities.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.session import ServerSessionT

    from fastmcp.server import Context

logger = get_logger(__name__)


class ToolManager:
    """Manages FastMCP tools."""

    def __init__(self, duplicate_behavior: DuplicateBehavior = DuplicateBehavior.WARN):
        self._tools: dict[str, Tool] = {}
        self.duplicate_behavior = duplicate_behavior

    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def get_tools(self) -> dict[str, Tool]:
        """Get all registered tools, keyed by registered name."""
        return self._tools

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self.get_tools().values())

    def list_mcp_tools(self) -> list[MCPTool]:
        """List all registered tools in the format expected by the low-level MCP server."""
        return [tool.to_mcp_tool(name=name) for name, tool in self._tools.items()]

    def add_tool_from_fn(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        tags: set[str] | None = None,
    ) -> Tool:
        """Add a tool to the server."""
        tool = Tool.from_function(fn, name=name, description=description, tags=tags)
        return self.add_tool(tool)

    def add_tool(self, tool: Tool, name: str | None = None) -> Tool:
        """Register a tool with the server."""
        name = name or tool.name
        existing = self._tools.get(name)
        if existing:
            if self.duplicate_behavior == DuplicateBehavior.WARN:
                logger.warning(f"Tool already exists: {name}")
                self._tools[name] = tool
            elif self.duplicate_behavior == DuplicateBehavior.REPLACE:
                self._tools[name] = tool
            elif self.duplicate_behavior == DuplicateBehavior.ERROR:
                raise ValueError(f"Tool already exists: {name}")
            elif self.duplicate_behavior == DuplicateBehavior.IGNORE:
                pass
        self._tools[name] = tool
        return tool

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[ServerSessionT, LifespanContextT] | None = None,
    ) -> Any:
        """Call a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")

        return await tool.run(arguments, context=context)

    def import_tools(
        self, tool_manager: ToolManager, prefix: str | None = None
    ) -> None:
        """
        Import all tools from another ToolManager with prefixed names.

        Args:
            tool_manager: Another ToolManager instance to import tools from
            prefix: Prefix to add to tool names, including the delimiter.
                   The resulting tool name will be in the format "{prefix}{original_name}"
                   if prefix is provided, otherwise the original name is used.
                   For example, with prefix "weather/" and tool "forecast",
                   the imported tool would be available as "weather/forecast"
        """
        for name, tool in tool_manager._tools.items():
            prefixed_name = f"{prefix}{name}" if prefix else name
            self.add_tool(tool, name=prefixed_name)
            logger.debug(f'Imported tool "{tool.name}" as "{prefixed_name}"')
