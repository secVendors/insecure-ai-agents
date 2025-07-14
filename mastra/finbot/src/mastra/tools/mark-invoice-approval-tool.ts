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

export const markInvoiceApprovalTool = createTool({
  id: 'mark-invoice-approval',
  description: 'Mark an invoice as approved or denied in the database by invoice id.',
  inputSchema: z.object({
    invoiceId: z.number().describe('The id of the invoice to update'),
    approved: z.boolean().describe('Whether the invoice is approved (true) or denied (false)'),
  }),
  outputSchema: z.object({
    invoiceId: z.number(),
    approved: z.boolean(),
    success: z.boolean(),
  }),
  execute: async ({ context }) => {
    return await markInvoiceApproval(context.invoiceId, context.approved);
  },
});

const markInvoiceApproval = async (invoiceId: number, approved: boolean) => {
  const client = new Client({ connectionString });
  let success = false;
  try {
    await client.connect();
    const res = await client.query(
      'UPDATE invoice SET approved = $1 WHERE id = $2',
      [approved, invoiceId]
    );
    success = res.rowCount > 0;
  } finally {
    await client.end();
  }
  return { invoiceId, approved, success };
}; 