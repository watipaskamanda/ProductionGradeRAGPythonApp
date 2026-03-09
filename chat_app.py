import streamlit as st
import requests
from dotenv import load_dotenv
import time
import pandas as pd

load_dotenv()

st.set_page_config(page_title="BIZINEZI AI Assistant", page_icon="🤖", layout="wide")

API_URL = "http://localhost:8000"

# Check API connection
def check_api_connection():
    try:
        response = requests.get(f"{API_URL}/docs", timeout=2)
        return response.status_code == 200
    except:
        return False

# API status indicator
api_status = check_api_connection()
if not api_status:
    st.error("🔴 API Server not running! Please start the FastAPI backend first.")
    st.info("Run `start.bat` or start the API manually: `py -m uvicorn api:app --reload`")
    st.stop()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "mode" not in st.session_state:
    st.session_state.mode = "📄 Document Q&A"

# Sidebar
st.sidebar.title("🤖 BIZINEZI AI Assistant")
mode = st.sidebar.radio(
    "Choose Mode:",
    ["📄 Document Q&A", "📊 Database Analytics", "📤 Upload Documents"]
)

# User level selection for progressive disclosure
if mode == "📊 Database Analytics":
    user_level = st.sidebar.selectbox(
        "👤 User Level:",
        ["Business User", "Data Analyst", "Developer"],
        index=0
    )
    user_level_code = user_level.split()[0].lower()  # "business", "data", "developer"
    
    # Debug mode toggle for advanced users
    debug_mode = False
    if user_level_code in ["data", "developer"]:
        debug_mode = st.sidebar.checkbox("🔧 Debug Mode", value=False)
else:
    user_level_code = "business"
    debug_mode = False

# Currency selection for Database Analytics
if mode == "📊 Database Analytics":
    currency = st.sidebar.selectbox(
        "💰 Currency:",
        ["MWK (Malawi Kwacha)", "USD (US Dollar)"],
        index=0
    )
    currency_code = "MWK" if "MWK" in currency else "USD"
else:
    currency_code = "USD"

# Update mode if changed
if mode != st.session_state.mode:
    st.session_state.mode = mode
    st.session_state.messages = []  # Clear chat when switching modes

# Upload Documents Mode
if mode == "📤 Upload Documents":
    st.title("📤 Upload Documents")
    st.caption("Add new PDFs to the knowledge base")
    
    uploaded = st.file_uploader("Choose a PDF", type=["pdf"], accept_multiple_files=False)

    if uploaded is not None:
        with st.spinner("Processing PDF..."):
            files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
            response = requests.post(f"{API_URL}/ingest", files=files)
            
            if response.status_code == 200:
                st.success(response.json()["message"])
            else:
                st.error(f"Error: {response.text}")

# Chat Modes
else:
    # Title based on mode
    if mode == "📄 Document Q&A":
        st.title("📄 Document Q&A Chat")
        st.caption("Ask questions about your uploaded documents")
        placeholder = "Ask me about your documents..."
        endpoint = "/query"
    else:
        st.title("📊 Database Analytics Chat")
        st.caption("Ask questions about your live transaction data")
        st.info("💡 Try: 'How many transactions?' or 'Show credit transactions'")
        placeholder = "Ask me about your data..."
        endpoint = "/query/database"

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show chart if available
            if message["role"] == "assistant" and "chart_config" in message:
                chart_config = message["chart_config"]
                if chart_config and chart_config.get("data"):
                    st.subheader("📊 Visualization")
                    try:
                        chart_df = pd.DataFrame(list(chart_config["data"].items()), columns=["Category", "Value"])
                        if chart_config.get("type") == "pie_chart":
                            st.write(f"**{chart_config.get('title', 'Chart')}**")
                        st.bar_chart(chart_df.set_index("Category"))
                    except Exception as e:
                        st.error(f"Chart error: {e}")
            
            # Show SQL query only for errors or debug
            if message["role"] == "assistant" and "sql" in message:
                if "error" in message["content"].lower() or "debug" in message.get("question", "").lower():
                    with st.expander("🔍 View SQL Query (Debug)"):
                        st.code(message["sql"], language="sql")

    # Chat input
    if prompt := st.chat_input(placeholder):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # Simulate streaming response
            with st.spinner("Analyzing..."):
                try:
                    if mode == "📄 Document Q&A":
                        payload = {"question": prompt, "top_k": 5}
                        response = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=30)
                        
                        if response.status_code == 200:
                            data = response.json()
                            answer = data["answer"]
                            
                            # Show sources if available
                            if data.get("sources"):
                                answer += "\n\n**Sources:**\n"
                                for source in data["sources"]:
                                    answer += f"- {source}\n"
                            
                            st.markdown(answer)
                            st.session_state.messages.append({"role": "assistant", "content": answer})
                        else:
                            error_msg = f"❌ Error: {response.text}"
                            st.markdown(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
                    else:  # Database Analytics
                        # Prepare chat history for context
                        chat_history = []
                        for msg in st.session_state.messages[-5:]:  # Last 5 messages for context
                            chat_history.append({
                                "role": msg["role"],
                                "content": msg["content"],
                                "question": msg.get("question", ""),
                                "sql": msg.get("sql", "")
                            })
                        
                        payload = {"question": prompt, "chat_history": chat_history, "currency": currency_code}
                        response = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=30)
                        
                        if response.status_code == 200:
                            data = response.json()
                            answer = data["answer"]
                            sql = data.get("sql", "")
                            markdown_table = data.get("markdown_table", "")
                            chart_config = data.get("chart_config", {})
                            
                            # Simulate streaming effect for professional feel
                            if len(answer) > 50:
                                displayed_text = ""
                                for i, char in enumerate(answer):
                                    displayed_text += char
                                    if i % 3 == 0:  # Update every 3 characters for smoother effect
                                        message_placeholder.markdown(displayed_text + "▌")
                                        time.sleep(0.02)
                                message_placeholder.markdown(answer)
                            else:
                                st.markdown(answer)
                            if markdown_table:
                                st.subheader("📊 Data Table")
                                st.markdown(markdown_table)
                            elif "No results found" in answer or "No data" in answer:
                                st.warning("📋 No data found for this query. Try checking the date range or adjusting your filters.")
                            
                            # Show chart if available
                            if chart_config and chart_config.get("data"):
                                st.subheader("📈 Visualization")
                                try:
                                    chart_df = pd.DataFrame(list(chart_config["data"].items()), columns=["Category", "Value"])
                                    chart_type = chart_config.get("type", "bar_chart")
                                    
                                    if chart_type == "pie_chart":
                                        st.write(f"**{chart_config.get('title', 'Chart')}**")
                                        st.bar_chart(chart_df.set_index("Category"))
                                    elif chart_type == "line_chart":
                                        st.line_chart(chart_df.set_index("Category"))
                                    else:
                                        st.bar_chart(chart_df.set_index("Category"))
                                except Exception as e:
                                    st.error(f"Chart error: {e}")
                            elif "chart" in prompt.lower() or "visualize" in prompt.lower():
                                st.warning("No data available for visualization. Try asking: 'Count transactions by type' or 'Sum amounts by bank_id'")
                            
                            # Show SQL query only on errors or when debugging
                            if sql and ("error" in data.get("answer", "").lower() or "debug" in prompt.lower()):
                                with st.expander("🔍 View SQL Query (Debug)"):
                                    st.code(sql, language="sql")
                            
                            # Store message with all data for history
                            message_data = {"role": "assistant", "content": answer}
                            if sql:
                                message_data["sql"] = sql
                            if chart_config:
                                message_data["chart_config"] = chart_config
                            st.session_state.messages.append(message_data)
                        else:
                            error_msg = f"❌ Error: {response.text}"
                            st.markdown(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                except requests.exceptions.ConnectionError:
                    error_msg = "❌ Connection failed! Make sure the FastAPI server is running on port 8000."
                    st.markdown(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.markdown(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

    # Clear chat button
    if st.sidebar.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()