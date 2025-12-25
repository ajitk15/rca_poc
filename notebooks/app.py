import streamlit as st
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

# Page configuration
st.set_page_config(
    page_title="ACE Log Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    .analysis-section {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "rag_agent" not in st.session_state:
    st.session_state.rag_agent = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "vectorstore_loaded" not in st.session_state:
    st.session_state.vectorstore_loaded = False


@st.cache_resource
def initialize_agent():
    """Initialize the RAG agent with caching"""
    load_dotenv()

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    embeddings = GoogleGenerativeAIEmbeddings(model="text-embedding-004")

    # Define agent state
    class agentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    # Try multiple possible paths
    possible_paths = [
        "data/ace_syslog_400.jsonl",  # Relative to current dir
        "../data/ace_syslog_400.jsonl",  # One level up
        "/workspace/data/ace_syslog_400.jsonl",  # Absolute path
        os.path.join(os.getcwd(), "data", "ace_syslog_400.jsonl"),
        os.path.join(os.path.dirname(os.getcwd()), "data", "ace_syslog_400.jsonl"),
    ]

    logs_path = None
    for path in possible_paths:
        if os.path.exists(path):
            logs_path = path
            st.sidebar.info(f"✅ Found file at: {path}")
            break

    if not logs_path:
        st.error(f"❌ Could not find logs file in any of these locations:")
        for path in possible_paths:
            st.error(f"  - {path}")
        st.info(f"📁 Current working directory: {os.getcwd()}")
        st.info(f"📂 Parent directory: {os.path.dirname(os.getcwd())}")
        return None

    json_loader = JSONLoader(
        file_path=logs_path, jq_schema=".", text_content=False, json_lines=True
    )

    try:
        docs = json_loader.load()
        st.sidebar.success(f"✅ Loaded {len(docs)} documents")
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

    # Set vector db directory - try parent directory first
    parent_dir = os.path.dirname(os.getcwd())
    vector_db_directory = os.path.join(parent_dir, "data", "db")

    # If parent doesn't have data folder, use current directory
    if not os.path.exists(os.path.join(parent_dir, "data")):
        vector_db_directory = os.path.join(os.getcwd(), "data", "db")

    collection_name = "logs"

    if os.path.exists(vector_db_directory):
        shutil.rmtree(vector_db_directory)

    os.makedirs(vector_db_directory, exist_ok=True)

    try:
        vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            collection_name=collection_name,
            persist_directory=vector_db_directory,
        )
        st.sidebar.success(
            f"✅ Vectorstore created: {vectorstore._collection.count()} docs"
        )
    except Exception as e:
        st.error(f"Error creating vectorstore: {e}")
        return None

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 10},
    )

    @tool
    def search_critical_errors(query: str) -> str:
        """Search for critical ACE errors and warnings."""
        results = retriever.invoke(query)
        critical_logs = []
        for doc in results:
            content = doc.page_content
            if '"severity": "E"' in content or '"severity": "W"' in content:
                critical_logs.append(doc)

        if not critical_logs:
            return "No critical errors found in the logs"

        formatted_logs = []
        for i, doc in enumerate(critical_logs[:5], 1):
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

⚠️ IMPORTANT RULES:
1. If there's conversation context (previous messages about ACE logs/errors), treat follow-up questions like "what can I do?", "how to fix?", "solve those" as referring to the previously discussed errors.
2. If the user asks about anything **completely unrelated to ACE log analysis** (like "capital of India", "write an email", "explain sorting algorithms"), respond exactly as: "I don't know"
3. Always assume pronouns like "those", "these", "it" refer to errors/issues in the current analysis context.
"""

    tools_dict = {our_tool.name: our_tool for our_tool in tools}

    def call_llm(state: agentState) -> agentState:
        messages = list(state["messages"])
        messages = [SystemMessage(content=system_prompt)] + messages
        messages = model_with_tools.invoke(messages)
        return {"messages": messages}

    def take_action(state: agentState) -> agentState:
        tool_calls = state["messages"][-1].tool_calls
        results = []
        for t in tool_calls:
            if t["name"] not in tools_dict:
                result = "Incorrect Tool Name"
            else:
                result = tools_dict[t["name"]].invoke(t["args"].get("query", ""))
            results.append(
                ToolMessage(tool_call_id=t["id"], name=t["name"], content=str(result))
            )
        return {"messages": results}

    def should_continue(state: agentState) -> bool:
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

    return graph.compile()


# Main UI
st.markdown(
    '<div class="main-header">🔍 ACE Log Analyzer</div>', unsafe_allow_html=True
)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")

    if st.button("🔄 Initialize Agent", type="primary", use_container_width=True):
        with st.spinner("Loading agent..."):
            st.session_state.rag_agent = initialize_agent()
            if st.session_state.rag_agent:
                st.session_state.vectorstore_loaded = True
                st.success("Agent initialized successfully!")

    st.divider()

    st.header("📊 System Status")
    if st.session_state.vectorstore_loaded:
        st.success("✅ Vectorstore Loaded")
        st.success("✅ Agent Ready")
    else:
        st.warning("⚠️ Agent Not Initialized")

    st.divider()

    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💬 Ask Questions About ACE Logs")

    # Example queries
    with st.expander("📋 Example Queries"):
        st.markdown("""
        - What critical errors are in the logs?
        - Analyze errors in ReturnsFlow
        - Show me database connection issues
        - What's causing the CacheStore errors?
        - Explain the ArrayIndexOutOfBoundsException
        """)

with col2:
    st.subheader("ℹ️ About")
    st.info("""
    This tool analyzes IBM App Connect Enterprise (ACE) logs to identify:
    - Critical errors (severity E)
    - Warnings (severity W)
    - Root causes
    - Remediation steps
    """)

# Chat interface
st.divider()

# Display chat history
for i, (query, response) in enumerate(st.session_state.chat_history):
    with st.container():
        st.markdown(f"**🧑 You:** {query}")
        st.markdown(f"**🤖 Assistant:**")
        st.markdown(response)
        st.divider()

# Input form
with st.form(key="query_form", clear_on_submit=True):
    user_query = st.text_input(
        "Enter your question:",
        placeholder="e.g., What are the critical errors in the logs?",
        label_visibility="collapsed",
    )
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        submit_button = st.form_submit_button(
            "🔍 Analyze", type="primary", use_container_width=True
        )
    with col2:
        clear_button = st.form_submit_button("🧹 Clear", use_container_width=True)

if clear_button:
    st.session_state.chat_history = []
    st.rerun()

if submit_button and user_query:
    if not st.session_state.rag_agent:
        st.error("⚠️ Please initialize the agent first using the sidebar button!")
    else:
        with st.spinner("🔄 Analyzing logs..."):
            try:
                messages = [HumanMessage(content=user_query)]
                result = st.session_state.rag_agent.invoke({"messages": messages})

                content = result["messages"][-1].content
                if (
                    isinstance(content, list)
                    and len(content) > 0
                    and "text" in content[0]
                ):
                    response_text = content[0]["text"]
                else:
                    response_text = content

                # Add to chat history
                st.session_state.chat_history.append((user_query, response_text))
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Footer
st.divider()
st.caption("🔧 ACE Log Analyzer | Powered by LangChain, LangGraph & Google Gemini")
