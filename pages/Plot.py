import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

st.title("Reservoirs Data")
st.header("Here you can interact with the data and plot it, select the data you want to see")

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

#adding radio button for area selection
select_area = st.radio("Select area", ["EL", "NO", "VASS"], horizontal = True)

#select boc for column and a slider for month
selected_column = st.selectbox("Select column",
                      ["All columns"] + df.columns.tolist())

months = sorted(df["Date"].dt.strftime("%Y-%m").unique())

if not months:
    st.info("No data available")
    st.stop()

start_month, end_month = st.select_slider(
    "Select month",
    options = months,
    value = (months[0], months[-1]))

#filter dates
date_month = df["Date"].dt.strftime("%Y-%m")

filtered_df = df[
    date_month.between(start_month, end_month) & (df["Area"] == select_area)
].copy()

#plot all numeric columns or selected column
if selected_column == "All columns":
    plot_data = (
        filtered_df
        .set_index("Date")
        .select_dtypes(include = "number")
    )

    st.line_chart(plot_data, x_label = "Date", y_label = "Value")

else: 
    columns_to_plot = list(
        dict.fromkeys(["Date", "Area label", selected_column])
    )

    st.line_chart(
        filtered_df[columns_to_plot],
        x_label = "Date",
        y_label = "Value"
    )
