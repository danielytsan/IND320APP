from multiprocessing.dummy import connection

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title = "Cross-border Flows", initial_sidebar_state = "expanded")

st.header("Here you can read more about the data and the project")

#loding the data from main page and checking if it is available
if "mongo_client" not in st.session_state:
    st.info("Open the main page first to load MongoDB")
    st.stop()

client = st.session_state["mongo_client"]
collection = client["Project_Ind320"]["crossborder_flows"]

#loading data from mongoDB
@st.cache_data
def get_flows_data():
    return pd.DataFrame(list(collection.find({}, {"_id": 0})))

#adding data into a dataframe and checking if it is empty
df_flows = get_flows_data()

if df_flows.empty:
    st.info("No data available in MongoDB")
    st.stop()

df_flows["Date"] = pd.to_datetime(df_flows["Date"], utc = True).dt.tz_convert("Europe/Oslo")

left, right = st.columns(2)

#creating the left side
with left:
    st.subheader("Data by connection and year")

    connections = st.radio("Select connection",options = sorted(df_flows["country"].dropna().unique()))
    year = st.selectbox("Select year", options = sorted(df_flows["Date"].dt.year.dropna().unique()))

    selected_data_f = df_flows[df_flows["country"] == connections & df_flows["Date"].dt.year == year].copy()
    #Convert MW to MWh: assumes every observation covers 1 hour
    selected_data_f["flow_MWh"] = selected_data_f["flow_MW"] * 1
    total_flows = selected_data_f.groupby("direction")["flow_MWh"].sum()

    total_flows.plot.pie(autopct='%1.1f%%', 
                        startangle=90, 
                        figsize=(5, 5), 
                        title=f"Total Flows between Norway and {connection} in {year}")
    plt.show()



#creating the right side
with right:
    st.subheader("Flows by month")

    months = {
        "January" : 1,
        "February" : 2,
        "March" : 3,
        "April" : 4,
        "May" : 5,
        "June" : 6,
        "July" : 7,
        "August" : 8,
        "September" : 9,
        "October" : 10,
        "November" : 11,
        "December" : 12
    }

    selected_month = st.pills(
        "Select month",
        options = list(months),
        selection_mode = "multi",
        default = ["January"]
    )

    if not selected_month:
        st.info("Please select at least one month")
    else:
        month_numbers = [months[month] for month in selected_month]

        selected_data = df_flows[df_flows["country"] == connections 
                                 & df_flows["Date"].dt.year == year 
                                 & df_flows["Date"].dt.month.isin(month_numbers)].copy()

        if selected_data.empty:
            st.info("No data available for the selected connection")
        else:
            #plotting the flows
            fig, ax = plt.subplots(figsize=(12, 6))

            for (country, direction), group in selected_data.groupby(["country", "direction"]):
                group = group.sort_values("Date")
                ax.plot(
                    group["Date"], 
                    group["flow_MW"], 
                    label=f"{country} - {direction}",
                    linewidth=.8
                )

            ax.set_title(f"Norway cross-border flows with {connection} in {year}")
            ax.set_xlabel("Date")
            ax.set_ylabel("Flow (MW)")
            ax.legend()
            ax.grid()

            fig.autofmt_xdate()
            plt.tight_layout()
            plt.show() 
                    
        
