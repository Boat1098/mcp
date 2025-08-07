import asyncio
import zipfile
from fastapi import UploadFile
from fastmcp import Client
import base64

async def example():
    async with Client("http://127.0.0.1:8000/llm/mcp") as client:
        # await client.ping()
        res = await client.call_tool(
            "get_repo_understand", 
            {
                "task_id": "", 
                "project_name":"jansson"
            })
        # res = await client.list_tools()
        print(res)

if __name__ == "__main__":
    asyncio.run(example())