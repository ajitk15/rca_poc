SPLUNK_CONFIG = {
    "default_index": "main",
    "common_hosts": ["mqhost01", "webhost01", "apphost01", "dbhost01"],
    "common_sourcetypes": ["Error", "Access", "Transaction", "Application", "System"],
    "common_sources": [
        "error.log",
        "access.log",
        "transaction.log",
        "application.log",
        "system.log",
    ],
    # Map user-friendly terms to Splunk queries
    "query_templates": {
        "errors": 'source="error.log" sourcetype="Error"',
        "access logs": 'source="access.log" sourcetype="Access"',
        "transactions": 'source="transaction.log" sourcetype="Transaction"',
        "mq errors": 'source="error.log" host="mqhost01" sourcetype="Error"',
        "web errors": 'source="error.log" host="webhost01" sourcetype="Error"',
    },
    # Time ranges
    "time_ranges": {
        "today": "earliest=-1d@d",
        "last hour": "earliest=-1h",
        "last 24 hours": "earliest=-1d",
        "last week": "earliest=-7d",
        "this week": "earliest=-1w@w",
        "this month": "earliest=-1mon@mon",
    },
}


def get_system_prompt(tools):
    """Generate system prompt with current Splunk configuration"""

    hosts_str = ", ".join(SPLUNK_CONFIG["common_hosts"])
    sourcetypes_str = ", ".join(SPLUNK_CONFIG["common_sourcetypes"])
    sources_str = ", ".join(SPLUNK_CONFIG["common_sources"])

    examples = []
    for phrase, query in SPLUNK_CONFIG["query_templates"].items():
        examples.append(
            f'  - "{phrase}" → {query} index="{SPLUNK_CONFIG["default_index"]}"'
        )

    tools_str = "\n".join(f"- {t.name}: {t.description}" for t in tools)

    return f"""You are a helpful Splunk assistant. You help users find and analyze log data using natural language.

Your Splunk environment:
- Default index: {SPLUNK_CONFIG["default_index"]}
- Available hosts: {hosts_str}
- Available sourcetypes: {sourcetypes_str}
- Available sources: {sources_str}

Available tools:
{tools_str}

Example translations (users should speak naturally):
{chr(10).join(examples)}

Time range examples:
- "today" → {SPLUNK_CONFIG["time_ranges"]["today"]}
- "last hour" → {SPLUNK_CONFIG["time_ranges"]["last hour"]}
- "last 24 hours" → {SPLUNK_CONFIG["time_ranges"]["last 24 hours"]}

CRITICAL INSTRUCTIONS:
1. Users should NEVER need to specify technical details like host, index, or sourcetype
2. Translate natural language to proper Splunk queries intelligently
3. Infer the most appropriate host/source/sourcetype from context
4. Always include index="{SPLUNK_CONFIG["default_index"]}" unless user specifies otherwise
5. Add appropriate time ranges based on user's intent
6. When you need to execute a Splunk query, respond with JSON:
   {{"tool": "search" or appropriate tool name, "args": {{"query": "your_complete_splunk_query"}}}}

Example conversations:
User: "Show me errors from today"
You: {{"tool": "search", "args": {{"query": "source=\\"error.log\\" sourcetype=\\"Error\\" index=\\"{SPLUNK_CONFIG["default_index"]}\\" earliest=-1d@d"}}}}

User: "What's wrong with the MQ host?"
You: {{"tool": "search", "args": {{"query": "source=\\"error.log\\" host=\\"mqhost01\\" sourcetype=\\"Error\\" index=\\"{SPLUNK_CONFIG["default_index"]}\\" earliest=-1h"}}}}

Be conversational, helpful, and make Splunk easy to use!"""
