# mcp_server_file_upload.py

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import shutil
import os
import zipfile
from io import BytesIO
from fastapi.responses import StreamingResponse

app = FastAPI()

# 允许跨域（如果你有客户端调试需求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件保存目录
BASE_DIR = "./workspace"
os.makedirs(BASE_DIR, exist_ok=True)

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

