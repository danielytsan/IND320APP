import pandas as pd
import streamlit as st
import requests

    #making a path to the secrets file and reading it into a dictionary
secrets = {}

with open("secrets.txt", "r") as file:
    for line in file:
        line = line.strip()

        #Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        name, value = line.split("=", 1)
        secrets[name.strip()] = value.strip()

#configuring the page
st.set_page_config(page_title = "Main page", initial_sidebar_state = "expanded")

st.title("Reservoirs Data")
st.header("This is the main page")
st.write("Welcome to the main page of my streamlit app on the left side you can navigate between the pages I hope you enjoy the app and find it useful")

#loading the data and caching
@st.cache_data
def get_data():
    #importing data form magasinstatistikk through API url and converting it into a pandas dataframe
    response = requests.get(secrets["magasinstatistikk_url"], timeout = 30)
    response.raise_for_status()

    df = pd.DataFrame(response.json())

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