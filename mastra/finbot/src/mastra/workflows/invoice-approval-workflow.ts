import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import pkg from 'pg';

const { Client } = pkg;

// PostgreSQL connection details
const host = "aws-0-us-east-2.pooler.supabase.com";
const port = 6543;
const user = "postgres.oqwfykofdqwhahcokrrl";
const database = "postgres";
const password = process.env.SUPABASE_PASSWORD!;
const connectionString = `postgresql://${user}:${password}@${host}:${port}/${database}`;

// Schema for invoice data
const invoiceSchema = z.object({
  amount: z.number(),
  category: z.string(),
  submitter: z.string(),
  dueDate: z.string(),
});

// Schema for human approval response
const approvalResponseSchema = z.object({
  approved: z.boolean(),
  reason: z.string().optional(),
});

// Step 1: Store invoice in database and get invoice ID
const storeInvoice = createStep({
  id: 'store-invoice',
  description: 'Stores the invoice in the database and returns the invoice ID',
  inputSchema: invoiceSchema,
  outputSchema: z.object({
    invoiceId: z.number(),
    amount: z.number(),
    category: z.string(),
    submitter: z.string(),
    dueDate: z.string(),
  }),
  execute: async ({ inputData }) => {
    if (!inputData) {
      throw new Error('Input data not found');
    }

    const { amount, category, submitter, dueDate } = inputData;

    const client = new Client({ connectionString });
    try {
      await client.connect();
      const result = await client.query(
        'INSERT INTO invoice (amount, category, submitter, due_date) VALUES ($1, $2, $3, $4) RETURNING id',
        [amount, category, submitter, dueDate]
      );
      
      const invoiceId = result.rows[0].id;
      
      return {
        invoiceId,
        amount,
        category,
        submitter,
        dueDate,
      };
    } finally {
      await client.end();
    }
  },
});

// Step 2: Request human approval (suspend workflow)
const requestHumanApproval = createStep({
  id: 'request-human-approval',
  description: 'Requests human approval for the invoice and suspends the workflow',
  inputSchema: z.object({
    invoiceId: z.number(),
    amount: z.number(),
    category: z.string(),
    submitter: z.string(),
    dueDate: z.string(),
  }),
  outputSchema: approvalResponseSchema,
  suspendSchema: z.object({}),
  resumeSchema: approvalResponseSchema,
  execute: async ({ inputData, resumeData, suspend }) => {
    if (!inputData) {
      throw new Error('Input data not found');
    }

    const { invoiceId, amount, category, submitter, dueDate } = inputData;

    // If we have resume data, return it (workflow was resumed)
    if (resumeData) {
      return resumeData;
    }

    // Create a user-friendly message for human approval
    const approvalMessage = `
🔍 INVOICE APPROVAL REQUIRED

Invoice ID: ${invoiceId}
Amount: $${amount.toLocaleString()}
Category: ${category}
Submitter: ${submitter}
Due Date: ${dueDate}

Please review this invoice and provide your decision.

Response format:
- approved: true/false
- reason: (optional) brief explanation for your decision
`;

    // Suspend the workflow and wait for human input
    await suspend({});

    // This return statement will only be reached if the step is resumed
    return {
      approved: false,
      reason: 'No response received'
    };
  },
});

// Step 3: Update invoice approval status
const updateInvoiceStatus = createStep({
  id: 'update-invoice-status',
  description: 'Updates the invoice approval status in the database',
  inputSchema: z.object({
    invoiceId: z.number(),
    approved: z.boolean(),
    reason: z.string().optional(),
  }),
  outputSchema: z.object({
    invoiceId: z.number(),
    approved: z.boolean(),
    success: z.boolean(),
    reason: z.string().optional(),
  }),
  execute: async ({ inputData }) => {
    if (!inputData) {
      throw new Error('Input data not found');
    }

    const { invoiceId, approved, reason } = inputData;

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

    return {
      invoiceId,
      approved,
      success,
      reason,
    };
  },
});

// Create the workflow
const invoiceApprovalWorkflow = createWorkflow({
  id: 'invoice-approval-workflow',
  inputSchema: invoiceSchema,
  outputSchema: z.object({
    invoiceId: z.number(),
    approved: z.boolean(),
    success: z.boolean(),
    reason: z.string().optional(),
  }),
})
  .then(storeInvoice)
  .then(requestHumanApproval)
  .then(updateInvoiceStatus);

invoiceApprovalWorkflow.commit();

export { invoiceApprovalWorkflow }; 