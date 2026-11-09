import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from scipy.fft import dct, idct
from scipy.stats import median_abs_deviation
from sklearn.neighbors import LocalOutlierFactor
from datetime import date


st.set_page_config(page_title = "Weather Data", initial_sidebar_state = "expanded")

st.title("Weather analysis")
st.header("Here you can see a SPC analysis and a LOF analysis for the weather data")

#loding the data from main page and checking if it is available
if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

area = st.session_state.get("reservoir_area")
load_weather = st.session_state.get("load_weather")
if area is None:
    st.info("select a resercoir area on Page 4 before loading weather")
    
st.caption(f"Selected resercoir area: {area}")
shapefile = "data/Budområder/Budområder.shp"

#making a function for plotting precipitation outliers
def plot_precipitation_outliers(weather, cutoff_days = 30, n_std = 3):
    data = weather[["time", "precipitation"]].copy()
    data["time"] = pd.to_datetime(data["time"], utc = True)

    #sort timestamps so it is in chronological order
    precipitation = (data.groupby("time")["precipitation"].mean().sort_index())

    #create a date range with the same start and end times as the precipitation data
    expected_time = pd.date_range(precipitation.index.min(), precipitation.index.max(), freq = "h",)
    values = precipitation.to_numpy(dtype = float)

    #romwing low frequencies
    coefficients = dct(values, type = 1, norm = "forward")
    frequencies = np.linspace(0, .5, len(values))
    coefficients[frequencies <= 1 / (cutoff_days * 24)] = 0
    satv = idct(coefficients, type = 1, norm = "forward")
    baseline = values - satv
    
    #estimate robust limits and change them to precipitation scale
    center = np.meadian(satv)
    robust_std = 1.4826 * median_abs_deviation(satv)
    #precipitation values
    lower = baseline + center - n_std * robust_std
    upper = baseline + center + n_std * robust_std
    above = values > upper
    below = values < lower
    flagged = above | below

    outliers = pd.DataFrame({
        "Precipitation": values[flagged],
        "Lower limit": lower[flagged],
        "Upper limit": upper[flagged],
        "Direction": np.where(above[flagged], "Above", "Below"),
    }, index = precipitation.index[flagged])

    summary = pd.Series({
        "Total hours": len(values),
        "Flagged hours": int(flagged.sum()),
        "Flagged hours (%)": 100 * flagged.mean(),
        "Above upper limit": int(above.sum()),
        "Below lower limit": int(below.sum()),
        "Robust Standard devition": robust_std,
    })

    #plotting and marking the hour outside the spc limits
    fig, ax = plt.subplots(figsize = (10, 5))
    ax.plot(precipitation.index, values, label = "Hourly precipitation")
    ax.plot(precipitation.index, upper, "r---", label = "SPC limits")
    ax.plot(precipitation.index, lower, "r---")
    ax.scatter(outliers.index, outliers["Precipitation"],
               color = "red", s = 15, zorder = 3, labels = "Outliers",)
    ax.set(
        title = "Hourly precipitation with robust SPC limits",
        xlabel = "Time",
        ylabel = "Preciptitation",
    )
    ax.legend()
    fig.tight_layout()
    return fig, summary, outliers

#making a function to plot temp outliers
def plot_temperature_outliers(weather, outlier_proportion = 0.01):
    data = weather[["time", "temperature_2m"]].copy()
    data["time"] = pd.to_datetime(data["time"], utc = True)
    temperature = data.groupby("time")["temperature_2m"].mean().sort_index()
    values = temperature.to_numpy(dtype = float)

    lof = LocalOutlierFactor(n_neighbors = min(20, len(values) - 1), contamination = outlier_proportion)
    flagged = lof.fit_predict(values.reshape(-1, 1)) == -1
    scores = -lof.negative_outlier_factor_

    outliers = pd.DataFrame({
        "Temperature": values[flagged],
        "LOF score": scores[flagged],
    }, index = temperature.index[flagged])

    summary = pd.Series({
            "Total hours": len(values),
            "Flagged hours": int(flagged.sum()),
            "Flagged hours (%)": 100 * flagged.mean(),
            "Requested outlier proportion (%)": 100 * outlier_proportion,
            "Highest LOF score": scores.max(),
        })

    fig, ax = plt.subplots(figsize = (10, 5))
    ax.plot(temperature.index, values, label = "Hourly temperature")
    ax.scatter(outliers.index, outliers["Temperature"],
               color = "red", s = 20, zorder = 4, label = "LOF anomalies",)
    ax.set(
        title = "Hourly temperature with LOF anomalies",
        xlabel = "Time",
        ylabel = "Temperature",
    )
    ax.legend()
    fig.tight_layout()
    return fig, summary, outliers

def show_results(fig, summary, outliers):
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("Summary statistics")
    st.dataframe(summary.to_fram("Value"))

    st.subheader("Flagged observations")
    st.dataframe(outliers)

#setting default to the most recent caldendar year
year = date.today().year - 1
with st.form("weather_download"):
    start_date = st.date_input("Start date", value = date(year, 1, 1))
    end_date = st.date_input("End date", value = date(year, 12, 31))
    download = st.form_submit_button("Load ERA5 weather")

#keeping the downloaded data while possible to change analysis setting
selection = (area, start_date, end_date)
if download:
    loaded_data = load_weather(area, shapefile, start_date, end_date)
    st.session_state["weather_analysis_data"] = (selection, loaded_data)

weather = None
loaded = st.session_state.get("weather_analysis_data")
if loaded is not None and loaded[0] == selection:
    weather, latitude, longitude = loaded[1]
    st.caption(f"Hourly ERA5 at one location ({latitude:.3f}, {longitude:.3f})")

if weather is None:
    st.info("Clock load ERA5 weather to run analysis")
    st.stop

spc_tab, lof_tab = st.tabs(["Outlier / SPC", "Anomaly /LOF"])

with spc_tab: 
    cutoff_days = st.number_input("DCT cutoff period", min_value = 1, value = 30)
    n_std = st.number_input("Robust standard deviations", min_value = 0.1, value = 3.0)
    show_results(*plot_precipitation_outliers(weather, cutoff_days, n_std))

with lof_tab:
    percent = st.number_input("Expected outliers (%)", min_value = 0.1, max_value = 50, value = 1)
    show_results(*plot_temperature_outliers(weather, percent / 100))
        

