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

st.title("Reservoirs Data")
st.header("This is the main page")
st.write("Welcome to the main page of my streamlit app on the left side you can navigate between the pages I hope you enjoy the app and find it useful")

#loading the data and caching
@st.cache_data
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

@st.cache_resource
def get_mongo_data():
    uri = f"mongodb+srv://open_for_all:{st.secrets['db_password']}@cluster0.esy9giu.mongodb.net/"

    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    return client

st.session_state["mongo_client"] = get_mongo_data()

@st.cache_data
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

@st.cache_data
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

#loading data and caching from open meteo
@st.cache_data
def load_weather(area, shapefile, start_date, end_date):
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
                                "start_date": start_date.isoformat(),
                                "end_date": end - pd.Timedelta(seconds = 1).date().isoformat(),
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