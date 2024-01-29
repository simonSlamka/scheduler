import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from tqdm import tqdm
from termcolor import colored
from calendar import monthrange
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
import logging
import argparse
import matplotlib.pyplot as plt
from matplotlib.table import Table
from pandas.plotting import table

parser = argparse.ArgumentParser(description="Wolter")
parser.add_argument("--target", type=float, default=0, help="Target earnings for current cycle (in USD)", nargs="?", const=0)
args = parser.parse_args()

logging.basicConfig(level=logging.INFO)


### Constants ###
Tweeks = 16  # total n of weeks
ThoursWeek = 21  # total n of hours/week
Cedu = 5000  # total cost of tech to purchase
Cbuf = 2500  # buffer
Cdating = 1000  # dating budget
CdebtRepayment = 11764.76  # debt repayment budget
CdebtRepaymentSeg1 = CdebtRepayment * 0.11 # debt repayment budget, segment 1
CdebtRepaymentSeg2 = CdebtRepayment * 0.11 # debt repayment budget, segment 2
CdebtRepaymentSeg3 = CdebtRepayment * 0.15 # debt repayment budget, segment 3
CdebtRepaymentSeg4 = CdebtRepayment * 0.63 # debt repayment budget, segment 4
taxRate = 0.46  # tax rate
taxThreshold = 619.43  # tax threshold in USD
usdToDkk = 6.84  # USD to DKK conversion rate, as of 2024-01-16 (YYYY-MM-DD)

def calculate_tax_and_earnings(cycleEarnings):
	earningsThisYearThusFar = df[df["year"] == datetime.now().year]["Rimmediate"].sum()
	if earningsThisYearThusFar <= 7200:
		taxRate = 0.0 # 0% tax rate for the first 7200 USD earned in a year
	taxable = max(0, cycleEarnings - (taxThreshold / 2))
	taxToPay = taxable * taxRate
	netProfit = cycleEarnings - taxToPay
	return netProfit, taxToPay

def calculate_intermediate_net_earnings(df, freq):
	df['dt'] = pd.to_datetime(df["dt"])
	df.set_index("dt", inplace=True)
	resampledDf = df['Rimmediate'].resample(freq).sum()
	netProfit = []
	for periodProfit in resampledDf:
		net, _ = calculate_tax_and_earnings(pd.DataFrame({"Rimmediate": [periodProfit]}))
		netProfit.append(net)
	return np.array(netProfit).mean()

def calculate_cycle_earnings(df, y, m, cycle):
	cycleDf = df[(df["year"] == y) & (df["month"] == m) & (df["cycle"] == cycle)]
	earnings = cycleDf["Rimmediate"].sum()
	netProfit, taxToPay = calculate_tax_and_earnings(earnings)
	return netProfit, taxToPay

def render_pbar(total, n, desc, color):
	pbar = tqdm(total=total, desc=colored(desc, color))
	pbar.n = n if n > 0 else 0
	pbar.last_print_n = n if n > 0 else 0
	pbar.refresh()
	pbar.close()

def get_current_cycle():
	today = datetime.now()
	mid = 15
	last = monthrange(today.year, today.month)[1]

	if today.day <= mid:
		start = today.replace(day=1)
		end = today.replace(day=mid)
		payoutDate = today.replace(day=25) if today.day != mid else (today.replace(day=1) + timedelta(months=1)).replace(day=25)
	else:
		start = today.replace(day=mid + 1)
		end = today.replace(day=last)
		payoutDate = today.replace(day=10, month=today.month + 1) if today.month != 12 else today.replace(day=10, month=1, year=today.year + 1)

	return start, end, payoutDate

def what_would_happen_if_i_didnt_work_on(date, df):
	# TODO: not working as expected, the predicted earnings are higher than what we predict for the current cycle (which is unlikely)
	# get all dates until now
	all = pd.date_range(start=df['dt'].min(), end=df['dt'].max())
	all = pd.DataFrame({"dt": all})
	df = all.merge(df, on="dt", how="left")
	df["Rimmediate"].fillna(0, inplace=True)

	# get all dates until now, but not including the date we want to predict
	df = df[df["dt"] < date]

	# get all dates until now, but not including the date we want to predict, and not including days with no earnings
	df = df[df["Rimmediate"] > 0]

	# get all dates until now, but not including the date we want to predict, and not including days with no earnings, and group by day
	df = df.groupby("dt")["Rimmediate"].sum().reset_index()

	# predict earnings at the end of current cycle, given that `date` is zero
	pred = predict_cycle_earnings(df, date.year, date.month, 1 if date.day <= 15 else 2)

	# pay tax on predicted earnings
	pred, taxToPay = calculate_tax_and_earnings(pred)

	return pred, taxToPay

def gen_schedule_for_cycle(df, y, m, cycle, targetEarnings):
	start, end = get_cycle_dates(y, m, cycle)
	today = datetime.now().date()

	bResumeAfterBreak = False

	if y == today.year and m == today.month and cycle == (1 if today.day <= 15 else 2):
		start = today + timedelta(days=1) # start from tomorrow
		# if we're resuming work after a break of at least 3 days, start easy, with only 2 hours max
		# if (today - pd.to_datetime(df["dt"]).max().date()).days >= 3:
		# 	bResumeAfterBreak = True
		# 	print(colored("Resuming work after a break of at least 3 days, starting easy with only 2 hours max", "yellow"))
		pass

	df["dt"] = pd.to_datetime(df["dt"])
	df["hour"] = pd.to_datetime(df["hour"], format="%I%p").dt.hour

	hourlies = df.groupby(["dt", "hour"])["Rimmediate"].sum().reset_index()

	schedule = []
	currentCycleEarnings = df[(df["year"] == y) & (df["month"] == m) & (df["cycle"] == cycle)]["Rimmediate"].sum()
	remaining = targetEarnings - (currentCycleEarnings if currentCycleEarnings < targetEarnings else 0)

	# firstDay = True # ! unused

	# peaks
	for date in pd.date_range(start, end):
		if date.weekday() >= 4: # peak days
			for hour in range(16, 23): # peak hours
				avg = hourlies[(hourlies["dt"].dt.dayofweek == date.weekday()) & (hourlies["hour"] == hour)]["Rimmediate"].mean()
				if avg > 0:
					schedule.append((date.strftime("%Y-%m-%d"), f"{hour}:00", avg))
					remaining -= avg
					if remaining <= 0:
						return schedule, remaining

	# non-peaks
	for date in pd.date_range(start, end):
		if date.weekday() < 4 or (date.weekday() >= 4 and hour < 17 or hour > 20):
			for hour in range(17, 20):
				if date.weekday() >= 4:
					continue
				avg = hourlies[(hourlies["dt"].dt.dayofweek == date.weekday()) & (hourlies["hour"] == hour)]["Rimmediate"].mean()
				if avg > 0:
					schedule.append((date.strftime("%Y-%m-%d"), f"{hour}:00", avg))
					remaining -= avg
					if remaining <= 0:
						return schedule, remaining

	return schedule, remaining

def get_days_in_month(y, m):
	return monthrange(y, m)[1]

def get_cycle_dates(y, m, cycle):
	if cycle == 1:
		start = datetime(y, m, 1)
		mid = datetime(y, m, 15)
		return start, mid
	else:
		mid = datetime(y, m, 16)
		end = datetime(y, m, get_days_in_month(y, m))
		return mid, end

def predict_cycle_earnings(df, y, m, cycle):
	dailies = df.copy()
	dailies = dailies.groupby("dt")["Rimmediate"].sum().reset_index() # sum earnings for each day (this also fills days with no earnings with 0 to prevent NaNs)
	dailies["dt"] = pd.to_datetime(dailies["dt"]).apply(lambda x: x.toordinal()) # convert dates to ordinal
	
	if dailies.empty:
		raise ValueError("No data to predict from")

	linreg = LinearRegression()
	linreg.fit(dailies[["dt"]], dailies["Rimmediate"])

	dtree = DecisionTreeRegressor(max_depth=3)
	dtree.fit(dailies[["dt"]], dailies["Rimmediate"])

	rforest = RandomForestRegressor()
	rforest.fit(dailies[["dt"]], dailies["Rimmediate"])

	# TODO: tune hyperparams
	svm = SVR(kernel="rbf", C=100, gamma=0.15, epsilon=.1) # C is the penalty parameter of the error term, gamma is the kernel coefficient for rbf, poly and sigmoid, and epsilon is the epsilon in the epsilon-SVR model
	svm.fit(dailies[["dt"]], dailies["Rimmediate"])

	start, end = get_cycle_dates(y, m, cycle)
	next = pd.DataFrame([date.toordinal() for date in pd.date_range(start, end)], columns=["dt"])
	logging.debug(f"Predicted cycle: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")

	logging.debug(f"Last date in dataset: {datetime.fromordinal(dailies['dt'].max())} with an Rimmediate of {dailies[dailies['dt'] == dailies['dt'].max()]['Rimmediate'].values[0]}")

	preds = {"linreg": linreg.predict(next), "dtree": dtree.predict(next), "rforest": rforest.predict(next), "svm": svm.predict(next)}

	pred = np.array(list({key: val.sum() for key, val in preds.items()}.values())).mean()

	# if any model's pred is too far from the mean, throw a warning
	for model, modelPred in preds.items():
		if abs(modelPred.sum() - pred) > 0.75 * pred:
			logging.warning(f"Predicted earnings for {model} are too far from the mean: {modelPred.sum()}")

	return pred

try:
	df = pd.read_csv("log.csv")
	df["dt"] = pd.to_datetime(df["dt"]).dt.strftime("%Y-%m-%d")
except FileNotFoundError:
	df = pd.DataFrame(columns=["dt", "hour", "Rimmediate"])

if "dt" in df.columns:
	df["month"] = pd.to_datetime(df["dt"]).dt.month
	df["year"] = pd.to_datetime(df["dt"]).dt.year
	df["cycle"] = np.where(pd.to_datetime(df["dt"]).dt.day <= 15, 1, 2)

start, end, payoutDate = get_current_cycle()
currentCycle = 1 if datetime.now().day <= 15 else 2
currentPeriodProfit, currentPeriodTaxToPay = calculate_cycle_earnings(df, datetime.now().year, datetime.now().month, currentCycle)

if args.target == 0:
	while True:
		hoursInput = input("Hour|Rimmediate (\"stop\" to break): ")
		if hoursInput.lower() == "stop" or hoursInput == "":
			break
		timeNow = datetime.now().strftime("%Y-%m-%d")
		hour, Rimmediate = hoursInput.split("|")
		Rimmediate = float(Rimmediate)
		df = pd.concat([df, pd.DataFrame({"dt": [timeNow], "hour": [hour], "Rimmediate": [Rimmediate], "month": [datetime.now().month], "year": [datetime.now().year], "cycle": [currentCycle]}).dropna()], ignore_index=True, sort=False)

	df.to_csv("log.csv", index=False)

# convert to datetime again
df["dt"] = pd.to_datetime(df["dt"])

Ttotal = Tweeks * ThoursWeek - len(df)  # total hours to work
Ce = 1000 if currentCycle == 1 else 300
Ctotal = Cedu + (Ce * (Tweeks/4)) + Cbuf + Cdating + CdebtRepayment  # total cost

if not df.empty:
	all = pd.date_range(start=df["dt"].min(), end=df["dt"].max() + timedelta(days=1) if datetime.now().day != df["dt"].max().day else df["dt"].max()) # add one day if today is not the last day in the dataset
	all = pd.DataFrame({"dt": all})
	df = all.merge(df, on="dt", how="left")
	df["Rimmediate"].fillna(0)

# calc earnings and stats (including means and running avgs) for both current cylce, all until now, and future
## totals
cumEarnings = 0
cumNetProfit = 0
cumTaxToPay = 0

for year in df["year"].unique():
	for month in df["month"].unique():
		for cycle in [1, 2]:
			netProfit, taxToPay = calculate_cycle_earnings(df, year, month, cycle)
			cumNetProfit += netProfit
			cumTaxToPay += taxToPay
			cycleDf = df[(df["year"] == year) & (df["month"] == month) & (df["cycle"] == cycle)]
			cumEarnings += cycleDf["Rimmediate"].sum()
workedDaysDf = df[df["Rimmediate"] > 0]
totalDaysWorked = workedDaysDf["dt"].nunique()
meanDailyEarnings = cumEarnings / df["dt"].nunique()
meanDailyNetProfit = cumNetProfit / df["dt"].nunique()
meanDailyHoursWorked = df.groupby("dt")["hour"].nunique().sum() / df["dt"].nunique()

## current cycle
start, end, payoutDate = get_current_cycle()
y = datetime.now().year
m = datetime.now().month
cycle = 1 if datetime.now().day <= 15 else 2
currentCycleDf = df[(df["year"] == y) & (df["month"] == m) & (df["cycle"] == cycle)]
currentCycleEarnings = currentCycleDf["Rimmediate"].sum()
currentCycleNetProfit, currentCycleTaxToPay = calculate_cycle_earnings(df, y, m, cycle)
currentCycleMeanEarnings = currentCycleEarnings / currentCycleDf["dt"].nunique() if not currentCycleDf.empty else 0

if currentCycleDf["dt"].nunique() > 0:
### show stats ###
	print(colored(f"Current cycle: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}", "white"))
	print(colored(f"Days left in current cycle: {end.day - datetime.now().day}", "white"))
	print(colored(f"Current cycle earnings: {currentCycleEarnings:.2f} USD ({currentCycleEarnings * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle net profit: {currentCycleNetProfit:.2f} USD ({currentCycleNetProfit * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle tax to pay: {currentCycleTaxToPay:.2f} USD ({currentCycleTaxToPay * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean earnings: {currentCycleMeanEarnings:.2f} USD ({currentCycleMeanEarnings * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean net profit: {currentCycleNetProfit / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	try:
		print(colored(f"Current cycle mean tax to pay: {currentCycleTaxToPay / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleTaxToPay / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	except ZeroDivisionError:
		print(colored(f"Current cycle mean tax to pay: 0 USD (0 DKK)", "white"))
	print(colored(f"Current cycle mean earnings per hour: {currentCycleEarnings / currentCycleDf['hour'].nunique():.2f} USD ({(currentCycleEarnings / currentCycleDf['hour'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean net profit per hour: {currentCycleNetProfit / currentCycleDf['hour'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['hour'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean earnings per day: {currentCycleEarnings / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleEarnings / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean net profit per day: {currentCycleNetProfit / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean earnings per week: {currentCycleEarnings / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleEarnings / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean net profit per week: {currentCycleNetProfit / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean earnings per month: {currentCycleEarnings / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleEarnings / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)", "white"))
	print(colored(f"Current cycle mean net profit per month: {currentCycleNetProfit / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK)\n", "white"))
else:
	print(colored("No data for current cycle\n", "red"))

print(colored(f"Total earnings: {cumEarnings:.2f} USD ({cumEarnings * usdToDkk:.2f} DKK)", "white"))
print(colored(f"Total net profit: {cumNetProfit:.2f} USD ({cumNetProfit * usdToDkk:.2f} DKK)", "white"))
print(colored(f"Total tax to pay: {cumTaxToPay:.2f} USD ({cumTaxToPay * usdToDkk:.2f} DKK)", "white"))
print(colored(f"Total days worked: {totalDaysWorked}", "white"))
print(colored(f"Total hours worked: {len(workedDaysDf)}\n", "white"))

## means ##
print(colored(f"Mean daily earnings: {meanDailyEarnings:.2f} USD ({meanDailyEarnings * usdToDkk:.2f} DKK)", "white"))
print(colored(f"Mean daily net profit: {meanDailyNetProfit:.2f} USD ({meanDailyNetProfit * usdToDkk:.2f} DKK)", "white"))
print(colored(f"Mean daily hours worked: {meanDailyHoursWorked:.2f}\n", "white"))

## preds ##
thisCyclePred = predict_cycle_earnings(df, y, m, cycle)
# pay tax on predicted earnings
thisCyclePreds, taxToPay = calculate_tax_and_earnings(thisCyclePred)
print(colored(f"Predicted earnings for this cycle: {thisCyclePred:.2f} USD - {taxToPay:.2f} USD = {thisCyclePreds:.2f} USD ({thisCyclePreds * usdToDkk:.2f} DKK)", "white"))
if currentCycle == 2:
	# print(colored(f"From predicted earnings this cycle, use 150 USD for food and {(thisCyclePreds - 150) / 2:.2f} USD for segment 1 of debt repayment", "yellow"))
	# ! remove the following line
	print(colored(f"From actual earnings this cycle, use 100 USD for food and {((currentCycleNetProfit - 100) - 350) * usdToDkk:.2f} DKK for segment 1 of debt repayment", "yellow"))

else:
	print(colored(f"From predicted earnings this cycle, use 150 USD for food, 685 USD for rent and {(thisCyclePreds - 150 - 685) / 2:.2f} USD for segment 1 of debt repayment", "yellow"))
nextCyclePred = predict_cycle_earnings(df, y, m + 1 if cycle == 2 else m, 1 if cycle == 2 else 2)
# pay tax on predicted earnings
nextCyclePreds, taxToPay = calculate_tax_and_earnings(nextCyclePred)
print(colored(f"Predicted earnings for next cycle: {nextCyclePred:.2f} USD - {taxToPay:.2f} USD = {nextCyclePreds:.2f} USD ({nextCyclePreds * usdToDkk:.2f} DKK)", "white"))

## suggested schedule for current cycle ##
if args.target > 0:
	schedule = gen_schedule_for_cycle(df, y, m, cycle, args.target)
	print(colored(f"Suggested schedule for current cycle (target: {args.target:.2f} USD):", "white"))

	if schedule[1] > 0: # 
		print(colored(f"WARNING: can't reach target earnings for this cycle ({schedule[1]:.2f} USD missing ({schedule[1] * usdToDkk:.2f} DKK))", "red"))
		# raise ValueError(colored("WILL NOT REACH TARGET EARNINGS FOR THIS CYCLE", "red"))
	else:
		print(schedule[1])
		print(colored(f"If you follow this schedule, you will reach your target earnings for this cycle ({args.target:.2f} USD ({args.target * usdToDkk:.2f} DKK))", "green"))

	today = datetime.now().date()
	schedule = [entry for entry in schedule[0] if datetime.strptime(entry[0], "%Y-%m-%d").date() >= today]
	schedule = sorted(schedule, key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))

	for entry in schedule:
		date, hour, estimatedEarnings = entry
		# print(colored(f"{date} {hour}:00 - {estimatedEarnings:.2f} USD ({estimatedEarnings * usdToDkk:.2f} DKK)", "white"))

	print(colored(f"Total hours to work from now until end of cycle: {len(schedule)}\nwith a total estimated earnings of {sum([entry[2] for entry in schedule]) + currentCycleEarnings:.2f} USD ({(sum([entry[2] for entry in schedule]) + currentCycleEarnings) * usdToDkk:.2f} DKK) (distributed as follows: {currentCycleEarnings:.2f} USD ({currentCycleEarnings * usdToDkk:.2f} DKK) from current cycle and {sum([entry[2] for entry in schedule]):.2f} USD ({sum([entry[2] for entry in schedule]) * usdToDkk:.2f} DKK) from suggested schedule)\nMean daily hours on schedule: {len(schedule) / (end.day - today.day):.2f}\n", "white"))

	scheduleDf = pd.DataFrame(schedule, columns=["Date", "Hour", "Estimated earnings (USD)"])
	scheduleDf["Estimated earnings (USD)"] = scheduleDf["Estimated earnings (USD)"].round(2)
	scheduleDf["Estimated earnings (DKK)"] = (scheduleDf["Estimated earnings (USD)"] * usdToDkk).round(2)

	fig, ax = plt.subplots(figsize=(12, len(schedule) * 0.5))
	ax.set_frame_on(False)
	ax.xaxis.set_visible(False)
	ax.yaxis.set_visible(False)

	tbl = Table(ax, bbox=[0, 0, 1, 1])

	ncols = len(scheduleDf.columns)
	for i, col in enumerate(scheduleDf.columns):
		tbl.add_cell(-1, i, width=1 / ncols, height=0.1, text=col, loc="center", facecolor="orange")
		color = "lightblue"
		for j, val in enumerate(scheduleDf[col]):
			tbl.add_cell(j, i, width=1 / ncols, height=0.1, text=val, loc="center", facecolor=color)

	ax.add_table(tbl)
	plt.show()

## what would happen if I didn't work on a given date ##
# date = input("What would happen if I didn't work on (YYYY-MM-DD): ")
# date = datetime.strptime(date, "%Y-%m-%d")
# pred = what_would_happen_if_i_didnt_work_on(date, df)
# print(colored(f"Predicted earnings if I didn't work on {date.strftime('%Y-%m-%d')}: {pred[0]:.2f} USD ({pred[0] * usdToDkk:.2f} DKK)", "white"))

print(colored(f"Days to repay debt at current pace: {(CdebtRepayment + Ce) / meanDailyNetProfit:.2f}", "white"))
print(colored(f"Days to repay debt at predicted pace: {(CdebtRepayment + Ce) / (thisCyclePreds / 15):.2f}", "white"))
print(colored(f"Days to repay segment 1 of debt at current pace: {(CdebtRepaymentSeg1 + Ce) / meanDailyNetProfit:.2f}", "white"))
print(colored(f"Days to repay segment 1 of debt at predicted pace: {(CdebtRepaymentSeg1 + Ce) / (thisCyclePreds / 15):.2f}", "white"))
print(colored(f"Days to repay segment 2 of debt at current pace: {(CdebtRepaymentSeg2 + Ce + CdebtRepaymentSeg1) / meanDailyNetProfit:.2f}", "white"))
print(colored(f"Days to repay segment 2 of debt at predicted pace: {(CdebtRepaymentSeg2 + Ce + CdebtRepaymentSeg1) / (thisCyclePreds / 15):.2f}", "white"))
print(colored(f"Days to repay segment 3 of debt at current pace: {(CdebtRepaymentSeg3 + Ce + CdebtRepaymentSeg2 + CdebtRepaymentSeg1) / meanDailyNetProfit:.2f}", "white"))
print(colored(f"Days to repay segment 3 of debt at predicted pace: {(CdebtRepaymentSeg3 + Ce + CdebtRepaymentSeg2 + CdebtRepaymentSeg1) / (thisCyclePreds / 15):.2f}", "white"))
print(colored(f"Days to repay segment 4 of debt at current pace: {(CdebtRepaymentSeg4 + Ce + CdebtRepaymentSeg3 + CdebtRepaymentSeg2 + CdebtRepaymentSeg1) / meanDailyNetProfit:.2f}", "white"))
print(colored(f"Days to repay segment 4 of debt at predicted pace: {(CdebtRepaymentSeg4 + Ce + CdebtRepaymentSeg3 + CdebtRepaymentSeg2 + CdebtRepaymentSeg1) / (thisCyclePreds / 15):.2f}", "white"))

render_pbar(Ce, currentCycleNetProfit, "Essentials", "black")
if  currentCycle == 1:
	render_pbar(Ce * 0.68, currentCycleNetProfit, "Rent", "black")
	print(colored("DANGER! This cycle is the rent cycle!", "red", attrs=["bold", "blink"]))

# budget progress bars
render_pbar(CdebtRepayment, currentCycleNetProfit - Ce, "Debt Repayment", "white")
render_pbar(Cedu, currentCycleNetProfit - Ce - CdebtRepayment, "Tech", "green")
render_pbar(Cdating, currentCycleNetProfit - Ce - Cedu - CdebtRepayment, "Dating", "magenta")
render_pbar(Cbuf, currentCycleNetProfit - Ce - Cedu - Cdating - CdebtRepayment, "Buffer", "yellow")
# absolute progress bar for motivation
render_pbar(Ctotal, currentCycleNetProfit, "Total", "grey")
print(f"At this rate, it will take you {Ctotal / meanDailyEarnings:.2f} days (that's {(Ctotal/meanDailyEarnings) / 365:.2f} FUCKING years) to reach your goal of {Ctotal:.2f} USD ({Ctotal * usdToDkk:.2f} DKK)")
print("")
# maintenance progress bars - get a full medical check-up every ~6 months (1000 work hours)
render_pbar(1000, len(workedDaysDf), "Maintenance (check-up)", "cyan")
render_pbar(150, len(workedDaysDf), "Maintenance (massage)", "cyan")
