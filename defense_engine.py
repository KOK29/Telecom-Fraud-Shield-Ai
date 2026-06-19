import pandas as pd
from datetime import datetime
from escalation_engine import escalate
from sim_registry import get_sim_record, check_ban_expired
from supabase_client import get_supabase

THREAT_TIERS = {
    "CRITICAL": {
        "min_probability": 0.80,
        "label": "🔴 CRITICAL",
        "description": "Immediate full account lockdown",
        "auto_block": ["OUTGOING_CALLS", "INTERNATIONAL_CALLS", "SMS_SERVICE", "DATA_SERVICE", "SIM_OPERATIONS", "ROAMING"],
        "auto_shutdown": ["OUTGOING_CALLS", "INTERNATIONAL_CALLS", "SIM_OPERATIONS"],
    },
    "HIGH": {
        "min_probability": 0.60,
        "label": "🟠 HIGH",
        "description": "Partial service restriction",
        "auto_block": ["INTERNATIONAL_CALLS", "SIM_OPERATIONS", "ROAMING"],
        "auto_shutdown": ["INTERNATIONAL_CALLS"],
    },
    "MEDIUM": {
        "min_probability": 0.35,
        "label": "🟡 MEDIUM",
        "description": "Enhanced monitoring & customer warning",
        "auto_block": [],
        "auto_shutdown": [],
    },
    "LOW": {
        "min_probability": 0.0,
        "label": "🟢 LOW",
        "description": "Passive monitoring only",
        "auto_block": [],
        "auto_shutdown": [],
    },
}

LOG_COLUMNS = ["id", "timestamp", "sim_id", "case_id", "threat_tier", "component", "action", "status", "detail", "penalty_level", "risk_score"]


def _classify_threat(probability):
    for tier_name in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        tier = THREAT_TIERS[tier_name]
        if probability >= tier["min_probability"]:
            return tier_name, tier
    return "LOW", THREAT_TIERS["LOW"]


def _pattern_blocks(input_data):
    extra_blocks = []
    reasons = []
    if input_data.get("sim_changes", 0) >= 5:
        extra_blocks.append("SIM_OPERATIONS")
        reasons.append("Excessive SIM changes detected — SIM operations locked")
    if input_data.get("international_calls", 0) > 300:
        extra_blocks.append("ROAMING")
        extra_blocks.append("INTERNATIONAL_CALLS")
        reasons.append("Extreme international call volume — roaming & intl calls blocked")
    if input_data.get("sms_per_day", 0) > 1000:
        extra_blocks.append("SMS_SERVICE")
        reasons.append("SMS flood detected — SMS service blocked")
    if input_data.get("calls_per_day", 0) > 700 and input_data.get("avg_call_duration", 99) < 1.0:
        extra_blocks.append("OUTGOING_CALLS")
        reasons.append("Robocall / Wangiri pattern — outgoing calls shut down")
    if input_data.get("device_changes", 0) >= 5 and input_data.get("sim_changes", 0) >= 3:
        extra_blocks.append("SIM_OPERATIONS")
        extra_blocks.append("DATA_SERVICE")
        reasons.append("Account takeover pattern — SIM & data locked")
    return list(set(extra_blocks)), reasons


def _append_defense_log(records):
    if records:
        get_supabase().table("defense_logs").insert(records).execute()


def get_defense_log():
    data = get_supabase().table("defense_logs").select("*").order("timestamp", desc=True).execute().data
    return pd.DataFrame(data, columns=LOG_COLUMNS)


def enforce_defense(case_id, probability, input_data, component_status_manager, sim_id=None):
    tier_name, tier = _classify_threat(probability)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    blocked = list(tier["auto_block"])
    shutdown = list(tier["auto_shutdown"])
    extra_blocks, pattern_reasons = _pattern_blocks(input_data)
    for comp in extra_blocks:
        if comp not in blocked:
            blocked.append(comp)
    escalation_report = None
    if sim_id:
        escalation_report = escalate(sim_id=sim_id, case_id=case_id, probability=probability, input_data=input_data)
        if escalation_report["is_permanent"]:
            if hasattr(component_status_manager, "deactivate_sim"):
                component_status_manager.deactivate_sim(sim_id)
        else:
            if hasattr(component_status_manager, "ban_sim"):
                component_status_manager.ban_sim(sim_id)
    log_records = []
    for comp in blocked:
        component_status_manager.block_component(comp)
        log_records.append({
            "timestamp": now,
            "sim_id": sim_id or "",
            "case_id": case_id,
            "threat_tier": tier_name,
            "component": comp,
            "action": "BLOCK",
            "status": "ENFORCED",
            "detail": tier["description"],
            "penalty_level": escalation_report["penalty_level"] if escalation_report else 0,
            "risk_score": escalation_report["risk_score"] if escalation_report else 0,
        })
    for comp in shutdown:
        component_status_manager.shutdown_component(comp)
        log_records.append({
            "timestamp": now,
            "sim_id": sim_id or "",
            "case_id": case_id,
            "threat_tier": tier_name,
            "component": comp,
            "action": "SHUTDOWN",
            "status": "ENFORCED",
            "detail": f"{comp} fully shut down",
            "penalty_level": escalation_report["penalty_level"] if escalation_report else 0,
            "risk_score": escalation_report["risk_score"] if escalation_report else 0,
        })
    _append_defense_log(log_records)
    if shutdown:
        defense_status = "SHUTDOWN_ENFORCED"
    elif blocked:
        defense_status = "BLOCKED"
    else:
        defense_status = "MONITORING"
    report = {
        "threat_tier": tier_name,
        "threat_label": tier["label"],
        "threat_description": tier["description"],
        "blocked_components": blocked,
        "shutdown_components": shutdown,
        "pattern_reasons": pattern_reasons,
        "enforcement_timestamp": now,
        "defense_status": defense_status,
    }
    if escalation_report:
        report["escalation_report"] = escalation_report
        report["penalty_level"] = escalation_report["penalty_level"]
        report["penalty_label"] = escalation_report["penalty_label"]
        report["ban_duration_text"] = escalation_report["ban_duration_text"]
        report["risk_score"] = escalation_report["risk_score"]
        report["offense_count"] = escalation_report["offense_count"]
        report["notification_message"] = escalation_report["notification_message"]
    return report


def lift_defense(case_id, component_status_manager, sim_id=None):
    log_df = get_defense_log()
    if log_df.empty:
        return []
    rows = log_df[log_df["case_id"] == case_id]
    lifted = []
    for comp in rows["component"].dropna().unique().tolist():
        if hasattr(component_status_manager, "unblock_component"):
            component_status_manager.unblock_component(comp)
        lifted.append(comp)
        get_supabase().table("defense_logs").insert({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sim_id": sim_id or "",
            "case_id": case_id,
            "threat_tier": "MANUAL",
            "component": comp,
            "action": "LIFT",
            "status": "LIFTED",
            "detail": "Defense lifted by admin",
            "penalty_level": 0,
            "risk_score": 0,
        }).execute()
    if sim_id and get_sim_record(sim_id) and check_ban_expired(sim_id):
        if hasattr(component_status_manager, "unban_sim"):
            component_status_manager.unban_sim(sim_id)
    return lifted


def lift_all_defenses(component_status_manager):
    lifted = []
    if hasattr(component_status_manager, "ALL_COMPONENTS"):
        for comp in component_status_manager.ALL_COMPONENTS:
            if hasattr(component_status_manager, "unblock_component"):
                component_status_manager.unblock_component(comp)
            lifted.append(comp)
    return lifted
