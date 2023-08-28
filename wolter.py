import pandas as pd
from datetime import datetime
from collections import defaultdict

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

while True:
    hours_input = input("Enter the hours worked and Rimmediate in the format 'Hour|Rimmediate' (type 'stop' to exit): ")
    if hours_input.lower() == 'stop':
        break
    timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hour, Rimmediate = hours_input.split("|")
    Rimmediate = float(Rimmediate)
    df = pd.concat([df, pd.DataFrame({'dt': [timeNow], 'hour': [hour], 'Rimmediate': [Rimmediate]})], ignore_index=True, sort=False)

df.to_csv("log.csv", index=False)

Ttotal = Tweeks * ThoursWeek - len(df)

grossSoFar = df['Rimmediate'].sum()
profitSoFar = netProfit1 + netProfit2
projectedGross = grossSoFar + Ttotal * df['Rimmediate'].mean()
taxToPay = taxToPay1 + taxToPay2
netProfit = projectedGross - taxToPay

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
print(f"Total Earned so Far: ${grossSoFar:.2f}")
print(f"Net Earned so Far: ${profitSoFar:.2f}")
print(f"Expected Earnings: ${projectedGross:.2f}")
print(f"Tax to be Paid: ${taxToPay:.2f}")
print(f"Net Earnings: ${netProfit:.2f}")
print(f"Best hour to work based on observed Rimmediate: {suggestedHour}")