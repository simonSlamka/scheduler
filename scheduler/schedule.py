# scheduler/schedule.py
"""This module contains the Schedule class for scheduling tasks."""

from datetime import datetime
from typing import List, Tuple

import pandas as pd


class Schedule:
    def __init__(self, tasks: List[str], hoursWaka: List[Tuple[datetime, int]], hoursAndMoodsLastfm: List[Tuple[datetime, str, str]]):
        self.tasks = tasks
        self.hoursWaka = hoursWaka
        self.hoursAndMoodsLastfm = hoursAndMoodsLastfm

    def estimate_optimal_waka_hours(self) -> pd.DataFrame:
        """
        This method estimates the optimal hours for WakaTime usage based on the data provided in the constructor.
        
        @return: a DataFrame with the hours and the amount of times they occur.
        """
        # here, we need to collect all the hours from the WakaTime data and find which ones occur the most (within a day, each day of the week)
        # we can then return a DataFrame with the hours and the amount of times they occur
        optimal = pd.DataFrame(self.hoursWaka, columns=["date", "hour"]).set_index("date")
        optimal["hour"] = optimal["hour"].dt.hour
        return optimal["hour"].value_counts().sort_index()  # this will return a Series with the hours as the index and the amount of times they occur as the values
