Splunk AI Assistant

Enterprise AI Agent for Natural-Language Splunk Querying

1. Executive Summary

This project implements an AI-assisted interface for Splunk that allows users to query operational data using natural language.
The solution integrates Google Gemini for reasoning and Splunk MCP (Model Context Protocol) for controlled, auditable execution of Splunk queries.

The design follows enterprise best practices:

Clear separation of concerns

No direct LLM access to production systems

Explicit tool invocation and execution boundaries

Async, non-blocking runtime model

Secure configuration via environment variables

2. Problem Statement

Traditional Splunk usage requires:

Knowledge of SPL (Search Processing Language)

Familiarity with indexes, hosts, and sourcetypes

Manual dashboard or search creation

This creates friction for:

New engineers

Support teams

On-call responders

Non-Splunk experts

Goal:
Enable users to retrieve accurate Splunk data using natural language without compromising security or reliability.

3. Solution Overview

This application acts as an AI agent, not a direct API wrapper.

Key Design Principle

The LLM reasons. The system executes.

Gemini:

Interprets user intent

Decides whether Splunk data is required

Selects the appropriate tool and arguments

MCP:

Executes Splunk operations

Enforces protocol and tool boundaries

Prevents hallucinated data access

Splunk:

Remains the single source of truth

4. High-Level Architecture
┌─────────────┐
│   User CLI  │
└─────┬───────┘
      │
      ▼
┌───────────────────┐
│ Gemini LLM        │
│ (Reasoning Layer) │
└─────┬─────────────┘
      │ Tool Request (JSON)
      ▼
┌───────────────────┐
│ MCP Client        │
│ (Python Runtime)  │
└─────┬─────────────┘
      │ stdio IPC
      ▼
┌───────────────────┐
│ Splunk MCP Server │
│ (Subprocess)      │
└─────┬─────────────┘
      │ REST (8089)
      ▼
┌───────────────────┐
│ Splunk Enterprise │
└───────────────────┘
