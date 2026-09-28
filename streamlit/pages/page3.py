import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()