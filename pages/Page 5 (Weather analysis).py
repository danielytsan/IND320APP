import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from scipy.fft import dct, idct
from scipy.stats import median_abs_deviation
from sklearn.neighbors import LocalOutlierFactor
from datetime import date



st.set_page_config(page_title = "Weather analysis", initial_sidebar_state = "expanded")

st.title("Weather analysis")
st.header("Here you can see a SPC analysis and a LOF analysis for the weather data")

load_weather = st.session_state.get("load_weather")
if load_weather is None:
    st.info("Open the main page first")
    st.stop()

area = st.session_state.get("reservoir_area")
if area is None:
    st.info("select a resercoir area on Page 4")
    st.stop()

st.caption(f"Selected resercoir area: {area}")
shapefile = "data/Budområder/Budområder.shp"

#making a function for plotting precipitation outliers
def plot_precipitation_outliers(weather, cutoff_days = 30, n_std = 3):
    data = weather[["time", "precipitation"]].copy()
    data["time"] = pd.to_datetime(data["time"], utc = True)

    #sort timestamps so it is in chronological order
    precipitation = (data.groupby("time")["precipitation"].mean().sort_index())
    values = precipitation.to_numpy(dtype = float)

    #romwing low frequencies
    coefficients = dct(values, type = 1, norm = "forward")
    frequencies = np.linspace(0, .5, len(values),)
    coefficients[frequencies <= 1 / (cutoff_days * 24)] = 0
    satv = idct(coefficients, type = 1, norm = "forward")
    baseline = values - satv
    
    #estimate robust limits and change them to precipitation scale
    center = np.median(satv)
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
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x = precipitation.index,
            y = values, 
            mode = "lines",
            name = "Hourly precipitation",
            line = {"width": 1.2},
        )
    )

    #dashing lines shows SPC limits
    fig.add_trace(
        go.Scattergl(
            x = precipitation.index,
            y = upper,
            mode = "lines",
            name = "SPC limits",
            legendgroup = "limits",
            line = {"dash": "dash", "width": 1.2,},
        )
    )

    fig.add_trace(
        go.Scattergl(
            x = precipitation.index,
            y = lower,
            mode = "lines",
            name = "SPC limits",
            legendgroup = "limits",
            showlegend = False,
            line = {"dash": "dash", "width": 1.2,},
        )
    )

    fig.add_trace(
        go.Scattergl(
            x = outliers.index,
            y = outliers["Precipitation"],
            mode = "markers",
            name = "Outliers",
            marker = {"size": 7, "symbol": "diamond",},
        )
    )

    fig.update_layout(
        title = "Hourly precipitation with robust SPC limits",
        height = 480,
        xaxis_title = "Time",
        yaxis_title = "Precimitation (mm/h)",
    )
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

    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x = temperature.index,
            y = values,
            mode = "lines",
            name = "Hourly temperature",
            line = {"width": 1.2},
        )
    )

    fig.add_trace(
        go.Scattergl(
            x = outliers.index,
            y = outliers["Temperature"],
            mode = "markers",
            name = "LOF anomalies",
            marker = {"size": 7, "symbol": "diamond",},

            #adding LOF scores to the marker info
            costumdata = outliers["LOF score"].to_numpy(),
            hovertemplate = (
                "%{x|%d %b %Y %H:%M}<br>"
                "%{y:.2f} C<br>"
                "LOF score %{customdata:.3f}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title = "Hourly temp with LOF anomalies",
        height = 480,
        xaxis_title = "Time",
        yaxis_title = "Temperature",
    )
    return fig, summary, outliers

def show_results(fig, summary, outliers):
    st.plotly_chart(fig, use_container_width = True, theme = "streamlit",)
    st.subheader("Summary statistics")
    st.dataframe(summary.to_frame("Value"))
    st.subheader("Flagged observations")
    st.dataframe(outliers)

#setting default to the most recent caldendar year
year = date.today().year - 1
start_date = st.date_input("Start date", value = date(year, 1, 1))
end_date = st.date_input("End date", value = date(year, 12, 31))
with st.spinner("Loading hourly ERA5 weather"):
    weather, latitude, longitude = load_weather(area, shapefile, start_date, end_date)
st.caption(f"Hourly ERA5 at one location ({latitude:.3f}, {longitude:.3f})")

spc_tab, lof_tab = st.tabs(["Outlier / SPC", "Anomaly /LOF"])

with spc_tab: 
    cutoff_days = st.number_input("DCT cutoff period", min_value = 1, value = 30)
    n_std = st.number_input("Robust standard deviations", min_value = 0.1, value = 3.0)
    show_results(*plot_precipitation_outliers(weather, cutoff_days, n_std))

with lof_tab:
    percent = st.number_input("Expected outliers (%)", min_value = 0.1, max_value = 50.0, value = 1.0)
    show_results(*plot_temperature_outliers(weather, percent / 100))
        

