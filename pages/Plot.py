import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

st.title("Reservoirs Data")
st.header("Here you can see the fill level for each area over time")

#loding the data from main page and checking if it is available
if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

#converting the date column to datetime and sorting the dataframe by date
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

#chaning the fill level to percentage and creating a new column with area and area number
df["Fill level (%)"] = df["Fill level"] * 100
df["Area label"] = (df["Area"] + " " + df["Area number"].astype(str))

#creating a plot showing the fill level for each area over time
plot_data = df.pivot(
    index = "Date",
    columns = "Area label",
    values = "Fill level (%)"
)

st.line_chart(
    plot_data,
    x_label = "Date",
    y_label = "Fill level (%)"
)

#select boc for column and a slider for month
select = st.selectbox("Select column",
                      ["All columns"] + df.columns.tolist())

months = sorted(df["Date"].dt.strftime("%Y-%m").unique())

start_month, end_month = st.select_slider(
    "Select month",
    options = months,
    value = (months[0], months[0]))