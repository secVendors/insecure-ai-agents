import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

export const requestHumanApprovalTool = createTool({
  id: 'request-human-approval',
  description: 'Request human approval for an invoice by calling the invoice approval workflow. Use this when you need human intervention to approve or deny an invoice.',
  inputSchema: z.object({
    amount: z.number().describe('The invoice amount'),
    category: z.string().describe('The invoice category'),
    submitter: z.string().describe('The person who submitted the invoice'),
    dueDate: z.string().describe('The due date of the invoice in YYYY-MM-DD format'),
  }),
  outputSchema: z.object({
    invoiceId: z.number(),
    approved: z.boolean(),
    success: z.boolean(),
    reason: z.string().optional(),
  }),
  execute: async ({ context, mastra }) => {
    const { amount, category, submitter, dueDate } = context;

    // Get the invoice approval workflow
    const workflow = mastra?.getWorkflow("invoiceApprovalWorkflow");
    if (!workflow) {
      throw new Error('Invoice approval workflow not found');
    }

    // Create a new run instance
    const run = await workflow.createRunAsync();

    // Start the workflow with the invoice data
    const result = await run.start({
      inputData: {
        amount,
        category,
        submitter,
        dueDate,
      }
    });

    // If the workflow is suspended, it means it's waiting for human approval
    if (result.status === "suspended") {
      return {
        invoiceId: 0, // Will be updated when workflow resumes
        approved: false,
        success: false,
        reason: 'Workflow suspended - waiting for human approval'
      };
    }

    // If the workflow completed successfully
    if (result.status === "success" && result.result) {
      return result.result;
    }

    // If the workflow failed
    throw new Error(`Workflow failed: ${result.error || 'Unknown error'}`);
  },
}); 