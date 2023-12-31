import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from tqdm import tqdm
from termcolor import colored
from calendar import monthrange

### Constants ###
Tweeks = 5  # total n of weeks
ThoursWeek = 20  # total n of hours/week
Ctech = 1500  # total cost of tech to purchase
Ce = 1000  # total cost of monthly essentials
Cbuf = 500  # buffer
Ctotal = 5730  # absolute cost
taxRate = 0.46  # tax rate
taxThreshold = 542  # tax threshold in USD

def calculate_tax_and_earnings(segment):
	profitThisCycle = segment['Rimmediate'].sum()
	taxToPay = max(0, profitThisCycle - taxThreshold) * taxRate
	netProfit = profitThisCycle - taxToPay
	return netProfit, taxToPay

def calculate_intermediate_net_earnings(df, freq):
	df['dt'] = pd.to_datetime(df['dt'])
	df.set_index('dt', inplace=True)
	resampledDf = df['Rimmediate'].resample(freq).sum()
	netProfit = []
	for periodProfit in resampledDf:
		net, _ = calculate_tax_and_earnings(pd.DataFrame({'Rimmediate': [periodProfit]}))
		netProfit.append(net)
	return np.array(netProfit).mean()

try:
	df = pd.read_csv("log.csv")
except FileNotFoundError:
	df = pd.DataFrame(columns=["dt", "hour", "Rimmediate"])

if 'dt' in df.columns:
	df['dt'] = pd.to_datetime(df['dt'])
df['day'] = df['dt'].dt.day

first = df[df['day'] <= 15]
second = df[df['day'] > 15]

netProfit1, taxToPay1 = calculate_tax_and_earnings(first)
netProfit2, taxToPay2 = calculate_tax_and_earnings(second)
currentPeriodProfit = [netProfit1, netProfit2][datetime.now().day > 15]

while True:
	hoursInput = input("Hour|Rimmediate (\"stop\" to break): ")
	if hoursInput.lower() == "stop" or hoursInput == "":
		break
	timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	hour, Rimmediate = hoursInput.split("|")
	Rimmediate = float(Rimmediate)
	df = pd.concat([df, pd.DataFrame({"dt": [timeNow], "hour": [hour], "Rimmediate": [Rimmediate]}).dropna()], ignore_index=True, sort=False)

df.to_csv("log.csv", index=False)

Ttotal = Tweeks * ThoursWeek - len(df)

now = datetime.now()

if now.day <= 15:
	periodEnd = now.replace(day=15, hour=23, minute=59, second=59, microsecond=999999)
else:
	last = monthrange(now.year, now.month)[1]
	periodEnd = now.replace(day=last, hour=23, minute=59, second=59, microsecond=999999)

remainingDaysInPeriod = (periodEnd - now).days
df["date"] = pd.to_datetime(df["dt"]).dt.date
TtotalPerDay = df.groupby("date")["hour"].nunique()
Tavg = TtotalPerDay.mean()

grossSoFar = df['Rimmediate'].sum()
profitSoFar = netProfit1 + netProfit2
Ravg = df['Rimmediate'].mean()
netProfitAvg = Ravg - max(0, Ravg - taxThreshold) * taxRate
tTotalMin = Ctotal / netProfitAvg
tTotalMinEssentials = (Ce * 3) / netProfitAvg # over entire period
projectedGross = grossSoFar + Ttotal * df['Rimmediate'].mean()
projectedGross40h = grossSoFar + 40 * df['Rimmediate'].mean()
projectedGross14h = grossSoFar + 14 * df['Rimmediate'].mean()
taxToPay = taxToPay1 + taxToPay2
netProjectedProfit = projectedGross - taxToPay
netProjectedProfit40h = projectedGross40h - taxToPay
netProjectedProfit14h = projectedGross14h - taxToPay
netProjectedProfitEndOfCurrentPeriod = (remainingDaysInPeriod * Tavg * netProfitAvg + currentPeriodProfit)
netDaily = calculate_intermediate_net_earnings(df.copy(), 'D')
netWeekly = calculate_intermediate_net_earnings(df.copy(), 'W')
netMonthly = calculate_intermediate_net_earnings(df.copy(), 'M')

Rimmediate = defaultdict(list)

for idx, row in df.iterrows():
	Rimmediate[row.at['hour']].append(row.at['Rimmediate'])

wMeans = {}
for hour, earnings in Rimmediate.items():
	wMean = sum(earnings) / len(earnings)
	wMeans[hour] = wMean

suggestedHour = max(wMeans, key=wMeans.get)

# Display results
print(f"Total Hours to be Worked: {Ttotal}")
print(f"Ravg: ${Ravg:.2f}")
print(f"Tavg: {Tavg:.2f}")
print(f"Total Earned so Far: ${grossSoFar:.2f}")
print(f"Net Earned so Far: ${profitSoFar:.2f}")
print(f"Expected Profit: ${projectedGross:.2f}")
print(f"Tax to be Paid: ${taxToPay:.2f}")
print(f"Net Daily Profit: ${netDaily:.2f}")
print(f"Net Weekly Profit: ${netWeekly:.2f}")
print(f"Net Per-Period Profit: ${netProfit1 + netProfit2:.2f}")
print(f"Net Monthly Profit: ${netMonthly:.2f}")
print(f"Net Projected Profit (40h/week): ${netProjectedProfit40h:.2f}")
print(f"Net Projected Profit (14h/week): ${netProjectedProfit14h:.2f}")
print(f"Net Projected Profit: ${netProjectedProfit:.2f}")
print(f"Best hour to work based on observed Rimmediate: {suggestedHour}")
print(f"Time to reach Ctotal at current rate: {tTotalMin:.2f} hours (per week: {tTotalMin / Tweeks:.2f} hours)")
print(f"Time to reach Ce * 3 at current rate (essentials only): {tTotalMinEssentials:.2f} hours (per week: {tTotalMinEssentials / Tweeks:.2f} hours)")

print("")

print(colored(f"Current payout for the current period: ${currentPeriodProfit:.2f} (DKK: {currentPeriodProfit * 6.97:.2f})", "yellow"))
if netProjectedProfitEndOfCurrentPeriod > Ce:
	print(colored(f"At this rate, you will have earned ${netProjectedProfitEndOfCurrentPeriod:.2f} by the end of the current period.", "blue"))
	print(colored("You can afford working every other day!", "green"))
else:
	print(colored(f"At this rate, you will have earned ${netProjectedProfitEndOfCurrentPeriod:.2f} (DKK: {netProjectedProfitEndOfCurrentPeriod * 6.97:.2f}) by the end of the current period.", "white", attrs=["bold", "underline", "blink"]))
	print(colored(f"You need to work at least {(Ce - currentPeriodProfit) / netProfitAvg:.2f} additional hours to afford essentials!", "red", attrs=["bold", "blink"]))
	print(colored(f"You need to work at least {(Ctotal - currentPeriodProfit) / netProfitAvg:.2f} additional hours to afford essentials AND the tech you want!", "grey"))
	print(colored(f"Per day, you need to work at least {((Ce - currentPeriodProfit) / netProfitAvg) / remainingDaysInPeriod:.2f} hours to afford essentials (OR {((Ce - currentPeriodProfit) / 28) / remainingDaysInPeriod:.2f} high-traffic hours)!", "red", attrs=["bold", "blink"]))

print("")

if netProjectedProfit >= Ctotal:
	print("If you keep up your current efficiency, you will be able to afford to buy essentials AND the tech you want by the end of week 13!")
	pbar = tqdm(total=Ctotal)
	pbar.n = profitSoFar
	pbar.last_print_n = profitSoFar
	pbar.refresh()
	pbar.close()
else:
	print("You cannot afford to buy essentials NOR the tech you want!")