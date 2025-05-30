import streamlit as st
import openai
import os
from datetime import datetime
import pandas as pd
import docx
from docx import Document
import io
import re

# New imports for footer styling
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Set your assistant ID here
ASSISTANT_ID = "asst_vr6ZFdxJVO4kd4oukqMUTk9m"

# Load API key securely from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Financial Report Generator", layout="centered")
st.title("📊 Financial Report Generator")
st.markdown(
    "Upload your client data as a `.txt`, `.csv`, or `.docx` file. "
    "The assistant will generate a detailed financial advice report based on the contents."
)

uploaded_file = st.file_uploader("Upload a file", type=["txt", "csv", "docx"])

def extract_text(file):
    file_type = file.name.split(".")[-1].lower()

    if file_type == "txt":
        text = file.read().decode("utf-8")
        return text, None

    elif file_type == "csv":
        df = pd.read_csv(file)
        text = df.to_string(index=False)
        return text, df

    elif file_type == "docx":
        document = docx.Document(file)
        text = "\n".join(p.text for p in document.paragraphs)
        return text, None

    else:
        return None, None

if uploaded_file:
    # reset when a new file is chosen
    if st.session_state.get("last_upload") != uploaded_file.name:
        st.session_state["last_upload"] = uploaded_file.name
        st.session_state.pop("report_generated", None)

    # 1️⃣ Extract text + optional df
    client_text, client_df = extract_text(uploaded_file)
    if not client_text:
        st.error("Unsupported file format or failed to extract text.")
        st.stop()

    # 🔍 View raw data
    with st.expander("📋 View Uploaded Client Data"):
        if client_df is not None:
            # pretty-print each CSV row
            for i, row in client_df.iterrows():
                st.markdown(f"**Record {i+1}:**")
                for col, val in row.items():
                    st.text(f"- {col}: {val}")
                st.write("---")
        else:
            # fallback for .txt and .docx
            st.text(client_text)

    # 2️⃣ Generate button
    if "report_generated" not in st.session_state:
        if st.button("🚀 Generate Report"):
            with st.spinner("Generating report…"):
                # Inject today's date
                today_date = datetime.now().strftime("%d %B %Y")
                system_injected_text = f"Today's date is {today_date}.\n\n{client_text}"

                # 🔹 OpenAI thread/run logic
                thread = openai.beta.threads.create()
                openai.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=system_injected_text
                )
                run = openai.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=ASSISTANT_ID
                )
                while True:
                    status = openai.beta.threads.runs.retrieve(
                        thread_id=thread.id, run_id=run.id
                    )
                    if status.status == "completed":
                        break
                    elif status.status == "failed":
                        st.error("Report generation failed. Please try again.")
                        st.stop()

                messages = openai.beta.threads.messages.list(thread_id=thread.id)
                report_text = messages.data[0].content[0].text.value

                # ── Markdown normalisation
                report_text = re.sub(
                    r"^\*\*(.+?)\*\*$", r"## \1",
                    report_text, flags=re.MULTILINE
                )
                report_text = re.sub(
                    r"^(## .+?)\s*\n+", r"\1\n\n",
                    report_text, flags=re.MULTILINE
                )

                # ── Ensure a blank line after any numbered heading ──
                report_text = re.sub(
                    r'^(?P<h>\d+\.\s[^\n]+)$',
                    r'\g<h>\n\n',
                    report_text,
                    flags=re.MULTILINE
                )

                # Build the in-memory DOCX
                doc = Document()
                bold_pattern = re.compile(r"\*\*(.+?)\*\*")
                for line in report_text.splitlines():
                    p = doc.add_paragraph()
                    last_end = 0
                    for m in bold_pattern.finditer(line):
                        if m.start() > last_end:
                            p.add_run(line[last_end:m.start()])
                        run = p.add_run(m.group(1))
                        run.bold = True
                        last_end = m.end()
                    if last_end < len(line):
                        p.add_run(line[last_end:])

                # ── Add a right-aligned branding footer ──
                section = doc.sections[0]
                footer = section.footer
                footer.clear()  # remove any existing footer text
                p_footer = footer.paragraphs[0]
                run = p_footer.add_run("— Generated with ALTORIX AI —")
                run.italic = True
                run.font.size = Pt(8)
                p_footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT

                # Save to BytesIO
                word_file = io.BytesIO()
                doc.save(word_file)
                word_file.seek(0)

                # Cache in session
                st.session_state.report_text      = report_text
                st.session_state.word_file        = word_file
                st.session_state.report_generated = True

    # 3️⃣ Display & download
    if st.session_state.get("report_generated"):
        st.subheader("📄 Generated Report")
        st.markdown(st.session_state.report_text)
        st.download_button(
            "📥 Download Report (.docx)",
            data=st.session_state.word_file,
            file_name=f"financial_report_{datetime.now():%Y%m%d_%H%M%S}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
