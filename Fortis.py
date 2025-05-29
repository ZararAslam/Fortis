import streamlit as st
import openai
import os
from datetime import datetime
import pandas as pd
from docx import Document
import io

# Set your assistant ID here
ASSISTANT_ID = "asst_vr6ZFdxJVO4kd4oukqMUTk9m"

# Load API key securely from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Financial Report Generator", layout="centered")
st.title("📊 Financial Report Generator")

st.markdown("Upload your client data as a `.txt`, `.csv`, or `.docx` file. The assistant will generate a detailed financial advice report based on the contents.")

uploaded_file = st.file_uploader("Upload a file", type=["txt", "csv", "docx"])

def extract_text(file):
    file_type = file.name.split(".")[-1].lower()

    if file_type == "txt":
        return file.read().decode("utf-8")

    elif file_type == "csv":
        df = pd.read_csv(file)
        return df.to_string(index=False)

    elif file_type == "docx":
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])

    else:
        return None

if uploaded_file:
    with st.spinner("Reading file and preparing report..."):
        client_input = extract_text(uploaded_file)

        if not client_input:
            st.error("Unsupported file format or failed to extract text.")
            st.stop()

        # Inject today's date into the message
        today_date = datetime.now().strftime("%d %B %Y")
        system_injected_text = f"Today's date is {today_date}.\n\n{client_input}"

        # Create a new thread for this session
        thread = openai.beta.threads.create()

        # Send message to assistant
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=system_injected_text
        )

        # Run the assistant
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Wait for run to complete
        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status == "completed":
                break
            elif run_status.status == "failed":
                st.error("The assistant failed to generate a report. Please try again.")
                st.stop()

        # Retrieve messages
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        report_text = messages.data[0].content[0].text.value

        # Display and allow download
        st.subheader("📄 Generated Report")
        st.text_area("Report Output", value=report_text, height=500)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create a Word document in memory
        doc = Document()
        for line in report_text.split("\n"):
            doc.add_paragraph(line)

        word_file = io.BytesIO()
        doc.save(word_file)
        word_file.seek(0)

        filename = f"financial_report_{timestamp}.docx"

        st.download_button(
            label="📥 Download Report (.docx)",
            data=word_file,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

