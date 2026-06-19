import pandas as pd
from datetime import datetime
from supabase_client import get_supabase
from sim_registry import file_appeal as sim_file_appeal

CASE_COLUMNS = [
    "case_id",
    "sim_id",
    "created_at",
    "fraud_probability",
    "risk_level",
    "fraud_status",
    "actions",
    "status",
    "defense_status",
    "threat_tier",
    "blocked_components",
    "shutdown_components",
    "enforced_at",
    "penalty_level",
    "ban_duration",
    "risk_score",
    "offense_count",
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
    "appeal_reason",
    "appeal_submitted_at",
]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_fraud_case(input_data, result, actions, defense_report=None, sim_id=None):
    if defense_report:
        defense_status = defense_report.get("defense_status", "OPEN")
        if defense_status == "SHUTDOWN_ENFORCED":
            case_status = "SHUTDOWN"
        elif defense_status == "BLOCKED":
            case_status = "BLOCKED"
        elif defense_status == "MONITORING":
            case_status = "UNDER_MONITORING"
        else:
            case_status = "OPEN"
    else:
        case_status = "OPEN"
    case = {
        "case_id": datetime.now().strftime("CASE%Y%m%d%H%M%S"),
        "sim_id": sim_id or "",
        "created_at": _now(),
        "fraud_probability": round(result["fraud_probability"] * 100, 2),
        "risk_level": result["risk_level"],
        "fraud_status": result["fraud_status"],
        "actions": ", ".join(actions),
        "status": case_status,
        "defense_status": "",
        "threat_tier": "",
        "blocked_components": "",
        "shutdown_components": "",
        "enforced_at": "",
        "penalty_level": 0,
        "ban_duration": "",
        "risk_score": 0,
        "offense_count": 0,
        "appeal_reason": "",
        "appeal_submitted_at": "",
    }
    if defense_report:
        case.update({
            "defense_status": defense_report.get("defense_status", ""),
            "threat_tier": defense_report.get("threat_tier", ""),
            "blocked_components": ", ".join(defense_report.get("blocked_components", [])),
            "shutdown_components": ", ".join(defense_report.get("shutdown_components", [])),
            "enforced_at": defense_report.get("enforcement_timestamp", ""),
            "penalty_level": defense_report.get("penalty_level", 0),
            "ban_duration": defense_report.get("ban_duration_text", ""),
            "risk_score": defense_report.get("risk_score", 0),
            "offense_count": defense_report.get("offense_count", 0),
        })
    case.update(input_data)
    get_supabase().table("fraud_cases").upsert(case, on_conflict="case_id").execute()
    return case


def resolve_case(case_id):
    data = get_supabase().table("fraud_cases").update({"status": "RESOLVED"}).eq("case_id", case_id).execute().data
    return bool(data)


def get_all_cases():
    data = get_supabase().table("fraud_cases").select("*").order("created_at", desc=True).execute().data
    return pd.DataFrame(data, columns=CASE_COLUMNS)


def get_cases_by_sim(sim_id):
    data = get_supabase().table("fraud_cases").select("*").eq("sim_id", sim_id).order("created_at", desc=True).execute().data
    return pd.DataFrame(data, columns=CASE_COLUMNS)


def appeal_case(case_id, sim_id, reason):
    data = get_supabase().table("fraud_cases").select("*").eq("case_id", case_id).limit(1).execute().data
    if not data:
        return False
    get_supabase().table("fraud_cases").update({
        "status": "APPEAL_PENDING",
        "appeal_reason": reason,
        "appeal_submitted_at": _now(),
    }).eq("case_id", case_id).execute()
    get_supabase().table("appeals").insert({
        "case_id": case_id,
        "sim_id": sim_id,
        "appeal_reason": reason,
        "appeal_status": "PENDING",
        "submitted_at": _now(),
        "resolved_at": "",
        "admin_decision": "",
    }).execute()
    sim_file_appeal(sim_id, reason)
    return True
