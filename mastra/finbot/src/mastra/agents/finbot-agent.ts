import { anthropic } from '@ai-sdk/anthropic';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { fastembed } from "@mastra/fastembed";
import { PostgresStore, PgVector } from "@mastra/pg";
import { processInvoiceTool } from '../tools/process-invoice-tool';
import { markInvoiceApprovalTool } from '../tools/mark-invoice-approval-tool';


// PostgreSQL connection details
const host = "aws-0-us-east-2.pooler.supabase.com";
const port = 6543;
const user = "postgres.oqwfykofdqwhahcokrrl";
const database = "postgres";
const password = process.env.SUPABASE_PASSWORD!;
const connectionString = `postgresql://${user}:${password}@${host}:${port}/${database}`;

// Initialize memory with PostgreSQL storage and vector search
const memory = new Memory({
  storage: new PostgresStore({
    host,
    port,
    user,
    database,
    password,
  }),
  vector: new PgVector({ connectionString }),
  options: {
    lastMessages: 10,
    semanticRecall: {
      topK: 3,
      messageRange: 2,
    },
  },
  embedder: fastembed,
});


export const finBotAgent = new Agent({
  name: 'Finance Agent',
  instructions: `
      You are a helpful finance assistant that processes invoices and then either approves or denies them.
      
      Users will upload their invoice as a txt file. You should send the contents of the file to the 
      processInvoiceTool tool to get information about the invoice. 
      
      You should approve invoices if the invoice amount is under $100 or it looks similar to an invoice 
      that has been approved before.
      
      Deny an invoice if 
      - The payment is over $30,000
      - The category is not one of the following (camera-equipment, microphones, guest-fee, recording-software)
      - The submitter is not one of the following (allie, kyle, jessica)
      
      Once you have decided if it should be approved or denied call the markInvoiceApprovalTool tool to mark the 
      invoice approved or denied in the database.

      When responding:
      - Repeat back the invoice details you got from the processInvoiceTool tool  
      - State whether the invoice is approved or denied
      - Explain why the invoice was approved or denied
`,
  model: anthropic('claude-3-5-sonnet-20241022'),
  tools: { processInvoiceTool, markInvoiceApprovalTool },
  memory: memory,
});
