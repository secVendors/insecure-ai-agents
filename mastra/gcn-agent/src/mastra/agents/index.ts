import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { LibSQLStore } from '@mastra/libsql';
import { weatherTool } from '../tools';
import { MCPClient } from '@mastra/mcp';
import { xai } from '@ai-sdk/xai';

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


const youtube_toolbox_mcp = new MCPClient({
  servers: {
    youtube: {
      command: "npx",
      env: {
        youtubeApiKey: process.env.YOUTUBE_API_KEY!,
      },
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@icraft2170/youtube-data-mcp-server",
        "--key",
        process.env.SMITHERY_API_KEY!,
        "--profile",
        "acceptable-terabyte-vV8Vz-"
      ]
    },
  },
});


const youtube_transcript_mcp = new MCPClient({
  servers: {
    mcp_youtube_transcript: {
      command: "npx",
      env: {
        YOUTUBE_API_KEY: process.env.YOUTUBE_API_KEY!,
      },
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@sinco-lab/mcp-youtube-transcript",
        "--key",
        process.env.SMITHERY_API_KEY!
      ]
    },
  },
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

const {youtube_searchVideos} = await youtube_toolbox_mcp.getTools();
const {mcp_youtube_transcript_get_transcripts} = await youtube_transcript_mcp.getTools();
const {exa_web_search_exa} = await web_search.getTools()

export const gcnAgent = new Agent({
  name: 'Bike Maintenance Agent',
  instructions: `
      You are a helpful cycling assistant from the Global Cycling Network that helps people clean or maintenance their road bikes.

      Your primary function is to help users maintenance their bike. When responding:
      - Give step by step instructions
      - Keep responses concise but informative

      Use the searchVideos tool and pass the channel_id gcn to search for helpful videos.
      Once you have found a video that can help get the transcript of that video using the 
      get_transcripts tool. Use this transcript to provide instructions to the user.
      If the user has follow up questions about maintenance tools or bike parts use
      the web_search_exa tool to find an image of the part. Show this image to the 
      user as a part of your answer.
`,
  model: openai('gpt-4o'),
  //tools: {youtube_searchVideos, mcp_youtube_transcript_get_transcripts, exa_web_search_exa},
  tools: { ...(await youtube_toolbox_mcp.getTools()), ...(await youtube_transcript_mcp.getTools()), ...(await web_search.getTools()) },
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


export const bikeImageAgent = new Agent({
  name: 'Bike Image Agent',
  instructions: `
      You are a helpful image generating assistant that generates images of bicycle part 
      or tools related to bike maintenance.
`,
  model: xai('grok-3'),
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

