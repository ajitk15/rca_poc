from typing import TypedDict, Annotated, Sequence
import os
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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


SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")


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

system_prompt = """You are an expert IBM App Connect Enterprise (ACE) log analyzer.

Your task is to analyze the last 5 critical errors and create a professional email report.

Format your response EXACTLY as HTML with this structure:

<html>
<body>
<h2>ACE Critical Errors Report</h2>
<p>Dear Team,</p>
<p>Please find below the analysis of the last 5 critical errors from the ACE logs:</p>

<table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%;">
<thead>
<tr style="background-color: #f2f2f2;">
<th>Error Code & Message</th>
<th>Node Name</th>
<th>Root Cause</th>
<th>Possible Fix</th>
</tr>
</thead>
<tbody>
<tr>
<td>[Error code and brief message]</td>
<td>[ACE node name from logs - e.g., HTTPInput, Compute, DatabaseRetrieve]</td>
<td>[Why this happened]</td>
<td>[Specific remediation steps]</td>
</tr>
<!-- Repeat for each error -->
</tbody>
</table>

<h3>Priority Actions</h3>
<ol>
<li>[Most urgent action]</li>
<li>[Second priority]</li>
<li>[Third priority]</li>
</ol>

<p>Best regards,<br>ACE Log Monitoring System</p>
</body>
</html>

**IMPORTANT**: 
- Output ONLY the HTML, no additional text
- Include exactly 5 errors in the table
- Extract the node name from the log entries (look for node-related fields in the JSON)
- Be concise but specific in each cell
- Focus on actionable information
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


def send_email(recipient_email: str, subject: str, html_content: str):
    """
    Send HTML email with the error report

    Args:
        recipient_email: Email address to send to
        subject: Email subject line
        html_content: HTML content of the email
    """

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise ValueError("Please set SENDER_EMAIL and SENDER_PASSWORD in .env file")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email

    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    try:
        # Connect to SMTP server
        print(f"\nConnecting to {SMTP_SERVER}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()

        # Login
        print("Logging in...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)

        # Send email
        print(f"Sending email to {recipient_email}...")
        server.send_message(msg)
        server.quit()

        print("✅ Email sent successfully!")

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise


def generate_and_send_report(recipient_email: str):
    """
    Generate error report and send via email

    Args:
        recipient_email: Email address to send the report to
    """

    print("\n" + "=" * 50)
    print("🔍 ACE CRITICAL ERRORS EMAIL REPORTER")
    print("=" * 50)

    # Trigger the agent to analyze logs
    messages = [
        HumanMessage(
            content="Analyze and retrieve the last 5 critical errors from ACE logs"
        )
    ]

    print("\n📊 Analyzing logs...")
    result = rag_agent.invoke({"messages": messages})

    # Extract the HTML content
    content = result["messages"][-1].content
    if isinstance(content, list) and len(content) > 0 and "text" in content[0]:
        html_content = content[0]["text"]
    else:
        html_content = content

    print("\n📧 Preparing email...")

    # Send the email
    subject = "ACE Critical Errors Report - Urgent Review Required"
    send_email(recipient_email, subject, html_content)

    print("\n" + "=" * 50)
    print("✅ Report generated and sent successfully!")
    print("=" * 50)


if __name__ == "__main__":
    # Get recipient email from user
    recipient = input("\n📧 Enter recipient email address: ").strip()

    if not recipient:
        print("❌ No email address provided. Exiting...")
    else:
        try:
            generate_and_send_report(recipient)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("\nMake sure you have set up your .env file with:")
            print("SENDER_EMAIL=your-email@gmail.com")
            print("SENDER_PASSWORD=your-app-password")
