import pandas as pd
import json
from matplotlib import pyplot as plt
import mplcyberpunk

j = json.load(open("data/wakatime-smdexec000protonmail.ch-70f280d92d7342e5894da0d0f2acbd75.json"))
# now, read the csv from Last.FM and display head
c = pd.read_csv("data/lastfm.csv")
print(c.head())
# the first col is the artist, the third is the track, and the last is the date + time
print(f"Artist: {c.iloc[0, 0]}, Track: {c.iloc[0, 2]}, Date: {c.iloc[0, 3]}")

print(f"Most listened-to artist: {c.iloc[:, 0].value_counts().idxmax()} | Track: {c.iloc[:, 2].value_counts().idxmax()}")

# now, let's construct a df so that we can plot this over the wakatime plot
c["date"] = pd.to_datetime(c.iloc[:, 3], utc=True)

# reciew the json data
print("keys:", j.keys())

# there is a key called "days". explore it
print("keys of days:", j["days"][0].keys())

# in there, there is "date". show it
print("keys of heartbeats in days:", j["days"][-1]["heartbeats"][0].keys())

# print "time" of the last heartbeat
print("time of the last heartbeat:", j["days"][-1]["heartbeats"][-1]["time"])

days = j["days"]

heartbeats: pd.DataFrame = pd.DataFrame([{
	**hb,
	"date": day["date"]
} for day in days for hb in day["heartbeats"]])

print(heartbeats.head())

heartbeats["created_at"] = pd.to_datetime(heartbeats["created_at"], utc=True)
heartbeats["created_at"] = heartbeats["created_at"].dt.tz_localize(None)

heartbeats = heartbeats.sort_values("created_at")

heartbeats["block"] = heartbeats["created_at"].dt.floor("15min")

heartbeats["dur"] = pd.Timedelta(minutes=1)
heartbeats.loc[heartbeats["block"].duplicated(keep=False), "dur"] = pd.Timedelta(minutes=15)

heartbeats = heartbeats.drop_duplicates(subset=["block"])

totalActiveTimeInHours = heartbeats["dur"].sum().total_seconds() / 3600

print("Total active time in hours:", totalActiveTimeInHours)

heartbeats["date"] = heartbeats["block"].dt.date

dailies = heartbeats.resample("D", on="created_at")["dur"].sum()
dailiyHours = dailies.dt.total_seconds() / 3600
# add moving avg
dailiyHoursMovingAvg = dailiyHours.rolling(28).mean()

for day in range(7):
	print(f"Most active hours for day {day}:", heartbeats[heartbeats["created_at"].dt.dayofweek == day].resample("h", on="created_at")["dur"].sum().idxmax())

# get the most productive hours of the entire dataset
print("Most active hours:", heartbeats.resample("h", on="created_at")["dur"].sum().idxmax())

listenedTracksHourlySums = c.resample("h", on="date").size()
listenedTracksDailySums = c.resample("D", on="date").size()

plt.style.use("cyberpunk")
plt.figure(figsize=(20, 5))
# plt.plot(listenedTracksDailySums.index, listenedTracksDailySums, color="red")
plt.plot(dailiyHours.index, dailiyHours, color="orange")
plt.plot(dailiyHoursMovingAvg.index, dailiyHoursMovingAvg, color="black", linewidth=3)
plt.title("Daily Active WakaTime Time")
plt.xlabel("Date")
plt.ylabel("Active Time (hours)")
plt.tight_layout()
plt.show()
