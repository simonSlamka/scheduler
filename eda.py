import pandas as pd
import json
from matplotlib import pyplot as plt
import mplcyberpunk
from m3u_parser import M3uParser

m = "data/sad.m3u"
parser = M3uParser()
parser.parse_m3u(m)
tracks = parser.get_list()
sad = []
for t in tracks:
    sad.append(t["name"])
m = "data/intro.m3u"
parser = M3uParser()
parser.parse_m3u(m)
tracks = parser.get_list()
intro = []
for t in tracks:
    intro.append(t["name"])

sadTracks = pd.DataFrame(sad, columns=["track"])
introTracks = pd.DataFrame(intro, columns=["track"])
# the artist name is the first part of the track name, before the first hyphen
negArtists = sadTracks["track"].str.split(" - ").str[0]
negArtists = negArtists[~negArtists.isin(["Imagine Dragons", "The Chainsmokers", "OneRepublic", "Sandro Cavazza", "Kygo", "Avicii"])]

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

# get count of when listened to "Falling in Reverse" over time since start of data
fir = c[c.iloc[:, 0] == "Falling in Reverse"]
# now, count occurences of `negArtists` in `c  over time
neg = c[c.iloc[:, 0].isin(negArtists)]
print(f"neg head: {neg.head()}")

# get the top 3 negative tracks and count of listens
print(f"Top 3 negative tracks: {neg.iloc[:, 2].value_counts().head(3)}")

firDailySums = fir.resample("D", on="date").size()
negDailySums = neg.resample("D", on="date").size()
# outer join the two series
sadSums = firDailySums.combine(negDailySums, max, fill_value=0)

sadSumsMovingAvg = sadSums.rolling(7).mean()

plt.style.use("cyberpunk")
plt.figure(figsize=(20, 5))

plt.plot(sadSumsMovingAvg.index, sadSumsMovingAvg, color="red", linewidth=3)
plt.title("m3u playlist-based negative tracks listens (7-day MA)")
plt.xlabel("Date")
plt.ylabel("Listens (7-day MA)")

# print every other month on the x-axis. don't print days, since there's too many
plt.xticks(sadSumsMovingAvg.index[::90], [date.strftime('%b %Y') for date in sadSumsMovingAvg.index[::90]], rotation=45)

plt.axhspan(sadSumsMovingAvg.min(), sadSumsMovingAvg.quantile(0.25), color='green', alpha=0.3)
plt.axhspan(sadSumsMovingAvg.quantile(0.25), sadSumsMovingAvg.quantile(0.5), color='yellow', alpha=0.3)
plt.axhspan(sadSumsMovingAvg.quantile(0.5), sadSumsMovingAvg.quantile(0.75), color='orange', alpha=0.3)
plt.axhspan(sadSumsMovingAvg.quantile(0.75), sadSumsMovingAvg.max(), color='red', alpha=0.3)

plt.legend(["7-day MA", "Happy (25th-50th quant)", "Mostly fine (50th-75th quant)", "Sad (75th-100th quant)", "Extremely sad (100th quant)"])

plt.tight_layout()
plt.savefig("sad_7day_ma.png")
plt.show()

# plt.plot(listenedTracksDailySums.index, listenedTracksDailySums, color="red")
# plt.plot(dailiyHours.index, dailiyHours, color="orange")
# plt.plot(dailiyHoursMovingAvg.index, dailiyHoursMovingAvg, color="black", linewidth=3)
# plt.title("Daily Active WakaTime Time")
# plt.xlabel("Date")
# plt.ylabel("Active Time (hours)")