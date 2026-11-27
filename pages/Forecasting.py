from datetime import timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from river import linear_model, optim, preprocessing, time_series, tree

st.set_page_config(page_title = "Reservoir forecast", layout = "wide")
st.title("Dynamic reservoir forecast")

required = ["df", "reservoir_area", "load_weather"]
if any(name not in st.session_state for name in required):
    st.info("Open the main page, then select an area on the map")
    st.stop()

properties = {
    "Temperature": ("temperature_2m", "mean", "C"),
    "Precipitation": ("precipitation", "sum", "mm"),
    "Snowfall": ("snowfall", "sum", "cm"),
}

default_history_years = 5

def prepare_fill(reservoir, area):
    data = reservoir.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    labels = data["Area"] + " " + data["Area number"].astype(int).astype(str)
    return data.loc[labels.eq(area)].groupby("Date")["Fill level"].mean().sort_index().asfreq("W-SUN") * 100


def weekly_weather(weather):
    data = weather.copy()
    data["time"] = pd.to_datetime(data["time"], utc = True)
    data = data.drop_duplicates("time").sort_values("time")
    local = data["time"].dt.tz_convert("Europe/Oslo")

    output = {}
    for name, (column, method, unit) in properties.items():
        times = local if method == "mean" else local - pd.Timedelta(nanoseconds = 1)
        weeks = times.dt.tz_localize(None).dt.to_period("W-SUN")
        grouped = pd.Series(data[column].to_numpy(), index = weeks).groupby(level = 0)
        values = grouped.mean() if method == "mean" else grouped.sum(min_count = 1)
        for week, count in grouped.count().items():
            start = week.start_time.tz_localize("Europe/Oslo")
            end = (week.start_time + pd.Timedelta(days = 7)).tz_localize("Europe/Oslo")
            
            if count != int((end - start) / pd.Timedelta(hours = 1)):
                values.loc[week] = np.nan
        values.index = values.index.to_timestamp(how = "end").normalize()
        output[name] = values
    return pd.DataFrame(output)

def make_regressor(kind, learning_rate, l2, grace_period, max_depth, leaf_prediction):
    linear = preprocessing.StandardScaler() | linear_model.LinearRegression(
        optimizer=optim.SGD(learning_rate), intercept_lr=learning_rate,
        l2 = l2, clip_gradient = 1.0,
    )
    if kind == "linear":
        return linear
    return tree.HoeffdingTreeRegressor(
        grace_period = grace_period, max_depth = max_depth,
        leaf_prediction = leaf_prediction, leaf_model = linear,
    )

def dynamic_forecast(fill, weather, start_date, end_date, horizon, orders,
                     kind = "tree", learning_rate = 0.02, l2 = 0.001,
                     grace_period = 25, max_depth = 5, leaf_prediction = "mean",
                     selected = (), weather_lag = 1, scenario = "Weekly historical mean",
                     calendar_features = True):
    #cuting off the observation before fitting or constructing futur inputs
    train = fill.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)].copy()
    p, d, q, m, sp, sd, sq = orders
    minimum = max(104, d + sd*m + max(p, q, sp*m, sq*m) + 26)
    origin = train.index[-1]

    known = pd.DataFrame()
    climatology = pd.DataFrame()
    history = pd.DataFrame()
    if selected:
        known = weather.loc[:origin - pd.Timedelta(weeks = 1), list(selected)].copy()
        history = known.loc[pd.Timestamp(start_date):].dropna()
        climatology = history.groupby(history.index.isocalendar().week.clip(upper=52)).mean()


    def features(target_date, future = False):
            x = {}
            if calendar_features:
                # Calendar features are known for every future date.
                phase = 2 * np.pi * target_date.day_of_year / 365.25
                x.update(season_sin = float(np.sin(phase)), season_cos = float(np.cos(phase)))
            source_date = target_date - pd.Timedelta(weeks = weather_lag)
            assumed = False
            if selected:
                if source_date in known.index and known.loc[source_date].notna().all():
                    row = known.loc[source_date]
                else:
                    # Future observed weather must never enter a forecast.
                    assumed = True
                    week = min(int(source_date.isocalendar().week), 52)
                    if scenario == "Weekly historical mean":
                        row = climatology.loc[week] if week in climatology.index else history.mean()
                    else:
                        row = history.iloc[-1]
                x.update({name: float(row[name]) for name in selected})
            return x, source_date, assumed
    
    regressor = make_regressor(
        kind,
        learning_rate,
        l2,
        grace_period,
        max_depth,
        leaf_prediction,
    )

    model = time_series.SNARIMAX(
        p = p,
        d = d,
        q = q,
        m = m,
        sp = sp,
        sd = sd,
        sq = sq,
        regressor = regressor,
    )

    #river learns one obsercation at a time in chronolog order
    for timestamp, value in train.items():
        x, _, _ = features(timestamp)
        model.learn_one(
            y=float(value) / 100,
            x=x,
        )

    #Generateing sunday labels for the requested forecast horizon.
    dates = pd.date_range(
        origin + pd.Timedelta(weeks = 1),
        periods = horizon,
        freq = "W-SUN",
    )

    xs, inputs = [], []

    for timestamp in dates:
        x, source_date, assumed = features(
            timestamp,
            future = True,
        )
        xs.append(x)
        inputs.append({
            "Date": timestamp,
            "Weather week": source_date,
            "Weather assumed": assumed,
            **{
                name: x[name]
                for name in selected
            },
        })

    #dynamic forcasting with SNARIMAX
    raw = np.asarray(
        model.forecast(horizon=horizon, xs=xs),
        dtype=float,
    ) * 100

    forecast = pd.DataFrame(
        {
            # Bound the displayed predictions to physically valid values.
            "prediction": np.clip(raw, 0, 100),

            # Simple comparison: repeat filling from 52 weeks earlier.
            "seasonal_naive": train.reindex(
                dates - pd.Timedelta(weeks = 52)
            ).to_numpy(),
        },
        index = dates,
    )

    forecast.index.name = "Date"

    #checking how many raw prediction required bounding
    forecast.attrs["clipped"] = int(
        ((raw < 0) | (raw > 100)).sum()
    )

    return train, forecast, pd.DataFrame(inputs).set_index("Date")

def forcasting(train, forecast, area):
    history = train.iloc[-104:]
    dates = [train.index[-1], *forecast.index]
    values = [
        float(train.iloc[-1]),
        *forecast["prediction"],
    ]

    fig = go.Figure([
        go.Scatter(
            x = history.index,
            y = history,
            name = "Observed filling",
            mode = "lines",
        ),
        go.Scatter(
            x = forecast.index,
            y = forecast["seasonal_naive"],
            name = "52-week baseline",
            mode = "lines",
            line = {"dash": "dash"},
        ),
        go.Scatter(
            x = dates[:1],
            y = values[:1],
            name = "Dynamic forecast",
            mode = "lines+markers",
        ),
    ])

    #each frame reveals one forecast week, observed history and the maseline remain in the plot
    fig.frames = [
        go.Frame(
            name = str(step),
            traces = [2],
            data = [
                go.Scatter(
                    x = dates[:step + 1],
                    y = values[:step + 1],
                ),
            ],
        )
        for step in range(len(forecast) + 1)
    ]

    #using by pause and by the slider to jump to a frame
    instant = {
        "mode": "immediate",
        "frame": {
            "duration": 0,
            "redraw": False,
        },
        "transition": {"duration": 0},
    }


    fig.update_layout(
        title=f"{area}: weekly reservoir filling",
        height = 570,
        xaxis = {
            "title": "Reporting week",
            "range": [
                history.index[0],
                forecast.index[-1],
            ],
            "autorange": False,
        },
        yaxis = {
            "title": "Filling (%)",
            "range": [0, 100],
            "autorange": False,
        },

        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "y": -0.18,
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "fromcurrent": True,
                                "frame": {
                                    "duration": 250,
                                    "redraw": False,
                                },
                                "transition": {"duration": 0},
                            },
                        ],
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [[None], instant],
                    },
                ],
            },
        ],

        sliders=[
            {
                "currentvalue": {
                    "prefix": "Forecast week: ",
                },
                "pad": {"t": 45},
                "steps": [
                    {
                        "label": str(step),
                        "method": "animate",
                        "args": [[str(step)], instant],
                    }
                    for step in range(len(forecast) + 1)
                ],
            },
        ],
        margin = {"b": 130},
    )

    fig.add_vline(
        x = train.index[-1],
        line_dash = "dot",
        line_width = 1,
    )

    return fig

#reading the region selected on the map and prepare the reservoir data
area = st.session_state["reservoir_area"]
fill = prepare_fill(st.session_state["df"], area)
today = pd.Timestamp.now(tz="Europe/Oslo").date()
first_date = fill.index[0].date()

end_default = min(
    max(
        pd.Timestamp(
            st.session_state.get(
                "map_end_date",
                fill.index[-1],
            )
        ).date(),
        first_date,
    ),
    today,
)

start_default = st.session_state.get(
    "forecast_training_start",
    (pd.Timestamp(end_default) - pd.DateOffset(years = default_history_years)).date(),
)

st.caption(
    f"Selected area: {area}. "
    "Training end and horizon are shared with the map."
)

left, right = st.columns(2)

with left:
    start_date = st.date_input(
        "Training start",
        value = max(
            first_date,
            min(start_default, end_default),
        ),
        min_value = first_date,
        max_value = today,
        key = "_forecast_start",
    )

    model_name = st.selectbox(
        "River regressor",
        ["Tree", "Linear"],
    )

    selected = st.multiselect(
        "Exogenous weather variables",
        list(properties),
    )

with right:
    end_date = st.date_input(
        "Training end",
        value = end_default,
        min_value = first_date,
        max_value = today,
        key = "_forecast_end",
    )

    horizon = st.slider(
        "Forecast horizon (weeks)",
        1,
        52,
        int(
            st.session_state.get(
                "forecast_horizon_weeks",
                13,
            )
        ),
        key = "_forecast_horizon",
    )

    calendar_features = st.checkbox(
        "Include annual calendar features",
        value = True,
    )


weather_lag, scenario = 1, "Weekly historical mean"

#selecting the parameters used by the forecasting model.
with st.expander("Model parameters"):
    a, b, c = st.columns(3)

    #non-seasonal parameters.
    p = a.number_input("p: filling lags", 0, 13, 4)
    d = b.number_input("d: differences", 0, 1, 1)
    q = c.number_input("q: error lags", 0, 3, 0)

    #seasonal parameters.
    m = a.number_input("m: season length (weeks)", 1, 52, 52)
    sp = b.number_input("sp: seasonal filling lags", 0, 2, 1)
    sd = c.number_input("sd: seasonal differences", 0, 1, 0)
    sq = a.number_input("sq: seasonal error lags", 0, 2, 0)

    grace_period = 25
    max_depth = 5
    leaf_prediction = "mean"
    learning_rate = 0.02
    l2 = 0.001

    if model_name == "Tree":
        grace_period = b.number_input(
            "Tree grace period", 5, 200, 25,
        )
        max_depth = c.number_input(
            "Tree maximum depth", 1, 10, 5,
        )
        leaf_prediction = a.selectbox(
            "Tree leaf prediction",
            ["mean", "model", "adaptive"],
        )

    if model_name == "Linear" or leaf_prediction != "mean":
        learning_rate = b.number_input(
            "Learning rate", 0.0001, 0.1, 0.02,
            format="%.4f",
        )
        l2 = c.number_input(
            "L2 regularisation", 0.0, 0.1, 0.001,
            format="%.4f",
        )

if selected:
    weather_lag = st.slider(
        "Weather lag (weeks)",
        1,
        12,
        1,
    )

    scenario = st.selectbox(
        "Unknown future weather",
        ["Weekly historical mean", "Last known value"],
    )

    st.caption(
        "Future weather inputs are assumptions based only on training history. "
        "Temperature is a weekly mean in °C; precipitation and snowfall "
        "are weekly totals in mm and cm."
    )

st.session_state["forecast_training_start"] = start_date
st.session_state["map_end_date"] = end_date
st.session_state["forecast_horizon_weeks"] = horizon

available = fill.loc[:pd.Timestamp(end_date)]
origin = available.index[-1]

st.session_state["forecast_start_date"] = (
    origin + pd.Timedelta(weeks=1)
).date()

st.session_state["forecast_end_date"] = (
    origin + pd.Timedelta(weeks=horizon)
).date()

st.caption(
    f"Last reservoir report: {origin.date()}. Forecast period: "
    f"{st.session_state['forecast_start_date']} "
    f"to {st.session_state['forecast_end_date']}."
)

if st.button("Run forecast", type="primary"):
    with st.spinner("Preparing data and fitting River…"):
        weather = None

        if selected:
            known_end = (origin - pd.Timedelta(weeks=1)).date()
            hourly, latitude, longitude = (
                st.session_state["load_weather"](
                    area,
                    "data/Budområder/Budområder.shp",
                    start_date - timedelta(weeks=13),
                    known_end + timedelta(days=1),
                )
            )
            
            weather = weekly_weather(hourly)

        #training and forecasting using the selected interface settings.
        train, forecast, future_inputs = dynamic_forecast(
            fill,
            weather,
            start_date,
            end_date,
            horizon,
            (p, d, q, m, sp, sd, sq),
            kind = model_name.lower(),
            learning_rate = learning_rate,
            l2 = l2,
            grace_period = grace_period,
            max_depth = max_depth,
            leaf_prediction = leaf_prediction,
            selected = selected,
            weather_lag = weather_lag,
            scenario = scenario,
            calendar_features = calendar_features,
        )

    if forecast.attrs["clipped"]:
        st.warning(
            f"{forecast.attrs['clipped']} predictions were outside "
            "0–100% and were bounded. Try simpler model orders or a lower learning rate."
        )

    st.caption(
        f"Training observations: {len(train)}. "
        "Press Play or move the slider to reveal the forecast."
    )

    st.plotly_chart(
        forcasting(train, forecast, area),
        use_container_width=True,
        theme="streamlit",
    )

    st.dataframe(forecast, width="stretch")

    if selected:
        # State clearly that the weather represents one point
        # within the selected area.
        st.caption(
            "Weather: ERA5 at the selected area's representative point "
            f"({latitude:.3f}, {longitude:.3f}), aggregated weekly."
        )

        with st.expander("Weather inputs used for the forecast"):
            st.dataframe(
                future_inputs,
                width="stretch",
            )

            st.caption(
                "Weather assumed=True identifies values generated "
                "by the selected scenario."
            )

