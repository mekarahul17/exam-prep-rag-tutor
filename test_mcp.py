import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("Real MCP server connected")

            result = await session.call_tool(
                "read_handwritten_note",
                {
                    "image_path": r"C:\Users\jagan\OneDrive\Pictures\Screenshots\new.png",
                },
            )

            print("\nHandwritten note result:")

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text[:10000])


if __name__ == "__main__":
    asyncio.run(main())