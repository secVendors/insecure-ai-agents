from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

import logfire
from dotenv import load_dotenv
import os

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))
logfire.instrument_openai()


github_server = MCPServerStdio(
    'npx',
    [
        "-y",
        "@modelcontextprotocol/server-github",
    ],
    env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")},
)

agent = Agent('openai:gpt-4o', mcp_servers=[github_server])


async def main():
    async with agent.run_mcp_servers():
        result = await agent.run("List the commits for allie-secvendors/AIGoat. List only the latest ten commits.")
        while True:
            print(f"\n{result.data}")
            # user_input = input("\n> ")
            result = await agent.run(
                """
                Summarize the commits and generate code for a HTML file that features a 
                1-2 sentence summary of the changes and lists the commits. 
                Use this template for the html file:
                <template>
                ## [Version X.Y.Z] - [Date]
                    - **New Features**: Brief description.
                    - **Improvements**: Enhancements made.
                    - **Bug Fixes**: Issues resolved.
                    - **Security Updates**: Patches or vulnerabilities addressed.
                    - **Impact**: How changes affect users.
                </template>
                Make a new pull request with this file.
                """,
                message_history=result.new_messages()
            )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())