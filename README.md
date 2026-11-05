# IND320 APP

- [GitHub repository](https://github.com/danielytsan/IND320APP)
- [Streamlit app](https://ind320app-s2bytfwvqxbzmwkxrm2aze.streamlit.app)
- [Jupyter Notebook](notebooks/Part2.ipynb)


# Project structure

```text
IND320APP/
├── main_page.py
├── requirements.txt
├── .streamlit/
│   └── secrets.toml
├── data/
│   └── reservoirs.csv
├── notebooks/
│   ├── Part1.ipynb
│   └── Part2.ipynb
└── pages/
    ├── Page 1 (LineChartColumn).py
    ├── Page 2 (Plot of data).py
    └── Page 3 (MongoDB data).py

```

## Data

In this project we are using MongoDB and magasinstatistikk where we reed this using pandas

Streamlit is containing 4 pages in total:
1. Main page
2. LineChartColumn
3. Plot of data
4. MongoDB data