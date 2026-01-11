from typing import List, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
from splunk_config import get_system_prompt, SPLUNK_CONFIG

load_dotenv()


#! MQ TOOL
@tool
def mq_search(query: str) -> str:
    """Search the latest logs in MQ. Use this when user asks for 'latest logs' or 'recent logs'."""
    return f"[MQ] Searching latest logs with query: {query}"


#! REDIS TOOL
@tool
def redis_search(query: str) -> str:
    """Search the latest logs in Redis. Use this when user asks for 'latest logs' or 'recent logs'."""
    return f"[Redis] Searching latest logs with query: {query}"


#! SPLUNK MCP TOOL WRAPPER
class SplunkToolWrapper:
    def __init__(self):
        self.mcp_session = None
        self.tools = []
        self._stdio_context = None
        self._session_context = None

    @asynccontextmanager
    async def connect(self):
        splunk_host = os.getenv("SPLUNK_HOST") or "localhost"
        splunk_port = os.getenv("SPLUNK_PORT") or "8089"
        splunk_username = os.getenv("SPLUNK_USERNAME") or ""
        splunk_password = os.getenv("SPLUNK_PASSWORD") or ""

        subprocess_env = os.environ.copy()
        subprocess_env.update(
            {
                "SPLUNK_HOST": splunk_host,
                "SPLUNK_PORT": splunk_port,
                "SPLUNK_USERNAME": splunk_username,
                "SPLUNK_PASSWORD": splunk_password,
                "SPLUNK_SCHEME": os.getenv("SPLUNK_SCHEME", "https"),
                "VERIFY_SSL": "false",
            }
        )

        server_params = StdioServerParameters(
            command="python",
            args=["/opt/splunk-mcp/splunk_mcp.py", "stdio"],
            env=subprocess_env,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                self.mcp_session = session
                await self.mcp_session.initialize()

                mcp_tools = await self.mcp_session.list_tools()

                for mcp_tool in mcp_tools.tools:
                    self.tools.append(self._create_langchain_tool(mcp_tool))

                yield self.tools

    def _create_langchain_tool(self, mcp_tool):
        from langchain_core.tools import StructuredTool

        tool_name = mcp_tool.name
        tool_description = mcp_tool.description or f"Splunk tool: {tool_name}"

        async def call_splunk_tool(**kwargs) -> str:
            print(f"[Calling Splunk tool: {tool_name}]")
            result = await self.mcp_session.call_tool(tool_name, kwargs)
            return str(result.content)

        return StructuredTool.from_function(
            coroutine=call_splunk_tool,
            name=tool_name,
            description=tool_description,
        )


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


#! MQ ROUTER
def should_use_mq(state: AgentState) -> bool:
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return False

    query = last_message.content.lower()

    latest_keywords = ["latest", "recent", "newest", "current", "mq", "MQ"]
    return any(keyword in query for keyword in latest_keywords)


#! REDIS ROUTER
def should_use_redis(state: AgentState) -> bool:
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return False

    query = last_message.content.lower()

    latest_keywords = ["latest", "recent", "newest", "current", "redis", "Redis"]
    return any(keyword in query for keyword in latest_keywords)


#! MQ AGENT
async def mq_agent(state: AgentState):
    messages = state["messages"]
    mq_system_prompt = get_system_prompt([mq_search])
    mq_instructions = """
    
ADDITIONAL MQ INSTRUCTIONS:
- You are handling queries about LATEST/RECENT logs
- Focus on the most recent data (typically last hour or less)
- Use the mq_search tool for these queries
"""

    system_message = SystemMessage(content=mq_system_prompt + mq_instructions)

    # Combine system prompt with conversation
    messages_with_system = [system_message] + list(messages)

    # Bind MQ tools to model
    model_with_tools = model.bind_tools([mq_search])
    response = await model_with_tools.ainvoke(messages_with_system)

    return {"messages": [response]}


#! REDIS AGENT
async def redis_agent(state: AgentState):
    messages = state["messages"]
    redis_system_prompt = get_system_prompt([redis_search])
    redis_instructions = """
    
ADDITIONAL REDIS INSTRUCTIONS:
- You are handling queries about LATEST/RECENT logs
- Focus on the most recent data (typically last hour or less)
- Use the redis_search tool for these queries
"""

    system_message = SystemMessage(content=redis_system_prompt + redis_instructions)

    # Combine system prompt with conversation
    messages_with_system = [system_message] + list(messages)

    # Bind Redis tools to model
    model_with_tools = model.bind_tools([redis_search])
    response = await model_with_tools.ainvoke(messages_with_system)

    return {"messages": [response]}


# SPLUNK AGENT
async def splunk_agent(state: AgentState):
    messages = state["messages"]
    splunk_system_prompt = get_system_prompt(splunk_tools)
    system_message = SystemMessage(content=splunk_system_prompt)
    messages_with_system = [system_message] + list(messages)
    model_with_tools = model.bind_tools(splunk_tools)
    response = await model_with_tools.ainvoke(messages_with_system)

    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


#! ----- GRAPH -------


async def create_agent(splunk_tools_list):
    global splunk_tools
    splunk_tools = splunk_tools_list

    workflow = StateGraph(AgentState)

    workflow.add_node("mq_agent", mq_agent)
    workflow.add_node("redis_agent", redis_agent)
    workflow.add_node("splunk_agent", splunk_agent)
    workflow.add_node("mq_tools", ToolNode([mq_search]))
    workflow.add_node("redis_tools", ToolNode([redis_search]))
    workflow.add_node("splunk_tools", ToolNode(splunk_tools))

    workflow.add_conditional_edges(
        START,
        lambda state: "mq_agent" if should_use_mq(state) else "redis_agent",
        {
            "mq_agent": "mq_agent",
            "redis_agent": "redis_agent",
        },
    )

    workflow.add_conditional_edges(
        "mq_agent", should_continue, {"tools": "mq_tools", END: "splunk_agent"}
    )
    workflow.add_edge("mq_tools", "mq_agent")

    workflow.add_conditional_edges(
        "redis_agent", should_continue, {"tools": "redis_tools", END: "splunk_agent"}
    )
    workflow.add_edge("redis_tools", "redis_agent")

    workflow.add_conditional_edges(
        "splunk_agent", should_continue, {"tools": "splunk_tools", END: END}
    )
    workflow.add_edge("splunk_tools", "splunk_agent")

    return workflow.compile()


#! VISUALIZE GRAPH
def visualize_graph(app):
    """Generate and save the graph visualization"""
    try:
        from IPython.display import Image, display

        # Generate and display PNG
        print("Generating graph visualization...")
        display(Image(app.get_graph().draw_mermaid_png()))

        # Also save to file
        png_data = app.get_graph().draw_mermaid_png()
        with open("langgraph_visualization.png", "wb") as f:
            f.write(png_data)
        print("✓ Graph saved as 'langgraph_visualization.png'")

    except ImportError:
        print("IPython not available (not in Jupyter), saving to file only...")
        try:
            png_data = app.get_graph().draw_mermaid_png()
            with open("langgraph_visualization.png", "wb") as f:
                f.write(png_data)
            print("✓ Graph saved as 'langgraph_visualization.png'")
            print("  Open the file to view the graph.")
        except Exception as e:
            print(f"PNG generation failed: {e}")
            print("Trying Mermaid syntax fallback...")
            visualize_mermaid_fallback(app)

    except Exception as e:
        print(f"Visualization error: {e}")
        print("Trying Mermaid syntax fallback...")
        visualize_mermaid_fallback(app)


def visualize_mermaid_fallback(app):
    try:
        mermaid_syntax = app.get_graph().draw_mermaid()

        with open("langgraph_visualization.mmd", "w") as f:
            f.write(mermaid_syntax)

        print("✓ Mermaid diagram saved as 'langgraph_visualization.mmd'")
        print("\nMermaid Diagram:")
        print("=" * 60)
        print(mermaid_syntax)
        print("=" * 60)
        print("\nVisualize at: https://mermaid.live/")

    except Exception as e2:
        print(f"Mermaid generation also failed: {e2}")




#! MAIN CHAT LOOP 

async def main():
    print("=" * 60)
    print("Splunk LangGraph Chatbot")
    print("=" * 60)
    print("Initializing Splunk MCP connection...")

    global model
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0)

    splunk_wrapper = SplunkToolWrapper()
    async with splunk_wrapper.connect() as splunk_tools_list:
        app = await create_agent(splunk_tools_list)

        print("\n" + "=" * 60)
        print("Graph Visualization")
        print("=" * 60)
        visualize_graph(app)

        print("\n" + "=" * 60)
        print("Chat Interface")
        print("=" * 60)
        print("Commands:")
        print("  - Type your query to search logs")
        print("  - Use 'latest' or 'recent' to search MQ")
        print("  - Type 'exit' or 'quit' to end")
        print("=" * 60 + "\n")

        while True:
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            try:
                result = await app.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]}
                )
                last_message = result["messages"][-1]
                print(f"\nBot: {last_message.content}\n")

            except Exception as e:
                print(f"Error: {e}")
                import traceback

                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
