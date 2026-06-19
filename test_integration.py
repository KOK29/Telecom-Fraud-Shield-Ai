"""Integration test for the enhanced FraudShield AI system."""

from sim_registry import (
    register_sim, record_offense, set_ban, get_sim_record,
    update_risk_score, file_appeal, resolve_appeal, check_ban_expired,
    get_all_sims, get_notifications,
)
from escalation_engine import escalate, calculate_risk_score
from predictor import predict_fraud

# Sample high-fraud input data
fraud_data = {
    "calls_per_day": 600,
    "unique_numbers_called": 300,
    "international_calls": 200,
    "sms_per_day": 50,
    "sim_changes": 4,
    "device_changes": 4,
    "avg_call_duration": 0.5,
    "account_age_days": 30,
    "age": 25,
    "data_usage_gb": 5,
    "recharge_amount": 20,
    "complaints_count": 3,
    "roaming_usage": 1,
    "late_payments": 1,
}


def test_risk_score():
    print("=== Test: Risk Score Calculation ===")
    score_0 = calculate_risk_score(fraud_data, 0.75, 0)
    score_2 = calculate_risk_score(fraud_data, 0.75, 2)
    score_3 = calculate_risk_score(fraud_data, 0.75, 3)
    print(f"  0 offenses: {score_0}/100")
    print(f"  2 offenses: {score_2}/100")
    print(f"  3 offenses: {score_3}/100")
    assert score_2 > score_0, "More offenses should mean higher risk"
    assert score_3 > score_2, "Even more offenses should mean even higher risk"
    assert 0 <= score_0 <= 100, "Score must be 0-100"
    print("  PASSED")


def test_escalation():
    print("=== Test: 3-Level Escalation ===")
    sim = "TEST-ESC-001"
    register_sim(sim)

    # 1st offense → Level 1 (24h ban)
    r1 = escalate(sim, "CASE-E1", 0.75, fraud_data)
    print(f"  1st: Level {r1['penalty_level']}, Ban: {r1['ban_duration_text']}")
    assert r1["penalty_level"] == 1
    assert r1["ban_duration_text"] == "24 hours"
    assert not r1["is_permanent"]

    # 2nd offense → Level 2 (7 days)
    r2 = escalate(sim, "CASE-E2", 0.80, fraud_data)
    print(f"  2nd: Level {r2['penalty_level']}, Ban: {r2['ban_duration_text']}")
    assert r2["penalty_level"] == 2
    assert r2["ban_duration_text"] == "7 days"
    assert not r2["is_permanent"]

    # 3rd offense → Level 3 (permanent)
    r3 = escalate(sim, "CASE-E3", 0.90, fraud_data)
    print(f"  3rd: Level {r3['penalty_level']}, Ban: {r3['ban_duration_text']}, Permanent: {r3['is_permanent']}")
    assert r3["penalty_level"] == 3
    assert r3["ban_duration_text"] == "Permanent"
    assert r3["is_permanent"]
    print("  PASSED")


def test_appeal():
    print("=== Test: Appeal Process ===")
    sim = "TEST-APPEAL-001"
    register_sim(sim)

    # Create an offense and ban
    escalate(sim, "CASE-A1", 0.70, fraud_data)
    rec = get_sim_record(sim)
    print(f"  Before appeal: ban_level={rec['ban_level']}, offenses={rec['offense_count']}")
    assert int(rec["ban_level"]) == 1

    # File appeal
    file_appeal(sim, "This was a false positive")
    rec = get_sim_record(sim)
    print(f"  Appeal status: {rec['appeal_status']}")
    assert rec["appeal_status"] == "PENDING"

    # Approve appeal
    resolve_appeal(sim, approved=True)
    rec = get_sim_record(sim)
    print(f"  After approve: ban_level={rec['ban_level']}, offenses={rec['offense_count']}, appeal={rec['appeal_status']}")
    assert int(rec["ban_level"]) == 0
    assert int(rec["offense_count"]) == 0
    assert rec["appeal_status"] == "APPROVED"
    print("  PASSED")


def test_appeal_denied():
    print("=== Test: Appeal Denied ===")
    sim = "TEST-DENY-001"
    register_sim(sim)
    escalate(sim, "CASE-D1", 0.70, fraud_data)

    file_appeal(sim, "I didn't do it")
    resolve_appeal(sim, approved=False)
    rec = get_sim_record(sim)
    print(f"  After deny: ban_level={rec['ban_level']}, appeal={rec['appeal_status']}")
    assert int(rec["ban_level"]) == 1  # ban remains
    assert rec["appeal_status"] == "DENIED"
    print("  PASSED")


def test_notifications():
    print("=== Test: Notification Log ===")
    notifs = get_notifications()
    print(f"  Total notifications: {len(notifs)}")
    assert len(notifs) > 0, "Should have logged notifications"
    print("  PASSED")


def test_predict_and_score():
    print("=== Test: Prediction + Risk Score Integration ===")
    result = predict_fraud(fraud_data)
    prob = result["fraud_probability"]
    score = calculate_risk_score(fraud_data, prob, 0)
    print(f"  Fraud probability: {prob:.4f}")
    print(f"  Risk score: {score}/100")
    assert 0 <= prob <= 1
    assert 0 <= score <= 100
    print("  PASSED")


if __name__ == "__main__":
    test_risk_score()
    test_escalation()
    test_appeal()
    test_appeal_denied()
    test_notifications()
    test_predict_and_score()
    print("\n" + "=" * 50)
    print("  ALL TESTS PASSED ✓")
    print("=" * 50)
