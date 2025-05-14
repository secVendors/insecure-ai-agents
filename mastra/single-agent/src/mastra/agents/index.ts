import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { LibSQLStore } from '@mastra/libsql';
import { weatherTool } from '../tools';
import { MCPClient } from '@mastra/mcp';

export const weatherAgent = new Agent({
  name: 'Weather Agent',
  instructions: `
      You are a helpful weather assistant that provides accurate weather information.

      Your primary function is to help users get weather details for specific locations. When responding:
      - Always ask for a location if none is provided
      - If the location name isn’t in English, please translate it
      - If giving a location with multiple parts (e.g. "New York, NY"), use the most relevant part (e.g. "New York")
      - Include relevant details like humidity, wind conditions, and precipitation
      - Keep responses concise but informative

      Use the weatherTool to fetch current weather data.
`,
  model: openai('gpt-4o'),
  tools: { weatherTool },
  memory: new Memory({
    storage: new LibSQLStore({
      url: 'file:../mastra.db', // path is relative to the .mastra/output directory
    }),
    options: {
      lastMessages: 10,
      semanticRecall: false,
      threads: {
        generateTitle: false,
      },
    },
  }),
});

const web_search = new MCPClient({
  servers: {
    exa: {
      command: "npx",
      args: [
        "-y",
        "@smithery/cli@latest",
        "run",
        "exa",
        "--key",
        process.env.SMITHERY_API_KEY!,
      ],
    },
  },
});

export const movePlannerAgent = new Agent({
  name: "Move Planner Agent",
  instructions: `
  You are a helpful assistant that helps tech startup founders decide to move to either New York City or San Francisco. 
  You can use the web_search tool to get information on cost of living.
  `,
  tools: { weatherTool, ...(await web_search.getTools()) },
  model: openai("gpt-4o"),
  memory: new Memory(),
});
