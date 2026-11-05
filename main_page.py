import pandas as pd
import streamlit as st
import requests
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

#configuring the page
st.set_page_config(page_title = "Main page", initial_sidebar_state = "expanded")

st.title("Reservoirs Data")
st.header("This is the main page")
st.write("Welcome to the main page of my streamlit app on the left side you can navigate between the pages I hope you enjoy the app and find it useful")

#loading the data and caching
@st.cache_data
def get_data():
    #importing data form magasinstatistikk through API url and converting it into a pandas dataframe
    response = requests.get(st.secrets["magasinstatistikk_url"], timeout = 30)
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

@st.cache_resource
def get_mongo_data():
    uri = f"mongodb+srv://open_for_all:{st.secrets['db_password']}@cluster0.esy9giu.mongodb.net/"

    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    return client

st.session_state["mongo_client"] = get_mongo_data()
