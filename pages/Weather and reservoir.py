import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
from plotly.subplots import make_subplots

st.set_page_config(page_title = "Weather and reservoir", layout = "wide")
st.title("Weather and reservoir correlation")

#using the data, selected area and weather loader
required = ["df", "reservoir_area", "load_weather"]
if any(name not in st.session_state for name in required):
    st.info("Open main page, then select an area on the map or reservoir page")
    st.stop()

area = st.session_state["reservoir_area"]
reservoir = st.session_state["df"]
load_weather = st.session_state["load_weather"]
st.caption(f"Selected area: {area}")

properties = {
    "Temperature": ("temperature_2m", "mean", "C"),
    "Precipitation": ("precipitation", "sum", "mm"),
    "Snowfall": ("snowfall", "sum", "cm"),
}

def weekly_data(reservoir, weather, area):
    data = reservoir.copy()
    labels = data["Area"] + " " + data["Area number"].astype(int).astype(str)
    fill = data.loc[labels.eq(area)].groupby("Date")["Fill level"].mean().sort_index().asfreq("W-SUN") * 100
    data = weather.copy()
    data["time"] = pd.to_datetime(data["time"], utc = True)
    data = data.drop_duplicates("time").sort_values("time")
    local_time = data["time"].dt.tz_convert("Europe/Oslo")

    weekly_weather = {}

    for name, (column, method, unit) in properties.items():
        times = local_time

        if method == "sum":
            times = times - pd.Timedelta(nanoseconds = 1)

        #making a calendar week label
        weeks = times.dt.tz_localize(None).dt.to_period("W-SUN")
        grouped = pd.Series(data[column].to_numpy(), index = weeks,).groupby(level = 0)

        if method == "mean":
            values = grouped.mean()
        else:
            #prevent group from missing
            values = grouped.sum(min_count = 1)

        #DST can have 167 or 169 hours week, when a normal week have 168
        for week, count in grouped.count().items():
            start = week.start_time.tz_localize("Europe/Oslo")
            #localise midnight to include DST changes
            end = (week.start_time + pd.Timedelta(days = 7)).tz_localize("Europe/Oslo")
            expected = int((end - start) / pd.Timedelta(hours = 1))

            if count != expected:
                values.loc[week] = np.nan

        #converting the weekly periods to sunday date labels (matching magasinstatistikk)
        values.index = values.index.to_timestam(how = "end").normalize()
        weekly_weather[name] = values

    #joining weather and reservoir observation by their weekly dates
    weekly = fill.to_frame("Filling level (%)").join(pd.DataFrame(weekly_weather))
    #calculating chang ebefor restricting the displayed period
    weekly["Weekly filling change (pp)"] = fill.diff()

    return weekly

def sliding_correlation(weekly, property_name, target_name, lag_weeks, window_weeks, start_date, end_date,):
    result = weekly[[target_name, property_name]].copy()
    result[property_name] = result[property_name].shift(lag_weeks)
    #restrict the comparison to the selected analysis period
    result = result.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)]
    #no correlation in the first window weeks
    result["Correlation"] = result[target_name].rolling(window_weeks, min_periods = window_weeks).corr(result[property_name].replay([np.inf, -np.inf, np.nan]))

    return result

today = pd.Timestamp.now(tz = "Europe/Oslo").date()
last_year = today.year - 1
#a buffer for era5 publicaton delays
latest_date = today - timedelta(days = 7)
left, right = st.columns(2)

with left:
    #start with fice years of recent history
    start_date = st.date_input(
        "Start date",
        value = date(last_year - 4, 1, 1),
        min_value = date(1995, 1, 1),
        max_value = latest_date,
    )

    property_name = st.selectbox("Weather property", list(properties),)
    #lag is measured in week
    lag_weeks = st.slider(
        "Weather lag (weeks)",
        min_value = 0,
        max_value = 12,
        value = 1,
    )

with right:
    end_date = st.date_input(
        "End date",
        value = min(date(last_year, 12, 31), latest_date),
        min_value = date(1995, 1, 1),
        max_value = latest_date,
    )

    #comparing the stored filling level er weekly change
    target_name = st.selectbox(
        "Reservoir variable",
        [
            "Weekly filling change (pp)",
            "Filling level (%)",
        ],
    )

    window_weeks = st.slider(
        "Window length (weeks)",
        min_value = 4,
        max_value = 52,
        value = 26,
    )

st.caption("Lag 1 pairs last weeks weather wiht this weaks reservoir value. "
           "Temperature uses weekly mean, precipitation and snowfall uses weekly totals.")


with st.spinner("loading weather and preparing weekly observationsl..."):
    weather, latitude, longitude = load_weather(
        area,
        "data/Budområder/Budområder.shp",
        start_date - timedelta(weeks = 13),
        end_date + timedelta(days = 1),
    )

    weekly = weekly_data(reservoir, weather, area,)

#recalulating the correlation usin ghte contorls
result = sliding_correlation(
    weekly,
    property_name,
    target_name,
    lag_weeks,
    window_weeks,
    start_date,
    end_date,
)

#calculating the overall correlation from all complete paris
paired = result[[target_name, property_name]].dropna()
overall = np.nan

#correlation requires variation in both variables
if(paired[target_name].nunique() > 1 and paired[property_name].nunique() > 1):
    overall = paired[target_name].corr(paired[property_name])

#taking the rolling correlation at hte final diplayed reporting week
latest = result["Correlation"].iloc[-1]
first, second, third = st.columns(3)

first.metric(
    "Overall pearson r",
    f"{overall:.2f}" if pd.notna(overall) else "Undefined",
)

second.metric(
    "Latest window r",
    f"{latest:.2f}" if pd.notna(latest) else "Undefined",
)

third.metric("paired weeks", len(paired))

if result["Correlation"].notna().sum() == 0:
    st.warning("No rolling correlation, try a longer period")

#showing the resercoir variable, lagged weather and correlation
fig = make_subplots(
    rows = 3,
    cols = 1,
    shared_xaxes = True,
    vertical_spacing = 0.08,
    subplot_title = [
        target_name,
        f"{property_name}: lagged {lag_weeks} weeks",
        f"Sliding correlation: {window_weeks} - week window", 
    ],
)

#the weather values have alreade been shifte to their target weeks
for row, column, in enumerate([target_name, property_name, "Correlation"], start = 1,):
    fig.add_trace(
        go.Scatter(
            x = result.index,
            y = result[column],
            mode = "lines",
            name = column,
            connectgaps = False,
        ),
        row = row,
        col = 1,
    )

#separate positive and negative vorrelation with a horizonatl zero line
fig.add_hline(
    y = 0,
    line_dash = "dot",
    line_width = 1,
    row = 3,
    col = 1,
)

fig.update_yaxes(
    title_text = properties[property_name][2],
    row = 2,
    col = 1,
)

fig.update_yaxes(
    title_text = "Pearson r",
    range = [-1, 1],
    row = 3,
    col = 1,
)

fig.update_xaxes(
    title_text = "Reporting week",
    row = 3,
    col = 1,
)

fig.update_layout(
    height = 850,
    hovermode = "x unified",
)

st.plotly_chart(
    fig,
    use_container_width = True,
    theme = "streamlit",
)

st.caption(f"ERA5 at one location {latitude:.3f}, {longitude:.3f} inside {area}. "
           "A full window of paired weeks is required, correlation is undefined for a constant series."
           " correlection identifies candidates for forcasting.")

#allwing inspoection of the exact values used in the comparison
with st.expander("weekly values used in the comparison"):
    st.datafram(result, width = "stretch")