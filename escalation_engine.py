"""
escalation_engine.py
====================
Three-level escalating penalty system with integrated risk scoring.

Penalty Levels
--------------
  Level 1 (1st offense)  → 24-hour temporary ban  + warning notification
  Level 2 (2nd offense)  → 7-day ban              + final warning
  Level 3 (3rd+ offense) → Permanent deactivation  + carrier notification
"""

from datetime import timedelta
from sim_registry import (
    register_sim,
    get_offense_count,
    record_offense,
    set_ban,
    update_risk_score,
    check_ban_expired,
    log_notification,
    get_sim_record,
)


# ---------------------------------------------------------------------------
# Penalty definitions
# ---------------------------------------------------------------------------

PENALTY_LEVELS = {
    1: {
        "label": "⚠️ Level 1 — Warning",
        "ban_duration_text": "24 hours",
        "ban_duration": timedelta(hours=24),
        "notification_type": "WARNING",
        "notification_message": (
            "Your SIM card has been temporarily suspended for 24 hours "
            "due to suspicious activity. If you believe this is an error, "
            "you may file an appeal through the system."
        ),
    },
    2: {
        "label": "🚫 Level 2 — Final Warning",
        "ban_duration_text": "7 days",
        "ban_duration": timedelta(days=7),
        "notification_type": "FINAL_WARNING",
        "notification_message": (
            "Your SIM card has been suspended for 7 days following a "
            "second violation. This is your FINAL WARNING. Any further "
            "violations will result in permanent deactivation. You may "
            "file an appeal if you believe this is a mistake."
        ),
    },
    3: {
        "label": "🔴 Level 3 — Permanent Deactivation",
        "ban_duration_text": "Permanent",
        "ban_duration": None,
        "notification_type": "PERMANENT_BAN",
        "notification_message": (
            "Your SIM card has been PERMANENTLY DEACTIVATED due to "
            "repeated violations of acceptable use policy. Contact "
            "your carrier for further information."
        ),
    },
}


# ---------------------------------------------------------------------------
# Risk score calculation
# ---------------------------------------------------------------------------

def calculate_risk_score(input_data, probability, offense_count):
    """
    Compute a composite risk score on a 0–100 scale.

    Components (weights):
      • ML/hybrid probability   → 35%  (0-1 scaled to 0-35)
      • Rule-based indicators   → 40%  (0-40 based on activity patterns)
      • Offense history         → 25%  (10 pts per offense, capped at 25)

    Parameters
    ----------
    input_data : dict
        Customer activity metrics.
    probability : float
        Combined fraud probability (0-1) from predictor.
    offense_count : int
        Number of past offenses for this SIM.

    Returns
    -------
    int  –  Risk score 0-100.
    """
    # --- ML component (0-35) ---
    ml_component = probability * 35.0

    # --- Rule component (0-40) ---
    rule_score = 0.0

    calls = input_data.get("calls_per_day", 0)
    unique = input_data.get("unique_numbers_called", 0)
    intl = input_data.get("international_calls", 0)
    sms = input_data.get("sms_per_day", 0)
    sim = input_data.get("sim_changes", 0)
    device = input_data.get("device_changes", 0)
    duration = input_data.get("avg_call_duration", 5.0)
    account_age = input_data.get("account_age_days", 500)

    # High call volume
    if calls > 300:
        rule_score += 4
    if calls > 500:
        rule_score += 5
    if calls > 700:
        rule_score += 6

    # Many unique numbers
    if unique > 150:
        rule_score += 4
    if unique > 300:
        rule_score += 5

    # International abuse
    if intl > 100:
        rule_score += 4
    if intl > 250:
        rule_score += 5

    # SMS flood
    if sms > 500:
        rule_score += 3
    if sms > 1000:
        rule_score += 5

    # SIM/device swap patterns
    if sim >= 3:
        rule_score += 4
    if device >= 3:
        rule_score += 3
    if sim >= 3 and device >= 3:
        rule_score += 5

    # Short-call robocall pattern
    if duration < 1.0 and calls > 500:
        rule_score += 5

    # New account risk
    if account_age < 90:
        rule_score += 4

    rule_component = min(rule_score, 40.0)

    # --- Offense history component (0-25) ---
    offense_component = min(offense_count * 10, 25)

    # --- Final score ---
    total = ml_component + rule_component + offense_component
    return int(max(0, min(100, round(total))))


# ---------------------------------------------------------------------------
# Core escalation logic
# ---------------------------------------------------------------------------

def escalate(sim_id, case_id, probability, input_data):
    """
    Determine and apply the correct penalty level for a SIM.

    Workflow:
      1. Register the SIM if new
      2. Check if an existing ban is still active
      3. Record the new offense
      4. Determine penalty level based on offense count
      5. Apply the ban
      6. Calculate & persist risk score
      7. Send notification
      8. Return an EscalationReport dict

    Parameters
    ----------
    sim_id : str
        The SIM card identifier.
    case_id : str
        The fraud case ID associated with this event.
    probability : float
        Combined fraud probability (0-1).
    input_data : dict
        Customer activity data.

    Returns
    -------
    dict — EscalationReport with keys:
        sim_id, penalty_level, penalty_label, ban_duration_text,
        notification_type, notification_message, risk_score,
        offense_count, is_permanent, was_already_banned
    """
    # 1. Ensure the SIM is registered
    register_sim(sim_id)

    # 2. Check if current ban is still active
    ban_expired = check_ban_expired(sim_id)
    current_record = get_sim_record(sim_id)
    was_already_banned = not ban_expired

    # If permanently blocked, refuse further escalation (already max level)
    if current_record and current_record.get("is_permanently_blocked") in (
        True, "True", "true", 1
    ):
        risk_score = calculate_risk_score(
            input_data, probability, int(current_record.get("offense_count", 3))
        )
        update_risk_score(sim_id, risk_score)
        return {
            "sim_id": sim_id,
            "penalty_level": 3,
            "penalty_label": PENALTY_LEVELS[3]["label"],
            "ban_duration_text": "Permanent",
            "notification_type": "PERMANENT_BAN",
            "notification_message": (
                "This SIM is already permanently deactivated."
            ),
            "risk_score": risk_score,
            "offense_count": int(current_record.get("offense_count", 3)),
            "is_permanent": True,
            "was_already_banned": True,
        }

    # 3. Record the new offense
    updated_record = record_offense(sim_id, case_id, severity="HIGH")
    new_offense_count = int(updated_record.get("offense_count", 1))

    # 4. Determine penalty level
    if new_offense_count >= 3:
        penalty_level = 3
    elif new_offense_count == 2:
        penalty_level = 2
    else:
        penalty_level = 1

    penalty = PENALTY_LEVELS[penalty_level]

    # 5. Apply the ban
    set_ban(sim_id, penalty_level)

    # 6. Calculate & persist risk score
    risk_score = calculate_risk_score(input_data, probability, new_offense_count)
    update_risk_score(sim_id, risk_score)

    # 7. Send notification
    log_notification(
        sim_id=sim_id,
        notification_type=penalty["notification_type"],
        message=penalty["notification_message"],
        penalty_level=penalty_level,
        ban_duration=penalty["ban_duration_text"],
    )

    # 8. Return report
    return {
        "sim_id": sim_id,
        "penalty_level": penalty_level,
        "penalty_label": penalty["label"],
        "ban_duration_text": penalty["ban_duration_text"],
        "notification_type": penalty["notification_type"],
        "notification_message": penalty["notification_message"],
        "risk_score": risk_score,
        "offense_count": new_offense_count,
        "is_permanent": penalty_level == 3,
        "was_already_banned": was_already_banned,
    }


def get_penalty_info(level):
    """Return the penalty definition dict for a given level (1, 2, or 3)."""
    return PENALTY_LEVELS.get(level, PENALTY_LEVELS[1])
