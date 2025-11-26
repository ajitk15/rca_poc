
import streamlit as st
import datetime

# --- Custom CSS for chat bubbles ---
st.markdown("""
<style>
.chat-bubble-bot {
    background-color: #e6f0ff;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 5px;
    width: fit-content;
}
.chat-bubble-user {
    background-color: #d4f7d4;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 5px;
    width: fit-content;
    margin-left: auto;
}
</style>
""", unsafe_allow_html=True)

# --- Initialize session state ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'responses' not in st.session_state:
    st.session_state.responses = {}
if 'history' not in st.session_state:
    st.session_state.history = []

# --- Questions ---
questions = [
    ("Issue (One-line summary):", "issue", "Messages stuck in DLQ for CHANNEL.ORDER.INPUT"),
    ("Incident Time (select date):", "incident_time", datetime.date.today()),
    ("Severity (Low / Medium / High):", "severity", ["Low", "Medium", "High"]),
    ("Environment (Dev / QA / Stage / Prod):", "environment", ["Dev", "QA", "Stage", "Prod"]),
    ("Exact question asked by the engineer:", "user_question", "Why are messages getting into DLQ in MQ queue ORDER.INPUT?"),
    ("Paste log snippets:", "log_snippets", "AMQ9637: Channel is not available due to SSL error\nAMQ9544: Channel ended abnormally\nMQRC_NOT_AUTHORIZED (2035)"),
    ("AI Interpretation of logs:", "ai_analysis", "The queue manager is rejecting inbound connections because the SSL certificate on the client channel expired, causing handshake failures."),
    ("Primary Cause Identified:", "root_cause", "SSL certificate expired on client-connecting channel CHL.ORDER.INPUT"),
    ("Evidence:", "evidence", "AMQ9637: SSL handshake error – certificate expired\nFDC: SSLCertExpiredProbe\nAMQ9544: Channel terminated abnormally\nDLQ message reason: MQRC_SSL_ERROR (2393)"),
    ("Impact:", "impact", "Messages stuck in DLQ\nChannel connection failures\nDownstream ACE / DataPower flows impacted\nDuration of disruption\nNumber of messages affected"),
    ("Recommended Fix:", "recommended_fix", "Renew and install updated SSL certificate for channel.\nRefresh security:\nRestart affected channel(s):\nReprocess DLQ messages using runmqdlq or custom script."),
    ("Preventive Measures:", "preventive_measures", "Set certificate expiry alerts.\nEnable MQ monitoring for channel status.\nAdd retry/backoff logic in upstream apps.\nPerform periodic SSL & CHL health checks."),
    ("Confidence Score (Low / Medium / High):", "confidence_score", ["Low", "Medium", "High"]),
    ("Feedback (✔️ Correct / ❌ Incorrect / 🔄 Partially Correct):", "feedback", ["✔️ Correct", "❌ Incorrect", "🔄 Partially Correct"]),
    ("Comments:", "comments", "")
]

# --- Display conversation history ---
st.title("IBM MQ – RCA Chatbot")
for msg in st.session_state.history:
    if msg['sender'] == 'bot':
        st.markdown(f"<div class='chat-bubble-bot'>🤖 {msg['text']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-user'>👤 {msg['text']}</div>", unsafe_allow_html=True)

# --- Current question ---
if st.session_state.step <= len(questions):
    question, key, placeholder = questions[st.session_state.step - 1]

    # Show bot question
    st.markdown(f"<div class='chat-bubble-bot'>🤖 {question}</div>", unsafe_allow_html=True)

    # Input field for answer
    if isinstance(placeholder, list):
        answer = st.selectbox("Your answer:", placeholder)
    elif isinstance(placeholder, datetime.date):
        answer = st.date_input("Your answer:", placeholder)
    else:
        answer = st.text_input("Your answer:", placeholder)

    # Send button
    if st.button("Send"):
        st.session_state.responses[key] = answer
        st.session_state.history.append({'sender': 'bot', 'text': question})
        st.session_state.history.append({'sender': 'user', 'text': str(answer)})
        st.session_state.step += 1
        st.rerun()
else:
    st.success("✅ All questions answered! Click below to generate RCA report.")
    if st.button("Generate RCA Report"):
        r = st.session_state.responses
        rca_report = f"""IBM MQ – Root Cause Analysis (RCA) Report

1. Summary
Issue: {r['issue']}
Incident Time: {r['incident_time']}
Severity: {r['severity']}
Environment: {r['environment']}

2. User Question
{r['user_question']}

3. Relevant MQ Logs
{r['log_snippets']}

4. MQ Analysis (AI Interpretation)
{r['ai_analysis']}

5. Root Cause
{r['root_cause']}

6. Evidence
{r['evidence']}

7. Impact
{r['impact']}

8. Recommended Fix
{r['recommended_fix']}

9. Preventive Measures
{r['preventive_measures']}

10. Confidence Score
{r['confidence_score']}

11. Engineer Feedback
Feedback: {r['feedback']}
Comments: {r['comments']}
"""
        st.download_button("Download RCA Report", rca_report, file_name="IBM_MQ_RCA_Report.txt")
