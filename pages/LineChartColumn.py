import streamlit as st
import pandas as pd

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

first_month = df["Date"].min().to_period("M")
month_data = df[df["Date"].dt.to_period("M") == first_month]

rows = []

for column in month_data.columns:
    values = month_data[column]

    rows.append({
        "Column": column,
        "First value": str(values.iloc[0]),
        "First month": (values.tolist()
                        if pd.api.types.is_numeric_dtype(values)
                        else None)
    })

st.dataframe(
    pd.DataFrame(rows),
    column_config = {
        "First month": st.column_config.LineChartColumn(
            "First month", width = "large"
        )
    }
)