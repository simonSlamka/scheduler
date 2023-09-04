import pandas as pd
from datetime import datetime
from collections import defaultdict
import numpy as np
from tqdm import tqdm
from termcolor import colored

### Constants ###
Tweeks = 13  # total n of weeks
ThoursWeek = 80  # total n of hours/week
Ctech = 1500  # total cost of tech to purchase
Ce = 910  # total cost of monthly essentials
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
	df = pd.DataFrame(columns=["dt", "hour", "Rimmediate", "smiles"])

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
	hour, Rimmediate, smiles = hoursInput.split("|")
	Rimmediate = float(Rimmediate)
	smiles = int(smiles)
	df = pd.concat([df, pd.DataFrame({"dt": [timeNow], "hour": [hour], "Rimmediate": [Rimmediate], "smiles": [smiles]})], ignore_index=True, sort=False)

df.to_csv("log.csv", index=False)

Ttotal = Tweeks * ThoursWeek - len(df)

grossSoFar = df['Rimmediate'].sum()
profitSoFar = netProfit1 + netProfit2
Ravg = df['Rimmediate'].mean()
netProfitAvg = Ravg - max(0, Ravg - taxThreshold) * taxRate
tTotalMin = Ctotal / netProfitAvg
tTotalMinEssentials = (Ce * 3) / netProfitAvg # over entire period
projectedGross = grossSoFar + Ttotal * df['Rimmediate'].mean()
projectedGross40h = grossSoFar + 40 * df['Rimmediate'].mean()
projectedGross10h = grossSoFar + 10 * df['Rimmediate'].mean()
taxToPay = taxToPay1 + taxToPay2
netProjectedProfit = projectedGross - taxToPay
netProjectedProfit40h = projectedGross40h - taxToPay
netProjectedProfit10h = projectedGross10h - taxToPay
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
print(f"Average Rimmediate (Ravg): ${Ravg:.2f}")
print(f"Total Earned so Far: ${grossSoFar:.2f}")
print(f"Net Earned so Far: ${profitSoFar:.2f}")
print(f"Expected Profit: ${projectedGross:.2f}")
print(f"Tax to be Paid: ${taxToPay:.2f}")
print(f"Net Daily Profit: ${netDaily:.2f}")
print(f"Net Weekly Profit: ${netWeekly:.2f}")
print(f"Net Per-Period Profit: ${netProfit1 + netProfit2:.2f}")
print(f"Net Monthly Profit: ${netMonthly:.2f}")
print(f"Net Projected Profit (40h/week): ${netProjectedProfit40h:.2f}")
print(f"Net Projected Profit (10h/week): ${netProjectedProfit10h:.2f}")
print(f"Net Projected Profit: ${netProjectedProfit:.2f}")
print(f"Best hour to work based on observed Rimmediate: {suggestedHour}")
print(f"Time to reach Ctotal at current rate: {tTotalMin:.2f} hours (per week: {tTotalMin / Tweeks:.2f} hours)")
print(f"Time to reach Ce * 3 at current rate (essentials only): {tTotalMinEssentials:.2f} hours (per week: {tTotalMinEssentials / Tweeks:.2f} hours)")

print("")

print(colored(f"Current payout for the current period: ${currentPeriodProfit:.2f}", "yellow"))

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