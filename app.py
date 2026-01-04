import streamlit as st

st.set_page_config(page_title="Change Execution Chatbot", layout="centered")

# -----------------------------
# CSS for chat bubbles
# -----------------------------
st.markdown("""
<style>
.bot {
    background-color: #eef2ff;
    padding: 10px;
    border-radius: 10px;
    margin: 5px 0;
    width: fit-content;
}
.user {
    background-color: #dcfce7;
    padding: 10px;
    border-radius: 10px;
    margin: 5px 0;
    width: fit-content;
    margin-left: auto;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 Change Execution Chatbot")

# -----------------------------
# Session State
# -----------------------------
if "step" not in st.session_state:
    st.session_state.step = 0
if "data" not in st.session_state:
    st.session_state.data = {}
if "history" not in st.session_state:
    st.session_state.history = []

# -----------------------------
# Questions Flow
# -----------------------------
BASE_QUESTIONS = [
    ("Change Number?", "change_number"),
    ("Requestor ID?", "requestor_id"),
    ("Approver ID?", "approver_id"),
    ("What type of change is this? (Script / Stored Procedure / SSIS / Variable ID)", "change_type")
]

SCRIPT_FLOW = [
    ("Script Name?", "script_name"),
    ("Destination Server?", "dest_server"),
    ("Destination Database?", "dest_db")
]

SP_FLOW = [
    ("Source Server?", "source_server"),
    ("Source Database?", "source_db"),
    ("Stored Procedure Name?", "sp_name"),
    ("Destination Server?", "dest_server"),
    ("Destination Database?", "dest_db")
]

SSIS_FLOW = [
    ("Server?", "server"),
    ("Source Database?", "source_db"),
    ("SSIS Package Name?", "ssis_name"),
    ("Destination Server?", "dest_server"),
    ("Destination Database?", "dest_db")
]

VAR_FLOW = [
    ("Environment Variable?", "env_var"),
    ("Destination Server?", "dest_server"),
    ("Destination Database?", "dest_db")
]

# -----------------------------
# Determine active flow
# -----------------------------
def get_active_questions():
    if st.session_state.step < len(BASE_QUESTIONS):
        return BASE_QUESTIONS

    change_type = st.session_state.data.get("change_type", "").lower()

    if "script" in change_type:
        return BASE_QUESTIONS + SCRIPT_FLOW
    elif "stored" in change_type:
        return BASE_QUESTIONS + SP_FLOW
    elif "ssis" in change_type:
        return BASE_QUESTIONS + SSIS_FLOW
    elif "variable" in change_type:
        return BASE_QUESTIONS + VAR_FLOW
    else:
        return BASE_QUESTIONS

QUESTIONS = get_active_questions()

# -----------------------------
# Display chat history
# -----------------------------
for msg in st.session_state.history:
    css = "bot" if msg["sender"] == "bot" else "user"
    st.markdown(f"<div class='{css}'>{msg['text']}</div>", unsafe_allow_html=True)

# -----------------------------
# Ask next question
# -----------------------------
if st.session_state.step < len(QUESTIONS):
    question, key = QUESTIONS[st.session_state.step]

    st.markdown(f"<div class='bot'>{question}</div>", unsafe_allow_html=True)
    user_input = st.text_input("Your answer", key=f"input_{st.session_state.step}")

    if st.button("Send"):
        st.session_state.data[key] = user_input
        st.session_state.history.append({"sender": "bot", "text": question})
        st.session_state.history.append({"sender": "user", "text": user_input})
        st.session_state.step += 1
        st.rerun()

# -----------------------------
# Summary
# -----------------------------
else:
    st.success("✅ All details collected")

    st.subheader("📋 Change Execution Summary")
    for k, v in st.session_state.data.items():
        st.write(f"**{k.replace('_', ' ').title()}:** {v}")
