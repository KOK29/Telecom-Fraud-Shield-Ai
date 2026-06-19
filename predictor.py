import os
import pandas as pd
import joblib

MODEL_PATH = "models/xgboost_model.pkl"
FEATURES_PATH = "models/features.pkl"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError("Model not found. Run: python model_training.py")

if not os.path.exists(FEATURES_PATH):
    raise FileNotFoundError("Features file not found. Run: python model_training.py")

model = joblib.load(MODEL_PATH)
features = joblib.load(FEATURES_PATH)


def calculate_rule_score(input_data):
    score = 0

    calls = input_data["calls_per_day"]
    unique = input_data["unique_numbers_called"]
    intl = input_data["international_calls"]
    sms = input_data["sms_per_day"]
    sim = input_data["sim_changes"]
    device = input_data["device_changes"]
    complaints = input_data["complaints_count"]
    account_age = input_data["account_age_days"]
    roaming = input_data["roaming_usage"]
    late = input_data["late_payments"]
    duration = input_data["avg_call_duration"]

    # Base individual risks
    if calls > 300:
        score += 0.08
    if calls > 500:
        score += 0.12
    if calls > 700:
        score += 0.15

    if unique > 150:
        score += 0.10
    if unique > 300:
        score += 0.15
    if unique > 500:
        score += 0.18

    if intl > 100:
        score += 0.12
    if intl > 250:
        score += 0.18
    if intl > 400:
        score += 0.22

    if sms > 500:
        score += 0.08
    if sms > 1000:
        score += 0.14

    if sim >= 3:
        score += 0.12
    if sim >= 6:
        score += 0.18

    if device >= 3:
        score += 0.08
    if device >= 6:
        score += 0.12

    if complaints >= 5:
        score += 0.10

    if account_age < 90:
        score += 0.12

    if roaming == 1:
        score += 0.05

    if late == 1:
        score += 0.03

    # Real telecom fraud patterns
    if calls > 500 and unique > 200:
        score += 0.25

    if calls > 700 and unique > 400:
        score += 0.30

    if calls > 400 and intl > 150:
        score += 0.25

    if intl > 250 and roaming == 1:
        score += 0.20

    if sms > 1000 and unique > 200:
        score += 0.25

    if sim >= 3 and device >= 3:
        score += 0.25

    if account_age < 90 and calls > 300:
        score += 0.20

    if account_age < 90 and intl > 100:
        score += 0.20

    if duration < 1.0 and calls > 500:
        score += 0.20

    return min(score, 1.0)


def predict_fraud(input_data):
    df = pd.DataFrame([input_data])
    df = df[features]

    ml_probability = float(model.predict_proba(df)[0][1])
    rule_score = calculate_rule_score(input_data)

    # Hybrid system: rule engine has stronger control
    probability = (ml_probability * 0.35) + (rule_score * 0.65)
    probability = min(probability, 1.0)

    if probability < 0.15:
        risk_level = "Very Low"
        fraud_status = "Definitely Not Fraud"
    elif probability < 0.35:
        risk_level = "Low"
        fraud_status = "Not Fraud"
    elif probability < 0.60:
        risk_level = "Medium"
        fraud_status = "Suspicious"
    elif probability < 0.80:
        risk_level = "High"
        fraud_status = "Fraud"
    else:
        risk_level = "Critical"
        fraud_status = "Immediate Threat"

    return {
        "fraud_probability": probability,
        "ml_probability": ml_probability,
        "rule_score": rule_score,
        "risk_level": risk_level,
        "fraud_status": fraud_status
    }


def explain_fraud(input_data):
    reasons = []

    if input_data["calls_per_day"] > 500:
        reasons.append("High call volume detected.")

    if input_data["calls_per_day"] > 700:
        reasons.append("Extremely high call activity may indicate robocalling or spam fraud.")

    if input_data["unique_numbers_called"] > 200:
        reasons.append("Customer is contacting many unique numbers.")

    if input_data["international_calls"] > 150:
        reasons.append("High international call activity detected.")

    if input_data["sms_per_day"] > 1000:
        reasons.append("Very high SMS activity may indicate SMS spam fraud.")

    if input_data["sim_changes"] >= 3:
        reasons.append("Frequent SIM changes may indicate SIM swap fraud.")

    if input_data["device_changes"] >= 3:
        reasons.append("Multiple device changes detected.")

    if input_data["account_age_days"] < 90:
        reasons.append("New account with risky activity pattern.")

    if input_data["complaints_count"] >= 5:
        reasons.append("High number of complaints linked to suspicious behavior.")

    if input_data["roaming_usage"] == 1 and input_data["international_calls"] > 100:
        reasons.append("Roaming and international activity are both high.")

    if input_data["avg_call_duration"] < 1.0 and input_data["calls_per_day"] > 500:
        reasons.append("Many short calls detected, possible Wangiri or spam-call behavior.")

    if input_data["calls_per_day"] > 500 and input_data["unique_numbers_called"] > 200:
        reasons.append("High calls to many unique numbers indicates spam-call fraud pattern.")

    if input_data["sim_changes"] >= 3 and input_data["device_changes"] >= 3:
        reasons.append("SIM and device changes together may indicate account takeover.")

    if not reasons:
        reasons.append("No major suspicious pattern detected.")

    return reasons


def fraud_action(probability):
    if probability < 0.15:
        return "No action required."
    elif probability < 0.35:
        return "Continue normal monitoring."
    elif probability < 0.60:
        return "Apply enhanced monitoring and review recent activity."
    elif probability < 0.80:
        return "Start fraud investigation, limit risky services, and verify customer identity."
    else:
        return "Immediately restrict risky services, block international usage, and require customer verification."


def what_if_analysis(input_data, feature_name, values):
    results = []

    for value in values:
        temp = input_data.copy()
        temp[feature_name] = value

        result = predict_fraud(temp)

        results.append({
            "Value": value,
            "Fraud Probability (%)": round(result["fraud_probability"] * 100, 2),
            "ML Probability (%)": round(result["ml_probability"] * 100, 2),
            "Rule Score (%)": round(result["rule_score"] * 100, 2),
            "Risk Level": result["risk_level"],
            "Fraud Status": result["fraud_status"]
        })

    return results