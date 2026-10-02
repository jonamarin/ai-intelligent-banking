"""Tests for demo/scenarios.py — offline, no DB, no API key.

`docs/implementation-roadmap.md` Phase 12: "each scenario has an automated
assertion of its expected outcome, run in CI." One test per
`docs/demo-script.md` scenario (A-L), asserting the specific grade
`demo/scenarios.py` computes — `PASS` where the documented guarantee holds
exactly, `PARTIAL` where it's a known, already-documented, non-unsafe
limitation. No scenario is graded `FAIL` today; a future regression that
breaks one of these guarantees fails its specific test here, not just the
aggregate `demo/run.py` walkthrough.
"""

from demo import scenarios


def test_scenario_a_legitimate_transaction_passes() -> None:
    result = scenarios.scenario_a_legitimate_transaction()
    assert result.grade == "PASS"


def test_scenario_b_clear_fraud_passes() -> None:
    result = scenarios.scenario_b_clear_fraud()
    assert result.grade == "PASS"


def test_scenario_c_ambiguous_transaction_passes() -> None:
    result = scenarios.scenario_c_ambiguous_transaction()
    assert result.grade == "PASS"


def test_scenario_d_critical_high_value_passes() -> None:
    result = scenarios.scenario_d_critical_high_value()
    assert result.grade == "PASS"


def test_scenario_e_llm_unavailable_passes() -> None:
    result = scenarios.scenario_e_llm_unavailable()
    assert result.grade == "PASS"


def test_scenario_f_db_or_model_unavailable_passes() -> None:
    """PASS since Phase 15 wired the fraud model into live orchestration:
    the DB half is verified elsewhere (tests/reliability/test_db_timeout.py)
    and the model-degraded-propagation half is verified directly in this
    scenario function (src/ml/score.py, src/orchestration/live_case.py)."""
    result = scenarios.scenario_f_db_or_model_unavailable()
    assert result.grade == "PASS"


def test_scenario_g_prompt_injection_passes() -> None:
    result = scenarios.scenario_g_prompt_injection()
    assert result.grade == "PASS"


def test_scenario_h_missing_data_passes() -> None:
    result = scenarios.scenario_h_missing_data()
    assert result.grade == "PASS"


def test_scenario_i_conflicting_evidence_passes() -> None:
    result = scenarios.scenario_i_conflicting_evidence()
    assert result.grade == "PASS"


def test_scenario_j_duplicate_action_is_partial_not_failed() -> None:
    """PARTIAL — only the offline-checkable half (idempotency-key
    derivation) is verified here; the DB round trip is verified live
    (src/policies/README.md, src/api/README.md)."""
    result = scenarios.scenario_j_duplicate_action()
    assert result.grade == "PARTIAL"


def test_scenario_k_human_escalation_is_partial_not_failed() -> None:
    """PARTIAL — the system proposes ask_question rather than escalate for
    this fixture, a genuine pre-existing limitation
    (src/orchestration/README.md), not an unsafe outcome."""
    result = scenarios.scenario_k_human_escalation()
    assert result.grade == "PARTIAL"


def test_scenario_l_policy_rejection_passes() -> None:
    result = scenarios.scenario_l_policy_rejection()
    assert result.grade == "PASS"


def test_no_scenario_is_ever_graded_fail_today() -> None:
    """The aggregate guarantee `demo/run.py`'s exit code depends on: if this
    ever regresses to FAIL, both this test and the specific scenario test
    above catch it."""
    results = scenarios.run_all_scenarios()
    failed = [r for r in results if r.grade == "FAIL"]
    assert failed == []


def test_all_twelve_scenarios_are_present_and_uniquely_lettered() -> None:
    results = scenarios.run_all_scenarios()
    letters = [r.scenario for r in results]
    assert letters == list("ABCDEFGHIJKL")
