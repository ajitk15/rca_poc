import os
import asyncio
import sys
import json
import traceback
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import google.generativeai as genai
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None
from splunk_config import get_system_prompt


script_dir = Path(__file__).resolve().parent
env_file = script_dir / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
else:
    print("[X] .env file not found!")

# Verify what was loaded
print("\n[+] Loaded values:")
print(f"   SPLUNK_HOST: {os.getenv('SPLUNK_HOST', 'NOT SET')}")
print(f"   SPLUNK_PORT: {os.getenv('SPLUNK_PORT', 'NOT SET')}")
print(f"   SPLUNK_USERNAME: {os.getenv('SPLUNK_USERNAME', 'NOT SET')}")
print(f"   GOOGLE_API_KEY: {'SET' if os.getenv('GOOGLE_API_KEY') else 'NOT SET'}\n")
print(f"   OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}\n")
print(f"   LLM_CONNECTION: {os.getenv('LLM_CONNECTION', 'gemini')}")

class SplunkChatbot:
    def __init__(self):
        self.llm_type = os.getenv("LLM_CONNECTION", "gemini").lower()
        self.chat = None
        self.openai_client = None
        self.messages = []  # History for OpenAI
        self.sessions = {}
        self.tool_map = {}

        if self.llm_type == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            if not AsyncOpenAI:
                 raise ImportError("openai package not installed. Run 'pip install openai'")
            self.openai_client = AsyncOpenAI(api_key=api_key)
            print("[I] Using OpenAI LLM")
        else:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            print("[I] Using Gemini LLM")

    # Initial Setup
    async def setup_bot(self, sessions):
        """Setup Chatbot with multiple MCP sessions"""
        self.sessions = sessions
        self.tool_map = {}
        
        all_tools = []
        
        # Initialize all sessions and gather tools
        for session_name, session in self.sessions.items():
            print(f"[I] Initializing {session_name} session...")
            await session.initialize()
            
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                self.tool_map[tool.name] = session_name
                all_tools.append(tool)
                
        print(f"Tools: {[t.name for t in all_tools]}\n")

        # Start chat with system prompt from config
        system_msg = get_system_prompt(all_tools)

        if self.llm_type == "openai":
             print("[I] System prompt generated. Initializing OpenAI history...")
             self.messages = [{"role": "system", "content": system_msg}]
        else:
            print("[I] System prompt generated. Starting Gemini chat...")
            # Initialize Gemini chat
            loop = asyncio.get_event_loop()
            self.chat = self.model.start_chat(history=[])
            await loop.run_in_executor(None, self.chat.send_message, system_msg)

    # Tools Setup
    async def call_tool(self, tool_name, args):
        print(f"\n{'='*60}")
        print(f"[Executing Tool: {tool_name}]")
        print(f"[Arguments:]")
        for key, value in args.items():
            print(f"  - {key}: {value}")
        print(f"{'='*60}\n")
        
        if tool_name not in self.tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        session_name = self.tool_map[tool_name]
        session = self.sessions[session_name]
        
        result = await session.call_tool(tool_name, args)
        return result.content

    # Chat loop
    async def send_message(self, message):
        loop = asyncio.get_event_loop()
        text = ""

        if self.llm_type == "openai":
            self.messages.append({"role": "user", "content": message})
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",  # or gpt-3.5-turbo
                messages=self.messages
            )
            text = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": text})
        else:
            response = await loop.run_in_executor(None, self.chat.send_message, message)
            text = response.text

        # Check if response has tool call (JSON)
        if "{" in text and '"tool"' in text:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                tool_data = json.loads(text[start:end])

                # Execute tool
                result = await self.call_tool(tool_data["tool"], tool_data["args"])

                # Get final answer
                if self.llm_type == "openai":
                    # For OpenAI, append tool result and ask for summary
                    self.messages.append({"role": "user", "content": f"Tool result: {result}\n\nSummarize for user:"})
                    final = await self.openai_client.chat.completions.create(
                         model="gpt-4o",
                         messages=self.messages
                    )
                    final_text = final.choices[0].message.content
                    self.messages.append({"role": "assistant", "content": final_text})
                    return final_text
                else:
                    final = await loop.run_in_executor(
                        None,
                        self.chat.send_message,
                        f"Tool result: {result}\n\nSummarize for user:",
                    )
                    return final.text
            except Exception as e:
                print(f"Tool execution error: {e}")
                pass
        return text

    # Main Chat Loop
    async def run_chat_loop(self):
        print("Type 'exit' to quit\n")

        loop = asyncio.get_event_loop()

        while True:
            try:
                user_input = await loop.run_in_executor(
                    None, lambda: input("You: ").strip()
                )

                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                response = await self.send_message(user_input)
                print(f"\nBot: {response}\n")

            except Exception as e:
                print(f"Error: {e}")


async def main():
    print("=" * 50)
    print("Splunk Chatbot")
    print("=" * 50)

    # Verify environment variables are loaded
    splunk_host = os.getenv("SPLUNK_HOST") or ""
    splunk_port = os.getenv("SPLUNK_PORT") or ""
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


    # Start MCP server (Splunk)
    server_script = script_dir.parent / "server" / "splunk_mcp.py"
    if not server_script.exists():
        print(f"[X] Server script not found at: {server_script}")
        return

    splunk_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script), "stdio"],
        env=subprocess_env,
    )
    
    # Start MCP server (IBM MQ)
    mq_script = script_dir.parent / "server" / "mqmcpserver.py"
    if not mq_script.exists():
        print(f"[X] MQ Server script not found at: {mq_script}")
        return
        
    mq_params = StdioServerParameters(
        command=sys.executable,
        args=[str(mq_script)],
        env=subprocess_env,
    )

    try:
        # Connect to both servers
        async with stdio_client(splunk_params) as (splunk_r, splunk_w), \
                   stdio_client(mq_params) as (mq_r, mq_w):
            
            async with ClientSession(splunk_r, splunk_w) as splunk_session, \
                       ClientSession(mq_r, mq_w) as mq_session:
                
                bot = SplunkChatbot()
                await bot.setup_bot({
                    "splunk": splunk_session,
                    "mq": mq_session
                })
                await bot.run_chat_loop()

    except Exception as e:
        print(f"[X] Connection failed: {e}")
        print(f"\nError details: {type(e).__name__}: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nCheck:")
        print("1. Splunk MCP server installed at splunk_mcp.py")
        print("2. Splunk running and accessible at https://localhost:8089")
        print("3. .env file exists with correct credentials in the script directory")
        print("4. Python dependencies installed (mcp, splunk-sdk)")


if __name__ == "__main__":
    asyncio.run(main())
