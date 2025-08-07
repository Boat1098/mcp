"""Advanced MCP tools for code analysis and testing."""
import json
import logging
import asyncio
import os, shutil, zipfile
import uuid
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Annotated
from pydantic import Field
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import File, UploadFile, Form, FastAPI
from fastmcp.server.http import create_sse_app
from project_understand.AGraphGenerate import GraphGenerater
from fastmcp import FastMCP
from io import BytesIO
from fastapi.responses import StreamingResponse
# from fastmcp
# from main import mcp
# from moatless_mcp.tools.base import MCPTool, ToolResult

BASE_DIR = "D://Files//mcp-http//workspace"

# 定义输入结构
class UploadFileInput:
    name: str
    mime_type: str  # 或 mime_type
    content: str     # base64 编码的字符串

# def save_and_extract_zip(task_id, upload_file) -> str:
#     os.makedirs(BASE_DIR, exist_ok=True)
#     Project_path = os.path.join(BASE_DIR, "project")
#     os.makedirs(Project_path, exist_ok=True)
#     zip_path = os.path.join(Project_path, f"{task_id}.zip")
#     extract_path = os.path.join(Project_path, task_id)

#     with open(zip_path, "wb") as f:
#         shutil.copyfileobj(upload_file.file, f)

#     with zipfile.ZipFile(zip_path, 'r') as zip_ref:
#         zip_ref.extractall(extract_path)

#     return extract_path

mcp = FastMCP(
    name="Project Understand"
)
logger = logging.getLogger("project")
file_handler = logging.FileHandler('D://Files//mcp-http//understand.log')
file_handler.setLevel(logging.DEBUG)  # 设置文件日志级别

# 定义日志输出格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 将 FileHandler 添加到 logger
logger.addHandler(file_handler)

TASKS: Dict[str, Dict[str, Any]] = {}

# @router.post("/project_understand")
@mcp.tool(
    name="get_repo_understand",
    description="""
Get the functional understanding of the target repository, including recovered architecture and activity graph.

Before using this tool, you need to ensure that the project's source code (as a ZIP file) has been uploaded to the corresponding MCP Server. You can upload the project using the following format (replace `<server_host>` and `<port>` with the actual MCP Server address):

`curl -X POST http://<server_host>:<port>/upload_project/ -F "file=@your_project.zip" -F "project_name=name_of_your_project"`

After the analysis is completed, you can download the result using:

`curl -X POST http://<server_host>:<port>/download_project/ -F "project_name=name_of_your_project" --output output.zip`

This command will return the analysis results in a ZIP file.

If you are using the windows powershell, pleace replace `curl` with `curl.exe`.
""",
)
def projectUnderstand(
    # project: UploadFile = File(description="The project source code.Please upload your zip file", mime_type="application/zip"),
    project_name: str = Field(default="", description="The name of the project that you want to analyze"),
    task_id: str = Field(default="", description="the task id of this request, if this is the first time, please set it empty"),
):
    try:
        # logger.debug("Received execution request: %s", arguments)
        if not task_id:
            task_id = str(uuid.uuid4())
            project_path = os.path.join(BASE_DIR, project_name, "project")
            # print(project_path)
            if not os.path.exists(project_path):
                return {
                    "status": "error",
                    "message": f"There is no such a project named {project_name},please upload projects first.",
                    "data": None
                }
            logger.info("Creating new task: %s", task_id)
            TASKS[task_id] = {
                "status": "pending",
                "created_at": asyncio.get_event_loop().time(),
                "result": {}
            }
            asyncio.create_task(run(task_id=task_id, project_name=project_name))
            # {
            #     "task_id": task_id,
            #     "project_name": project_name
            # }
            return {
                "status": "success",
                "message": f"Task {task_id} created. Please poll with task_id to check status.",
                "data": {"task_id": task_id}
            }
        else:
            logger.info("Checking status for task: %s", task_id)
            task = TASKS.get(task_id)
            if not task:
                return {
                    "status": "error",
                    "message": "there is no such a task",
                    "data": None
                }
            if task["status"] == "success":
                return {
                    "status": "success",
                    "message": task["result"]["message"],
                    "data": task["result"]["properties"]
                }
                # return ToolResult(success=True, message=task["result"]["message"], properties=task["result"]["properties"])
            elif task["status"] == "failed":
                return {
                    "status": "error",
                    "message": "the task is fail, please retry",
                    "data": task["result"]
                }
            else:
                return {
                    "status": "success",
                    "message": f"Task {task_id} still running",
                    "data": {"task_id": task_id}
                }
                # return ToolResult(success=True, message=f"Task {task_id} still running.", properties={})
    except Exception as e:
        logger.exception("Exception in execute")
        return {
            "status": "error",
            "message": str(e),
            "data": None
        }

async def run(task_id, project_name):
    try:
        # project_path = save_and_extract_zip(task_id, project)
        project_path = os.path.join(BASE_DIR, project_name, "project")
        print(project_path)
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"Project directory not found for {project_name}.Please upload projects first.")
        languages = language_get(project_path)
        output_path = os.path.join(BASE_DIR, project_name, "output")
        os.makedirs(output_path, exist_ok=True)
        depends_path = depends(task_id, project_path, languages, output_path)
        logger.info("[Task %s] Running graph generation", task_id)
        ag = GraphGenerater(filepath=depends_path)
        await asyncio.to_thread(ag._dp_init)
        # ag._dp_init()
        logger.info("[Task %s] dp init finish", task_id)
        # res = await ag.optimize_by_llm()
        # result_data = ag.output_result(res)
        result_data = ag.output()
        graph_path = os.path.join(output_path, "graph")
        os.makedirs(graph_path, exist_ok=True)
        for puml in result_data["sub_pumls"]:
            with open(os.path.join(graph_path, f"{puml['module_name']}.puml"), "w", encoding="utf-8") as f:
                f.write(puml["content"])
                f.close()
        result_path = os.path.join(output_path, "result.json")
        with open(os.path.join(output_path, "communities.json"), "w", encoding="utf-8") as f:
            json.dump({
                "project_name": project_name,
                "communities": result_data["communities"],
            }, f, ensure_ascii=False, indent=2)
            f.close()
        with open(os.path.join(output_path, "nodes.json"), "w", encoding="utf-8") as f:
            json.dump({
                "project_name": project_name,
                "nodes": result_data["nodes"],
            }, f, ensure_ascii=False, indent=2)
            f.close()
        with open(os.path.join(graph_path, "activity_graph.puml"), "w", encoding="utf-8") as f:
            f.write(result_data["plantuml_diagram"])
            f.close()
        with open(os.path.join(output_path, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)
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

def depends(task_id, project_path, languages, output_path):
    # task_id = args["task_id"]
    # project_path = args["project_path"]
    # language = args["language"]
    # output_path = args["output_path"]
    base_dir = "."
    jar_path = os.path.join("D://Files//mcp-http", 'others', 'depends.jar')
    os.makedirs(output_path, exist_ok=True)
    depends_path = os.path.join(output_path, "depends")
    os.makedirs(depends_path, exist_ok=True)
    logger.info("[Jar Path]: [%s]" % jar_path)
    for language in languages:
        if language not in ["cpp", "java", "python"]:
            continue
        # depends_log_apth = os.path.join(base_dir, 'log', 'depends')
        if not os.path.exists(jar_path):
            raise FileNotFoundError(f"Depends JAR not found: {jar_path}")
        
        logger.info(f"[Task {task_id}] Running depends for {language}")

        result = subprocess.run(
            ["java", "-jar", jar_path, "--auto-include", language, project_path, os.path.join(".", language)],
            cwd=depends_path,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("[Task %s] Depends completed: %s", task_id, result.stdout)

    # if not os.path.exists(os.path.join(output_path, "depends-file.json")):
    #     logger.info("[Task %s] Depends output not found: %s", task_id, os.path.join(output_path, "depends-file.json"))
    # else:
    #     logger.info("[Task %s] Depends output found: %s", task_id, os.path.join(output_path, "depends-file.json"))
    return depends_path
        
def language_get(source_dir):
    from collections import defaultdict
    EXTENSION_MAP = {
        '.py': 'python',
        '.java': 'java',
        '.c': 'cpp',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.h': 'cpp',  # 可自定义规则
    }
    lang_count = defaultdict(int)
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXTENSION_MAP:
                lang = EXTENSION_MAP[ext]
                lang_count[lang] += 1
    return list(dict(lang_count).keys())           


# @router.post('/check')
@mcp.tool(name="get_understand_result", description="get the understanding of a repository, including recovered architecture and activity graph.Before using this tool, you need to call `get_repo_understand` first or you are certain that your repo has already been analyzed by `get_repo_understand`")
def check(
    task_id: str = Field("", description="The ID of the wanted task"),
    target_id: str = Field("", description="The ID of the wanted target.If you want all results, leave this empty")
):
    try:
        if not task_id or not task_id in TASKS.keys():
            return {
                "status": "error",
                "message": f"Please use `get_repo_understand` before using this tool.You need to give a valid task_id",
                "data": None,
            }
        # if not target_id:
        #     result = TASKS[task_id]["result"]
        #     return ToolResult(success=True, message=f"The result get successfully.", properties=result)
        # else:
        if TASKS[task_id]["status"] == "pending":
            return {
                "status": "success",
                "message": f"The task status is pending, please wait for it to complete.",
                "data": None
            }
        # ToolResult(success=True, message=f"The task status is {TASKS[task_id]['status']}, please wait for it to complete.")
        elif TASKS[task_id]["status"] == "failed":
            return {
                "status":"failed",
                "message":"The task has been failed, please retry after some time.",
                "data":None
            }
        # ToolResult(success=False, message=f"The task has been failed, please retry after some time.")
        else:
            if not target_id:
                return {
                    "status": "success",
                    "message": f"The result get successfully.",
                    "data": TASKS[task_id]["result"],
                }
            # ToolResult(success=True, message=f"The result get successfully.", properties=TASKS[task_id]["result"])
            result = TASKS[task_id]["result"]
            communities = result["properties"]["communities"]
            nodes = result["properties"]["nodes"]
            c_id = [c["id"] for c in communities]
            node_id = [n["id"] for n in nodes]
            if target_id in c_id:
                index = c_id.index(target_id)
                return {
                    "status": "success",
                    "message": f"The result get successfully.",
                    "data": communities[index]
                }
            # ToolResult(success=True, message=f"The result get successfully.", properties=communities[index])
            elif target_id in node_id:
                index = node_id.index(target_id)
                return {
                    "status": "success",
                    "message": f"The result get successfully.",
                    "data": nodes[index]
                }
            # ToolResult(success=True, message=f"The result get successfully.", properties=nodes[index])
            else:
                return {
                    "status": "error",
                    "message": f"The target id is invalid",
                    "data": None
                }
    except Exception as e:
        logger.exception("Exception in execute")
        return {
            "status": "error",
            "message": f"An error occurred while executing the tool: {str(e)}",
            "data": None
        }

# router = APIRouter()
# mcp_app = mcp.http_app(path="/mcp")
mcp_app = create_sse_app(mcp, sse_path="/mcp", message_path="/messages")
app = FastAPI(title="Project Understand MCP APi", lifespan=mcp_app.lifespan)
app.mount("/llm", mcp_app)

# 允许跨域（如果你有客户端调试需求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload_project/")
async def upload_project(
    project_name: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # 检查扩展名
        if not file.filename.endswith(".zip"):
            return {"error": "Only .zip files are allowed"}
        # name = file.filename
        os.makedirs(os.path.join(BASE_DIR, project_name), exist_ok=True)
        # 生成唯一 project ID 目录
        project_dir = os.path.join(BASE_DIR, project_name, "project")
        os.makedirs(project_dir, exist_ok=True)

        save_path = os.path.join(project_dir, file.filename)

        # 保存上传文件
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        with zipfile.ZipFile(save_path, 'r') as zip_ref:
            zip_ref.extractall(project_dir)

        return {
            "message": "Upload successful",
            "filename": file.filename,
            "saved_path": save_path,
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/download_project/")
async def download_project(
    project_name: str = Form(...),
):
    project_path = os.path.join(BASE_DIR, project_name, "output")
    if not os.path.exists(project_path):
        return {"error": "Project not found"}
    else:
        zip_stream = BytesIO()
        with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(project_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, project_path)
                    zipf.write(full_path, arcname=relative_path)

        zip_stream.seek(0)
        return StreamingResponse(zip_stream, media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename={project_name}.zip"
        })


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=4200,
        path="/project_understand",
        log_level="info",
    )