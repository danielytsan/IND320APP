import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.signal import stft
from statsmodels.tsa.seasonal import STL

st.set_page_config(page_title = "Rescervoirs Data", initial_sidebar_state = "expanded")

st.title("Reservoirs analysis")
st.header("Here you can see a STL analysis and a spectogram for the reservoir data")

#loding the data from main page and checking if it is available
if "df" not in st.session_state:
    st.info("Open the main page first to load the data")
    st.stop()
df = st.session_state["df"].copy()

df["Area label"] = df["Area"] + " " + df["Area number"].astype(str)
areas = sorted(df["Area label"].dropna().unique())
area = st.selectbox("select area", areas, index = areas.index("NO 0") if "NO 0" in areas else 0)

#preparing one weekly fill series for the tabs
data = df.loc[df["Areas label"] == area, ["Date", "Fill level"]].copy()
data["Date"] = pd.to_datetime(data["Date"])
fill = data.set_index("Date")["Fill level"].sort_index() * 100

#Indexing to sundays so gaps in the weekly series transforms to missing values
fill = fill.asfreq("W-SUN")

def plot_fill_stl(df, seasonal = 7, trend = 101, robust = True):
    result = STL(
        fill, 
        period = 52,
        seasonal = seasonal,
        trend = trend,
        robust = robust
    ).fit()

    fig, axes = plt.subplots(
        4,
        1,
        sharex = True,
        figsize = (11, 8),
        layout = "constrained"
    )

    components = (
        (result.observed, "Observed (%)"),
        (result.trend, "Trend (%)"),
        (result.seasonal, "Seasonal"),
        (reuslt.resid, "Residual")
    )

    for ax, (values, label) in zip(axes, components):
        ax.plot(fill.index, values, linewidth = .9)
        ax.set_ylabel(label)
        ax.grid(alpha = .25)

    axes[-1].set_xlabel("Date")
    fig.suptitle("STL decompostion of reservoir fill level")
    return fig

#plot for spectrogram
def plot_fill_spectrogram(data, window_length = 208, window_overlap = 156):
    fill = (
            data.set_index("Date")["Fill level (%)"]
            .sort_index()
            .asfreq("W-SUN"))

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
    cycles_per_year = frequncies * 52

    fig, ax = plt.subplots(figsize = (10, 5), layout = "constrained")
    mesh = ax.pcolormesh(
        dates, cycles_per_year, np.abs(coefficients)
    )

    #marking the frequency of one cycle pr year
    ax.axhline(1, color = "white", linestyle = "--", label = "Anual cycle")
    ax.set(
        title = "Resercoir fill spectrogram",
        xlabel = "Date",
        ylabel = "Frequency"
    )
    ax.legend()
    fig.colorbar(mesh, ax = ax, label = "STFT magnitude")
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
        st.pyplot(fig)
        plt.close(fig)

with spectogram_tab:
    window = st.number_input("Window length", min_value = 2, max_value = len(fill), value = min(208, len(fill)),)
    overlap = st.number_input("Window overlap", min_value = 0, value = min(156, window - 1),)

    if overlap >= window:
        st.warning("Window overlap must be shorter than window length")
    else:
        fig = plot_fill_spectrogram(fill, window, overlap)
        st.pyplot(fig)
        plt.close(fig)