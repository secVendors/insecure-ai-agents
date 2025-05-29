# A Collection of Insecure Agents Built with Common AI Agent Frameworks

## Frameworks covered so far
- PydanticAI
  - Single Agent Examples
    - Compliance Agent helps you create a log of security patches in your codebase using GitHub's MCP server
    - SQL Agent that's vulnerable to sql injection
    - Agent that's vulnerable to memory poisoning, this is a WIP
- Mastra
  - Single Agent Examples
    - Helps you decide to move to SF or NYC, uses MCP servers and APIs to do research
    - GCN Bike Maintenance Agent, has 3 MCP servers and scrapes Global Cycling Network (GCN) YouTube videos and explains them to the user
    - COT RAG Agent, reads in files and answers questions using them. One file has an indirect prompt injection.
- LangGraph
  - Multi Agent Examples
    - Helps match ALS patients in a local db with clinical trials found on the web


## Want to contribute?
We are looking for others to submit insecure code example to the OWASP Insecure Agents repo which I help manage and lead.
https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/tree/main/initiatives/agent_security_initiative