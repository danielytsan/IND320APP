import pandas as pd
import geopandas as gpd
import streamlit as st
import requests
import json
from datetime import timedelta
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

#configuring the page
st.set_page_config(page_title = "Main page", initial_sidebar_state = "expanded")

def home():
    st.title("This is the main page of the streamlit app")

    st.write("Explore Norwegian resercoirs, weather and electricity data.")

    st.markdown("""
        - **Eplore:** Reservoir data overview, Cross-boarder electricity flows, and Map and area selection
        - **Analysis:** Reservoir analysis, Weather anomalies, and Weather and reservoir correlation
        - **Prediction:** Forecasting of water magazine filling
    """)


@st.cache_data(ttl = 3600, max_entries = 1, show_spinner = "Loading reservoir data…")
def get_data():
    #importing data form magasinstatistikk through API url and converting it into a pandas dataframe
    response = requests.get(st.secrets["magasinstatistikk_url"], timeout = 30)
    response.raise_for_status()

    df = pd.DataFrame(response.json())

    df.columns = [
    "Date",
    "Area",
    "Area number",
    "Year",
    "Week",
    "Fill level",
    "Capacity in TWh",
    "Stored energy in TWh",
    "Next publication",
    "Previous week fill level",
    "Fill level change"
    ]
    return df

st.session_state["df"] = get_data()


@st.cache_resource(show_spinner = "Preparing the database connection…")
def get_mongo_data():
    uri = f"mongodb+srv://open_for_all:{st.secrets['db_password']}@cluster0.esy9giu.mongodb.net/"

    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    return client

st.session_state["mongo_client"] = get_mongo_data()


@st.cache_data(max_entries = 3, show_spinner = "Loading area boundaries…")
def load_areas(area_type):
    if area_type in ("EL", "NO"):
        areas = gpd.read_file("data/Budområder/Budområder.shp")
        #converting shapefile labels such as no3 to el3
        numbers = areas["budomr"].str.extract(r"(\d+)")[0]
        areas["area_id"] = "EL " + numbers
        if area_type == "NO":
            areas["area_id"] = "NO 0"

    else:
        areas = gpd.read_file("data/NVE_Region/NVE_Region.shp", encoding = "utf-8")

        #combine regions
        areas["area_id"] = areas["REGION"].str.strip().map({
            "RS": "VASS 1",
            "RØ": "VASS 1",
            "RV": "VASS 2",
            "RM": "VASS 3",
            "RN": "VASS 3",
        })

    areas = areas[["area_id", "geometry"]].dissolve(by = "area_id").to_crs(4326)

    #select one stable point inside each area for weather data
    points = areas.geometry.representative_point()
    areas["latitude"] = points.y
    areas["longitude"] = points.x
    areas["area_id"] = areas.index

    #convert to geojson
    return json.loads(areas.to_json())
st.session_state["load_areas"] = load_areas

def utc_period(start_date, end_date):
    #using norwegion calendar and separating midnights
    start = pd.Timestamp(start_date).tz_localize("Europe/Oslo").tz_convert("UTC")
    end = pd.Timestamp(end_date + timedelta(days = 1)).tz_localize("Europe/Oslo").tz_convert("UTC")

    return start, end

st.session_state["utc_period"] = utc_period

@st.cache_data(ttl = 3600, max_entries = 256, show_spinner = "Loading electricity prices…")
def load_prices(zone, day):
    #finding api on hvakosterstrommen.no
    url = "https://www.hvakosterstrommen.no/api/v1/prices/"f"{day:%Y}/{day:%m-%d}_{zone}.json"
    response = requests.get(url, timeout = 20)
    response.raise_for_status()
    prices = pd.DataFrame(response.json())
    prices["start"] = pd.to_datetime(prices["time_start"], utc = True) 
    prices["end"] = pd.to_datetime(prices["time_end"], utc = True) 
    prices = prices.sort_values("start")
    start, end = utc_period(day, day)

    #checks that intervals cover the entire day without gaps and overlaps
    contiguous = (prices["start"].iloc[1:].reset_index(drop = True) == prices["end"].iloc[:-1].reset_index(drop = True)).all()
    duration = prices["end"] - prices["start"]
    hours = duration.dt.total_seconds() / 3600

    return float((prices["NOK_per_kWh"] * hours).sum() / hours.sum())

st.session_state["load_prices"] = load_prices

#cacheing each weather request for one day.
@st.cache_data(max_entries = 32, show_spinner = "Loading weather data…")
def load_weather(area, shapefile, start_date, end_date):
    if response.status_code == 429:
        st.warning("The api limit has been reached, sorry for that")
        st.stop()
    response.raise_for_status()
    features = load_areas(area.split()[0])["features"]
    location = next(
        feature["properties"]
        for feature in features if feature["properties"]["area_id"] == area
    )
    start, end = utc_period(start_date, end_date)

    #requst hour ERA5 data
    response = requests.get(st.secrets["open_meteo"], 
                            params = {
                                "latitude": location["latitude"],
                                "longitude": location["longitude"],
                                "start_date": start.date().isoformat(),
                                "end_date": (end - pd.Timedelta(seconds = 1)).date().isoformat(),
                                "hourly": "temperature_2m,precipitation,snowfall",
                                "models": "era5",
                                "timezone": "GMT"
                            }, timeout = 30)
    response.raise_for_status()
    weather = pd.DataFrame(response.json()["hourly"])
    weather["time"] = pd.to_datetime(weather["time"], utc = True)
    weather = weather.loc[weather["time"].ge(start) & weather["time"].lt(end)]
    
    return weather, location["latitude"], location["longitude"]

st.session_state["load_weather"] = load_weather

pages = {"":[
    st.Page(home, title = "Home", default = True,),
    ],

    "Explore": [
        st.Page("pages/Map explorer.py", title = "Map and area selection",),
        st.Page("pages/Date overview.py", title = "Reservoir data overview",),
        st.Page("pages/Cross-boarder flow.py", title = "Cross-boarder electricity flows",),
    ],

    "Analysis": [
        st.Page("pages/Reservoir analysis.py", title = "Reservoir analysis",),
        st.Page("pages/Weather analysis.py", title = "Weather anomalies",),
        st.Page("pages/Weather and reservoir correlation.py", title = "Weather and reservoirs correlation",),
    ],

    "Prediction": [st.Page("pages/Forecasting.py", title = "Forcasting of water magazine filling",),],
}

selected_page = st.navigation(pages, position = "sidebar", expanded = True,)
selected_page.run()
