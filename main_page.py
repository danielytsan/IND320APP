import pandas as pd
import streamlit as st
from pathlib import Path

#configuring the page
st.set_page_config(page_title = "Main page", initial_sidebar_state = "expanded")

st.title("Data")
st.header("This is the main page")
st.write("Welcome to the main page of my streamlit app" \
"on the left side you can navigate between the pages" \
"I hope you enjoy the app and find it useful")

#loading the data and caching
@st.cache_data
def get_data():
    df = pd.read_csv("data/reservoirs.csv")

    df.columns = [
    "Date",
    "Area",
    "Area number",
    "Year",
    "Week",
    "Fill level",
    "Capacity in TWh",
    "Stored energy in TWh",
    "Next publication",
    "Previous week fill level",
    "Fill level change"
    ]
    return df

st.session_state["df"] = get_data()