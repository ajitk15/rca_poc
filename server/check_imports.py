import json
import logging
import os
import ssl
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

print("Importing splunklib...")
import splunklib.client
print("Importing decouple...")
from decouple import config
print("Importing mcp.server.fastmcp...")
from mcp.server.fastmcp import FastMCP
print("Importing splunklib (results)...")
from splunklib import results
import sys
import socket
print("Importing fastapi...")
from fastapi import FastAPI, APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
print("Importing mcp.server.sse...")
from mcp.server.sse import SseServerTransport
from starlette.routing import Mount
import uvicorn

print("All imports successful")
