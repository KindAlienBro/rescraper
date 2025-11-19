import streamlit as st
from result_analyzer import analyze_results # Import the function from your other file
from datetime import datetime

st.set_page_config(page_title="VTU Result Analyzer", layout="wide")

st.title("🎓 VTU Result Analyzer")
st.write("Upload the Excel sheet from your result scraper to automatically generate an analysis report with charts.")

# --- File Uploader ---
uploaded_file = st.file_uploader(
    "Choose your results Excel file",
    type=['xlsx']
)

if uploaded_file is not None:
    st.success(f"File '{uploaded_file.name}' uploaded successfully!")

    # --- Analysis Button ---
    if st.button("Analyze Results", type="primary"):
        with st.spinner('Processing your file... This may take a moment.'):
            try:
                # Call the analysis function
                analysis_report_bytes = analyze_results(uploaded_file)
                
                st.balloons()
                st.header("✅ Analysis Complete!")
                st.write("Your report is ready for download.")

                # --- Download Button ---
                # Generate a dynamic filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"Analysis_Report_{timestamp}.xlsx"

                st.download_button(
                    label="📥 Download Analysis Report",
                    data=analysis_report_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"An error occurred during analysis: {e}")
                st.warning("Please ensure your uploaded file is the correct VTU result format.")

else:
    st.info("Awaiting file upload...")