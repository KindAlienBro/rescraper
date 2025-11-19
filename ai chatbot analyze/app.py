# app.py
import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
from prompt import SYSTEM_INSTRUCTIONS

# --- CONFIGURATION ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- PAGE SETUP ---
st.set_page_config(
    page_title="AI Results Analyzer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- SESSION STATE INITIALIZATION ---
# This is crucial for remembering chat history and loaded data
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_df" not in st.session_state:
    st.session_state.current_df = None
if "current_file_name" not in st.session_state:
    st.session_state.current_file_name = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("📄 AI Results Analyzer")
    
    # Model selection using the list you discovered
    available_models = ['gemini-pro-latest', 'gemini-2.5-flash', 'gemini-1.5-flash-latest']
    selected_model = st.selectbox("Select Model", available_models)
    
    st.markdown("---")
    
    if st.button("New Chat", use_container_width=True):
        # Clear session state to start a new conversation
        st.session_state.messages = []
        st.session_state.current_df = None
        st.session_state.current_file_name = None
        st.rerun()

    st.markdown("---")
    st.header("How to Use")
    st.info(
        "1. Start by typing a message that includes the file you want to analyze, e.g., `Analyze @results.xlsx`.\n"
        "2. The file must be in the same directory as the app.\n"
        "3. Once the file is loaded, ask any question about its content."
    )
    if st.session_state.current_file_name:
        st.success(f"File Loaded: `{st.session_state.current_file_name}`")

# --- MAIN CHAT INTERFACE ---
st.header(f"Chat with {selected_model}")

# Display an expander for the System Prompt, mimicking the reference UI
with st.expander("View System Prompt"):
    st.markdown(SYSTEM_INSTRUCTIONS)

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Type your message here... (e.g., 'What is the pass percentage in @results.xlsx?')"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- CORE LOGIC ---
    with st.chat_message("assistant"):
        response = ""
        # 1. Check if the user is trying to load a file
        file_match = re.search(r'@([\w\s-]+\.(?:xlsx|xls))', prompt)
        
        if file_match:
            file_name = file_match.group(1)
            try:
                if os.path.exists(file_name):
                    with st.spinner(f"Loading and reading `{file_name}`..."):
                        df = pd.read_excel(file_name)
                        st.session_state.current_df = df
                        st.session_state.current_file_name = file_name
                    response = f"✅ **Success!** The file `{file_name}` has been loaded. I'm ready for your questions."
                    st.success(f"File Loaded: {file_name}") # Also show a temporary success message
                else:
                    response = f"⚠️ **Error:** The file `{file_name}` was not found in the directory. Please make sure it's in the same folder as the application."
            except Exception as e:
                response = f"❌ **Error reading file:** Could not process `{file_name}`. The error is: {e}"
        
        # 2. If no file is mentioned, check if one is already loaded
        elif st.session_state.current_df is not None:
            with st.spinner("Analyzing the data..."):
                try:
                    # Convert the DataFrame to a Markdown string for the prompt
                    data_context = st.session_state.current_df.to_markdown(index=False)
                    
                    # Construct the full prompt for the AI
                    full_prompt = f"""
                    {SYSTEM_INSTRUCTIONS}
                    
                    ------------------------------------------
                    DATASET (from file: {st.session_state.current_file_name}):
                    ------------------------------------------
                    {data_context}
                    
                    ------------------------------------------
                    USER QUESTION:
                    ------------------------------------------
                    {prompt}
                    """
                    
                    # Call the Gemini API
                    model = genai.GenerativeModel(selected_model)
                    api_response = model.generate_content(full_prompt)
                    response = api_response.text
                    
                except Exception as e:
                    response = f"An error occurred during analysis: {e}"

        # 3. If no file is loaded and none is mentioned
        else:
            response = "I'm ready to help! Please specify a results file to analyze by mentioning it, for example: `Can you analyze @results.xlsx for me?`"

        # Display assistant response and add to chat history
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})