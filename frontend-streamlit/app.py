import streamlit as st
import requests
import json
import os
import pandas as pd
from datetime import datetime

# ---- Page Config ----
st.set_page_config(page_title="Secure LLM Gateway", page_icon="🛡️", layout="wide")

st.title("🛡️ Secure LLM Gateway")

# ==========================================
# 🧠 SIDEBAR: NAVIGATION & SETTINGS
# ==========================================
with st.sidebar:
    st.header("📍 Navigation")
    page = st.radio("Go to:", ["Chat Interface", "Governance Audit Logs"])

    st.divider()

    st.header("⚙️ Connection Settings")
    # Defaults
    default_url = os.getenv("API_URL", "http://127.0.0.1:8000")
    default_key = os.getenv("API_KEY", "dev-key-1")

    api_url = st.text_input(
        "API Base URL",
        value=default_url,
        help="Root URL of the API (No trailing slash)",
    )
    api_key = st.text_input("API Key", value=default_key, type="password")
    model_name = st.text_input(
        "Model Name",
        value="mistral:7b-instruct-q4_K_M",
        help="Use 'tinyllama' for Cloud Sandbox",
    )

# ---- Global Headers ----
HEADERS = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# ==========================================
# PAGE 1: CHAT INTERFACE
# ==========================================
if page == "Chat Interface":
    st.subheader("💬 Enterprise Chat")

    # Connection Status Check
    try:
        health = requests.get(f"{api_url}/health/live", timeout=2)
        if health.status_code == 200:
            st.success(f"Connected to: `{api_url}`")
        else:
            st.error(f"Backend Unhealthy: {health.status_code}")
    except Exception:
        st.error(f"❌ Connection Error: Cannot reach `{api_url}`")
        st.stop()

    # Session State
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Enter your prompt (e.g., 'What is zero trust?')"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"Thinking ({model_name})..."):
                try:
                    payload = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                    response = requests.post(
                        f"{api_url}/v1/chat/completions", json=payload, headers=HEADERS
                    )

                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        st.markdown(content)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": content}
                        )

                        with st.expander("🔍 Governance Data (Trace & Latency)"):
                            # Display usage if available
                            usage = data.get("usage", {})
                            st.json(
                                {
                                    "trace_id": data.get("id"),
                                    "latency_ms": "Saved to DB",
                                    "model": data.get("model"),
                                    "usage": usage,
                                    "raw_response": data,
                                }
                            )
                    else:
                        st.error(f"❌ Error {response.status_code}: {response.text}")

                except Exception as e:
                    st.error(f"Connection Failed: {str(e)}")

# ==========================================
# PAGE 2: AUDIT LOGS
# ==========================================
elif page == "Governance Audit Logs":
    st.subheader("📋 Immutable Audit Trail")
    st.info(f"Fetching logs from: `{api_url}`")

    if st.button("Refresh Logs"):
        st.rerun()

    try:
        response = requests.get(f"{api_url}/v1/audit/logs?limit=50", headers=HEADERS)

        if response.status_code == 200:
            data = response.json()

            if len(data) > 0:
                df = pd.DataFrame(data)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

                # Check for token columns (graceful fallback if old data exists)
                if "total_tokens" not in df.columns:
                    df["total_tokens"] = 0
                    df["prompt_tokens"] = 0
                    df["completion_tokens"] = 0

                # Reorder columns to show Token Usage
                df = df[
                    [
                        "timestamp",
                        "model",
                        "status_code",
                        "latency_ms",
                        "total_tokens",  # <--- New
                        "prompt_tokens",  # <--- New
                        "completion_tokens",  # <--- New
                        "user_hash",
                        "request_id",
                    ]
                ]

                def highlight_status(val):
                    color = "green" if val == 200 else "red"
                    return f"color: {color}"

                st.dataframe(
                    df.style.map(highlight_status, subset=["status_code"]),
                    use_container_width=True,
                )

                # Metrics
                if not df.empty:
                    # 1. Reliability
                    error_count = len(df[df["status_code"] != 200])
                    error_rate = (error_count / len(df)) * 100

                    # 2. Performance
                    avg_latency = df[df["status_code"] == 200]["latency_ms"].mean()

                    # 3. Volume (Cost Driver)
                    total_vol = df["total_tokens"].sum()

                    # 4. Estimated Cost ($0.20 per 1M tokens - example rate)
                    est_cost = (total_vol / 1_000_000) * 0.20

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Requests", len(df))
                    col2.metric("Avg Latency", f"{avg_latency:.0f} ms")
                    col3.metric("Total Tokens", f"{total_vol:,}")
                    col4.metric("Est. Cost", f"${est_cost:.6f}")

            else:
                st.warning("No logs found.")
        else:
            st.error(f"Failed to fetch logs: {response.text}")

    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
