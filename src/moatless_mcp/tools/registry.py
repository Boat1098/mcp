"""
Tool registry for managing MCP tools
"""

import logging
from typing import Dict, List

from mcp.types import Tool

from moatless_mcp.tools.base import MCPTool, ToolResult
from moatless_mcp.tools.file_operations import (
    ReadFileTool, 
    WriteFileTool, 
    ListFilesTool, 
    StringReplaceTool
)
from moatless_mcp.tools.search_tools import (
    GrepTool, 
    FindFilesTool, 
    WorkspaceInfoTool
)
from moatless_mcp.tools.advanced_tools import (
    FindClassTool,
    FindFunctionTool, 
    ViewCodeTool,
    SemanticSearchTool,
    RunTestsTool
)
from moatless_mcp.tools.vector_tools import (
    BuildVectorIndexTool,
    VectorIndexStatusTool,
    ClearVectorIndexTool
)

from moatless_mcp.tools.project_understand import ProjectUnderstandTool, UnderstandResultTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing MCP tools"""
    
    def __init__(self, workspace):
        self.workspace = workspace
        self.tools: Dict[str, MCPTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default tools"""
        
        # File operation tools
        tools = [
            ReadFileTool(self.workspace),
            WriteFileTool(self.workspace),
            ListFilesTool(self.workspace),
            StringReplaceTool(self.workspace),
            
            # Search tools
            GrepTool(self.workspace),
            FindFilesTool(self.workspace),
            WorkspaceInfoTool(self.workspace),
            
            # Advanced tools
            FindClassTool(self.workspace),
            FindFunctionTool(self.workspace),
            ViewCodeTool(self.workspace),
            SemanticSearchTool(self.workspace),
            RunTestsTool(self.workspace),
            
            # Vector database tools
            BuildVectorIndexTool(self.workspace),
            VectorIndexStatusTool(self.workspace),
            ClearVectorIndexTool(self.workspace),

            # Project Understand tools
            ProjectUnderstandTool(self.workspace),
            UnderstandResultTool(self.workspace),
        ]
        
        for tool in tools:
            self.register_tool(tool)
        
        logger.info(f"Registered {len(self.tools)} tools")
    
    def register_tool(self, tool: MCPTool):
        """Register a new tool"""
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def get_tools(self) -> List[Tool]:
        """Get all tools in MCP format"""
        return [tool.to_mcp_tool() for tool in self.tools.values()]
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names"""
        return list(self.tools.keys())
    
    async def execute_tool(self, name: str, arguments: Dict) -> ToolResult:
        """Execute a tool by name"""
        if name not in self.tools:
            available_tools = ", ".join(self.tools.keys())
            raise ValueError(f"Unknown tool '{name}'. Available tools: {available_tools}")
        
        tool = self.tools[name]
        logger.info(f"Executing tool: {name}")
        
        try:
            result = await tool.execute(arguments)
            logger.debug(f"Tool {name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return tool.format_error(e)