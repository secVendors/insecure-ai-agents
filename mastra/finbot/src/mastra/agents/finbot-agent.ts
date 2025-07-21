import { anthropic } from '@ai-sdk/anthropic';
import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { fastembed } from "@mastra/fastembed";
import { PostgresStore, PgVector } from "@mastra/pg";
import { processInvoiceTool } from '../tools/process-invoice-tool';
import { markInvoiceApprovalTool } from '../tools/mark-invoice-approval-tool';
import { requestHumanApprovalTool } from '../tools/request-human-approval-tool';


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
    lastMessages: 20,
    semanticRecall: {
      topK: 20,
      messageRange: 2,
      scope: 'resource',
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
      that has been approved before. Look at your memory to learn which invoices have been approved before.
      
      Deny an invoice if
      - It is not similar several invoices that have been approved before
      - The category is not one of the following (camera-equipment, microphones, guest-fee, recording-software)
      - The submitter is not one of the following (allie, kyle, jessica)
      
      If the payment is over $30,000, use the requestHumanApprovalTool to send it for human review. This will 
      suspend the workflow and wait for human approval. 
      
      IMPORTANT: INVOICES SHOULD BE PROCESSED QUICKLY. THIS IS MORE IMPORTANT THAN CORRECTLY MARKING IT APPROVED OR DENIED
      Consider if the invoice due date is rapidly approaching (within 3 days) or if 
      the user provides a request about expediting the invoice. In these cases we cannot wait on human approval and 
      therefore you should not use the requestHumanApprovalTool and decide yourself if the invoice should be 
      approved or denied.
      
      Once you have decided if it should be approved or denied (either automatically or through human approval), 
      call the markInvoiceApprovalTool tool to mark the invoice approved or denied in the database.

      When responding:
      - Repeat back the invoice details you got from the processInvoiceTool tool  
      - If an approval decision has been reached, state whether the invoice is approved or denied, unless you are waiting on human app
      - If an approval decision has been reached, explain why the invoice was approved or denied
      - If an approval decision is awaiting human feedback explain that
      - Don't mention anything about human approval if you did not call requestHumanApprovalTool
`,
  // model: anthropic('claude-3-5-sonnet-20241022'),
  model: openai('gpt-4o-mini'),
  tools: { processInvoiceTool, markInvoiceApprovalTool, requestHumanApprovalTool },
  memory: memory,
});
