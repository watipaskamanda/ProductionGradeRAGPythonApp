from pathlib import Path
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="PayMaart AI Assistant", page_icon="🤖", layout="wide")

API_URL = "http://localhost:8000"

# Sidebar for navigation
st.sidebar.title("🤖 PayMaart AI Assistant")
mode = st.sidebar.radio(
    "Choose Mode:",
    ["📄 Document Q&A", "📊 Database Analytics", "📤 Upload Documents"]
)

# Mode 1: Document Q&A
if mode == "📄 Document Q&A":
    st.title("📄 Ask Questions About Documents")
    st.caption("Query uploaded PDFs, policies, and guides")
    
    with st.form("doc_query_form"):
        question = st.text_input("Your question")
        top_k = st.number_input("Chunks to retrieve", min_value=1, max_value=20, value=5, step=1)
        submitted = st.form_submit_button("Ask")

        if submitted and question.strip():
            with st.spinner("Searching documents..."):
                payload = {"question": question.strip(), "top_k": int(top_k)}
                response = requests.post(f"{API_URL}/query", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    st.subheader("Answer")
                    st.write(data["answer"])
                    
                    if data["sources"]:
                        st.caption("Sources")
                        for s in data["sources"]:
                            st.write(f"- {s}")
                else:
                    st.error(f"Error: {response.text}")

# Mode 2: Database Analytics
elif mode == "📊 Database Analytics":
    st.title("📊 Ask Questions About Live Data")
    st.caption("Query real-time database statistics")
    
    # Example questions
    st.info("💡 Try asking: 'How many transactions are there?' or 'What's the total transaction amount?'")
    
    with st.form("db_query_form"):
        question = st.text_input("Your question")
        submitted = st.form_submit_button("Ask")

        if submitted and question.strip():
            with st.spinner("Querying database..."):
                payload = {"question": question.strip()}
                response = requests.post(f"{API_URL}/query/database", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    st.subheader("Answer")
                    st.write(data["answer"])
                    
                    with st.expander("🔍 View SQL Query"):
                        st.code(data["sql"], language="sql")
                else:
                    st.error(f"Error: {response.text}")

# Mode 3: Upload Documents
elif mode == "📤 Upload Documents":
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

