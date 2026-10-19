import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

st.header("Here you can read more about the data and the project")

#loding the data from main page and checking if it is available
if "mongo_client" not in st.session_state:
    st.info("Open the main page first to load MongoDB")
    st.stop()
client = st.session_state["mongo_client"]


st.write("This page is still under development, but it will contain information" \
"in later parts of the projct")

