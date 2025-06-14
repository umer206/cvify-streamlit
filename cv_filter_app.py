import streamlit as st
import os
import re
import shutil
import tempfile
from docx import Document
import pandas as pd
import PyPDF2

# --- Extract Text Functions ---
def extract_text_from_pdf(file_path):
    text = ""
    is_image_based = False
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                content = page.extract_text()
                if content:
                    text += content
                else:
                    is_image_based = True
    except:
        is_image_based = True
    return text, is_image_based

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except:
        return ""

# --- Name Extraction ---
def extract_name(text):
    lines = text.strip().splitlines()
    for line in lines:
        line = line.strip()
        if (
            line 
            and len(line.split()) <= 4 
            and line.replace(" ", "").isalpha() 
            and line[0].isupper()
        ):
            return line
    return ""

# --- Info Extraction ---
def extract_candidate_info(text):
    # --- Email ---
    email_match = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text
    )
    email = email_match.group().strip() if email_match else ""

    # --- Phone (Pakistan formats incl. with +092 and dashes) ---
    phone_match = re.search(
        r"(?:(?:\+92|0092|0)?[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{4})", text
    )
    phone = phone_match.group().strip() if phone_match else ""

    # --- LinkedIn ---
    linkedin_match = re.search(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_/]+", text
    )
    linkedin = linkedin_match.group().strip() if linkedin_match else ""
    if linkedin and not linkedin.startswith("http"):
        linkedin = "https://" + linkedin

    # Optional name extraction placeholder
    name = extract_name(text)  # You can enhance this using `nameparser` or from filename

    return {
        "Name": name,
        "Email": email,
        "Phone": phone,
        "LinkedIn": linkedin,
    }



def match_keywords(text, keywords):
    found = [kw for kw in keywords if re.search(rf"\b{re.escape(kw.lower())}\b", text.lower())]
    score = int(len(found) / len(keywords) * 100) if keywords else 0
    return found, score

# --- Process Files ---
def process_files(source_folder, keywords):
    matched_files = []
    manual_review_files = []
    data = []

    dest_dir = os.path.join(source_folder, "matched")
    manual_dir = os.path.join(dest_dir, "manual_review")
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(manual_dir, exist_ok=True)

    for file in os.listdir(source_folder):
        path = os.path.join(source_folder, file)
        ext = file.lower()

        if not os.path.isfile(path) or not ext.endswith(('.pdf', '.docx')):
            continue

        if ext.endswith('.pdf'):
            text, is_image = extract_text_from_pdf(path)
        else:
            text = extract_text_from_docx(path)
            is_image = False

        candidate_info = extract_candidate_info(text)
        matched_keywords, score = match_keywords(text, keywords)

        record = {
            "Filename": file,
            "Name": candidate_info.get("Name", ""),
            "Email": candidate_info.get("Email", ""),
            "Phone": candidate_info.get("Phone", ""),
            "LinkedIn": candidate_info.get("LinkedIn", ""),
            "Match Score": score,
            "Matched Keywords": ", ".join(matched_keywords),
            "Manual Review": "Yes" if is_image else "No",
            "Match": "Yes" if matched_keywords else "No"
        }

        data.append(record)

        # Copy files to matched or manual folders
        if matched_keywords:
            shutil.copy(path, os.path.join(dest_dir, file))
        if is_image:
            shutil.copy(path, os.path.join(manual_dir, file))

    return data, dest_dir

# --- Streamlit UI ---
st.set_page_config("CV Filter App", layout="wide")
#st.title("📁 CV Keyword Filter & Report Generator")
col1, col2 = st.columns([4, 6])

with col1:
    st.markdown("# CVify")
    st.markdown("###### Fast. Focused. Filtered.")
    #st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)  # placeholder logo

with col2:
    #st.markdown("## CVify")
    st.markdown("#### ")


uploaded_zip = st.file_uploader("Upload Zipped CVs (PDF/DOCX)", type=["zip"])
keyword_input = st.text_input("Keywords (comma-separated)", "Python, SQL, T24, Agile")

if st.button("Process"):
    if not uploaded_zip:
        st.error("Please upload a zip file.")
    else:
        # Extract zip to temp folder
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "cvs.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())

        shutil.unpack_archive(zip_path, temp_dir)

        # Extract keywords
        keywords = [k.strip() for k in keyword_input.split(",") if k.strip()]
        st.success("Processing CVs...")
        result_data, matched_folder = process_files(temp_dir, keywords)

        if result_data:
            df = pd.DataFrame(result_data)

            #st.subheader("📊 Match Results")
            #st.dataframe(df)
            st.subheader("📊 Match Results")

            # Filter for matched or manual review only
            filtered_df = df[(df["Match"] == "Yes") | (df["Manual Review"] == "Yes")]

            # Highlight manual review rows
            def highlight_manual_review(row):
                color = "#9e8942" if row["Manual Review"] == "Yes" else ""
                return ['background-color: {}'.format(color)] * len(row)

            # Use Styler to show highlighted rows
            st.dataframe(
                filtered_df.style.apply(highlight_manual_review, axis=1),
                use_container_width=True
            )


            # Save Excel
            excel_path = os.path.join(temp_dir, "CV_Report.xlsx")
            df.to_excel(excel_path, index=False)
            with open(excel_path, "rb") as f:
                st.download_button("📥 Download Excel Report", f, file_name="CV_Report.xlsx")

            # Zip matched folder
            matched_zip = shutil.make_archive(os.path.join(temp_dir, "matched_cv_output"), 'zip', matched_folder)
            with open(matched_zip, "rb") as f:
                st.download_button("📥 Download Matched CVs", f, file_name="Matched_CVs.zip")

            # Basic stats
            total = len(df)
            matched = df["Match"].value_counts().get("Yes", 0)
            manual_review = df["Manual Review"].value_counts().get("Yes", 0)

            st.info(f"✅ {matched}/{total} CVs matched keywords.")
            if manual_review:
                st.warning(f"⚠️ {manual_review} CVs may be image-based and need manual review.")
        else:
            st.warning("No valid CVs found or none matched.")
