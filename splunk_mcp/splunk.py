import os
import asyncio
import json
import traceback
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import google.generativeai as genai
from splunk_config import get_system_prompt


script_dir = Path(__file__).resolve().parent
env_file = script_dir / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
else:
    print("❌ .env file not found!")

# Verify what was loaded
print("\n📋 Loaded values:")
print(f"   SPLUNK_HOST: {os.getenv('SPLUNK_HOST', 'NOT SET')}")
print(f"   SPLUNK_PORT: {os.getenv('SPLUNK_PORT', 'NOT SET')}")
print(f"   SPLUNK_USERNAME: {os.getenv('SPLUNK_USERNAME', 'NOT SET')}")
print(f"   GOOGLE_API_KEY: {'SET' if os.getenv('GOOGLE_API_KEY') else 'NOT SET'}\n")


class SplunkChatbot:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.chat = None
        self.mcp_session = None
        self.read_stream = None
        self.write_stream = None

    # Initial Setup
    async def setup_splunk(self, read_stream, write_stream, session):
        """Setup Splunk MCP session"""
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.mcp_session = session

        # Initialize the session
        await self.mcp_session.initialize()

        tools = await self.mcp_session.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}\n")

        # Start chat with system prompt from config
        system_msg = get_system_prompt(tools.tools)

        # Initialize Gemini chat
        loop = asyncio.get_event_loop()
        self.chat = self.model.start_chat(history=[])
        await loop.run_in_executor(None, self.chat.send_message, system_msg)

    # Tools Setup
    async def call_tool(self, tool_name, args):
        print(f"[Calling: {tool_name}]")
        result = await self.mcp_session.call_tool(tool_name, args)
        return result.content

    # Chat loop
    async def send_message(self, message):
        loop = asyncio.get_event_loop()
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
    splunk_host = os.getenv("SPLUNK_HOST")
    splunk_port = os.getenv("SPLUNK_PORT")
    splunk_username = os.getenv("SPLUNK_USERNAME")
    splunk_password = os.getenv("SPLUNK_PASSWORD")

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

    # Start MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["/opt/splunk-mcp/splunk_mcp.py", "stdio"],
        env=subprocess_env,
    )

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                bot = SplunkChatbot()
                await bot.setup_splunk(read_stream, write_stream, session)
                await bot.run_chat_loop()

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print(f"\nError details: {type(e).__name__}: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nCheck:")
        print("1. Splunk MCP server installed at /opt/splunk-mcp/splunk_mcp.py")
        print("2. Splunk running and accessible at https://localhost:8089")
        print("3. .env file exists with correct credentials in the script directory")
        print("4. Python dependencies installed (mcp, splunk-sdk)")


if __name__ == "__main__":
    asyncio.run(main())
