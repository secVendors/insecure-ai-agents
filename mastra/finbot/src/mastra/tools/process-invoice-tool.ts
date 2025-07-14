import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import pkg from 'pg';

const { Client } = pkg;

const host = "aws-0-us-east-2.pooler.supabase.com";
const port = 6543;
const user = "postgres.oqwfykofdqwhahcokrrl";
const database = "postgres";
const password = process.env.SUPABASE_PASSWORD!;
const connectionString = `postgresql://${user}:${password}@${host}:${port}/${database}`;

export const processInvoiceTool = createTool({
  id: 'process-invoice',
  description: 'Process an invoice from a JSON string with amount, category, submitter, and dueDate, and store it in the database',
  inputSchema: z.object({
    invoiceJson: z.string().describe('A JSON string with keys: amount (integer), category (string), submitter (string), dueDate (date in YYYY-MM-DD format)'),
  }),
  outputSchema: z.object({
    amount: z.number(),
    category: z.string(),
    submitter: z.string(),
    dueDate: z.string(),
  }),
  execute: async ({ context }) => {
    return await processInvoice(context.invoiceJson);
  },
});

const invoiceSchema = z.object({
  amount: z.number(),
  category: z.string(),
  submitter: z.string(),
  dueDate: z.string().refine(
    (date) => /^\d{4}-\d{2}-\d{2}$/.test(date),
    { message: 'dueDate must be in YYYY-MM-DD format' }
  ),
});

const processInvoice = async (invoiceJson: string) => {
  let parsed;
  try {
    parsed = JSON.parse(invoiceJson);
  } catch (e) {
    throw new Error('Invalid JSON string');
  }
  const result = invoiceSchema.safeParse(parsed);
  if (!result.success) {
    throw new Error('Invalid invoice data: ' + JSON.stringify(result.error.issues));
  }
  const { amount, category, submitter, dueDate } = result.data;

  // Insert into the invoice table
  const client = new Client({ connectionString });
  try {
    await client.connect();
    await client.query(
      'INSERT INTO invoice (amount, category, submitter, due_date) VALUES ($1, $2, $3, $4)',
      [amount, category, submitter, dueDate]
    );
  } finally {
    await client.end();
  }

  return result.data;
}; 