from typing import TypedDict, Annotated, Sequence
import os
import shutil
from langchain_core.messages import (
    HumanMessage,
    ToolMessage,
    SystemMessage,
    BaseMessage,
)
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain_community.vectorstores import Chroma


load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

embeddings = GoogleGenerativeAIEmbeddings(model="text-embedding-004")


#! Defining the agent state
class agentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


logs_path = "data/ace_syslog_400.jsonl"

if not os.path.exists(logs_path):
    raise ValueError("Logs file does not exist")

json_loader = JSONLoader(
    file_path=logs_path, jq_schema=".", text_content=False, json_lines=True
)

try:
    docs = json_loader.load()
    print(f"File loaded successfully - {len(docs)} documents found")
except Exception as e:
    print(f"Error loading file: {e}")
    docs = []


vector_db_directory = "data/db/"
collection_name = "logs"


if os.path.exists(vector_db_directory):
    print("Removing existing vectorstore...")
    shutil.rmtree(vector_db_directory)


os.makedirs(vector_db_directory)

#! Loading the data into vector db
try:
    print("Creating fresh vectorstore...")
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=vector_db_directory,
    )
    print(f"Total documents in vectorstore: {vectorstore._collection.count()}")

except Exception as e:
    print(f"Error creating vectorstore: {e}")


#! Retriver function to retrive the records from the db
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 10},
)


#! Tool to search for error code in db
@tool
def search_critical_errors(query: str) -> str:
    """
    Search for critical ACE (IBM App Connect Enterprise) errors and warnings.
    Use this tool when user asks about errors, issues, or problems in ACE logs.

    Args:
        query: Description of the error or issue to search for

    Returns:
        Analysis of critical errors with potential fixes
    """

    results = retriever.invoke(query)
    critical_logs = []
    for doc in results:
        content = doc.page_content
        metadata = doc.metadata

        if '"severity": "E"' in content or '"severity": "W"' in content:
            critical_logs.append(doc)

    if not critical_logs:
        return "No critical errors found in the logs"

    formatted_logs = []
    for i, doc in enumerate(critical_logs[:5], 1):  # 5 critical issues
        formatted_logs.append(f"Log {i}:\n{doc.page_content}\n")

    return "\n".join(formatted_logs)


tools = [search_critical_errors]

model_with_tools = llm.bind_tools(tools)

system_prompt = """You are an expert IBM App Connect Enterprise (ACE) log analyzer with deep knowledge of:
- ACE error codes and their meanings
- Common ACE integration patterns and failure modes
- Database connectivity issues in integration flows
- Message broker configurations
- Troubleshooting distributed integration systems

Your role is to:
1. Analyze ACE logs retrieved from the vector database
2. Identify critical errors (severity: E) and warnings (severity: W)
3. Explain what each error means and why it likely occurred
4. Provide specific, actionable remediation steps based on the error context
5. Prioritize issues by severity and impact

When analyzing logs:
- Parse the error code, message, affected components (flow, node, application)
- Consider the timestamp to identify patterns or cascading failures
- Look at context like PID, CorrelationID, MsgID for tracking related issues
- Provide IBM ACE-specific troubleshooting steps

Format your response as:
## Critical Issues Summary
[Brief overview of high-severity problems]

## Detailed Analysis
For each critical error:
- **Error Code & Message**: [What was logged]
- **Root Cause**: [Why this happened]
- **Impact**: [What systems/flows are affected]
- **Remediation Steps**: [Specific actions to fix]

## Priority Actions
[Ordered list of what to do first]

⚠️ IMPORTANT RULE:
If the user asks about anything **not related to ACE log analysis, errors, warnings, failures, or remediation**, respond exactly as:

"I don't know"

Examples of queries you must reply to with "I don't know":
- What is the capital of India?
- Who is the president of the USA?
- Explain bubble sort
- Write me an email
- Generate an image
- Any non-log-analysis question

Stick strictly to this rule, no matter how simple or obvious the question is.
"""


tools_dict = {our_tool.name: our_tool for our_tool in tools}


#! LLM agent call function
def call_llm(state: agentState) -> agentState:
    """Function to call the LLM with current state"""

    messages = list(state["messages"])
    messages = [SystemMessage(content=system_prompt)] + messages
    messages = model_with_tools.invoke(messages)
    return {"messages": messages}


#! Tool execution function
def take_action(state: agentState) -> agentState:
    """Execute tool calls from the LLM's response."""

    tool_calls = state["messages"][-1].tool_calls
    results = []
    for t in tool_calls:
        print(
            f"Calling Tool: {t['name']} with query: {t['args'].get('query', 'No query provided')}"
        )

        if t["name"] not in tools_dict:
            print(f"\nTool: {t['name']} does not exist.")
            result = "Incorrect Tool Name, Please Retry and Select tool from List of Available tools."

        else:
            result = tools_dict[t["name"]].invoke(t["args"].get("query", ""))
            print(f"Result length: {len(str(result))}")

        # Appends the Tool Message
        results.append(
            ToolMessage(tool_call_id=t["id"], name=t["name"], content=str(result))
        )

    print("Tools Execution Complete. Back to the model!")
    return {"messages": results}


def should_continue(state: agentState) -> bool:
    """Check if the last message contains tool calls."""

    result = state["messages"][-1]
    return hasattr(result, "tool_calls") and len(result.tool_calls) > 0


graph = StateGraph(agentState)

graph.add_node("llm", call_llm)
graph.add_node("retriver_agent", take_action)

graph.add_conditional_edges(
    "llm",
    should_continue,
    {True: "retriver_agent", False: END},
)

graph.add_edge("retriver_agent", "llm")
graph.add_edge(START, "llm")

rag_agent = graph.compile()


def running_agent():
    print("\n=== RAG AGENT===")

    while True:
        user_input = input("\nWhat is your question: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        messages = [HumanMessage(content=user_input)]

        result = rag_agent.invoke({"messages": messages})

        print("\n=== ANSWER ===")
        print("\n" + "=" * 40)
        print("🔍 ACE LOG ANALYSIS RESULT")
        print("=" * 40 + "\n")
        content = result["messages"][-1].content
        if isinstance(content, list) and len(content) > 0 and "text" in content[0]:
            print(content[0]["text"])
        else:
            print(content)
        print("\n" + "=" * 40)


if __name__ == "__main__":
    running_agent()
