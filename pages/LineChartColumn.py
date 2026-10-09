import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

st.title("Reservoirs Data")
st.header("Here you can see the data for the first month")

#loding the data from main page and checking if it is available
if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

#converting the date column to datetime and sorting the dataframe by date
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

#getting the first month and filtering the dataframe to only include data from that month
first_month = df["Date"].min().to_period("M")
month_data = df[df["Date"].dt.to_period("M") == first_month]
columns_to_plot = [
        "Fill level",
        "Capacity in twh",
        "Stored energy in twh",
        "Next publcation",
        "Previous week fill level",
        "Fill level change"
]

rows = []

#making a column for each column and getting the first value and the values for the first month
for column in columns_to_plot:
    values = month_data[column]

    rows.append({
        "Column": column,
        "First value": str(values.iloc[0]),
        "First month": (values.tolist()
                        if pd.api.types.is_numeric_dtype(values)
                        else None)
    })

#displaying the first month values
st.dataframe(
    pd.DataFrame(rows),
    column_config = {
        "First month": st.column_config.LineChartColumn(
            "First month", width = "large"
        )
    }
)