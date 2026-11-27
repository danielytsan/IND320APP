import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.signal import stft
from statsmodels.tsa.seasonal import STL

from plotly.subplots import make_subplots
import plotly.graph_objects as go


st.set_page_config(page_title = "Rescervoirs analysis", initial_sidebar_state = "expanded")

st.title("Reservoirs analysis")
st.header("Here you can see a STL analysis and a spectogram")

#loding the data from main page and checking if it is available
if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

df["Area label"] = df["Area"] + " " + df["Area number"].astype(str)
areas = sorted(df["Area label"].dropna().unique())
area = st.selectbox("select area", areas, index = areas.index("NO 0") if "NO 0" in areas else 0)
st.session_state["reservoir_area"] = area

#preparing one weekly fill series for the tabs
data = df.loc[df["Area label"] == area, ["Date", "Fill level"]].copy()
data["Date"] = pd.to_datetime(data["Date"])
fill = data.set_index("Date")["Fill level"].sort_index() * 100

#Indexing to sundays so gaps in the weekly series transforms to missing values
fill = fill.asfreq("W-SUN")

def plot_fill_stl(fill, seasonal = 7, trend = 101, robust = True):
    result = STL(
        fill, 
        period = 52,
        seasonal = seasonal,
        trend = trend,
        robust = robust
    ).fit()

    components = [
        (result.observed, "Observed filling (%)"),
        (result.trend, "Trend (%)"),
        (result.seasonal, "Seasonal"),
        (result.resid, "Residual")
    ]

    fig = make_subplots(
        rows = 4,
        cols = 1,
        shared_xaxes = True,
        subplot_titles = [label for _, label in components],
        vertical_spacing = 0.07,
    )

    for row, (values, label) in enumerate(components, start = 1):
        fig.add_trace(
            go.Scatter(
                x = fill.index,
                y  = values,
                mode = "lines",
                name = label,
                line = {"width": 1.5},
                hovertemplate = (
                    "%{x|%d %b %Y}<br>"
                    "%{y:.2f}"
                    "<extra%{fullData.name}</extra>"
                ),
            ),
            row = row,
            col = 1,
        )

        fig.update_yaxes(
            title_text = label,
            row = row,
            col = 1,
        )

    fig.update_layout(
        title = "STIL decomposition of reservoir filling",
        height = 820,
        showlegend = False
    )

    return fig

#plot for spectrogram
def plot_fill_spectrogram(fill, window_length = 208, window_overlap = 156):
    frequncies, weeks, coefficients = stft(
        fill.to_numpy(),
        fs = 1,
        nperseg = window_length,
        noverlap = window_overlap,
        detrend = "constant",
        boundary = None,
        padded = False
    )

    dates = fill.index[0] + pd.to_timedelta(weeks * 7, unit = "D") 
    #to be able to see the plot more clearer i have added a dB scale so it is easier to see variation on the higher frequencies
    magnitude = np.abs(coefficients)
    peak = magnitude.max()
    reference = peak if peak > 0 else 1.0
    magnitude_db = 20 * np.log10(np.maximum(magnitude / reference, 1e-12))
    
    fig = go.Figure(
       go.Heatmap(
           x = dates,
           y = frequncies * 52,
           z = magnitude_db,
           zmin = -60,
           zmax = 0,
           colorbar = {"title": "Magnitude (dB)"},
           hovertemplate = (
                "%{x|%d %b %Y}<br>"
                "%{y:.2f} cycle pr year"
                "%{z:.1f} dB"
                "<extra></extra>"
            ),
       )
   )

    #mark one cycle pr year
    fig.add_hline(
        y = 1,
        line_dash = "dash",
        annotation_text = "annual cycle",
        annotation_position = "top left",
    )

    fig.update_layout(
        title = "Reservoir filling spectrogram",
        height = 500,
        xaxis_title = "Date",
        yaxis_title = "Frequency (cycles pr year)",
    )
    return fig

stl_tab, spectogram_tab = st.tabs(["STL", "Spectrogram"])

with stl_tab:
    #making it possible to adjust the smotter and robust on the app
    seasonal = st.number_input("Seasonal smoother", min_value = 7, value = 7, step = 2)
    trend = st.number_input("Trend smoother (weeks)", min_value = 53, value = 101, step = 2)
    robust = st.checkbox("Robust fitting", value = True)

    if seasonal % 2 == 0 or trend % 2 == 0:
        st.warning("Both smooting windows has to be odd")
    else:
        fig = plot_fill_stl(fill, seasonal, trend, robust)
        st.plotly_chart(fig, use_container_width = True, theme = "streamlit",)

with spectogram_tab:
    window = st.number_input("Window length", min_value = 2, max_value = len(fill), value = min(208, len(fill)),)
    overlap = st.number_input("Window overlap", min_value = 0, value = min(156, window - 1),)

    if overlap >= window:
        st.warning("Window overlap must be shorter than window length")
    else:
        fig = plot_fill_spectrogram(fill, window, overlap)
        st.plotly_chart(fig, use_container_width = True, theme = "streamlit",)