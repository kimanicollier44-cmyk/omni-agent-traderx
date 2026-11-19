"""Tests for omni-agent-traderx. Every test grades a computed
number or behaviour in main.py (plus the verbatim sandbox chamber)
against an independent recomputation or the stated policy. Tests
import ONLY main.py / sandbox_api.py - no fixtures, no network."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as omni


def test_nsi_bearish_sample():
    assert omni.compute_nsi(omni.SAMPLE_PARTS_BEARISH) == -53.47
    assert omni.compute_nsi(omni.SAMPLE_PARTS_BULLISH) == 45.0
    assert abs(sum(omni.NSI_WEIGHTS.values()) - 1.0) < 1e-12


def test_bear_pricing_sample():
    bear = omni.bear_pricing(-53.47)
    assert bear["multiplier"] == 1.802
    assert bear["price_usd"] == 180.21
    assert bear["supply"] == 1
    assert omni.bear_pricing(90.0)["price_usd"] == 25.00
    assert omni.bear_pricing(-200.0)["price_usd"] == 300.00


def test_bear_mint_burn_blocked():
    assert omni.bear_mint_attempt()["status"] == "HOLD"
    assert omni.bear_burn_attempt()["gate"] == "bear_mint_burn"


def test_regime_thresholds():
    assert omni.regime_for_nsi(-20) == "BEARISH_REGIME"
    assert omni.regime_for_nsi(20) == "BULLISH_REGIME"
    assert omni.regime_for_nsi(0) == "NEUTRAL_REGIME"


def test_hedge_branches():
    bearish = omni.hedge_decision("BEARISH_REGIME", 800.0)
    assert bearish["hedge"] == "ON"
    assert bearish["effective_notional_usd"] == 500.0
    assert bearish["bear_hedge_usd"] == 300.00
    bullish = omni.hedge_decision("BULLISH_REGIME", 800.0)
    assert bullish["hedge"] == "OFF"
    assert bullish["bear_hedge_usd"] == 0.0


def test_multi_asset_routing_and_clamp():
    rep = omni.multi_asset_report()
    assert rep["total_routed_usd"] == 2500.0
    assert rep["signals"][-1]["routed_notional_usd"] == 1000.0
    live = omni.route_signal({"assetClass": "crypto",
                              "symbol": "BTC", "mode": "live"})
    assert live["status"] == "HOLD"


def test_hft_caps_and_live_hold():
    rep = omni.hft_report()
    assert rep["oversized_clamped"]["max_notional_usd"] == 1000.0
    assert rep["oversized_clamped"]["max_slippage_bps"] == 100
    assert rep["live_attempt"]["status"] == "HOLD"
    assert rep["live_attempt"]["private_key_exposed"] is False


def test_intent_parser():
    parsed = omni.parse_intent(
        "Rebalance my portfolio to target and reduce risk")
    assert parsed["intent"] == "rebalance_portfolio"
    assert parsed["risk_mode"] == "defensive"
    assert parsed["live_calls"] == 0
    parsed = omni.parse_intent("Buy MON and hedge with BEAR")
    assert parsed["intent"] == "buy"
    assert parsed["assets"] == ["MON"]
    assert parsed["hedge"] is True


def test_rebalance_math():
    plan = omni.rebalance_plan()
    assert plan["total_usd"] == 10000.0
    assert plan["net_delta_usd"] == 0.0
    assert plan["gross_turnover_usd"] == 1400.0
    assert plan["orders_submitted"] == 0
    legs = {leg["asset"]: leg for leg in plan["legs"]}
    assert legs["BTC"]["delta_usd"] == -700.0
    assert legs["ETH"]["delta_usd"] == 400.0
    assert legs["MON"]["delta_usd"] == 300.0


def test_risk_manager():
    assert omni.risk_check_order(400.0)["approved"] is True
    assert omni.risk_check_order(750.0)["approved"] is False
    assert omni.risk_check_order(100.0, halted=True)["approved"] is False
    assert omni.kill_switch(10000.0, 9200.0)["tripped"] is False
    trip = omni.kill_switch(10000.0, 8800.0)
    assert trip["tripped"] is True
    assert trip["drawdown_pct"] == 12.0
    assert trip["auto_clear"] is False


def test_sandbox_triage_counts():
    rep = omni.sandbox_report()
    assert rep["allowed"] == 3
    assert rep["held"] == 3
    assert rep["any_executed"] is False
    assert rep["network_attempts_total"] == 0


def test_sandbox_chamber_verbatim_sha():
    import hashlib
    path = Path(__file__).resolve().parent.parent / "sandbox_api.py"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == ("28b3365c0466027079a4985520840f6532d7d9a0c5"
                      "b4239b840e561f06de54b0")


def test_honeypotx_counts():
    rep = omni.honeypotx_report()
    assert rep["attempts"] == 12
    assert rep["by_class"] == {"scanner": 4, "env_harvest": 3,
                               "lfi_probe": 2, "sqli_probe": 2,
                               "upload_attempt": 1}
    assert rep["top_threat_score"] == 100
    assert len(rep["bursts"]) == 1
    assert rep["listener_open"] is False
    assert rep["access_granted"] is False


def test_gateway_402_shape():
    status, body = omni.handle_execute(
        {}, {"capability": "trading", "payload": {}})
    assert status == 402
    assert body["x402Version"] == 1
    assert body["error"] == "Payment Required"
    accept = body["accepts"][0]
    assert accept["scheme"] == "exact"
    assert accept["network"] == "monad-mainnet"
    assert accept["maxAmountRequired"] == omni.PRICE_ATOMIC
    assert accept["description"] == "All-in-One omni-agent-traderx"
    assert accept["asset"] == omni.USDC_MONAD


def test_gateway_paid_all_capabilities():
    for cap in omni.CAPABILITIES:
        status, resp = omni.handle_execute(
            {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
            {"capability": cap, "payload": {}})
        assert status == 200 and resp["ok"] is True
        assert omni.verify_receipt(resp["receipt"])


def test_gateway_trading_caps_clamp():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "trading",
         "payload": {"maxNotionalUsd": 99999.0,
                     "maxSlippageBps": 999}})
    assert status == 200
    dispatch = resp["result"]["dispatch"]
    assert dispatch["max_notional_usd"] == 1000.0
    assert dispatch["max_slippage_bps"] == 100
    assert dispatch["mode"] == "dry_run"


def test_gateway_defi_defaults():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "defi", "payload": {}})
    assert status == 200
    dispatch = resp["result"]["dispatch"]
    assert dispatch["pool"] == "MON/USDC"
    assert dispatch["liquidity_check"] == "passed"
    assert dispatch["slippage_guard_bps"] == 50


def test_gateway_errors_400():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "nope", "payload": {}})
    assert status == 400 and resp["ok"] is False
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "trading", "payload": {"mode": "live"}})
    assert status == 400 and "HOLD" in resp["error"]
    status, resp = omni.handle_execute(
        {"X-PAYMENT": "forged"},
        {"capability": "trading", "payload": {}})
    assert status == 400


def test_gateway_chamber_blocks_first():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "data",
         "payload": {"leak": "AGENT_SIGNER_KEY"}})
    assert status == 400
    assert "sandbox chamber HOLD" in resp["error"]


def test_receipt_tamper_fails():
    _, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "research", "payload": {}})
    receipt = dict(resp["receipt"])
    assert omni.verify_receipt(receipt)
    receipt["resultHash"] = "0" * 64
    assert omni.verify_receipt(receipt) is False
    assert "DEMO/OFFLINE" in resp["receipt"]["signer"]


def test_facilitator_stubs_hold():
    verify = omni.facilitator_verify(omni.DEMO_PAYMENT_HEADER)
    assert verify["status"] == "HOLD"
    assert verify["verified"] is False
    assert verify["endpoint"].endswith("/verify")
    settle = omni.facilitator_settle(omni.DEMO_PAYMENT_HEADER)
    assert settle["settled"] is False


def test_agent_card():
    card = omni.agent_card()
    assert card["name"] == "omni-agent-traderx"
    assert card["capabilities"] == omni.CAPABILITIES
    assert card["erc8004"]["identity_registry"] == (
        "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432")
    assert card["erc8004"]["reputation_registry"] == (
        "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63")
    assert len(card["merged_sources"]) == 8
    assert card["merged_sources"][-1] == "sol-plex-problems"
    mint = omni.erc8004_mint_attempt()
    assert mint["status"] == "HOLD"
    assert mint["transaction_submitted"] is False


def test_broadcast_queue():
    rep = omni.broadcast_report()
    assert rep["queued"] == 3
    assert rep["posts_sent"] == 0
    assert rep["voice"]["speech_recognition_run"] is False
    assert rep["voice"]["praw_run"] is False
    assert rep["reddit"]["values_read"] is False
    assert rep["reddit"]["live_posting"] == "HOLD"


def test_inspector_counts():
    rep = omni.inspect_rpc_trace()
    assert rep["traces_parsed"] == 10
    assert rep["clean"] == 6
    assert rep["flagged"] == 4
    assert [f["flag"] for f in rep["flags"]] == [
        "unknown_contract", "live_send_attempt", "chain_mismatch",
        "malformed_response"]
    assert rep["network_attempts"] == 0
    assert rep["browser_extension_shipped"] is False
    assert rep["live_monitoring"] == "HOLD"


def test_classifier():
    rep = omni.classifier_report()
    assert rep["bearish_deep"]["knn"] == "bearish-hedge-on"
    assert rep["bullish_deep"]["knn"] == "bullish-hedge-off"
    for feats, label in omni.TRAINING_GRID:
        assert omni.classify_features(feats) == label


def test_hold_gates():
    assert len(omni.HOLD_GATES) == 21
    for action in ("live_trading", "live_hft_execution",
                   "x402_live_settlement", "facilitator_live_verify",
                   "erc8004_live_mint", "bear_mint_burn",
                   "private_key_exposure", "coinbase_live_trading",
                   "coinbase_live_connection", "social_live_posting",
                   "live_honeypot_listener", "live_sample_detonation",
                   "live_rpc_monitoring", "solplex_live_cloud"):
        assert omni.gate(action) == "HOLD"
    assert omni.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    brains = omni.brains_report()
    assert brains["decider"]["can_override_hold"] is False
    assert brains["decider"]["model_id"] == "gemini-argon-4"
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False


def test_argon4_trace_recomputes_and_stress_control():
    brains = omni.brains_report()
    decider = brains["decider"]
    assert decider["trace_sha256_16"] == omni._trace(
        decider["trace_input"])
    assert decider["pipeline"] == ["MAP", "MODEL", "STRESS",
                                   "DECIDE"]
    assert decider["tiers"] == [2048, 8192, 32768]
    stress = brains["argon_stress"]
    assert all(v == "PROCEED"
               for v in stress["other_seats"].values())
    assert stress["argon_decision"] == "HOLD"
    assert stress["final_decision"] == "HOLD"
    assert stress["trace_sha256_16"] == omni._trace(
        stress["trace_input"])


def test_solplex_decomposition_and_routing():
    rep = omni.solplex_solve_problem()
    assert rep["subproblem_count"] == 8
    assert rep["routed_count"] == 8
    assert rep["domains_detected"] == [
        "regime_risk", "portfolio", "payments_gateway",
        "communications", "safety_constraints"]
    assert all(s["outcome"]["ok"] for s in rep["subproblems"])
    pos = {name: i for i, name in
           enumerate(rep["execution_order"])}
    assert all(pos[d] < pos[s["id"]] for s in rep["subproblems"]
               for d in s["depends_on"])
    assert rep["verdict"].startswith("PROCEED")
    assert rep["hold_gates_tripped"] == []
    assert rep["live_cloud_calls"] == 0
    assert rep["live_cloud_gate"] == "HOLD"


def test_solplex_solver_matches_brute_force():
    anneal = omni.solplex_anneal()
    referee = omni.solplex_brute_force()
    assert referee["space_size"] == 120
    assert referee["evaluated"] == 120
    assert anneal["best_choice"] == referee["best_choice"]
    assert anneal["best_cost"] == referee["best_cost"] == 0.0
    assert anneal["best_choice"] == {
        "hedge_ratio": 0.6, "notional_usd": 500.0,
        "gateway_mode": "dry_run", "broadcast": "queue_only"}


def test_flowx_planner_both_flows():
    fx = omni.flowx_plan()
    assert fx["subtasks"] == 9
    assert fx["level_count"] == 5
    assert fx["level_sizes"] == [2, 3, 2, 1, 1]
    assert sum(fx["level_sizes"]) == fx["subtasks"]
    assert fx["recommended_agents"] == 3
    assert fx["queue_wait"] == 0
    assert fx["wall_clock_steps"] == fx["critical_path_steps"] == 5
    brains = omni.brains_report()
    assert brains["both_flows_used"] is True
    assert brains["flows"] == ["Gemini-FlowX", "Google Flow"]
    assert brains["flow"]["rendered"] is False


def test_checks_all_pass():
    checks = omni.run_checks()
    assert all(ok for _, ok in checks), [
        n for n, ok in checks if not ok]
    assert len(checks) == 75


def test_cli_hold_demo_exit_2():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent
                             / "main.py"), "hold-demo"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "HOLD" in proc.stdout


def test_cli_checks_command():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent
                             / "main.py"), "checks"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "CHECKS 75/75" in proc.stdout


def test_cli_agent_card_matches_generated_file():
    import json
    root = Path(__file__).resolve().parent.parent
    committed = json.loads((root / "agent-card.json").read_text())
    assert committed == omni.agent_card()


def test_demo_deterministic():
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    a = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    b = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    assert a.stdout == b.stdout and a.returncode == 0
