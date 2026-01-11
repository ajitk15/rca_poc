import os
import sys
import subprocess
from pathlib import Path

# Setup paths
script_dir = Path(__file__).resolve().parent # This file is in splunk_mcp/
server_script = script_dir.parent / "server" / "splunk_mcp.py"

# Setup env
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

print(f"Running server: {server_script}")
print(f"Command: {sys.executable} {server_script} stdio")

try:
    p = subprocess.Popen(
        [sys.executable, str(server_script), "stdio"], 
        env=subprocess_env, 
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a bit to see if it crashes immediately
    try:
        stdout, stderr = p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        print("Server is running (timeout expired as expected)")
        p.kill()
        stdout, stderr = p.communicate()
    
    print("STDOUT:", stdout.decode(errors='replace'))
    print("STDERR:", stderr.decode(errors='replace'))
    print("Return code:", p.returncode)

except Exception as e:
    print(f"Error running subprocess: {e}")
