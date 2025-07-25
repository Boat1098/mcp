"""Advanced MCP tools for code analysis and testing."""

import json
import logging
import asyncio
import os
import uuid
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.types import Tool
from moatless_mcp.project_understand.AGraphGenerate import GraphGenerater
from moatless_mcp.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)
# file_handler = logging.FileHandler('D:/Files/mcp/understand.log')
# file_handler.setLevel(logging.DEBUG)  # 设置文件日志级别

# # 定义日志输出格式
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# file_handler.setFormatter(formatter)

# # 将 FileHandler 添加到 logger
# logger.addHandler(file_handler)

TASKS: Dict[str, Dict[str, Any]] = {}

class ProjectUnderstandTool(MCPTool):
    """Tool for get the understanding of a repository, including recovered architecture and activity graph"""
    # self.task_id = ""

    @property
    def name(self) -> str:
        return "get_repo_understand"
    
    @property
    def description(self) -> str:
        return "get the functional understand of the target repository, including recovered architecture and activity graph"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id":{
                    "type":"string",
                    "description":"the task id of this request, if this is the first time, please set it empty"
                },
                "project_path": {
                    "type": "string",
                    "description": "the absolute path of the target repository"
                },
                "language": {
                    "type": "string",
                    "description": "the programming language of the target repository. Now only support cpp, java and python"
                },
                "output_path": {
                    "type": "string",
                    "description": "the absolute path of the output directory"
                }
            },
            "required": ["task_id", "project_path", "language", "output_path"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            logger.debug("Received execution request: %s", arguments)
            task_id = arguments.get("task_id", "")

            if not task_id:
                task_id = str(uuid.uuid4())
                logger.info("Creating new task: %s", task_id)
                TASKS[task_id] = {
                    "status": "pending",
                    "created_at": asyncio.get_event_loop().time(),
                    "result": {}
                }
                asyncio.create_task(self.run({
                    "task_id": task_id,
                    "project_path": arguments["project_path"],
                    "language": arguments["language"],
                    "output_path": arguments["output_path"]
                }))
                return ToolResult(
                    success=True,
                    message=f"Task {task_id} created. Please poll with task_id to check status.",
                    properties={"task_id": task_id}
                )
            else:
                logger.debug("Checking status for task: %s", task_id)
                task = TASKS.get(task_id)
                if not task:
                    return self.format_error("Invalid task_id.")
                if task["status"] == "success":
                    return ToolResult(success=True, message=task["result"]["message"], properties=task["result"]["properties"])
                elif task["status"] == "failed":
                    return self.format_error(task["result"].get("message", "Unknown error."))
                else:
                    return ToolResult(success=True, message=f"Task {task_id} still running.", properties={})
        except Exception as e:
            logger.exception("Exception in execute")
            return self.format_error(str(e))

    async def run(self, args: Dict[str, Any]):
        task_id = args["task_id"]
        try:
            logger.info("[Task %s] Starting analysis", task_id)
            output_path = args["output_path"]
            
            file_path = os.path.join(output_path, "depends-file.json")
            
            if not os.path.exists(file_path):
                file_path = self.depends(args)
                if not os.path.exists(file_path):
                    return self.format_error(f"Expected analysis output not found: {file_path}")
            else:
                logger.info("[Task %s] depends analysis already exists", task_id)

            logger.info("[Task %s] Running graph generation", task_id)
            ag = GraphGenerater(filepath=file_path)
            await ag._dp_init()
            logger.info("[Task %s] dp init finish", task_id)
            res = await ag.optimize_by_llm()
            result_data = ag.output_result(res)

            result_path = os.path.join(output_path, "result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
                f.close()
            with open(os.path.join(output_path, "graph.puml"), "w", encoding="utf-8") as f:
                f.write(result_data["plantuml_diagram"])
                f.close()

            message = f"Analysis completed. Results at {result_path}"
            logger.info("[Task %s] Analysis done.", task_id)

            TASKS[task_id]["status"] = "success"
            TASKS[task_id]["result"] = {"message": message, "properties": result_data}

        except subprocess.CalledProcessError as e:
            logger.error("[Task %s] Depends failed: %s", task_id, e.stderr)
            TASKS[task_id]["status"] = "failed"
            TASKS[task_id]["result"] = {"message": f"Depends error: {e.stderr}"}

        except Exception as e:
            logger.exception("[Task %s] Exception during run", task_id)
            TASKS[task_id]["status"] = "failed"
            TASKS[task_id]["result"] = {"message": str(e)}
    
    def depends(self, args):
        task_id = args["task_id"]
        project_path = args["project_path"]
        language = args["language"]
        output_path = args["output_path"]

        if language not in ["cpp", "java"]:
            raise ValueError("Unsupported language: %s" % language)

        base_dir = os.path.dirname(__file__)
        jar_path = os.path.join(base_dir, 'Jarlib', 'depends.jar')
        logger.info("[Jar Path]: [%s]" % jar_path)
        # depends_log_apth = os.path.join(base_dir, 'log', 'depends')
        if not os.path.exists(jar_path):
            raise FileNotFoundError(f"Depends JAR not found: {jar_path}")
        
        logger.info("[Task %s] Running depends", task_id)
        os.makedirs(output_path, exist_ok=True)
        result = subprocess.run(
            ["java", "-jar", jar_path, "--auto-include", language, project_path, "./depends"],
            cwd=output_path,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("[Task %s] Depends completed: %s", task_id, result.stdout)

        if not os.path.exists(os.path.join(output_path, "depends-file.json")):
            logger.info("[Task %s] Depends output not found: %s", task_id, os.path.join(output_path, "depends-file.json"))
        else:
            logger.info("[Task %s] Depends output found: %s", task_id, os.path.join(output_path, "depends-file.json"))
        return os.path.join(output_path, "depends-file.json")
    
class UnderstandResultTool(MCPTool):
    """Tool for get the understanding result of target communities from a repository"""
    # self.task_id = ""

    @property
    def name(self) -> str:
        return "get_understand_result"
    
    @property
    def description(self) -> str:
        return "get the understand result of the target task.The task is created by `get_repo_understand`.The result contains the architecture and the communities."
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id":{
                    "type":"string",
                    "description":"the task id of this request, if this is the first time, please set it empty"
                },
            },
            "required": ["task_id"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            task_id = arguments["task_id"]
            if not task_id or not task_id in TASKS.keys():
                self.format_error(f"Please use `get_repo_understand` before using this tool.You need to give a valid task_id")
            result = TASKS[task_id]["result"]
            res = {
                "architecture": result["properties"]["architecture"],
                "communities": result["properties"]["communities"]
            }
            return ToolResult(success=True, message=res, properties=result["properties"])

        except Exception as e:
            logger.exception("Exception in execute")
            return self.format_error(str(e))
