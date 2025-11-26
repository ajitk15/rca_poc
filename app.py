import streamlit as st
from datetime import datetime

st.set_page_config(page_title="IBM MQ RCA Form", layout="centered")

st.title("IBM MQ — RCA Form")

# 1. Summary
st.header("1. Summary")
issue = st.text_input("Issue (one-line)")
incident_time = st.text_input("Incident Time (YYYY-MM-DD HH:MM)", datetime.now().strftime("%Y-%m-%d %H:%M"))
severity = st.selectbox("Severity", ["Low", "Medium", "High"])
environment = st.selectbox("Environment", ["Dev", "QA", "Stage", "Prod"])

# 2. User Question
st.header("2. User Question")
user_question = st.text_area("Exact question asked by the engineer")

# 3. Relevant MQ Logs Retrieved
st.header("3. Relevant MQ Logs Retrieved")
log_files = st.text_area("List of logs/files retrieved (one per line)", value="AMQERR01\n*.FDC\nchannel.log\napp.log")
log_snippets = st.text_area("Important log snippets", value="AMQ9637: Channel is not available due to SSL error.\nAMQ9544: Channel ended abnormally.\nMQRC_NOT_AUTHORIZED (2035)")

# 4. MQ Analysis
st.header("4. MQ Analysis (Interpretation)")
analysis = st.text_area("Analysis / sequence of events")

# 5. Root Cause
st.header("5. Root Cause")
root_cause = st.text_input("Primary Cause Identified")

# 6. Evidence
st.header("6. Evidence (Direct MQ Log References)")
evidence = st.text_area("List direct log references / FDCs")

# 7. Impact
st.header("7. Impact")
impact_summary = st.text_area("Impact summary (duration, messages affected, downstream impact)")

# 8. Recommended Fix
st.header("8. Recommended Fix")
recommended_fix = st.text_area("Recommended immediate remediation steps (ordered with owners)")

# 9. Preventive Measures
st.header("9. Preventive Measures")
preventive = st.text_area("Preventive measures / monitoring / runbook items")

# 10. Confidence Score
st.header("10. Confidence Score")
confidence = st.selectbox("Confidence", ["Low", "Medium", "High"])
confidence_note = st.text_input("Short justification for confidence")

# 11. Engineer Feedback
st.header("11. Engineer Feedback")
engineer_feedback = st.text_area("Engineer feedback placeholder")

# Generate markdown
def build_markdown():
    md = []
    md.append("# IBM MQ — Root Cause Analysis (RCA)")
    md.append("\n## 1. Summary")
    md.append(f"- **Issue:** {issue or '-'}")
    md.append(f"- **Incident Time:** {incident_time or '-'}")
    md.append(f"- **Severity:** {severity}")
    md.append(f"- **Environment:** {environment}")
    md.append("\n## 2. User Question")
    md.append(user_question or "-")
    md.append("\n## 3. Relevant MQ Logs Retrieved")
    md.append(f"```\n{log_files}\n```")
    md.append("\n**Important snippets:**")
    md.append(f"```\n{log_snippets}\n```")
    md.append("\n## 4. MQ Analysis (Interpretation)")
    md.append(analysis or "-")
    md.append("\n## 5. Root Cause")
    md.append(root_cause or "-")
    md.append("\n## 6. Evidence (Direct MQ Log References)")
    md.append(evidence or "-")
    md.append("\n## 7. Impact")
    md.append(impact_summary or "-")
    md.append("\n## 8. Recommended Fix (Immediate)")
    md.append(recommended_fix or "-")
    md.append("\n## 9. Preventive Measures")
    md.append(preventive or "-")
    md.append("\n## 10. Confidence Score")
    md.append(f"- **{confidence}** — {confidence_note or '-'}")
    md.append("\n## 11. Engineer Feedback")
    md.append(engineer_feedback or "-")
    return "\n\n".join(md)

md_output = build_markdown()

st.download_button("Download RCA as Markdown", md_output, file_name="RCA.md", mime="text/markdown")

st.markdown("---")
st.subheader("Preview (Markdown)")
st.markdown(md_output)
