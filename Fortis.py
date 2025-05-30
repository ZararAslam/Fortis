import streamlit as st
import openai
import os
from datetime import datetime
import pandas as pd
from docx import Document
import io
import re

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

        st.subheader("📄 Generated Report")

        # ── Begin Markdown normalization ──
        # (1) Turn any **Heading** lines into Markdown H2 headings
        report_text = re.sub(
            r"^\*\*(.+?)\*\*$",
            r"## \1",
            report_text,
            flags=re.MULTILINE
        )
        # (2) Ensure exactly one blank line after each Markdown heading
        report_text = re.sub(
            r"^(## .+?)\s*\n+",
            r"\1\n\n",
            report_text,
            flags=re.MULTILINE
        )
        # ── End Markdown normalization ──

        # Render the processed text as Markdown (bold headings, proper paragraphs)
        st.markdown(report_text)


        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create a Word document in memory, converting all **bold** spans to real bold text
        doc = Document()
        bold_pattern = re.compile(r"\*\*(.+?)\*\*")

        for line in report_text.splitlines():
            p = doc.add_paragraph()
            last_end = 0

            for m in bold_pattern.finditer(line):
                # add text before the **…**
                if m.start() > last_end:
                    p.add_run(line[last_end:m.start()])
                # add the bold portion
                bold_text = m.group(1)
                run = p.add_run(bold_text)
                run.bold = True
                last_end = m.end()

            # add any remaining text after the last match
            if last_end < len(line):
                p.add_run(line[last_end:])


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

