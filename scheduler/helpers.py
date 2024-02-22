# scheduler/helpers.py
"""This module contains helper functions for the scheduler module."""

import pandas as pd
import json

def load_lastfm():
    return pd.read_csv("data/lastfm.csv")

def load_wakatime():
    with open("data/wakatime-smdexec000protonmail.ch-70f280d92d7342e5894da0d0f2acbd75.json") as f:
        return json.load(f)

def load_heartbeats():
    j = load_wakatime()
    days = j["days"]
    heartbeats: pd.DataFrame = pd.DataFrame([{
        **hb,
        "date": day["date"]
    } for day in days for hb in day["heartbeats"]])

    heartbeats["created_at"] = pd.to_datetime(heartbeats["created_at"], utc=True)
    heartbeats["created_at"] = heartbeats["created_at"].dt.tz_localize(None)

    heartbeats = heartbeats.sort_values("created_at")

    heartbeats["block"] = heartbeats["created_at"].dt.floor("15min")

    heartbeats["dur"] = pd.Timedelta(minutes=1)
    heartbeats.loc[heartbeats["block"].duplicated(keep=False), "dur"] = pd.Timedelta(minutes=15)

    heartbeats = heartbeats.drop_duplicates(subset=["block"])

    return heartbeats

def get_waka_total_active_time_in_hours():
    heartbeats = load_heartbeats()
    return heartbeats["dur"].sum().total_seconds() / 3600

def get_waka_daily_hours():
    heartbeats = load_heartbeats()
    dailies = heartbeats.resample("D", on="created_at")["dur"].sum()
    return dailies.dt.total_seconds() / 3600

def get_waka_specific_daily_hours():
    heartbeats = load_heartbeats()
    return heartbeats.resample("D", on="created_at")["dur"].sum()

def get_lastfm_most_listened_to():
    c = load_lastfm()
    return c.iloc[:, 0].value_counts().idxmax(), c.iloc[:, 2].value_counts().idxmax()

def get_lastfm_total_tracks():
    c = load_lastfm()
    return c.shape[0]

def get_lastfm_daily_tracks():
    c = load_lastfm()
    return c.resample("H", on="date").size()