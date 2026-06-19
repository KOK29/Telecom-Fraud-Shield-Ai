from datetime import datetime


def _severity_header(defense_report):
    """Return a colored severity header based on the defense report."""
    if defense_report and defense_report.get("threat_label"):
        return defense_report["threat_label"]
    return "🟢 LOW"


def _format_blocked_list(components):
    """Format a list of blocked component names into a readable block."""
    if not components:
        return "  None"
    return "\n".join(f"  ⛔ {comp}" for comp in components)


def _format_shutdown_list(components):
    """Format a list of shutdown component names into a readable block."""
    if not components:
        return "  None"
    return "\n".join(f"  🔻 {comp}" for comp in components)


def generate_alert(case, defense_report=None):
    """
    Generate a human-readable security alert string.

    Parameters
    ----------
    case : dict
        Fraud case dict from case_manager.
    defense_report : dict or None
        DefenseReport returned by defense_engine.enforce_defense().
        When provided the alert includes enforcement details.
    """
    severity = _severity_header(defense_report)

    # Base alert
    alert = f"""
{'═' * 52}
  🚨 FRAUD ALERT  —  {severity}
{'═' * 52}

Case ID:          {case["case_id"]}
SIM ID:           {case.get("sim_id", "N/A")}
Created At:       {case["created_at"]}

Risk Level:       {case["risk_level"]}
Fraud Status:     {case["fraud_status"]}
Fraud Probability:{case["fraud_probability"]}%
"""

    # Add risk score if available
    risk_score = case.get("risk_score") or (
        defense_report.get("risk_score") if defense_report else None
    )
    if risk_score is not None:
        alert += f"Risk Score:       {risk_score}/100\n"

    alert += f"""
Protective Actions:
  {case["actions"]}

Case Status:      {case["status"]}
"""

    # Append defense details when available
    if defense_report:
        blocked_section = _format_blocked_list(
            defense_report.get("blocked_components", [])
        )
        shutdown_section = _format_shutdown_list(
            defense_report.get("shutdown_components", [])
        )
        pattern_reasons = defense_report.get("pattern_reasons", [])
        reasons_section = (
            "\n".join(f"  ⚠ {r}" for r in pattern_reasons)
            if pattern_reasons
            else "  None"
        )

        alert += f"""
{'─' * 52}
  🛡️  DEFENSE ENFORCEMENT DETAILS
{'─' * 52}

Defense Status:   {defense_report.get("defense_status", "N/A")}
Threat Tier:      {defense_report.get("threat_tier", "N/A")}
Enforced At:      {defense_report.get("enforcement_timestamp", "N/A")}

Blocked Components:
{blocked_section}

Shutdown Components:
{shutdown_section}

Pattern-Based Detections:
{reasons_section}
"""

        # Escalation details
        penalty_level = defense_report.get("penalty_level")
        if penalty_level:
            penalty_label = defense_report.get("penalty_label", f"Level {penalty_level}")
            ban_duration = defense_report.get("ban_duration_text", "N/A")
            notification_msg = defense_report.get("notification_message", "")
            offense_count = defense_report.get("offense_count", 0)

            alert += f"""
{'─' * 52}
  ⚡ ESCALATION & PENALTY DETAILS
{'─' * 52}

Penalty Level:    {penalty_label}
Ban Duration:     {ban_duration}
Offense Count:    {offense_count}
Risk Score:       {defense_report.get("risk_score", "N/A")}/100

📨 Notification Sent:
  {notification_msg}
"""

            if penalty_level < 3:
                alert += f"""
📋 APPEAL INSTRUCTIONS:
  If you believe this action was taken in error, you may
  file an appeal through the FraudShield dashboard under
  the "Risk & SIM Monitor" tab. Provide a detailed
  explanation and your appeal will be reviewed by an admin.
"""

        alert += f"\n{'═' * 52}\n"
    else:
        alert += f"\n{'═' * 52}\n"

    return alert