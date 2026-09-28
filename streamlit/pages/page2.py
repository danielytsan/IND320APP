import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

df["Fill level (%)"] = df["Fill level"] * 100

plot_data = df.pivot(
    index = "Date",
    columns = "Area",
    values = "Fill level (%)"
)

st.line_chart(
    plot_data,
    x_label = "Date",
    y_label = "Fill level (%)"
)

select = st.selectbox("Select column",
                      ["All columns"] + df.columns.tolist())

months = sorted(df["Date"].dt.strftime("%Y-%m").unique())

start_month, end_month = st.select_slider(
    "Select month",
    options = months,
    value = (months[0], months[0]))