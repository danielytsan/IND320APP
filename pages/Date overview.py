import streamlit as st
import plotly.express as px
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
    date_month.between(start_month, end_month) & (df["Area"].eq(select_area))
].copy()

#plot all numeric columns or selected column
if selected_column == "All columns":
    numeric_columns = filtered_df.select_dtypes(include = "number").columns.tolist()

    #changing from wide to long format
    long_data = filtered_df.melt(
        id_vars = ["Date", "Area label"],
        value_vars = numeric_columns,
        var_name = "Variable",
        value_name = "Value",
    )

    fig = px.line(
        long_data,
        x = "Date",
        y = "Value",
        color = "Variable",
        line_group = "Area label",
        hover_data = ["Area label"],
        render_mode = "webgl",
    )
else:
    fig = px.line(
        filtered_df,
        x = "Date",
        y = selected_column,
        color = "Area label",
        render_mode = "webgl",
        labels = {"Area label": "Region"},
    )

fig.update_layout(title = "Resercoir data", height = 550,)
st.plotly_chart(fig, use_container_width = True, theme = "streamlit",)