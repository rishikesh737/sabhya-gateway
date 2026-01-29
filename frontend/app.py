import streamlit as st
import requests
import json
import time

# ---- Configuration & Sidebar ----
st.set_page_config(page_title="LLM Governance Interface", page_icon="🛡️")

st.sidebar.header("🔌 Connection Settings")
api_url = st.sidebar.text_input(
    "API URL",
    value="http://localhost:8000/v1/chat/completions",
    help="Point this to localhost for local dev, or your OpenShift Route for cloud.",
)
api_key = st.sidebar.text_input("API Key", value="dev-key-1", type="password")
model_name = st.sidebar.text_input("Model Name", value="mistral:7b-instruct-q4_K_M")

st.sidebar.divider()
st.sidebar.markdown("**Governance Audit**")
st.sidebar.info(
    "This interface logs raw latency and JSON payloads for safety evaluation."
)

# ---- Session State ----
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- UI Layout ----
st.title("🛡️ Secure LLM Gateway Client")
st.caption(f"Connected to: `{api_url}`")

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # If there is debug info attached to this message, show it
        if "debug" in msg:
            with st.expander("🔍 Governance Data (Latency & Raw JSON)"):
                st.json(msg["debug"])

# Chat Input
if prompt := st.chat_input("Enter your prompt..."):
    # 1. Add User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Call API
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Thinking...*")

        start_time = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
            }

            response = requests.post(
                api_url, json=payload, headers=headers, timeout=120
            )
            latency = round(time.time() - start_time, 3)

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Show Response
                message_placeholder.markdown(content)

                # Show Governance Data
                debug_info = {
                    "latency_seconds": latency,
                    "status": response.status_code,
                    "raw_response": data,
                }
                with st.expander("🔍 Governance Data (Latency & Raw JSON)"):
                    st.json(debug_info)

                # Save to History
                st.session_state.messages.append(
                    {"role": "assistant", "content": content, "debug": debug_info}
                )

            else:
                message_placeholder.error(
                    f"❌ Error {response.status_code}: {response.text}"
                )

        except requests.exceptions.ConnectionError:
            message_placeholder.error("❌ Connection Error: Is the backend running?")
        except requests.exceptions.Timeout:
            message_placeholder.error("❌ Timeout: The model took too long to reply.")
        except Exception as e:
            message_placeholder.error(f"❌ Unexpected Error: {e}")
