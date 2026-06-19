import pandas as pd
from datetime import datetime, timedelta
from supabase_client import get_supabase

BAN_DURATIONS = {
    1: timedelta(hours=24),
    2: timedelta(days=7),
    3: None,
}

SIM_COLUMNS = [
    "sim_id",
    "registered_at",
    "offense_count",
    "risk_score",
    "ban_level",
    "ban_start",
    "ban_expires",
    "is_permanently_blocked",
    "appeal_status",
    "appeal_reason",
    "last_offense_at",
    "last_case_id",
]

NOTIFICATION_COLUMNS = [
    "timestamp",
    "sim_id",
    "notification_type",
    "message",
    "penalty_level",
    "ban_duration",
]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_sim_record(sim_id):
    return {
        "sim_id": sim_id,
        "registered_at": _now(),
        "offense_count": 0,
        "risk_score": 0,
        "ban_level": 0,
        "ban_start": "",
        "ban_expires": "",
        "is_permanently_blocked": False,
        "appeal_status": "NONE",
        "appeal_reason": "",
        "last_offense_at": "",
        "last_case_id": "",
    }


def _clean_record(record):
    if not record:
        return None
    cleaned = dict(record)
    cleaned["offense_count"] = int(cleaned.get("offense_count") or 0)
    cleaned["risk_score"] = int(cleaned.get("risk_score") or 0)
    cleaned["ban_level"] = int(cleaned.get("ban_level") or 0)
    return cleaned


def _load_registry():
    data = get_supabase().table("sims").select("*").order("registered_at", desc=True).execute().data
    return pd.DataFrame(data, columns=SIM_COLUMNS)


def _save_registry(df):
    records = df.fillna("").to_dict(orient="records")
    for rec in records:
        if rec.get("sim_id"):
            get_supabase().table("sims").upsert(rec, on_conflict="sim_id").execute()


def _load_notifications():
    data = get_supabase().table("notifications").select("*").order("timestamp", desc=True).execute().data
    return pd.DataFrame(data, columns=NOTIFICATION_COLUMNS)


def _save_notifications(df):
    records = df.fillna("").to_dict(orient="records")
    for rec in records:
        rec.pop("id", None)
        get_supabase().table("notifications").insert(rec).execute()


def register_sim(sim_id):
    existing = get_sim_record(sim_id)
    if existing:
        return existing
    record = _default_sim_record(sim_id)
    get_supabase().table("sims").insert(record).execute()
    return record


def get_sim_record(sim_id):
    data = get_supabase().table("sims").select("*").eq("sim_id", sim_id).limit(1).execute().data
    return _clean_record(data[0]) if data else None


def get_offense_count(sim_id):
    record = get_sim_record(sim_id)
    return int(record.get("offense_count", 0)) if record else 0


def record_offense(sim_id, case_id, severity="HIGH"):
    record = register_sim(sim_id)
    offense_count = int(record.get("offense_count", 0)) + 1
    update_data = {
        "offense_count": offense_count,
        "last_offense_at": _now(),
        "last_case_id": str(case_id),
    }
    get_supabase().table("sims").update(update_data).eq("sim_id", sim_id).execute()
    return get_sim_record(sim_id)


def update_risk_score(sim_id, score):
    register_sim(sim_id)
    score = int(max(0, min(100, score)))
    get_supabase().table("sims").update({"risk_score": score}).eq("sim_id", sim_id).execute()


def set_ban(sim_id, level):
    register_sim(sim_id)
    level = int(level)
    now_dt = datetime.now()
    if level == 3:
        ban_expires = ""
        permanent = True
    else:
        duration = BAN_DURATIONS.get(level, timedelta(hours=24))
        ban_expires = (now_dt + duration).strftime("%Y-%m-%d %H:%M:%S")
        permanent = False
    get_supabase().table("sims").update({
        "ban_level": level,
        "ban_start": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "ban_expires": ban_expires,
        "is_permanently_blocked": permanent,
    }).eq("sim_id", sim_id).execute()


def check_ban_expired(sim_id):
    record = get_sim_record(sim_id)
    if not record:
        return True
    ban_level = int(record.get("ban_level", 0))
    if ban_level == 0:
        return True
    if record.get("is_permanently_blocked") in (True, "True", "true", 1, "1"):
        return False
    ban_expires = record.get("ban_expires", "")
    if not ban_expires:
        return False
    try:
        expires_dt = datetime.strptime(str(ban_expires), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    if datetime.now() >= expires_dt:
        get_supabase().table("sims").update({
            "ban_level": 0,
            "ban_start": "",
            "ban_expires": "",
            "is_permanently_blocked": False,
        }).eq("sim_id", sim_id).execute()
        return True
    return False


def file_appeal(sim_id, reason):
    record = get_sim_record(sim_id)
    if not record:
        return False
    get_supabase().table("sims").update({
        "appeal_status": "PENDING",
        "appeal_reason": reason,
    }).eq("sim_id", sim_id).execute()
    get_supabase().table("appeals").insert({
        "case_id": record.get("last_case_id", ""),
        "sim_id": sim_id,
        "appeal_reason": reason,
        "appeal_status": "PENDING",
        "submitted_at": _now(),
        "resolved_at": "",
        "admin_decision": "",
    }).execute()
    _log_notification(sim_id, "APPEAL_FILED", f"Appeal filed for SIM {sim_id}: {reason}", int(record.get("ban_level", 0)), "Pending review")
    return True


def resolve_appeal(sim_id, approved):
    record = get_sim_record(sim_id)
    if not record:
        return False
    status = "APPROVED" if approved else "DENIED"
    if approved:
        update_data = {
            "appeal_status": status,
            "offense_count": 0,
            "ban_level": 0,
            "ban_start": "",
            "ban_expires": "",
            "is_permanently_blocked": False,
        }
        message = f"Appeal approved for SIM {sim_id}. Ban lifted and offense count reset."
    else:
        update_data = {"appeal_status": status}
        message = f"Appeal denied for SIM {sim_id}. Current penalty remains active."
    get_supabase().table("sims").update(update_data).eq("sim_id", sim_id).execute()
    get_supabase().table("appeals").update({
        "appeal_status": status,
        "resolved_at": _now(),
        "admin_decision": status,
    }).eq("sim_id", sim_id).eq("appeal_status", "PENDING").execute()
    _log_notification(sim_id, "APPEAL_RESULT", message, int(record.get("ban_level", 0)), "Appeal resolved")
    return True


def get_pending_appeals():
    data = get_supabase().table("appeals").select("*").eq("appeal_status", "PENDING").order("submitted_at", desc=True).execute().data
    return pd.DataFrame(data)


def _log_notification(sim_id, notification_type, message, penalty_level, ban_duration):
    record = {
        "timestamp": _now(),
        "sim_id": sim_id,
        "notification_type": notification_type,
        "message": message,
        "penalty_level": int(penalty_level),
        "ban_duration": ban_duration,
    }
    get_supabase().table("notifications").insert(record).execute()
    return record


def log_notification(sim_id, notification_type, message, penalty_level, ban_duration):
    return _log_notification(sim_id, notification_type, message, penalty_level, ban_duration)


def get_notifications(sim_id=None):
    query = get_supabase().table("notifications").select("*")
    if sim_id:
        query = query.eq("sim_id", sim_id)
    data = query.order("timestamp", desc=True).execute().data
    return pd.DataFrame(data, columns=["id"] + NOTIFICATION_COLUMNS)


def get_all_sims():
    data = get_supabase().table("sims").select("*").order("registered_at", desc=True).execute().data
    return pd.DataFrame(data, columns=SIM_COLUMNS)
