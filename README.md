# Project Understand MCP Server

一个基于FastAPI的MCP服务器，用于分析代码仓库并生成架构图和活动图。

## 功能特性

- 上传项目代码(zip格式)
- 自动分析代码依赖关系
- 生成架构图和活动图(PUML格式)
- 下载分析结果
- 支持Python、Java、C++项目

## 安装与运行

### 前置要求

- Python 3.8+
- Java 8+ (用于运行depends.jar)
- FastAPI及相关依赖

### 安装步骤

1. 克隆仓库：
   ```bash
   git clone git@github.com:Boat1098/mcp.git
   cd mcp
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 确保depends.jar文件位于`others/`目录下

### 运行服务

```bash
uvicorn analysis:app --reload --port 8000 --limit-max-requests 100
```

服务默认运行在`127.0.0.1:8000`

## API接口

### 上传项目

```
POST /upload_project/
```

参数：
- `project_name`: 项目名称
- `file`: 项目代码zip文件

### 分析项目

```
POST /mcp/project_understand
```

参数：
- `project_name`: 要分析的项目名称
- `task_id`: 任务ID(首次调用留空)

### 下载结果

```
POST /download_project/
```

参数：
- `project_name`: 要下载的项目名称

### 获取分析结果

```
POST /mcp/get_understand_result
```

参数：
- `task_id`: 分析任务ID
- `target_id`: 可选，指定要获取的模块或节点ID

## 使用示例

1. 上传项目：
   ```bash
   curl -X POST http://localhost:4200/upload_project/ \
     -F "file=@your_project.zip" \
     -F "project_name=my_project"
   ```

2. 开始分析：
   ```bash
   curl -X POST http://localhost:4200/mcp/project_understand \
     -H "Content-Type: application/json" \
     -d '{"project_name": "my_project"}'
   ```

3. 获取分析结果：
   ```bash
   curl -X POST http://localhost:4200/mcp/get_understand_result \
     -H "Content-Type: application/json" \
     -d '{"task_id": "your_task_id"}'
   ```

4. 下载结果：
   ```bash
   curl -X POST http://localhost:4200/download_project/ \
     -F "project_name=my_project" \
     --output results.zip
   ```

## 项目结构

```
mcp/
├── analysis.py        # 主服务入口
├── app.py             # 文件上传下载API
├── project_understand/ # 分析模块
│   ├── AGraphGenerate.py # 图生成
│   ├── dataProcess.py    # 数据处理
│   ├── ModuleChat.py     # 模块交互
│   └── util.py           # 工具函数
├── others/            # 依赖工具
│   └── depends.jar    # 依赖分析工具
└── workspace/         # 工作目录
```

## 注意事项

1. 上传的项目必须是zip格式
2. 分析大型项目可能需要较长时间
3. 确保有足够的磁盘空间存放分析结果
