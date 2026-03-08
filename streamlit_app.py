from pathlib import Path
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="RAG PDF Chat", page_icon="📄", layout="centered")

API_URL = "http://localhost:8000"

st.title("📄 Upload a PDF to Ingest")
uploaded = st.file_uploader("Choose a PDF", type=["pdf"], accept_multiple_files=False)

if uploaded is not None:
    with st.spinner("Processing PDF..."):
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        response = requests.post(f"{API_URL}/ingest", files=files)
        
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(f"Error: {response.text}")

st.divider()
st.title("💬 Ask a Question")

with st.form("rag_query_form"):
    question = st.text_input("Your question")
    top_k = st.number_input("How many chunks to retrieve", min_value=1, max_value=20, value=5, step=1)
    submitted = st.form_submit_button("Ask")

    if submitted and question.strip():
        with st.spinner("Generating answer..."):
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

