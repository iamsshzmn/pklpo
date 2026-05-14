import os

import pandas as pd
import plotly.graph_objs as go
import psycopg2
from dash import Dash, Input, Output, dcc, html

from src.models import INDICATORS_TABLE_NAME

# --- Настройки подключения ---
conn = psycopg2.connect(
    dbname="pklpo",
    user="pklpo_user",
    password=os.environ.get("PKLPO_DB_PASSWORD", ""),
    host="localhost",
    port="5432",
)


# --- Получение доступных символов и таймфреймов ---
def get_symbols_timeframes():
    df = pd.read_sql("SELECT DISTINCT symbol, timeframe FROM ohlcv", conn)
    return df["symbol"].unique(), df["timeframe"].unique()


symbols, timeframes = get_symbols_timeframes()

# --- Dash-приложение ---
app = Dash(__name__)
app.layout = html.Div(
    [
        html.H1("Визуализация OHLCV, индикаторов и комбинаций"),
        html.Label("Symbol:"),
        dcc.Dropdown(
            id="symbol",
            options=[{"label": s, "value": s} for s in symbols],
            value=symbols[0],
        ),
        html.Label("Timeframe:"),
        dcc.Dropdown(
            id="timeframe",
            options=[{"label": t, "value": t} for t in timeframes],
            value=timeframes[0],
        ),
        html.Label("Таблица:"),
        dcc.RadioItems(
            id="table",
            options=[
                {"label": "OHLCV", "value": "ohlcv"},
                {"label": "Indicators", "value": "indicators"},
                {"label": "Combinations", "value": "indicator_combinations"},
            ],
            value="ohlcv",
            inline=True,
        ),
        dcc.Graph(id="main-graph"),
    ]
)


@app.callback(
    Output("main-graph", "figure"),
    Input("symbol", "value"),
    Input("timeframe", "value"),
    Input("table", "value"),
)
def update_graph(symbol, timeframe, table):
    if table == "ohlcv":
        query = "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol = %s AND timeframe = %s ORDER BY ts ASC"
        df = pd.read_sql(query, conn, params=(symbol, timeframe))
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        data = [
            go.Candlestick(
                x=df["ts"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
            ),
            go.Bar(
                x=df["ts"],
                y=df["volume"],
                name="Volume",
                yaxis="y2",
                marker_color="lightblue",
            ),
        ]
        layout = go.Layout(
            title=f"{symbol} {timeframe} OHLCV",
            xaxis={"title": "Time"},
            yaxis={"title": "Price"},
            yaxis2={
                "title": "Volume",
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
            },
            height=700,
        )
        return go.Figure(data=data, layout=layout)

    if table == "indicators":
        query = (
            f"SELECT * FROM {INDICATORS_TABLE_NAME} "
            "WHERE symbol = %s AND timeframe = %s ORDER BY timestamp ASC"
        )
        df = pd.read_sql(query, conn, params=(symbol, timeframe))
        df["ts"] = pd.to_datetime(df["timestamp"], unit="ms")
        # Визуализируем close + несколько индикаторов (например, MACD, RSI)
        data = [
            go.Scatter(x=df["ts"], y=df["close"], name="Close", line={"color": "black"})
        ]
        for col in ["macd", "rsi14", "ema21", "bb_upper", "bb_lower"]:
            if col in df.columns:
                data.append(go.Scatter(x=df["ts"], y=df[col], name=col))
        layout = go.Layout(
            title=f"{symbol} {timeframe} Indicators",
            xaxis={"title": "Time"},
            yaxis={"title": "Value"},
            height=700,
        )
        return go.Figure(data=data, layout=layout)

    if table == "indicator_combinations":
        # Пример: визуализируем первую попавшуюся комбинацию
        query = """
            SELECT * FROM indicator_combinations
            WHERE symbol = %s AND timeframe = %s
            ORDER BY ts ASC
            LIMIT 500
        """
        df = pd.read_sql(query, conn, params=(symbol, timeframe))
        if df.empty:
            return go.Figure()
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        # Вытаскиваем значения value_1...value_10
        value_cols = [col for col in df.columns if col.startswith("value_")]
        data = []
        for col in value_cols:
            data.append(go.Scatter(x=df["ts"], y=df[col], name=col))
        layout = go.Layout(
            title=f'{symbol} {timeframe} Combination: {df.iloc[0]["combination"]}',
            xaxis={"title": "Time"},
            yaxis={"title": "Value"},
            height=700,
        )
        return go.Figure(data=data, layout=layout)
    return None


if __name__ == "__main__":
    app.run_server(debug=True)
