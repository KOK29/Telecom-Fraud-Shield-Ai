# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
import os

from predictor import predict_fraud, explain_fraud
from protection_engine import (
    protection_action,
    get_component_status,
    ALL_COMPONENTS,
    reset_all_components,
    get_sim_status,
    ban_sim,
    unban_sim,
    deactivate_sim,
)
import protection_engine as pe_module  # passed to defense_engine as the manager
from case_manager import (
    create_fraud_case,
    resolve_case,
    get_all_cases,
    get_cases_by_sim,
    appeal_case,
)
from alert_system import generate_alert
from defense_engine import (
    enforce_defense,
    lift_defense,
    lift_all_defenses,
    get_defense_log,
)
from sim_registry import (
    register_sim,
    get_sim_record,
    get_all_sims,
    get_notifications,
    get_pending_appeals,
    resolve_appeal,
    check_ban_expired,
    update_risk_score,
)
from escalation_engine import calculate_risk_score, PENALTY_LEVELS

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FraudShield AI Protective System",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ FraudShield AI")
st.subheader("Real-Time Telecom Fraud Detection & Protection System")

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar – SIM ID & customer activity inputs
# ──────────────────────────────────────────────────────────────────────────────
st.sidebar.header("SIM Card Identity")
sim_id = st.sidebar.text_input(
    "SIM ID",
    value="SIM-100001",
    help="Enter the SIM card identifier to track (e.g. SIM-100001)",
)

# Show current SIM status in sidebar
if sim_id:
    rec = get_sim_record(sim_id)
    if rec:
        ban_level = int(rec.get("ban_level", 0))
        risk = int(rec.get("risk_score", 0))
        offenses = int(rec.get("offense_count", 0))

        if rec.get("is_permanently_blocked") in (True, "True", "true", 1):
            st.sidebar.error(f"🔴 PERMANENTLY DEACTIVATED")
        elif ban_level > 0:
            check_ban_expired(sim_id)  # auto-lift if expired
            rec = get_sim_record(sim_id)  # refresh
            ban_level = int(rec.get("ban_level", 0))
            if ban_level > 0:
                st.sidebar.warning(f"⛔ BANNED (Level {ban_level})")
                st.sidebar.caption(f"Expires: {rec.get('ban_expires', 'N/A')}")
            else:
                st.sidebar.success("✅ ACTIVE")
        else:
            st.sidebar.success("✅ ACTIVE")

        st.sidebar.metric("Risk Score", f"{risk}/100")
        st.sidebar.metric("Offense Count", offenses)
    else:
        st.sidebar.info("New SIM — will be registered on first analysis")

st.sidebar.divider()
st.sidebar.header("Live Customer Activity")

input_data = {
    "age": st.sidebar.slider("Age", 18, 75, 30),
    "account_age_days": st.sidebar.slider("Account Age Days", 1, 1500, 200),
    "calls_per_day": st.sidebar.slider("Calls Per Day", 0, 1000, 20),
    "avg_call_duration": st.sidebar.slider("Average Call Duration", 0.1, 12.0, 3.0),
    "unique_numbers_called": st.sidebar.slider("Unique Numbers Called", 1, 700, 10),
    "international_calls": st.sidebar.slider("International Calls", 0, 550, 0),
    "sms_per_day": st.sidebar.slider("SMS Per Day", 0, 1700, 20),
    "data_usage_gb": st.sidebar.slider("Data Usage GB", 0.1, 30.0, 5.0),
    "recharge_amount": st.sidebar.slider("Recharge Amount", 1, 150, 20),
    "sim_changes": st.sidebar.slider("SIM Changes", 0, 12, 0),
    "device_changes": st.sidebar.slider("Device Changes", 0, 12, 0),
    "complaints_count": st.sidebar.slider("Complaints Count", 0, 12, 0),
    "roaming_usage": st.sidebar.selectbox("Roaming Usage", [0, 1]),
    "late_payments": st.sidebar.selectbox("Late Payments", [0, 1]),
}

# ──────────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Live Detection",
    "🛡️ Protection Center",
    "📁 Fraud Cases",
    "🚨 Defense Control Center",
    "📊 Risk & SIM Monitor",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – Live Detection  (with automatic defense enforcement)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Customer Activity")
    st.dataframe(pd.DataFrame([input_data]), use_container_width=True, hide_index=True)

    if st.button("Analyze & Protect", use_container_width=True):
        # Register SIM
        register_sim(sim_id)

        result = predict_fraud(input_data)
        probability = result["fraud_probability"]

        reasons = explain_fraud(input_data)
        actions = protection_action(probability, input_data)

        # ── Metrics ──────────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Fraud Probability", f"{probability * 100:.2f}%")
        col2.metric("Risk Level", result["risk_level"])
        col3.metric("Status", result["fraud_status"])

        # Quick risk score preview
        rec = get_sim_record(sim_id)
        offense_count = int(rec.get("offense_count", 0)) if rec else 0
        preview_risk = calculate_risk_score(input_data, probability, offense_count)
        col4.metric("Risk Score", f"{preview_risk}/100")

        if probability >= 0.80:
            st.error("🚨 CRITICAL FRAUD THREAT DETECTED")
        elif probability >= 0.60:
            st.warning("⚠️ HIGH RISK FRAUD DETECTED")
        elif probability >= 0.35:
            st.info("🟡 SUSPICIOUS ACTIVITY")
        else:
            st.success("✅ LOW RISK")

        # ── AI Explanation ───────────────────────────────────────────────
        st.subheader("AI Explanation")
        for reason in reasons:
            st.write("•", reason)

        # ── Protective Actions ───────────────────────────────────────────
        st.subheader("Protective Actions")
        for action in actions:
            st.write("🛡️", action)

        # ── Automatic Defense Enforcement ────────────────────────────────
        defense_report = None
        if probability >= 0.35:
            st.divider()
            st.subheader("⚡ Automatic Defense Enforcement")

            # Create case first to get an ID
            temp_case_id = pd.Timestamp.now().strftime("CASE%Y%m%d%H%M%S")

            defense_report = enforce_defense(
                case_id=temp_case_id,
                probability=probability,
                input_data=input_data,
                component_status_manager=pe_module,
                sim_id=sim_id,
            )

            # Show enforcement result
            tier = defense_report["threat_tier"]
            label = defense_report["threat_label"]
            status = defense_report["defense_status"]

            if tier == "CRITICAL":
                st.error(f"{label} — Defense Status: **{status}**")
            elif tier == "HIGH":
                st.warning(f"{label} — Defense Status: **{status}**")
            else:
                st.info(f"{label} — Defense Status: **{status}**")

            # ── Escalation / Penalty display ─────────────────────────────
            escalation = defense_report.get("escalation_report")
            if escalation:
                st.divider()
                st.subheader("⚡ Escalation & Penalty")

                pen_col1, pen_col2, pen_col3, pen_col4 = st.columns(4)
                pen_col1.metric("Penalty Level", escalation["penalty_label"])
                pen_col2.metric("Ban Duration", escalation["ban_duration_text"])
                pen_col3.metric("Offense Count", escalation["offense_count"])
                pen_col4.metric("Risk Score", f"{escalation['risk_score']}/100")

                # Notification message
                if escalation["penalty_level"] == 1:
                    st.warning(f"📨 **Notification Sent:** {escalation['notification_message']}")
                elif escalation["penalty_level"] == 2:
                    st.error(f"📨 **Final Warning Sent:** {escalation['notification_message']}")
                elif escalation["penalty_level"] == 3:
                    st.error(f"🔴 **PERMANENT DEACTIVATION:** {escalation['notification_message']}")

                if escalation["was_already_banned"]:
                    st.warning("⚠️ This SIM was already under an active ban when this violation occurred.")

            # Blocked components badges
            blocked = defense_report.get("blocked_components", [])
            shutdown = defense_report.get("shutdown_components", [])

            if blocked:
                st.write("**Blocked Components:**")
                badge_cols = st.columns(len(blocked))
                for i, comp in enumerate(blocked):
                    is_shutdown = comp in shutdown
                    icon = "🔻" if is_shutdown else "⛔"
                    state = "SHUTDOWN" if is_shutdown else "BLOCKED"
                    badge_cols[i].error(f"{icon} {comp}\n{state}")

            # Pattern detections
            patterns = defense_report.get("pattern_reasons", [])
            if patterns:
                st.write("**Pattern-Based Detections:**")
                for p in patterns:
                    st.warning(f"⚠ {p}")

            # Live component status after enforcement
            st.write("**Live Component Status After Enforcement:**")
            comp_status = get_component_status()
            status_cols = st.columns(len(ALL_COMPONENTS))
            for i, comp in enumerate(ALL_COMPONENTS):
                state = comp_status[comp]
                if state == "SHUTDOWN":
                    status_cols[i].error(f"🔻 {comp}\nSHUTDOWN")
                elif state == "BLOCKED":
                    status_cols[i].warning(f"⛔ {comp}\nBLOCKED")
                else:
                    status_cols[i].success(f"✅ {comp}\nACTIVE")

        # ── Create fraud case (with defense metadata) ────────────────────
        if probability >= 0.50:
            case = create_fraud_case(
                input_data, result, actions, defense_report, sim_id=sim_id,
            )
            alert = generate_alert(case, defense_report)

            st.divider()
            st.subheader("Fraud Case Created")
            st.success(f"Case created: **{case['case_id']}** — SIM: **{sim_id}** — Status: **{case['status']}**")

            st.subheader("Security Alert")
            st.code(alert)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – Protection Center
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Protection Rule Center")

    st.write("This system can automatically apply these protection actions:")

    st.table(pd.DataFrame([
        ["Critical Risk", "Block outgoing calls, block international calls, require verification"],
        ["High Risk", "Block international calls, limit daily calls"],
        ["Medium Risk", "Enhanced monitoring, warning notification"],
        ["SIM Abuse", "Lock SIM swap request"],
        ["Roaming Abuse", "Temporary roaming block"],
    ], columns=["Threat Type", "Protection Action"]))

    st.divider()
    st.subheader("Defense Enforcement Tiers")
    st.table(pd.DataFrame([
        ["🔴 CRITICAL (≥80%)", "Full account lockdown", "Calls, Intl Calls, SMS, Data, SIM, Roaming", "Calls, Intl Calls, SIM"],
        ["🟠 HIGH (≥60%)", "Partial restriction", "Intl Calls, SIM, Roaming", "Intl Calls"],
        ["🟡 MEDIUM (≥35%)", "Enhanced monitoring", "None", "None"],
        ["🟢 LOW (<35%)", "Passive monitoring", "None", "None"],
    ], columns=["Tier", "Description", "Auto-Blocked Components", "Auto-Shutdown Components"]))

    st.divider()
    st.subheader("Escalating Penalty System")
    st.table(pd.DataFrame([
        ["⚠️ Level 1", "1st Offense", "24-hour temporary ban", "Warning notification sent to user"],
        ["🚫 Level 2", "2nd Offense", "7-day ban", "Final warning — next violation is permanent"],
        ["🔴 Level 3", "3rd+ Offense", "Permanent deactivation", "SIM card permanently blocked"],
    ], columns=["Level", "Trigger", "Ban Duration", "Action"]))

    st.warning(
        "In a real telecom company, these actions must connect to APIs from billing, SIM, CRM, SMS gateway, and network systems."
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – Fraud Cases
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Fraud Case Management")

    # SIM filter
    filter_sim = st.text_input("Filter by SIM ID (leave empty for all)", key="case_sim_filter")

    cases = get_all_cases()
    if filter_sim and not cases.empty and "sim_id" in cases.columns:
        cases = cases[cases["sim_id"] == filter_sim]

    if not cases.empty:
        st.dataframe(cases, use_container_width=True, hide_index=True)

        st.download_button(
            "Download Fraud Cases",
            data=cases.to_csv(index=False),
            file_name="fraud_cases.csv",
            mime="text/csv",
            use_container_width=True
        )

        # Resolve a case
        st.divider()
        st.subheader("Resolve a Case")
        open_cases = cases[cases["status"] != "RESOLVED"]
        if not open_cases.empty:
            case_to_resolve = st.selectbox(
                "Select Case to Resolve",
                open_cases["case_id"].tolist(),
            )
            if st.button("✅ Resolve Case & Lift Defenses"):
                # Get SIM ID from the case
                case_row = cases[cases["case_id"] == case_to_resolve]
                case_sim = case_row["sim_id"].iloc[0] if "sim_id" in case_row.columns else None
                resolve_case(case_to_resolve)
                lift_defense(case_to_resolve, pe_module, sim_id=case_sim)
                st.success(f"Case **{case_to_resolve}** resolved and defenses lifted.")
                st.rerun()
        else:
            st.info("All cases are resolved.")

        # File an appeal
        st.divider()
        st.subheader("📋 File an Appeal")
        appeal_cases = cases[cases["status"].isin(["BLOCKED", "SHUTDOWN", "UNDER_MONITORING"])]
        if not appeal_cases.empty:
            appeal_case_id = st.selectbox(
                "Select Case to Appeal",
                appeal_cases["case_id"].tolist(),
                key="appeal_case_select",
            )
            appeal_reason = st.text_area(
                "Appeal Reason",
                placeholder="Explain why you believe this was a false positive...",
                key="appeal_reason_input",
            )
            if st.button("📤 Submit Appeal", use_container_width=True):
                if appeal_reason.strip():
                    case_row = cases[cases["case_id"] == appeal_case_id]
                    case_sim = case_row["sim_id"].iloc[0] if "sim_id" in case_row.columns else sim_id
                    appeal_case(appeal_case_id, case_sim, appeal_reason)
                    st.success(f"Appeal submitted for case **{appeal_case_id}**. An admin will review it.")
                    st.rerun()
                else:
                    st.error("Please provide a reason for the appeal.")
        else:
            st.info("No active cases available for appeal.")
    else:
        st.info("No fraud cases created yet.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – Defense Control Center
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("🚨 Defense Control Center")
    st.caption("Real-time overview of all active defenses and component states")

    # ── Live Component Status ────────────────────────────────────────────
    st.write("### Live Component Status")
    comp_status = get_component_status()

    cols = st.columns(len(ALL_COMPONENTS))
    active_count = 0
    blocked_count = 0
    shutdown_count = 0

    for i, comp in enumerate(ALL_COMPONENTS):
        state = comp_status[comp]
        if state == "SHUTDOWN":
            cols[i].error(f"🔻 **{comp}**\n\nSHUTDOWN")
            shutdown_count += 1
        elif state == "BLOCKED":
            cols[i].warning(f"⛔ **{comp}**\n\nBLOCKED")
            blocked_count += 1
        else:
            cols[i].success(f"✅ **{comp}**\n\nACTIVE")
            active_count += 1

    # ── SIM Ban Status ───────────────────────────────────────────────────
    st.divider()
    st.write("### SIM Ban Status")
    sim_df = get_all_sims()
    if not sim_df.empty:
        banned_sims = sim_df[sim_df["ban_level"].astype(int) > 0]
        if not banned_sims.empty:
            banned_cols = [
                "sim_id",
                "ban_level",
                "ban_start",
                "ban_expires",
                "is_permanently_blocked",
                "risk_score",
                "offense_count"
            ]
            available_banned_cols = [col for col in banned_cols if col in banned_sims.columns]
            st.dataframe(
                banned_sims[available_banned_cols],
                use_container_width=True,
                hide_index=True
            )

            # Admin unban controls
            st.write("**Admin: Unban a SIM**")
            unban_sim_id = st.selectbox(
                "Select SIM to Unban",
                banned_sims["sim_id"].tolist(),
                key="admin_unban_sim",
            )
            if st.button("🔓 Unban Selected SIM", key="admin_unban_btn"):
                from supabase_client import get_supabase
                get_supabase().table("sims").update({
                    "ban_level": 0,
                    "ban_start": "",
                    "ban_expires": "",
                    "is_permanently_blocked": False
                }).eq("sim_id", unban_sim_id).execute()
                unban_sim(unban_sim_id)
                st.success(f"SIM **{unban_sim_id}** has been unbanned.")
                st.rerun()
        else:
            st.success("No SIMs are currently banned.")
    else:
        st.info("No SIMs registered yet.")

    # ── Summary Metrics ──────────────────────────────────────────────────
    st.divider()
    st.write("### Defense Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Components", active_count)
    m2.metric("Blocked Components", blocked_count)
    m3.metric("Shutdown Components", shutdown_count)

    log_df = get_defense_log()
    enforced_count = len(log_df[log_df["status"] == "ENFORCED"]) if not log_df.empty else 0
    m4.metric("Total Actions Enforced", enforced_count)

    # ── Manual Override Controls ─────────────────────────────────────────
    st.divider()
    st.write("### Manual Override Controls")
    st.caption("⚠️ Use with caution — lifting defenses re-enables blocked services")

    override_col1, override_col2 = st.columns(2)

    with override_col1:
        if st.button("🔓 Lift ALL Defenses", use_container_width=True, type="primary"):
            lifted = lift_all_defenses(pe_module)
            st.success(f"All defenses lifted. Components restored: {', '.join(lifted)}")
            st.rerun()

    with override_col2:
        if st.button("🔄 Reset All Components to ACTIVE", use_container_width=True):
            reset_all_components()
            st.success("All components reset to ACTIVE.")
            st.rerun()

    # Per-component unblock
    blocked_comps = [c for c, s in comp_status.items() if s in ("BLOCKED", "SHUTDOWN")]
    if blocked_comps:
        st.write("**Unblock Individual Components:**")
        unblock_cols = st.columns(len(blocked_comps))
        for i, comp in enumerate(blocked_comps):
            if unblock_cols[i].button(f"Unblock {comp}", key=f"unblock_{comp}"):
                pe_module.unblock_component(comp)
                st.success(f"{comp} restored to ACTIVE.")
                st.rerun()

    # ── Defense Action Log ───────────────────────────────────────────────
    st.divider()
    st.write("### Defense Action Log")
    if not log_df.empty:
        # Show most recent first
        st.dataframe(
            log_df.sort_index(ascending=False),
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 Download Defense Log",
            data=log_df.to_csv(index=False),
            file_name="defense_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("No defense actions recorded yet. Analyze a customer to trigger enforcement.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 – Risk & SIM Monitor
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("📊 Risk & SIM Monitor")
    st.caption("Track risk scores, offense history, and manage appeals for all SIM cards")

    # ── SIM Registry Overview ────────────────────────────────────────────
    st.write("### SIM Registry")
    all_sims = get_all_sims()
    if not all_sims.empty:
        # Color-code the display
        display_cols = [
            "sim_id", "risk_score", "offense_count", "ban_level",
            "ban_expires", "is_permanently_blocked", "appeal_status",
            "last_offense_at", "registered_at",
        ]
        available_cols = [c for c in display_cols if c in all_sims.columns]
        st.dataframe(all_sims[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No SIMs registered yet. Analyze a customer in the Live Detection tab to register a SIM.")

    # ── Current SIM Detail ───────────────────────────────────────────────
    st.divider()
    st.write(f"### SIM Detail: `{sim_id}`")

    current_rec = get_sim_record(sim_id)
    if current_rec:
        detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)

        risk = int(current_rec.get("risk_score", 0))
        offenses = int(current_rec.get("offense_count", 0))
        ban_lvl = int(current_rec.get("ban_level", 0))

        # Risk score with color
        if risk >= 70:
            detail_col1.error(f"🔴 Risk Score: **{risk}/100**")
        elif risk >= 40:
            detail_col1.warning(f"🟡 Risk Score: **{risk}/100**")
        else:
            detail_col1.success(f"🟢 Risk Score: **{risk}/100**")

        detail_col2.metric("Offenses", offenses)

        if ban_lvl == 0:
            detail_col3.success("✅ No Ban")
        elif ban_lvl == 1:
            detail_col3.warning(f"⚠️ Level 1 Ban")
        elif ban_lvl == 2:
            detail_col3.error(f"🚫 Level 2 Ban")
        elif ban_lvl == 3:
            detail_col3.error(f"🔴 PERMANENTLY DEACTIVATED")

        appeal_st = current_rec.get("appeal_status", "NONE")
        if appeal_st == "PENDING":
            detail_col4.warning(f"📋 Appeal: PENDING")
        elif appeal_st == "APPROVED":
            detail_col4.success(f"✅ Appeal: APPROVED")
        elif appeal_st == "DENIED":
            detail_col4.error(f"❌ Appeal: DENIED")
        else:
            detail_col4.info(f"📋 Appeal: None")

        # Risk score gauge visualization
        st.write("**Risk Score Gauge:**")
        gauge_bar = "█" * risk + "░" * (100 - risk)
        if risk >= 70:
            st.error(f"```\n[{gauge_bar}] {risk}/100 — HIGH RISK\n```")
        elif risk >= 40:
            st.warning(f"```\n[{gauge_bar}] {risk}/100 — MODERATE RISK\n```")
        else:
            st.success(f"```\n[{gauge_bar}] {risk}/100 — LOW RISK\n```")

        # Offense history (from cases)
        st.write("**Offense History:**")
        sim_cases = get_cases_by_sim(sim_id)
        if not sim_cases.empty:
            history_cols = [c for c in [
                "case_id", "created_at", "fraud_probability", "risk_level",
                "penalty_level", "ban_duration", "risk_score", "status",
            ] if c in sim_cases.columns]
            st.dataframe(sim_cases[history_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No offense history for this SIM.")

    else:
        st.info(f"SIM `{sim_id}` is not registered yet. Run an analysis in the Live Detection tab.")

    # ── Appeal Submission ────────────────────────────────────────────────
    st.divider()
    st.write("### 📋 Submit an Appeal")
    st.caption("If your SIM card was wrongly flagged, submit an appeal for admin review.")

    appeal_sim = st.text_input(
        "SIM ID for Appeal",
        value=sim_id,
        key="appeal_sim_input",
    )
    appeal_text = st.text_area(
        "Reason for Appeal",
        placeholder="Explain why you believe the flagging was a false positive. Provide any relevant details...",
        key="appeal_text_tab5",
    )

    if st.button("📤 Submit Appeal", key="submit_appeal_tab5", use_container_width=True):
        if appeal_text.strip():
            rec = get_sim_record(appeal_sim)
            if rec and int(rec.get("ban_level", 0)) > 0:
                from sim_registry import file_appeal
                file_appeal(appeal_sim, appeal_text)
                st.success(f"Appeal submitted for SIM **{appeal_sim}**. An admin will review it shortly.")
                st.rerun()
            else:
                st.warning("This SIM is not currently banned. No appeal necessary.")
        else:
            st.error("Please provide a reason for the appeal.")

    # ── Admin: Pending Appeals ───────────────────────────────────────────
    st.divider()
    st.write("### 🔐 Admin: Pending Appeals")
    st.caption("Review and approve/deny pending appeals from flagged SIM cards")

    pending = get_pending_appeals()

    if not pending.empty:
        pending_cols = [
            "sim_id",
            "offense_count",
            "risk_score",
            "ban_level",
            "appeal_status",
            "appeal_reason"
        ]

        available_pending_cols = [
            col for col in pending_cols
            if col in pending.columns
        ]

        st.dataframe(
            pending[available_pending_cols],
            use_container_width=True,
            hide_index=True
        )

        review_sim = st.selectbox(
            "Select SIM to Review",
            pending["sim_id"].tolist(),
            key="admin_review_sim",
        )

        # Show the appeal reason
        appeal_row = pending[pending["sim_id"] == review_sim].iloc[0]
        st.info(f"**Appeal Reason:** {appeal_row.get('appeal_reason', 'N/A')}")
        st.write(f"**Offense Count:** {appeal_row.get('offense_count', 0)} | "
                 f"**Risk Score:** {appeal_row.get('risk_score', 0)}/100 | "
                 f"**Ban Level:** {appeal_row.get('ban_level', 0)}")

        approve_col, deny_col = st.columns(2)
        with approve_col:
            if st.button("✅ Approve Appeal", key="approve_appeal", use_container_width=True,
                         type="primary"):
                resolve_appeal(review_sim, approved=True)
                unban_sim(review_sim)
                st.success(f"Appeal APPROVED for SIM **{review_sim}**. All restrictions lifted.")
                st.rerun()
        with deny_col:
            if st.button("❌ Deny Appeal", key="deny_appeal", use_container_width=True):
                resolve_appeal(review_sim, approved=False)
                st.error(f"Appeal DENIED for SIM **{review_sim}**. Current penalties remain.")
                st.rerun()
    else:
        st.success("No pending appeals.")

    # ── Notification Log ─────────────────────────────────────────────────
    st.divider()
    st.write("### 📨 Notification Log")
    notif_filter = st.text_input("Filter by SIM ID", key="notif_sim_filter")
    notifs = get_notifications(notif_filter if notif_filter else None)
    if not notifs.empty:
        st.dataframe(notifs.sort_index(ascending=False), use_container_width=True, hide_index=True)

        st.download_button(
            "📥 Download Notification Log",
            data=notifs.to_csv(index=False),
            file_name="notification_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("No notifications recorded yet.")