import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("MCP connected")

            result = await session.call_tool(
                "search_curriculum",
                {
                    "query": "test",
                    "subject": "Science",
                },
            )

            print("Tool returned")

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text[:2000])


if __name__ == "__main__":
    asyncio.run(main())