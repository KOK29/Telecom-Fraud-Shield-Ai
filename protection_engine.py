# ---------------------------------------------------------------------------
# All telecom components that can be individually controlled
# ---------------------------------------------------------------------------
ALL_COMPONENTS = [
    "OUTGOING_CALLS",
    "INTERNATIONAL_CALLS",
    "SMS_SERVICE",
    "DATA_SERVICE",
    "SIM_OPERATIONS",
    "ROAMING",
]

# In-memory live status of each component.
# In a production system this would be backed by a database / API gateway.
COMPONENT_STATUS = {comp: "ACTIVE" for comp in ALL_COMPONENTS}


# ---------------------------------------------------------------------------
# Component state management
# ---------------------------------------------------------------------------

def block_component(name):
    """Mark a component as BLOCKED."""
    if name in COMPONENT_STATUS:
        COMPONENT_STATUS[name] = "BLOCKED"


def unblock_component(name):
    """Restore a component to ACTIVE."""
    if name in COMPONENT_STATUS:
        COMPONENT_STATUS[name] = "ACTIVE"


def shutdown_component(name):
    """Mark a component as fully SHUTDOWN (stronger than BLOCKED)."""
    if name in COMPONENT_STATUS:
        COMPONENT_STATUS[name] = "SHUTDOWN"


def is_blocked(name):
    """Return True if the component is BLOCKED or SHUTDOWN."""
    return COMPONENT_STATUS.get(name) in ("BLOCKED", "SHUTDOWN")


def get_component_status():
    """Return a copy of the current component-status dict."""
    return dict(COMPONENT_STATUS)


def reset_all_components():
    """Set every component back to ACTIVE."""
    for comp in ALL_COMPONENTS:
        COMPONENT_STATUS[comp] = "ACTIVE"


# ---------------------------------------------------------------------------
# Protection action recommendations (original logic, preserved)
# ---------------------------------------------------------------------------

def protection_action(probability, input_data):
    actions = []

    if probability >= 0.85:
        actions.append("BLOCK_OUTGOING_CALLS")
        actions.append("BLOCK_INTERNATIONAL_CALLS")
        actions.append("REQUIRE_CUSTOMER_VERIFICATION")
        actions.append("ESCALATE_TO_FRAUD_TEAM")

    elif probability >= 0.70:
        actions.append("BLOCK_INTERNATIONAL_CALLS")
        actions.append("LIMIT_DAILY_CALLS")
        actions.append("REQUIRE_CUSTOMER_VERIFICATION")

    elif probability >= 0.50:
        actions.append("ENABLE_ENHANCED_MONITORING")
        actions.append("SEND_WARNING_TO_CUSTOMER")

    elif probability >= 0.30:
        actions.append("MONITOR_ACCOUNT")

    else:
        actions.append("NO_ACTION")

    if input_data["sim_changes"] >= 5:
        actions.append("LOCK_SIM_SWAP_REQUEST")

    if input_data["international_calls"] > 300:
        actions.append("TEMP_BLOCK_ROAMING")

    return actions


# ---------------------------------------------------------------------------
# Per-SIM status tracking
# ---------------------------------------------------------------------------
# Maps SIM IDs to their current operational state.
# In production this would be backed by the carrier's SIM management platform.
SIM_STATUS = {}  # sim_id -> "ACTIVE" / "BANNED" / "DEACTIVATED"


def ban_sim(sim_id):
    """Mark a SIM as temporarily BANNED."""
    SIM_STATUS[sim_id] = "BANNED"


def unban_sim(sim_id):
    """Restore a SIM to ACTIVE status."""
    SIM_STATUS[sim_id] = "ACTIVE"


def deactivate_sim(sim_id):
    """Permanently DEACTIVATE a SIM (Level 3 penalty)."""
    SIM_STATUS[sim_id] = "DEACTIVATED"


def is_sim_banned(sim_id):
    """Return True if the SIM is BANNED or DEACTIVATED."""
    return SIM_STATUS.get(sim_id) in ("BANNED", "DEACTIVATED")


def get_sim_status(sim_id):
    """Return the current status string for a SIM (ACTIVE if unknown)."""
    return SIM_STATUS.get(sim_id, "ACTIVE")


def get_all_sim_statuses():
    """Return a copy of the entire SIM status dict."""
    return dict(SIM_STATUS)