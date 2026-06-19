import os
import numpy as np
import pandas as pd

np.random.seed(42)
os.makedirs("data", exist_ok=True)

rows = []

for i in range(6000):
    customer_id = 100000 + i

    fraud = np.random.choice([0, 1], p=[0.65, 0.35])

    age = np.random.randint(18, 75)

    if fraud == 1:
        account_age_days = np.random.randint(1, 250)
        calls_per_day = np.random.randint(120, 1000)
        avg_call_duration = round(np.random.uniform(0.2, 4.5), 2)
        unique_numbers_called = np.random.randint(80, 700)
        international_calls = np.random.randint(30, 550)
        sms_per_day = np.random.randint(150, 1700)
        data_usage_gb = round(np.random.uniform(0.2, 25), 2)
        recharge_amount = np.random.randint(1, 60)
        sim_changes = np.random.randint(2, 12)
        device_changes = np.random.randint(1, 12)
        complaints_count = np.random.randint(1, 12)
        roaming_usage = np.random.choice([0, 1], p=[0.45, 0.55])
        late_payments = np.random.choice([0, 1], p=[0.4, 0.6])
    else:
        account_age_days = np.random.randint(90, 1500)
        calls_per_day = np.random.randint(1, 220)
        avg_call_duration = round(np.random.uniform(1.5, 12), 2)
        unique_numbers_called = np.random.randint(2, 120)
        international_calls = np.random.randint(0, 70)
        sms_per_day = np.random.randint(1, 300)
        data_usage_gb = round(np.random.uniform(0.2, 30), 2)
        recharge_amount = np.random.randint(20, 150)
        sim_changes = np.random.randint(0, 3)
        device_changes = np.random.randint(0, 3)
        complaints_count = np.random.randint(0, 4)
        roaming_usage = np.random.choice([0, 1], p=[0.85, 0.15])
        late_payments = np.random.choice([0, 1], p=[0.8, 0.2])

    rows.append([
        customer_id,
        age,
        account_age_days,
        calls_per_day,
        avg_call_duration,
        unique_numbers_called,
        international_calls,
        sms_per_day,
        data_usage_gb,
        recharge_amount,
        sim_changes,
        device_changes,
        complaints_count,
        roaming_usage,
        late_payments,
        fraud
    ])

columns = [
    "customer_id",
    "age",
    "account_age_days",
    "calls_per_day",
    "avg_call_duration",
    "unique_numbers_called",
    "international_calls",
    "sms_per_day",
    "data_usage_gb",
    "recharge_amount",
    "sim_changes",
    "device_changes",
    "complaints_count",
    "roaming_usage",
    "late_payments",
    "fraud_label"
]

df = pd.DataFrame(rows, columns=columns)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

df.to_csv("data/telecom_fraud.csv", index=False)

print("Dataset created successfully.")
print(df["fraud_label"].value_counts())