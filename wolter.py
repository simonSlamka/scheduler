import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from tqdm import tqdm
from termcolor import colored
from calendar import monthrange
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import logging

logging.basicConfig(level=logging.INFO)


### Constants ###
Tweeks = 16  # total n of weeks
ThoursWeek = 21  # total n of hours/week
Cedu = 5000  # total cost of tech to purchase
Ce = 1000  # total cost of monthly essentials
Cbuf = 2500  # buffer
Cdating = 1000  # dating budget
CdebtRepayment = 11764.76  # debt repayment budget
Ctotal = Cedu + (Ce * (Tweeks/4)) + Cbuf + Cdating + CdebtRepayment  # total cost
taxRate = 0.46  # tax rate
taxThreshold = 619.43  # tax threshold in USD
usdToDkk = 6.84  # USD to DKK conversion rate, as of 2024-01-16 (YYYY-MM-DD)

def calculate_tax_and_earnings(cycleEarnings):
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

	model = LinearRegression()
	model.fit(dailies[["dt"]], dailies["Rimmediate"])

	start, end = get_cycle_dates(y, m, cycle)
	next = pd.DataFrame([date.toordinal() for date in pd.date_range(start, end)], columns=["dt"])
	logging.debug(f"Predicted cycle: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")

	logging.debug(f"Last date in dataset: {datetime.fromordinal(dailies['dt'].max())} with an Rimmediate of {dailies[dailies['dt'] == dailies['dt'].max()]['Rimmediate'].values[0]}")

	preds = model.predict(next)
	sum = np.sum(preds)
	return sum

try:
	df = pd.read_csv("log.csv")
	df["dt"] = pd.to_datetime(df["dt"])
except FileNotFoundError:
	df = pd.DataFrame(columns=["dt", "hour", "Rimmediate"])

if "dt" in df.columns:
	df["month"] = df["dt"].dt.month
	df["year"] = df["dt"].dt.year
	df["cycle"] = np.where(df["dt"].dt.day <= 15, 1, 2)

start, end, payoutDate = get_current_cycle()
currentCycle = 1 if datetime.now().day <= 15 else 2
currentPeriodProfit, currentPeriodTaxToPay = calculate_cycle_earnings(df, datetime.now().year, datetime.now().month, currentCycle)

while True:
	hoursInput = input("Hour|Rimmediate (\"stop\" to break): ")
	if hoursInput.lower() == "stop" or hoursInput == "":
		break
	timeNow = datetime.now().strftime("%Y-%m-%d")
	hour, Rimmediate = hoursInput.split("|")
	Rimmediate = float(Rimmediate)
	df = pd.concat([df, pd.DataFrame({"dt": [timeNow], "hour": [hour], "Rimmediate": [Rimmediate], "month": [datetime.now().month], "year": [datetime.now().year], "cycle": [currentCycle]}).dropna()], ignore_index=True, sort=False)

df.to_csv("log.csv", index=False)

Ttotal = Tweeks * ThoursWeek - len(df)  # total hours to work

if not df.empty:
	all = pd.date_range(start=df["dt"].min(), end=df["dt"].max() + timedelta(days=1) if datetime.now().day != df["dt"].max().day else df["dt"].max()) # add one day if today is not the last day in the dataset
	all = pd.DataFrame({"dt": all})
	df = all.merge(df, on="dt", how="left")
	df["Rimmediate"].fillna(0, inplace=True)

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
	print(colored(f"Current cycle mean net profit per month: {currentCycleNetProfit / currentCycleDf['dt'].nunique():.2f} USD ({(currentCycleNetProfit / currentCycleDf['dt'].nunique()) * usdToDkk:.2f} DKK\n", "white"))
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
nextCyclePred = predict_cycle_earnings(df, y, m + 1 if cycle == 2 else m, 1 if cycle == 2 else 2)
# pay tax on predicted earnings
nextCyclePreds, taxToPay = calculate_tax_and_earnings(nextCyclePred)
print(colored(f"Predicted earnings for next cycle: {nextCyclePred:.2f} USD - {taxToPay:.2f} USD = {nextCyclePreds:.2f} USD ({nextCyclePreds * usdToDkk:.2f} DKK)", "white"))

## what would happen if I didn't work on a given date ##
# date = input("What would happen if I didn't work on (YYYY-MM-DD): ")
# date = datetime.strptime(date, "%Y-%m-%d")
# pred = what_would_happen_if_i_didnt_work_on(date, df)
# print(colored(f"Predicted earnings if I didn't work on {date.strftime('%Y-%m-%d')}: {pred[0]:.2f} USD ({pred[0] * usdToDkk:.2f} DKK)", "white"))

print(colored(f"Days to repay debt: {(CdebtRepayment + Ce) / meanDailyNetProfit:.2f}", "white"))

render_pbar(Ce, currentCycleNetProfit, "Essentials", "black")
if  currentCycle == 1:
	render_pbar(Ce * 0.68, currentCycleNetProfit, "Rent", "black")
	print(colored("DANGER! This cycle is the rent cycle!", "red", attrs=["bold", "blink"]))
# # budget pbars
# render_pbar(CdebtRepayment, profitSoFar - Ce, "Debt Repayment", "white")
# print(colored(f"Days to pay off debt: {(CdebtRepayment + (Ce - profitSoFar)) / netDaily:.2f}", "white"))
# render_pbar(Cedu, profitSoFar - Ce - CdebtRepayment, "Tech", "green")
# render_pbar(Cdating, profitSoFar - Ce - Cedu - CdebtRepayment, "Dating", "magenta")
# render_pbar(Cbuf, profitSoFar - Ce - Cedu - Cdating - CdebtRepayment, "Buffer", "yellow")
# # absolute pbar for motivation
# render_pbar(Ctotal, profitSoFar, "Total", "grey")
# print("")
# # maintenance pbars - get a full medical check-up every ~6 months (1000 work hours)
# render_pbar(1000, Ttotal, "Maintenance (check-up)", "cyan")
# render_pbar(150, Ttotal, "Maintenance (massage)", "cyan")