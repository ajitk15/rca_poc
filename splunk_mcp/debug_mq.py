import sys
import subprocess
from pathlib import Path
import os

# Setup paths
script_dir = Path(__file__).resolve().parent # This file is in splunk_mcp/
mq_script = script_dir.parent / "server" / "splunk_mcp.py"

print(f"Running MQ server: {mq_script}")

try:
    p = subprocess.Popen(
        [sys.executable, str(mq_script), "stdio"], 
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print("Server started. PID:", p.pid)
    
    # Wait a bit to see if it crashes immediately
    try:
        stdout, stderr = p.communicate(timeout=5)
        print("Server finished (unexpectedly)!")
    except subprocess.TimeoutExpired:
        print("Server is still running (good). Killing it now.")
        p.kill()
        stdout, stderr = p.communicate()
    
    print("STDOUT:", stdout)
    print("STDERR:", stderr)
    print("Return code:", p.returncode)

except Exception as e:
    print(f"Error running subprocess: {e}")
