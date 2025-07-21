
import { Mastra } from '@mastra/core/mastra';
import { Memory } from "@mastra/memory";
import { PinoLogger } from '@mastra/loggers';
import { LibSQLStore } from '@mastra/libsql';
import { weatherWorkflow } from './workflows/weather-workflow';
import { invoiceApprovalWorkflow } from './workflows/invoice-approval-workflow';
import { weatherAgent } from './agents/weather-agent';
import {finBotAgent } from './agents/finbot-agent'

export const mastra = new Mastra({
  workflows: { weatherWorkflow, invoiceApprovalWorkflow },
  agents: { weatherAgent, finBotAgent },
  storage: new LibSQLStore({
    // stores telemetry, evals, ... into memory storage, if it needs to persist, change to file:../mastra.db
    url: ":memory:",
  }),
  logger: new PinoLogger({
    name: 'Mastra',
    level: 'info',
  }),
});
