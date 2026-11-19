"""Tests for omni-agent-traderx. Every test grades a computed
number or behaviour in main.py (plus the verbatim sandbox chamber)
against an independent recomputation, a published test vector, or
the stated policy. Live paths are exercised end-to-end against
injected fake transports - zero network, zero real credentials."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as omni

ROOT = Path(__file__).resolve().parent.parent
TEST_KEY_HEX = "0x" + "00" * 31 + "01"
REG_ENV = {"AGENT_SIGNER_KEY": TEST_KEY_HEX,
           "MONAD_RPC_URL": "https://rpc.test"}
GATEWAY_ENV = {"AGENT_PAY_TO": "0xE7512f65508306Dc669Ef232Bcb31A8Aacd73A37",
               "USDC_MONAD": omni.USDC_MONAD, "PRICE_ATOMIC": "10000",
               "AGENT_SIGNER_KEY": TEST_KEY_HEX,
               "HFT_BRIDGE_URL": "https://hft-bridge.test/orders"}


def _combined_transport(request):
    if "facilitator" in request["url"]:
        return omni.demo_facilitator_transport(request)
    if "hft-bridge" in request["url"]:
        return omni.demo_hft_transport(request)
    raise AssertionError(request["url"])


# ------------------------------------------------------------ crypto core
def test_keccak_vectors():
    assert omni.keccak256(b"").hex() == (
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045"
        "d85a470")
    assert omni.keccak256(b"abc").hex() == (
        "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12"
        "d6c45")


def test_secp256k1_address_vector():
    assert omni.privkey_to_address(1) == (
        "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf")
    assert omni.TEST_ADDRESS == omni.privkey_to_address(
        omni.TEST_PRIVATE_KEY)


def test_eip55_checksum_vector():
    # Darion's Monad wallet, already public in the
    # Monad-Bearish-Bull README - checksum format example only.
    raw = bytes.fromhex("e7512f65508306dc669ef232bcb31a8aacd73a37")
    assert omni.to_checksum_address(raw) == (
        "0xE7512f65508306Dc669Ef232Bcb31A8Aacd73A37")


def test_ecdsa_sign_verify_recover_deterministic():
    digest = omni.keccak256(b"omni test")
    v, r, s = omni.sign_digest(1, digest)
    assert omni.verify_digest(omni._ec_mul(1), digest, r, s)
    assert omni.ecrecover(digest, v, r, s) == omni.TEST_ADDRESS
    assert omni.sign_digest(1, digest) == (v, r, s)  # RFC6979
    assert s <= omni._SECP_N // 2  # low-s


def test_message_signing_roundtrip():
    sig = omni.sign_message(1, b"receipt-digest")
    assert omni.recover_message_signer(b"receipt-digest", sig) == (
        omni.TEST_ADDRESS)
    assert omni.recover_message_signer(b"other", sig) != (
        omni.TEST_ADDRESS)


# ------------------------------------------------------------ regime / BEAR
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


def test_bear_mint_burn_source_invariant():
    # Not a refusal: the source token has no mint function.
    assert omni.bear_mint_attempt()["status"] == "NOT_A_FUNCTION"
    assert omni.bear_burn_attempt()["status"] == "NOT_A_FUNCTION"
    assert omni.bear_mint_attempt()["supply"] == 1


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
    neutral = omni.hedge_decision("NEUTRAL_REGIME", 800.0)
    assert neutral["effective_notional_usd"] == 750.0
    assert neutral["bear_hedge_usd"] == 187.50


# ------------------------------------------------------------ routing / HFT
def test_multi_asset_routing_and_clamp():
    rep = omni.multi_asset_report()
    assert rep["total_routed_usd"] == 2500.0
    assert rep["signals"][-1]["routed_notional_usd"] == 1000.0


def test_multi_asset_live_config_missing():
    live = omni.route_signal({"assetClass": "crypto",
                              "symbol": "BTC", "mode": "live"},
                             env={})
    assert live["status"] == "CONFIG-MISSING"
    assert live["missing"] == ["HFT_BRIDGE_URL"]
    assert live["orderSubmitted"] is False


def test_multi_asset_live_via_bridge_double():
    live = omni.route_signal(
        {"assetClass": "crypto", "symbol": "MON", "side": "buy",
         "notionalUsd": 250.0, "mode": "live"},
        env={"HFT_BRIDGE_URL": "https://hft-bridge.test/orders"},
        transport=omni.demo_hft_transport)
    assert live["status"] == "routed_live"
    assert live["orderSubmitted"] is True
    assert live["dispatch"]["fills"][0]["filled"] is True


def test_hft_caps_and_live():
    rep = omni.hft_report()
    assert rep["oversized_clamped"]["max_notional_usd"] == 1000.0
    assert rep["oversized_clamped"]["max_slippage_bps"] == 100
    assert rep["live_attempt"]["status"] == "CONFIG-MISSING"
    assert rep["live_attempt"]["missing"] == ["HFT_BRIDGE_URL"]
    assert rep["live_attempt"]["private_key_exposed"] is False
    assert rep["live_demo"]["status"] == "submitted"
    assert rep["live_demo"]["order_submitted"] is True


# ------------------------------------------------------------ Muse layer
def test_intent_parser():
    parsed = omni.parse_intent(
        "Rebalance my portfolio to target and reduce risk")
    assert parsed["intent"] == "rebalance_portfolio"
    assert parsed["risk_mode"] == "defensive"
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


def test_coinbase_signature_known_answer():
    import base64
    import hashlib
    import hmac as hmac_mod
    secret = base64.b64encode(b"test-secret-bytes").decode()
    body = '{"product_id":"BTC-USD"}'
    expected = base64.b64encode(hmac_mod.new(
        base64.b64decode(secret),
        f"1700000000POST/orders{body}".encode(),
        hashlib.sha256).digest()).decode()
    assert omni.coinbase_signature(
        secret, "1700000000", "POST", "/orders", body) == expected


def test_coinbase_client_config_missing():
    out = omni.coinbase_accounts(env={})
    assert out["status"] == "CONFIG-MISSING"
    assert out["missing"] == omni.COINBASE_ENV_NAMES


def test_coinbase_live_rebalance_via_double():
    out = omni.execute_rebalance_live(
        env=omni.DEMO_COINBASE_ENV,
        transport=omni.demo_coinbase_transport,
        timestamp="1700000000")
    assert out["status"] == "submitted"
    assert out["orders_submitted"] == 3
    assert out["rejected"] == []
    assert all(o["order"]["http_status"] == 200
               for o in out["orders"])
    accounts = omni.coinbase_accounts(
        env=omni.DEMO_COINBASE_ENV,
        transport=omni.demo_coinbase_transport,
        timestamp="1700000000")
    assert accounts["status"] == "ok"
    assert accounts["response"][0]["currency"] == "BTC"
    book = omni.coinbase_product_book(
        "BTC-USD", env=omni.DEMO_COINBASE_ENV,
        transport=omni.demo_coinbase_transport,
        timestamp="1700000000")
    assert book["response"]["bids"][0][0] == "89999.00"


def test_coinbase_order_payload_builder():
    payload = omni.coinbase_limit_order_payload(
        "BTC-USD", "SELL", 90000.0, "0.00555555")
    assert payload == {"product_id": "BTC-USD", "side": "sell",
                       "type": "limit", "price": "90000.0",
                       "size": "0.00555555", "time_in_force": "GTC"}


# ------------------------------------------------------------ chamber
def test_sandbox_triage_counts():
    rep = omni.sandbox_report()
    assert rep["allowed"] == 4
    assert rep["held"] == 2
    assert rep["any_executed"] is False
    assert rep["network_attempts_total"] == 0


def test_sandbox_chamber_verbatim_sha():
    import hashlib
    path = ROOT / "sandbox_api.py"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == ("28b3365c0466027079a4985520840f6532d7d9a0c5"
                      "b4239b840e561f06de54b0")


# ------------------------------------------------------------ HoneypotX
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


def test_honeypot_listener_handler_logic():
    state = []
    status, body = omni.honeypot_process(
        state, "GET", "/.env", "", "curl/8", ip="198.51.100.7")
    assert status == 200 and body["bait"] is True
    assert "not-real" in body["content"]
    status, body = omni.honeypot_process(
        state, "GET", omni.EXECUTE_RESOURCE, "", "Mozilla/5.0",
        ip="198.51.100.7")
    assert status == 402 and body["error"] == "Payment Required"
    status, body = omni.honeypot_process(
        state, "GET", "/v1/data", "id=1 UNION SELECT x", "sqlmap",
        ip="198.51.100.9")
    assert status == 200 and body["class"] == "sqli_probe"
    rep = omni.honeypotx_report(state)
    assert rep["attempts"] == 3
    assert rep["by_class"]["env_harvest"] == 1
    assert rep["by_class"]["sqli_probe"] == 1


# ------------------------------------------------------------ gateway
def test_gateway_402_shape():
    status, body = omni.handle_execute(
        {}, {"capability": "trading", "payload": {}}, env={})
    assert status == 402
    assert body["x402Version"] == 1
    assert body["error"] == "Payment Required"
    accept = body["accepts"][0]
    assert accept["scheme"] == "exact"
    assert accept["network"] == "monad-mainnet"
    assert accept["maxAmountRequired"] == omni.PRICE_ATOMIC
    assert accept["description"] == "All-in-One omni-agent-traderx"
    assert accept["asset"] == omni.USDC_MONAD


def test_gateway_paid_all_capabilities_demo():
    for cap in omni.CAPABILITIES:
        status, resp = omni.handle_execute(
            {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
            {"capability": cap, "payload": {}}, env={})
        assert status == 200 and resp["ok"] is True
        assert omni.verify_receipt(resp["receipt"])
        assert resp["settlement"]["transaction"].startswith("0x")


def test_gateway_live_flow_configured():
    hdr = omni.build_x402_payment_header(
        2, GATEWAY_ENV["AGENT_PAY_TO"], "10000", nonce_seed="c1")
    status, resp = omni.handle_execute(
        {"X-PAYMENT": hdr},
        {"capability": "trading",
         "payload": {"pair": "MON/USDC", "side": "buy",
                     "maxNotionalUsd": 250.0, "mode": "live"}},
        env=GATEWAY_ENV, transport=_combined_transport)
    assert status == 200 and resp["ok"] is True
    assert resp["settlement"]["mode"] == "live"
    assert resp["result"]["dispatch"]["order_submitted"] is True
    assert omni.verify_receipt(resp["receipt"])
    assert resp["receipt"]["signer"] == omni.TEST_ADDRESS
    assert resp["receipt"]["key_source"].startswith(
        "AGENT_SIGNER_KEY")


def test_gateway_unconfigured_attempt_config_missing():
    hdr = omni.build_x402_payment_header(
        2, GATEWAY_ENV["AGENT_PAY_TO"], "10000", nonce_seed="c2")
    status, resp = omni.handle_execute(
        {"X-PAYMENT": hdr}, {"capability": "data", "payload": {}},
        env={})
    assert status == 503
    assert resp["status"] == "CONFIG-MISSING"
    assert resp["missing"] == (
        omni.FEATURE_REQUIREMENTS["x402_gateway"])


def test_gateway_trading_caps_clamp():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "trading",
         "payload": {"maxNotionalUsd": 99999.0,
                     "maxSlippageBps": 999}}, env={})
    assert status == 200
    dispatch = resp["result"]["dispatch"]
    assert dispatch["max_notional_usd"] == 1000.0
    assert dispatch["max_slippage_bps"] == 100
    assert dispatch["mode"] == "dry_run"


def test_gateway_defi_defaults():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "defi", "payload": {}}, env={})
    assert status == 200
    dispatch = resp["result"]["dispatch"]
    assert dispatch["pool"] == "MON/USDC"
    assert dispatch["liquidity_check"] == "passed"
    assert dispatch["slippage_guard_bps"] == 50


def test_gateway_errors():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "nope", "payload": {}}, env={})
    assert status == 400 and resp["ok"] is False
    # live trading with no bridge config: precise CONFIG-MISSING,
    # not a generic refusal
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "trading", "payload": {"mode": "live"}},
        env={})
    assert status == 400 and "CONFIG-MISSING" in resp["error"]
    assert "HFT_BRIDGE_URL" in resp["error"]
    status, resp = omni.handle_execute(
        {"X-PAYMENT": "!!!not-base64!!!"},
        {"capability": "trading", "payload": {}}, env={})
    assert status == 503  # unconfigured live attempt fails first


def test_gateway_chamber_blocks_first():
    status, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "data",
         "payload": {"leak": "AGENT_SIGNER_KEY"}}, env={})
    assert status == 400
    assert "sandbox chamber triage" in resp["error"]


def test_receipt_signing_real_secp256k1():
    _, resp = omni.handle_execute(
        {"X-PAYMENT": omni.DEMO_PAYMENT_HEADER},
        {"capability": "research", "payload": {}}, env={})
    receipt = resp["receipt"]
    assert receipt["signer"] == omni.TEST_ADDRESS
    assert "TEST KEY" in receipt["key_source"]
    assert omni.verify_receipt(receipt)
    tampered = dict(receipt)
    tampered["resultHash"] = "0" * 64
    assert omni.verify_receipt(tampered) is False
    forged = dict(receipt)
    forged["signature"] = omni.sign_message(2, bytes.fromhex(
        receipt["receiptDigest"]))
    assert omni.verify_receipt(forged) is False


def test_facilitator_happy_and_failure_paths():
    payload = omni.parse_payment_header(omni.DEMO_PAYMENT_HEADER)
    req = omni.payment_required(env={})["accepts"][0]
    verify = omni.facilitator_verify(
        payload, req, transport=omni.demo_facilitator_transport)
    assert verify["verified"] is True
    assert verify["payer"] == omni.TEST_ADDRESS
    settle = omni.facilitator_settle(
        payload, req, transport=omni.demo_facilitator_transport)
    assert settle["settled"] is True
    assert settle["transaction"].startswith("0x")
    bad_req = dict(req)
    bad_req["maxAmountRequired"] = "999"
    verify = omni.facilitator_verify(
        payload, bad_req, transport=omni.demo_facilitator_transport)
    assert verify["verified"] is False
    assert "amount mismatch" in verify["invalid_reason"]


def test_parse_payment_header_rejects_garbage():
    import pytest
    with pytest.raises(ValueError):
        omni.parse_payment_header("not-a-real-header")


# ------------------------------------------------------------ ERC-8004
def test_agent_card():
    card = omni.agent_card()
    assert card["name"] == "omni-agent-traderx"
    assert card["capabilities"] == omni.CAPABILITIES
    assert card["erc8004"]["identity_registry"] == (
        "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432")
    assert card["erc8004"]["reputation_registry"] == (
        "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63")
    assert len(card["merged_sources"]) == 8
    assert card["live_config"]["coinbase_live"] == (
        omni.COINBASE_ENV_NAMES)
    assert card["live_config"]["erc8004_registration"] == (
        ["AGENT_SIGNER_KEY", "MONAD_RPC_URL"])


def test_erc8004_calldata_byte_exact():
    uri = "https://example.test/agent-card.json"
    calldata = omni.build_register_calldata(uri)
    expected = (
        omni.function_selector("register(string)")
        + (32).to_bytes(32, "big")
        + len(uri.encode()).to_bytes(32, "big")
        + uri.encode()
        + b"\x00" * ((32 - len(uri.encode()) % 32) % 32))
    assert calldata == expected
    preview = omni.erc8004_registration_preview(uri, env={})
    assert preview["calldata"] == "0x" + expected.hex()
    assert preview["from"] == omni.TEST_ADDRESS


def test_erc8004_register_fake_rpc_full_path():
    out1 = omni.erc8004_register(env=REG_ENV,
                                 transport=omni.demo_rpc_transport)
    out2 = omni.erc8004_register(env=REG_ENV,
                                 transport=omni.demo_rpc_transport)
    assert out1["status"] == "submitted"
    assert out1["from"] == omni.TEST_ADDRESS
    assert out1["to"] == omni.IDENTITY_REGISTRY
    assert out1["tx_hash"] == out1["local_tx_hash"]
    assert out1["raw_tx"] == out2["raw_tx"]  # RFC6979 deterministic
    assert out1["tx_fields"]["chain_id"] == 143


def test_erc8004_register_config_missing():
    out = omni.erc8004_register(env={})
    assert out["status"] == "CONFIG-MISSING"
    assert out["missing"] == ["AGENT_SIGNER_KEY", "MONAD_RPC_URL"]


def test_erc8004_reputation_selector_computed():
    selector = omni.function_selector(
        omni.REPUTATION_FEEDBACK_SIGNATURE)
    assert selector == omni.keccak256(
        omni.REPUTATION_FEEDBACK_SIGNATURE.encode())[:4]
    out = omni.erc8004_reputation_feedback(
        omni.TEST_ADDRESS, 90, "solid fills", env=REG_ENV,
        transport=omni.demo_rpc_transport)
    assert out["status"] == "submitted"
    assert out["selector"] == "0x" + selector.hex()
    assert out["to"] == omni.REPUTATION_REGISTRY
    assert out["calldata"][2:10] == selector.hex()


# ------------------------------------------------------------ broadcast
def test_broadcast_queues_when_unconfigured():
    rep = omni.broadcast_report(env={})
    assert rep["queued"] == 3
    assert rep["posts_sent"] == 0
    assert rep["reddit"]["missing"] == omni.REDDIT_ENV_NAMES
    assert rep["reddit"]["send"]["status"] == "CONFIG-MISSING"
    assert rep["voice"]["transcripts"]["voice_hedge"]["intent"] == (
        "buy")


def test_broadcast_sends_via_fake_transport():
    rep = omni.broadcast_report(env=omni.DEMO_REDDIT_ENV,
                                transport=omni.demo_reddit_transport)
    assert rep["posts_sent"] == 3
    assert rep["queued"] == 0
    assert all(q["status"] == "sent" and q["post_id"]
               and q["post_url"].startswith("https://www.reddit.com")
               for q in rep["broadcast_queue"])


def test_reddit_token_and_submit_units():
    token = omni.reddit_access_token(
        omni.DEMO_REDDIT_ENV, transport=omni.demo_reddit_transport)
    assert token == "demo-reddit-token"
    resp = omni.reddit_submit(token, "Monad", "title", "text",
                              transport=omni.demo_reddit_transport)
    assert resp["json"]["data"]["id"].startswith("t3_")


def test_voice_command_path():
    out = omni.voice_command("Sell BTC now")
    assert out["intent"]["intent"] == "sell"
    assert "device-side" in out["note"]


# ------------------------------------------------------------ inspector
def test_inspector_counts():
    rep = omni.inspect_rpc_trace()
    assert rep["traces_parsed"] == 10
    assert rep["clean"] == 6
    assert rep["flagged"] == 4
    assert [f["flag"] for f in rep["flags"]] == [
        "unknown_contract", "live_send_attempt", "chain_mismatch",
        "malformed_response"]
    assert rep["network_attempts"] == 0


def test_rpc_live_monitor():
    out = omni.rpc_live_monitor(
        env={"MONAD_RPC_URL": "https://rpc.test"},
        transport=omni.demo_rpc_transport)
    assert out["status"] == "ok"
    assert out["chain_id"] == 143 and out["chain_ok"] is True
    assert out["block_number"] == int("0x2a4f1", 16)
    assert out["network_attempts"] == 3
    missing = omni.rpc_live_monitor(env={})
    assert missing["status"] == "CONFIG-MISSING"
    assert missing["missing"] == ["MONAD_RPC_URL"]


# ------------------------------------------------------------ misc layers
def test_classifier():
    rep = omni.classifier_report()
    assert rep["bearish_deep"]["knn"] == "bearish-hedge-on"
    assert rep["bullish_deep"]["knn"] == "bullish-hedge-off"
    for feats, label in omni.TRAINING_GRID:
        assert omni.classify_features(feats) == label


def test_live_status_empty_env_precise():
    status = omni.live_status({})
    feats = status["features"]
    assert feats["x402_gateway"]["status"] == "NEEDS CONFIG"
    assert feats["x402_gateway"]["missing"] == (
        omni.FEATURE_REQUIREMENTS["x402_gateway"])
    assert feats["coinbase_live"]["missing"] == (
        omni.COINBASE_ENV_NAMES)
    assert feats["reddit_broadcast"]["missing"] == (
        omni.REDDIT_ENV_NAMES)
    assert feats["hft_bridge_live"]["missing"] == ["HFT_BRIDGE_URL"]
    assert feats["rpc_live_monitoring"]["missing"] == (
        ["MONAD_RPC_URL"])
    assert feats["honeypot_listener"]["status"] == "LIVE-READY"
    assert status["signer"]["test_key"] is True
    full = {name: "x" for names in
            omni.FEATURE_REQUIREMENTS.values() for name in names}
    full["AGENT_SIGNER_KEY"] = TEST_KEY_HEX
    ready = omni.live_status(full)
    assert ready["needs_config"] == []
    assert all(f["status"] == "LIVE-READY"
               for f in ready["features"].values())


def test_safety_rails_present():
    assert len(omni.SAFETY_RAILS) == 9
    assert not hasattr(omni, "HOLD_GATES")
    assert not hasattr(omni, "gate")


def test_seats_veto_scoped():
    brains = omni.brains_report()
    assert brains["decider"]["can_veto_trade"] is True
    assert brains["advisor"]["live_calls"] == 0
    assert "cannot disable features" in brains["advisor"]["authority"]
    assert brains["flow"]["rendered"] is False
    stress = brains["argon_stress"]
    assert stress["argon_decision"] == "VETO"
    assert stress["final_decision"] == "VETO"
    assert len(stress["rails_breached"]) == 2


def test_argon4_trace_recomputes():
    brains = omni.brains_report()
    decider = brains["decider"]
    assert decider["trace_sha256_16"] == omni._trace(
        decider["trace_input"])
    assert decider["pipeline"] == ["MAP", "MODEL", "STRESS",
                                   "DECIDE"]
    assert decider["tiers"] == [2048, 8192, 32768]


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
    assert rep["safety_rails_tripped"] == []


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


# ------------------------------------------------------------ CLI / suite
def test_checks_all_pass():
    checks = omni.run_checks()
    assert all(ok for _, ok in checks), [
        n for n, ok in checks if not ok]
    assert len(checks) == 93


def test_cli_checks_command():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "checks"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "CHECKS 93/93" in proc.stdout


def test_cli_live_status_and_register_config_missing():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "live-status"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"})
    assert proc.returncode == 0
    assert "NEEDS CONFIG" in proc.stdout
    assert "AGENT_SIGNER_KEY" in proc.stdout
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "register"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"})
    assert proc.returncode == 3
    assert "CONFIG-MISSING" in proc.stdout


def test_cli_agent_card_matches_generated_file():
    import json
    committed = json.loads((ROOT / "agent-card.json").read_text())
    assert committed == omni.agent_card()


def test_demo_deterministic():
    main_py = str(ROOT / "main.py")
    a = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    b = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    assert a.stdout == b.stdout and a.returncode == 0
