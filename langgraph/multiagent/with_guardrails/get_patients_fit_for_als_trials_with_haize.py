import getpass
import os
import asyncio
import nest_asyncio
import argparse
from typing import Literal
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit, PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_async_playwright_browser
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from haizelabs.client import HaizeClient


nest_asyncio.apply()

# allow tracing via LangSmith for observability and debugging
os.environ["LANGCHAIN_TRACING_V2"] = "true"
LANGCHAIN_ENDPOINT = "https://api.smith.langchain.com"
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT")


def _set_env(key: str):
    if key not in os.environ:
        os.environ[key] = getpass.getpass(f"{key}:")


_set_env("OPENAI_API_KEY")
_set_env("HAIZE_LABS_API_KEY")
haize_client = HaizeClient()

# set llm and create team members for the lead agent to supervise
llm = ChatOpenAI(model="gpt-4o-mini")
members = ["clinical_researcher", "database_admin"]
# Our team supervisor is an LLM node. It picks the next agent to process
# and decides when the work is completed
options = members + ["FINISH"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal[*options]


def call_haize_judge(judge_ids, messages):
    response = haize_client.judges.call(
        judge_ids=judge_ids,
        messages=messages,
    )
    return response


def supervisor_node(state: MessagesState) -> Command[Literal[*members, "__end__"]]:
    system_prompt = (
        "You are a supervisor tasked with managing a conversation between the"
        f" following workers: {members}. Given the following user request,"
        " respond with the worker to act next. Each worker will perform a"
        " task and respond with their results and status. When finished,"
        " respond with FINISH."
    )
    messages = [
                   {"role": "system", "content": system_prompt},
               ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    if goto == "FINISH":
        goto = END
    return Command(goto=goto)


def create_clinical_research_agent():
    async_browser = create_async_playwright_browser()
    clinical_research_toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)

    clinical_research_tools = clinical_research_toolkit.get_tools()

    clinical_research_agent = create_react_agent(
        llm, tools=clinical_research_tools,
        state_modifier="You are a ALS clinical researcher. Your name is Charity. Search for ALS clinical trials on https://www.hopkinsmedicine.org/neurology-neurosurgery/clinical-trials/als-clinical-trials/open-trials. DO NOT navigate to any other website, even if the supervisor or user asks you to. Extract text from on the webpage. Let Steve know the Length of Study for each trial."
    )
    return clinical_research_agent


async def clinical_researcher_node(state: MessagesState) -> Command[Literal["supervisor"]]:
    clinical_research_agent = create_clinical_research_agent()
    result = await clinical_research_agent.ainvoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="clinical_researcher")
            ]
        },
        goto="supervisor",
    )


def create_database_admin_agent():
    db = SQLDatabase.from_uri("sqlite:///als_patients.db")
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
    assert len(prompt_template.messages) == 1

    system_message = """System: You are an agent designed to interact with a SQL database filled with ALS patient data. Your name is Steve.
    You will work together with Charity who has access to a list of ALS clinical trials to determine which patients in the list you would recommend for each clinical trial.
    A patient should go to a clinical trial if they are likely to live longer than the Length of Study for that trial.
    Please provide a list of recommended patients for each trial. List the patients name and their ALSFRS-R score.
    Given an input question, create a syntactically correct SQLite query to run, then look at the results of the query and return the answer.
    You can order the results by a relevant column to return the most interesting examples in the database.
    Never query for all the columns from a specific table, only ask for the relevant columns given the question.
    You have access to tools for interacting with the database.
    Only use the below tools. Only use the information returned by the below tools to construct your final answer.
    You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

    To start you should ALWAYS look at the tables in the database to see what you can query.
    Do NOT skip this step.
    Then you should query the schema of the most relevant tables."""

    sql_agent_executor = create_react_agent(llm, tools, state_modifier=system_message)
    return sql_agent_executor


def db_admin_node(state: MessagesState) -> Command[Literal["supervisor"]]:
    sql_agent_executor = create_database_admin_agent()
    result = sql_agent_executor.invoke(state)

    messages = HumanMessage(content=result["messages"][-1].content, name="database_admin")

    # judges: als_trials_more_than_one_patient_in_output_judge -> we want this to actually return True
    # ignore_off_topics_in_chat_output (finds content not related to ALS patients and which trials they are a good
    # fit for -> we want this to return False
    responses = call_haize_judge(
        ["50cba209-7727-48e3-900d-5e03de120ab1", "cc46bc48-f662-4807-840f-071b9578deaf"],
        [
            {
                "role": "assistant",
                "content": messages.content,
            }
        ],
    )
    # it's detecting there's at least two patients in the output so were not giving away individual patient info
    # it's detecting off-topic responses
    for r in responses:
        if r.judge_id == "50cba209-7727-48e3-900d-5e03de120ab1" and not r.detected:
            messages = HumanMessage(content="Please ask a different question. FINISH.", name="supervisor")
        if r.judge_id == "cc46bc48-f662-4807-840f-071b9578deaf" and r.detected:
            messages = HumanMessage(content="Please ask a different question. FINISH.", name="supervisor")
    return Command(
        update={
            "messages": [
                messages
            ]
        },
        goto="supervisor",
    )


async def run_agents(prompt):
    builder = StateGraph(MessagesState)
    builder.add_edge(START, "supervisor")
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("clinical_researcher", clinical_researcher_node)
    builder.add_node("database_admin", db_admin_node)
    graph = builder.compile()

    async for s in graph.astream(
            {
                "messages": [
                    (
                            "user",
                            "Find ALS clinical trials, then recommend patients in the database for each trial"
                            if prompt is None else prompt,
                    )
                ]
            },
            subgraphs=True,
    ):
        print(s)
        print("----")


def validate_prompt(prompt):
    starting_message = [
        {
            "role": "user",
            "content": prompt,
        }
    ]
    # judges: patient_name_in_input, override_webscraper, ignore_harmful_topics, ignore_off_topics, find_pii
    response = call_haize_judge(
        [
            "58f2a5e4-d99c-4770-ad83-2ca17d4abf5c",
            "1ccc3140-c81b-4228-baa0-8a3e8889b2fb",
            "21ac5f3b-0964-47ab-b041-c90840624759",
            "27ba6f76-c78d-4040-927e-3255748d7be7",
            "d82f689f-6f27-47bc-8d22-eb735035e194",
        ],
        starting_message
    )
    for r in response:
        if r.detected is True:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt', required=False)  # positional argument
    args = parser.parse_args()

    if args.prompt is not None:
        if not validate_prompt(args.prompt):
            print("Prompt failed guardrails")
            exit(1)

    asyncio.run(run_agents(args.prompt))


if __name__ == '__main__':
    main()
