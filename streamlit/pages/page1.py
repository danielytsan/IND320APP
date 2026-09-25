import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")
df = pd.read_csv("data/reservoirs.csv")
st.dataframe(df)