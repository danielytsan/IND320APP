import json
from datetime import date, timedelta
import folium
import geopandas as gpd
import pandas as pd
import requests
import streamlit as st
from branca.colormap import LinearColormap
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

st.set_page_config(page_title = "Map and selectors", layout = "wide")
st.title("Map and area selection")

#calling the functions from main page
load_areas = st.session_state["load_areas"]
utc_period = st.session_state["utc_period"]
load_prices = st.session_state["load_prices"]
load_weather = st.session_state["load_weather"]
reservoir = st.session_state["df"].copy()
reservoir["Date"] = pd.to_datetime(reservoir["Date"])
reservoir["Area label"] = reservoir["Area"] + " " + reservoir["Area number"].astype(int).astype(str)

#using tabs
left, right = st.columns(2)

with left:
    color_by = st.selectbox("color by",
                            [
                                "Reservoir filling",
                                "Electricity price",
                                "Weather property",
                            ])

    if color_by == "Electricity price":
        area_type = "EL"
        st.caption("Electricity prices have 5 price areas NO1-NO5")
    else:
        types = {
            "Price areas": "EL",
            "Water areas": "VASS",
            "Norway": "NO",
        }

        current_type = st.session_state.get("reservoir_area", "EL 3").split()[0]
        selected_type = st.selectbox("Area type", list(types), index = list(types.values()).index(current_type), key = "_map_type",)
        area_type = types[selected_type]


with right:
    today = pd.Timestamp.now(tz = "Europe/Oslo").date()

    #historical deafult allows for era5 publication delats
    default_day = min(reservoir["Date"].max().date(), today - timedelta(days = 7),)
    selected_day = st.date_input(
        "Date",
        value = default_day,
        min_value = date(1995, 1, 1),
        max_value = today,
        key = "_map_date",
    )

    if color_by == "Weahter property":
        property_name = st.selectbox("Weather property", ["Temperature", "Precipitation", "Snowfall"],)

#loading the geojson for the chosen area type
geojson = load_areas(area_type)
area_ids = [feature["properties"]["area_id"] for feature in geojson["features"]]

#keeping the previous selection if it belongs to the area type
if st.session_state.get("reservoir_area") not in area_ids:
    st.session_state["reservoir_area"] = "EL 3" if "EL 3" in area_ids else area_ids[0]
selected_area = st.session_state["reservoir_area"]


#weather is aggregated over seven days ending on the selected date
week_start = selected_day - timedelta(days = 6)

#sharing the selcted period for later analisi and forecasing
st.session_state["map_start_date"] = selected_day if color_by == "Electricity price" else week_start
st.session_state["map_end_date"] = selected_day

values = {}
unit = "%"

if color_by == "Reservoir filling":
    #uses the latest NVE report
    eligible = reservoir.loc[reservoir["Date"].le(pd.Timestamp(selected_day)) & reservoir["Area label"].isin(area_ids)]
    latest = eligible.loc[eligible["Date"].eq(eligible["Date"].max())]
    values = dict(zip(latest["Area label"], latest["Fill level"] * 100,))
    report = latest["Date"].max()
    report_label = report.date() if pd.notna(report) else "no report"

    st.caption(f"Latest NVE report on or before {selected_day}:"
               f"{report_label}")

else:
    if color_by == "Electricity price":
        unit = "NOK/kWh"

        st.caption("Daily mean price, exxcluding VAT, gridcages and subsidies"
                   "Source: (httos://www.hvakosterstrommen.no/strompris-api).")

        if selected_day < date(2021, 12, 1):
            st.info("Electricity price history starts on 1. decemebr 2021")
    else:
        variable, method, unit = {
            "Temperature": ("temperature_2m", "mean", "C"),
            "Precipitation": ("precipitation", "sum", "mm"),
            "Snowfall": ("snowfall", "sum", "cm"),
        }[property_name]

        st.caption(f"ERA5, {week_start} to {selected_day}: temperature mean or percipitation/snow total.")

    with st.spinner("Loading map values..."):
        for area in area_ids:
            if color_by == "Electricity price":
                zone = f"NO{area.split()[1]}"
                values[area] = load_prices(zone, selected_day)
            else:
                weather, _, _ = load_weather(
                area,
                None,
                week_start,
                selected_day,
            )

                #checking that period is available
                start, end = utc_period(week_start, selected_day)
                expected_hour = int((end - start) / pd.Timedelta(hours = 1))
                complete = len(weather) == expected_hour
                series = weather[variable]

                if complete and series.notna().all():
                    values[area] = series.mean() if method == "mean" else series.sum()

color = st.get_option("theme.chartSequentialColors")
primary = st.get_option("theme.primaryColor")
valid = pd.Series(values, dtype = float).dropna()

if color_by == "Reservoir filling":
    low, high = 0, 100
elif valid.empty:
    low, high = 0, 1
else:
    low, high = float(valid.min()), float(valid.max())

#the color scale needs different upper and lower limit
if low == high:
    low, high = low - 0.5, high + 0.5

legend_name = property_name if color_by == "Weahter property" else color
legend = LinearColormap(
    color,
    vmin = low,
    vmax = high,
    caption = f"{legend_name} ({unit})",
)

#adding display vlaues and oclor to the geosjon
for feature in geojson["features"]:
    area = feature["properties"]["area_id"]
    value = values.get(area, float("nan"))

    if pd.notna(value):
        feature["properties"]["value"] = f"{value:.2f} {unit}"
        feature["properties"]["fill"] = legend(value)
    else:
        feature["properties"]["value"] = "no data"
        feature["properties"]["value"] = "#9CA3AF"

#creating the map using folium
map_object = folium.Map(
    location = [65, 14],
    zoom_start = 4, 
    tiles = "OpenStreetMap",
)

map_object.get_root().header.add_child(
    folium.Element(
        "<style>"
        ".leaflet-container, .leaflet-tooltip, .legend"
        "</style>"
    )
)

#add transparent fills with thin outlines
folium.GeoJson(
    geojson,
    style_function = lambda feature: {
        "fillColor": feature["properties"]["fill"],
        "fillOpacity": 0.45,
        "color": "#555555",
        "weight": 1,
    },
    tooltip = folium.GeoJsonTooltip(
        fields = ["area_id", "value"],
        aliases = ["Area", "Value"],
    ),
).add_to(map_object)

#drawing thicker outline around the selected area
selection = {
    "type": "FeatureCollection",
    "features": [feature for feature in geojson["features"] if feature["properties"]["area_id"] == selected_area],
}

folium.GeoJson(
    selection,
    style_function = lambda feature:{
        "fillOpacity": 0,
        "color": primary,
        "weight": 5,
    },
    interactive = False,
).add_to(map_object)

result = st_folium(
    map_object,
    key = f"map_{area_type}",
    height = 600,
    use_container_width = True,
    returned_objects = ["last_clicked"],
)

#finding area containing the clicked location
clicked = (result or {}).get("last_clicked")

if clicked:
    event = area_type, clicked["lat"], clicked["lng"]
    #process each new click
    if event != st.session_state.get("_map_last_click"):
        st.session_state["_map_last_click"] = event

        #getting longitude first
        point = Point(clicked["lng"], clicked["lat"])
        for feature in geojson["features"]:
            if shape(feature["geometry"]).covers(point):
                area = feature["properties"]["area_id"]
                if area != selected_area:
                    st.session_state["reservoir_area"] = area
                    st.rerun()


st.success(f"Selected area: {st.session_state['reservoir_area']}")

st.caption("The thick outline shows the selected area."
           "Grey areas have missing or incomplete data."
           "Boundaries and filling: NVE. Weather: Open-meteo ERA5")
