"""This module is responsible for defining the base class for Hours. An Hour is the smallest unit of time in the schedule."""

from typing import List, Tuple
from datetime import datetime, timedelta
from ABCs import ABC, abstractmethod

from task import Task


class Hour(ABC):
    """
    This class represents an hour in the schedule.

    An hour is the smallest unit of time in the schedule. It has a start and end datetime, a value in USD, and a priority.
    """
    def __init__(self, start: datetime, end: datetime, value: float = 0, priority: int = 0):
        """
        This method initializes the Hour object.

        @param start: the start datetime of the hour.
        @param end: the end datetime of the hour.
        @param value: the value of the hour in USD.
        @param priority: the priority of the hour (10 is the lowest, 1 is the highest).
        """
        self._start = start
        self._end = end
        self._value = value
        self._priority = priority
        self._tasks: List[Task] = []

    @abstractmethod
    def add_task(self, task: Task) -> None:
        """
        This method adds a task to the hour.

        @param task: the task to be added to the hour.
        """
        pass

    @abstractmethod
    def remove_task(self, task: Task) -> None:
        """
        This method removes a task from the hour.

        @param task: the task to be removed from the hour.
        """
        pass

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, start: datetime) -> None:
        self._start = start

    @property
    def end(self) -> datetime:
        return self._end

    @end.setter
    def end(self, end: datetime) -> None:
        self._end = end
