#importing libraries
import pandas as pd
import streamlit as st

#given the site a title
st.title("Reservoirs Data")

#reading the csv file
df = pd.read_csv("../data/reservoirs.csv")

#changing the names on the columns
df.columns = [
    "Date", 
    "Area", 
    "Area number",
    "Year",
    "Week",
    "Fill level",
    "Capacity in twh",
    "Stored energy in twh",
    "Next publcation",
    "Previous week fill level",
    "Fill level change"
]

#converting the date column to datetime and sorting the dataframe by date in descending order
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values(by="Date", ascending=False)

#creating new columns for fill level and fill level change in percentage
df["Fill level (%)"] = df["Fill level"] * 100
df["Fill level change (%)"] = df["Fill level change"] * 100

#displaying the dataframe with selected columns rounded to 2 decimal places
st.dataframe(df[[
    "Date",
    "Area",
    "Area number",
    "Fill level (%)",
    "Capacity in twh",
    "Stored energy in twh",
    "Fill level change (%)"
]].round(2))

#creating a selectbox for the user to select an area and area number
area = st.selectbox("Select area", df["Area"].unique())

#creating a selectbox for the user to select an area number
area_number = st.selectbox("Select area number",
                           sorted(df[df["Area"] == area]["Area number"].unique()))

#filtering the dataframe based on the selected
filtered_df = (df[(df["Area"] == area) & (df["Area number"] == area_number)]
               .sort_values(by="Date")
               .set_index("Date"))

#creating a list of columns to plot
columns_to_plot = [
    "Fill level (%)",
    "Capacity in twh",
    "Stored energy in twh",
    "Fill level change (%)"
]
#Could have ploted year and week, but it would not shown anything usefull

#plotting the selected columns as line charts
for column in columns_to_plot:
    st.subheader(column)
    st.line_chart(filtered_df[column])

columns_to_plot_2 = [
    "Fill level (%)",
    "Capacity in twh",
    "Stored energy in twh",
    "Previous week fill level",
    "Fill level change (%)"
]

#getting the values of the selected columns
values = filtered_df[columns_to_plot_2]

#normalizing the values to a range of 0 to 1
ranges = values.max() - values.min()
normalized = (values - values.min()) / ranges.replace(0, 1)

#plotting the normalized values as line charts
st.subheader("Reservoir data over time")
st.line_chart(normalized)