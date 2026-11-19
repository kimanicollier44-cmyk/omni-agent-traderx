#!/usr/bin/env python3
"""omni-agent-traderx - all-in-one Monad agent (offline simulation).

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Deterministic: run it twice, get byte-identical output.

What this is - eight merged sources behind ONE interface, plus the
MoltForest gateway from Darion's Gemini screen-recording (the
remaining four merges - 0mni-B0t broadcast, the verbatim
sandbox-api chamber in sandbox_api.py, HoneypotX log analysis and
the WEB3-insp3ct offline RPC inspector - have their own sections
below, sections 6, 7, 10 and 11). Source 8, sol-plex-problems
(section 14), is a role-layer re-implementation from its Docker
Hub description ("cloud cognitive engine for complex
problem-solving with secure quantum logic") - no local clone of
the original exists, so nothing here is a source copy. The house
council components are merged components in their own right:
Gemini Argon 4 Extended Thinking (house DECIDER seat, section 13)
and BOTH Google flows - the Gemini-FlowX planner (section 15)
plus the Google Flow video seat (plan-only, section 13):

  1. Monad-Bearish-Bull (credkellar/Monad-Bearish-Bull) - the regime
     engine: a Nationwide Sentiment Index (NSI) over crypto, stocks,
     forex and prediction markets, and the BEAR inverse token on
     Monad. In the original, BEAR mint/burn are BLOCKED (exactly 1
     BEAR, supply 1) - that honesty is preserved here: hedge routing
     is paper/simulated and mint/redeem stay HOLD-gated forever.
  2. Quantum-TraderX (ddkellar01/Quantum-TraderX) - the multi-asset
     execution engine: signals routed across crypto, equities,
     forex and prediction markets with risk rules and paper
     execution adapters.
  3. AI-Muse-Trading-Advanced-Elite-Agent (forked from
     ddkellar01/AI-Muse-Trading-Advanced-Elite-Agent) - "Advanced AI
     trading agent combining Muse natural language intelligence
     with a GitHub-powered algorithmic engine. Seamlessly connects
     to Coinbase Advanced to automate portfolio rebalancing, execute
     multi-market strategies, and manage risk 24/7 with secure API
     infrastructure." Here it is the Muse-brain / portfolio layer:
     natural-language intent parsing (deterministic offline rules,
     NOT a live LLM call), paper portfolio rebalancing, multi-market
     strategy routing into the multi-asset engine, and a 24/7 risk
     manager (per-trade cap + drawdown kill-switch, pattern adapted
     from crypto-agent-fleet/firm/risk.py). The Coinbase Advanced
     connection is names-only and HOLD-gated; nothing connects live.

  Gateway (agent/gateway in the video, package name
  "omni-agent-traderx-gateway", ethers + express in TypeScript -
  the SAME logic is re-implemented here in Python stdlib, honestly):
  MoltForest-compatible (moltforest.ai) on Monad with ERC-8004
  on-chain identity & reputation, x402 HTTP 402 micropayments,
  signed execution receipts, and multi-capability routing
  (payments, defi, research, data, trading, mcp).

Honest scope, stated up front: EVERYTHING here is offline
simulation. No live trading, no live HFT execution, no live x402
settlement, no live facilitator verification, no ERC-8004 mint, no
Coinbase connection, no real funds. Live paths are HOLD gates.
The offline receipt signature is an HMAC-SHA256 over the receipt
digest with an in-file DEMO key - labelled DEMO/OFFLINE, never a
real wallet signature; the video's keccak256 / ethers Wallet
signing is the live path and is HOLD-gated.
"""
import hashlib
import hmac
import itertools
import json
import math
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"
AGENT_NAME = "omni-agent-traderx"
AGENT_DESCRIPTION = "All-in-One omni-agent-traderx"
DEMO_TIMESTAMP = "2026-11-18T23:50:00Z"

CAPABILITIES = ["payments", "defi", "research", "data", "trading", "mcp"]

# x402 / Monad constants (from the video scaffold)
X402_VERSION = 1
X402_SCHEME = "exact"
X402_NETWORK = "monad-mainnet"
MONAD_CHAIN = "eip155:143"
EXECUTE_RESOURCE = "/v1/execute"
FACILITATOR_BASE = "https://x402-facilitator.molandak.org"
# Demo placeholder values for the offline build. A live deploy
# (HOLD-gated) would read the env names in GATEWAY_ENV_NAMES instead;
# values are never read or printed by this file.
DEMO_PORT = 8402
DEMO_PAY_TO = "0x0000000000000000000000000000000000000000"
USDC_MONAD = "0x754704Bc059F8C67012fEd69BC8A327a5aafb603"
PRICE_ATOMIC = "10000"  # 0.01 USDC at 6 decimals - the x402 price
GATEWAY_ENV_NAMES = ["PORT", "AGENT_PAY_TO", "USDC_MONAD",
                     "PRICE_ATOMIC", "AGENT_SIGNER_KEY"]
COINBASE_ENV_NAMES = ["COINBASE_API_KEY", "COINBASE_API_SECRET"]
DEMO_PAYMENT_HEADER = "demo-x402-payment-omni-agent-traderx"
# DEMO/OFFLINE receipt signer key - derived in-file, demo only.
DEMO_SIGNER_SECRET = "omni-agent-traderx-DEMO-offline-signer-v1"

# ERC-8004 registries (as shown in the video)
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

# HFT bridge caps - enforced by clamping, asserted in CHECKS
MAX_NOTIONAL_USD_CAP = 1000.0
MAX_SLIPPAGE_BPS_CAP = 100
DEFAULT_NOTIONAL_USD = 250.0
DEFAULT_SLIPPAGE_BPS = 50
DEFI_SLIPPAGE_GUARD_BPS = 50

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "live_trading": "HOLD - no live trading on any venue, ever, from this build",
    "live_hft_execution": "HOLD - external x402 callers are limited to telemetry/quotes + dry_run; live HFT orders are never accepted by the gateway",
    "x402_live_settlement": "HOLD - no live x402 settlement; offline demo simulates payment with a demo header only",
    "facilitator_live_verify": "HOLD - TODO: replace the placeholder header check with live calls to the Monad facilitator /verify and /settle; the offline stub refuses",
    "erc8004_live_mint": "HOLD - the ERC-8004 identity mint transaction is never submitted from this build; only the agent card is generated",
    "bear_mint_burn": "HOLD - PERMANENT, from the original Monad-Bearish-Bull: BEAR supply is exactly 1; mint and burn are blocked in code, forever",
    "private_key_exposure": "HOLD - no private key is ever exposed to the gateway; the HFT engine's keys never leave the engine (video Security & Custody note)",
    "live_mainnet_deployment": "HOLD - no live mainnet deployment and no public HTTPS endpoint is stood up from this build",
    "real_funds": "HOLD - no real funds move anywhere in this build; every number is paper",
    "reputation_live_feedback": "HOLD - no live ERC-8004 reputation feedback is written on-chain",
    "live_copy_execution": "HOLD - copy-trading style live execution for external callers is never enabled; quotes and dry_run only",
    "user_fund_custody": "HOLD - the agent never takes custody of user funds",
    "live_public_endpoint": "HOLD - no public endpoint is exposed; the gateway logic runs as offline functions here",
    "leverage_and_shorts": "HOLD - no leverage and no real shorts; the BEAR leg is a paper inverse hedge only",
    "coinbase_live_trading": "HOLD - no live trading through Coinbase Advanced; rebalancing is paper only",
    "coinbase_live_connection": "HOLD - no live Coinbase Advanced connection; COINBASE_API_KEY / COINBASE_API_SECRET are names only, values never read",
    "social_live_posting": "HOLD - no live social posting (0mni-B0t broadcasts are queued dry-run only); Reddit credentials are names only, values never read",
    "live_honeypot_listener": "HOLD - no live honeypot listener is ever opened; HoneypotX is log analysis only",
    "live_sample_detonation": "HOLD - chamber standard: samples are never detonated live; sandbox triage is static analysis of data only",
    "live_rpc_monitoring": "HOLD - no live RPC monitoring and no live browser inspection (WEB3-insp3ct layer works on recorded/synthetic traces only); MONAD_RPC_URL is a name only",
    "solplex_live_cloud": "HOLD - no live sol-plex cloud calls; the cognitive-engine re-implementation runs offline locally ('cloud cognitive engine' is the source repo's framing, not this build's runtime)",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ hashing kit
def canonical(obj):
    """Canonical JSON: sorted keys, tight separators. One form only."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_hex(text):
    return hashlib.sha256(text.encode()).hexdigest()


def hash_obj(obj):
    return sha256_hex(canonical(obj))


# ================================================================ 1. Regime engine
# From Monad-Bearish-Bull: the four market engines score sentiment
# -100..+100; the NSI blends them crypto 30 / stocks 30 / forex 20 /
# prediction 20. Regime: NSI <= -20 BEARISH, NSI >= +20 BULLISH.
# BEAR pricing: multiplier = clamp(1 - 1.5 x NSI/100, 0.25, 3.0),
# price = $100 x multiplier, supply exactly 1. Prices are money, so
# they are rounded half-up to cents with Decimal (financial
# convention): NSI -53.47 -> multiplier 1.80205 -> $180.21.

NSI_WEIGHTS = {"crypto": 0.30, "stocks": 0.30, "forex": 0.20,
               "prediction": 0.20}
BEAR_BASE_PRICE = Decimal("100")
BEAR_SUPPLY = 1
SAMPLE_PARTS_BEARISH = {"crypto": -62.0, "stocks": -58.0,
                        "forex": -41.35, "prediction": -46.0}
SAMPLE_PARTS_BULLISH = {"crypto": 48.0, "stocks": 52.0,
                        "forex": 35.0, "prediction": 40.0}
SAMPLE_PARTS_NEUTRAL = {"crypto": 4.0, "stocks": -2.0,
                        "forex": 6.0, "prediction": 0.0}


def compute_nsi(parts):
    """NSI = weighted blend of the four market sentiments, 2dp."""
    return round(sum(parts[k] * NSI_WEIGHTS[k] for k in NSI_WEIGHTS), 2)


def regime_for_nsi(nsi):
    if nsi <= -20:
        return "BEARISH_REGIME"
    if nsi >= 20:
        return "BULLISH_REGIME"
    return "NEUTRAL_REGIME"


def bear_pricing(nsi):
    """Inverse BEAR pricing by Decimal recomputation, half-up cents."""
    raw = (Decimal("1") - Decimal("1.5") * Decimal(str(nsi))
           / Decimal("100"))
    clamped = max(Decimal("0.25"), min(Decimal("3.0"), raw))
    price = (BEAR_BASE_PRICE * clamped).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    mult3 = clamped.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if nsi <= -20:
        stance = "BULLISH"  # BEAR is bullish when the nation is bearish
    elif nsi >= 20:
        stance = "BEARISH"
    else:
        stance = "NEUTRAL"
    return {
        "symbol": "BEAR",
        "supply": BEAR_SUPPLY,
        "nsi": nsi,
        "multiplier_raw": float(raw),
        "multiplier": float(mult3),
        "price_usd": float(price),
        "market_cap_usd": float(price * BEAR_SUPPLY),
        "stance": stance,
        "mint_burn": "BLOCKED (HOLD: bear_mint_burn, permanent)",
    }


def bear_mint_attempt(amount=1.0):
    """Mint is blocked in the original and stays blocked here."""
    return {"status": "HOLD", "gate": "bear_mint_burn",
            "action": "mint", "amount": amount, "supply": BEAR_SUPPLY,
            "reason": "BEAR supply is hard-capped at exactly 1 token"}


def bear_burn_attempt(amount=1.0):
    return {"status": "HOLD", "gate": "bear_mint_burn",
            "action": "burn", "amount": amount, "supply": BEAR_SUPPLY,
            "reason": "the 1 personal BEAR token stays whole in supply"}


def regime_report(parts=None):
    parts = dict(SAMPLE_PARTS_BEARISH if parts is None else parts)
    nsi = compute_nsi(parts)
    return {
        "source": "engine/bearish_bull (Monad-Bearish-Bull)",
        "parts": parts,
        "weights": dict(NSI_WEIGHTS),
        "nsi": nsi,
        "regime": regime_for_nsi(nsi),
        "bear": bear_pricing(nsi),
    }


# ================================================================ 2. Hedge module
# Regime & Inverse Hedging Module: BEARISH_REGIME -> hedge ON, route
# a paper hedge via the BEAR inverse leg and cap multi-asset
# notional at the bearish cap; BULLISH_REGIME -> hedge OFF, standard
# cap; NEUTRAL_REGIME -> reduced hedge.

BEARISH_NOTIONAL_CAP_USD = 500.0
NEUTRAL_NOTIONAL_CAP_USD = 750.0
STANDARD_NOTIONAL_CAP_USD = 1000.0
BEARISH_HEDGE_RATIO = 0.60
NEUTRAL_HEDGE_RATIO = 0.25
BULLISH_HEDGE_RATIO = 0.0


def hedge_decision(regime, requested_notional_usd):
    requested = float(requested_notional_usd)
    if regime == "BEARISH_REGIME":
        cap, ratio, stance = (BEARISH_NOTIONAL_CAP_USD,
                              BEARISH_HEDGE_RATIO, "ON")
    elif regime == "BULLISH_REGIME":
        cap, ratio, stance = (STANDARD_NOTIONAL_CAP_USD,
                              BULLISH_HEDGE_RATIO, "OFF")
    else:
        cap, ratio, stance = (NEUTRAL_NOTIONAL_CAP_USD,
                              NEUTRAL_HEDGE_RATIO, "REDUCED")
    effective = min(requested, cap)
    return {
        "regime": regime,
        "hedge": stance,
        "leg": "BEAR inverse token (paper)" if stance != "OFF" else "none",
        "hedge_ratio": ratio,
        "requested_notional_usd": requested,
        "notional_cap_usd": cap,
        "effective_notional_usd": effective,
        "bear_hedge_usd": round(effective * ratio, 2),
        "mode": "paper",
        "mint_redeem": "HOLD (bear_mint_burn)",
    }


def hedge_report(requested_notional_usd=800.0):
    rows = {}
    for label, parts in (("bearish", SAMPLE_PARTS_BEARISH),
                         ("bullish", SAMPLE_PARTS_BULLISH),
                         ("neutral", SAMPLE_PARTS_NEUTRAL)):
        rep = regime_report(parts)
        rows[label] = hedge_decision(rep["regime"],
                                     requested_notional_usd)
        rows[label]["nsi"] = rep["nsi"]
    return {"requested_notional_usd": requested_notional_usd,
            "branches": rows}


# ================================================================ 3. Multi-asset
# From Quantum-TraderX: route signals across crypto, equities,
# forex and prediction markets with risk rules and execution
# adapters. Every adapter here is a PAPER adapter: routing is
# computed and asserted offline, no order is ever submitted.

ASSET_UNIVERSE = {
    "crypto": ["BTC", "ETH", "MON", "SOL"],
    "equities": ["SPX", "NDX", "DJI", "RUT"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
    "prediction": ["US_WEEK_BEARISH"],
}
MULTI_ASSET_NOTIONAL_CAP_USD = MAX_NOTIONAL_USD_CAP


def route_signal(signal):
    """Route one signal through the risk rules to a paper adapter."""
    asset_class = signal.get("assetClass")
    symbol = signal.get("symbol")
    side = signal.get("side", "quote_only")
    mode = signal.get("mode", "dry_run")
    if asset_class not in ASSET_UNIVERSE:
        raise ValueError(f"unknown assetClass: {asset_class}")
    if symbol not in ASSET_UNIVERSE[asset_class]:
        raise ValueError(f"symbol {symbol} not in {asset_class} universe")
    if mode == "live":
        return {"status": "HOLD", "gate": "live_trading",
                "assetClass": asset_class, "symbol": symbol,
                "orderSubmitted": False,
                "reason": "live execution is a HOLD gate; paper only"}
    requested = float(signal.get("notionalUsd", DEFAULT_NOTIONAL_USD))
    routed = max(0.0, min(requested, MULTI_ASSET_NOTIONAL_CAP_USD))
    return {
        "status": "routed_dry_run",
        "assetClass": asset_class,
        "symbol": symbol,
        "side": side,
        "mode": "dry_run",
        "adapter": f"{asset_class}-paper-adapter",
        "requested_notional_usd": requested,
        "routed_notional_usd": routed,
        "capped": routed < requested,
        "orderSubmitted": False,
    }


SAMPLE_SIGNALS = [
    {"assetClass": "crypto", "symbol": "MON", "side": "buy",
     "notionalUsd": 400.0},
    {"assetClass": "equities", "symbol": "SPX", "side": "sell",
     "notionalUsd": 600.0},
    {"assetClass": "forex", "symbol": "EURUSD", "side": "buy",
     "notionalUsd": 300.0},
    {"assetClass": "prediction", "symbol": "US_WEEK_BEARISH",
     "side": "buy", "notionalUsd": 200.0},
    {"assetClass": "crypto", "symbol": "BTC", "side": "buy",
     "notionalUsd": 5000.0},  # oversized on purpose: must clamp
]


def multi_asset_report():
    routed = [route_signal(dict(s)) for s in SAMPLE_SIGNALS]
    return {
        "source": "engine/multi_asset (Quantum-TraderX)",
        "universe": {k: list(v) for k, v in ASSET_UNIVERSE.items()},
        "notional_cap_usd": MULTI_ASSET_NOTIONAL_CAP_USD,
        "signals": routed,
        "total_routed_usd": round(sum(r["routed_notional_usd"]
                                      for r in routed), 2),
        "live_orders": 0,
    }


# ================================================================ 4. HFT bridge
# dispatchToMonadHft from the video, as an offline stub. It returns
# orderbook telemetry (liquidity depth, routing quotes, paper
# signals). Darion's standing rule answers the video's open
# question: external x402 callers are limited to telemetry/quotes +
# dry_run; live copy/execution orders are a HOLD gate. The gateway
# never holds an HFT private key (private_key_exposure gate).

def _telemetry(pair):
    seed = int(sha256_hex(pair)[:8], 16)
    return {
        "pair": pair,
        "mid_price": round(0.5 + (seed % 10000) / 10000.0 * 2.0, 4),
        "bid_depth_usd": 25000 + seed % 75000,
        "ask_depth_usd": 25000 + (seed >> 8) % 75000,
        "spread_bps": 5 + seed % 20,
        "source": "offline-stub (no live feed)",
    }


def dispatch_to_monad_hft(command):
    """Offline HFT bridge. Live mode returns HOLD, never an order."""
    mode = command.get("mode", "dry_run")
    base = {
        "bridge": "monad-hft-bridge",
        "transport": "offline-stub",
        "external_caller_policy": "telemetry/quotes + dry_run only",
        "order_submitted": False,
        "private_key_exposed": False,
        "custody": "gateway holds no HFT private key",
    }
    if mode == "live":
        return {**base, "status": "HOLD", "gate": "live_hft_execution",
                "mode": "live",
                "reason": "live HFT execution is a HOLD gate"}
    if "pool" in command:  # DeFi quote path from the video
        guard = int(command.get("slippageGuardBps",
                                DEFI_SLIPPAGE_GUARD_BPS))
        return {**base, "status": "quoted", "kind": "defi",
                "pool": command["pool"],
                "depth_usd": float(command.get("depthUsd", 10000.0)),
                "liquidity_check": command.get("liquidityCheck",
                                               "passed"),
                "slippage_guard_bps": max(
                    0, min(guard, MAX_SLIPPAGE_BPS_CAP)),
                "mode": "dry_run",
                "telemetry": _telemetry(command["pool"])}
    pair = command.get("pair", "MON/USDC")
    notional = float(command.get("maxNotionalUsd", DEFAULT_NOTIONAL_USD))
    slippage = int(command.get("maxSlippageBps", DEFAULT_SLIPPAGE_BPS))
    return {**base, "status": "quoted", "kind": "trading",
            "pair": pair,
            "side": command.get("side", "quote_only"),
            "max_notional_usd": max(
                0.0, min(notional, MAX_NOTIONAL_USD_CAP)),
            "max_slippage_bps": max(
                0, min(slippage, MAX_SLIPPAGE_BPS_CAP)),
            "mode": "dry_run",
            "telemetry": _telemetry(pair)}


def hft_report():
    quote = dispatch_to_monad_hft(
        {"pair": "MON/USDC", "side": "quote_only",
         "maxNotionalUsd": 250.0, "maxSlippageBps": 50})
    oversized = dispatch_to_monad_hft(
        {"pair": "MON/USDC", "side": "buy",
         "maxNotionalUsd": 99999.0, "maxSlippageBps": 999})
    live = dispatch_to_monad_hft({"pair": "MON/USDC", "mode": "live"})
    return {"quote": quote, "oversized_clamped": oversized,
            "live_attempt": live,
            "caps": {"max_notional_usd": MAX_NOTIONAL_USD_CAP,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS_CAP}}


# ================================================================ 5. Muse trading
# From AI-Muse-Trading-Advanced-Elite-Agent: the Muse-brain /
# portfolio layer. Four pieces, all offline and paper:
#   a) NL intent parsing - deterministic keyword/rule parser over
#      the user's words. NOT a live LLM call (live_calls = 0).
#   b) Paper portfolio rebalancing - target allocations, deltas
#      computed exactly and asserted in CHECKS.
#   c) Multi-market strategy routing - parsed intents and rebalance
#      legs route into the multi-asset engine above.
#   d) 24/7 risk manager - per-trade cap + drawdown kill-switch
#      that stays tripped until an explicit reset, never auto-clear
#      (pattern adapted from crypto-agent-fleet/firm/risk.py).
# Coinbase Advanced: COINBASE_API_KEY / COINBASE_API_SECRET are
# names only, values never read; live connection and live trading
# through it are HOLD gates (coinbase_live_connection,
# coinbase_live_trading).

PAPER_PORTFOLIO_USD = {"BTC": 4200.0, "ETH": 2600.0, "MON": 1200.0,
                       "USDC": 2000.0}
TARGET_ALLOCATIONS = {"BTC": 0.35, "ETH": 0.30, "MON": 0.15,
                      "USDC": 0.20}
PAPER_PRICES_USD = {"BTC": 90000.0, "ETH": 3000.0, "MON": 2.50,
                    "USDC": 1.0}
PER_TRADE_CAP_USD = 500.0
MAX_DRAWDOWN_PCT = 10.0

_INTENT_ASSETS = {"bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH",
                  "eth": "ETH", "monad": "MON", "mon": "MON",
                  "solana": "SOL", "sol": "SOL", "usdc": "USDC"}


def parse_intent(text):
    """Deterministic offline NL intent parser (rules, not an LLM)."""
    words = text.lower().replace(",", " ").replace(".", " ").split()
    lowered = " " + " ".join(words) + " "
    assets = []
    for word in words:
        sym = _INTENT_ASSETS.get(word)
        if sym and sym not in assets:
            assets.append(sym)
    if "rebalance" in words or "rebalancing" in words:
        intent = "rebalance_portfolio"
    elif "buy" in words or "purchase" in words:
        intent = "buy"
    elif "sell" in words:
        intent = "sell"
    elif "hedge" in words:
        intent = "hedge"
    else:
        intent = "monitor"
    if "buy" in words:
        side = "buy"
    elif "sell" in words:
        side = "sell"
    else:
        side = "none"
    if ("reduce risk" in lowered or "conservative" in words
            or "defensive" in words):
        risk_mode = "defensive"
    elif "aggressive" in words:
        risk_mode = "growth"
    else:
        risk_mode = "balanced"
    return {
        "parser": "deterministic-rules (offline, not an LLM call)",
        "live_calls": 0,
        "text": text,
        "intent": intent,
        "assets": assets,
        "side": side,
        "hedge": "hedge" in words or "bear" in words,
        "risk_mode": risk_mode,
    }


INTENT_SCENARIOS = {
    "rebalance_defensive":
        "Rebalance my portfolio to target and reduce risk",
    "buy_mon_hedge":
        "Buy MON if the regime turns bearish and hedge with BEAR",
    "sell_btc": "Sell BTC now",
    "monitor": "Watch the portfolio and manage risk",
}


def rebalance_plan(portfolio=None, targets=None):
    """Paper rebalance: deltas = target value - current value."""
    portfolio = dict(PAPER_PORTFOLIO_USD if portfolio is None
                     else portfolio)
    targets = dict(TARGET_ALLOCATIONS if targets is None else targets)
    total = round(sum(portfolio.values()), 2)
    legs = []
    for asset in sorted(portfolio):
        target_value = round(total * targets[asset], 2)
        delta = round(target_value - portfolio[asset], 2)
        action = "BUY" if delta > 0 else ("SELL" if delta < 0
                                          else "HOLD")
        legs.append({"asset": asset,
                     "current_usd": portfolio[asset],
                     "target_weight": targets[asset],
                     "target_usd": target_value,
                     "delta_usd": delta,
                     "action": action})
    return {
        "mode": "paper (dry_run)",
        "venue": "coinbase-advanced-paper-adapter (no live connection)",
        "total_usd": total,
        "legs": legs,
        "net_delta_usd": round(sum(l["delta_usd"] for l in legs), 2),
        "gross_turnover_usd": round(
            sum(abs(l["delta_usd"]) for l in legs), 2),
        "rebalance_needed": any(l["delta_usd"] != 0 for l in legs),
        "orders_submitted": 0,
        "live_gate": gate("coinbase_live_trading"),
    }


def risk_check_order(notional_usd, halted=False):
    """Per-trade pre-check, adapted from firm/risk.py check_order."""
    notional = float(notional_usd)
    if halted:
        return {"approved": False, "reason": "kill-switch halted",
                "notional_usd": notional}
    if notional <= 0:
        return {"approved": False,
                "reason": "non-positive notional",
                "notional_usd": notional}
    if notional > PER_TRADE_CAP_USD:
        return {"approved": False,
                "reason": f"notional ${notional:,.2f} > per-trade cap "
                          f"${PER_TRADE_CAP_USD:,.2f}",
                "notional_usd": notional}
    return {"approved": True, "reason": "ok",
            "notional_usd": notional}


def drawdown_pct(peak_equity, current_equity):
    if not peak_equity:
        return 0.0
    return max(0.0, (peak_equity - current_equity)
               / peak_equity * 100.0)


def kill_switch(peak_equity, current_equity):
    """Trips at MAX_DRAWDOWN_PCT; once tripped it stays tripped
    until an explicit human reset - modelled here as a pure check,
    with the standing rule stated in the report."""
    dd = drawdown_pct(peak_equity, current_equity)
    return {"peak_equity": peak_equity,
            "current_equity": current_equity,
            "drawdown_pct": round(dd, 2),
            "max_drawdown_pct": MAX_DRAWDOWN_PCT,
            "tripped": dd >= MAX_DRAWDOWN_PCT,
            "auto_clear": False,
            "reset": "explicit human action only"}


def muse_trading_report():
    plan = rebalance_plan()
    routed = []
    asset_class = {"BTC": "crypto", "ETH": "crypto", "MON": "crypto",
                   "USDC": "crypto"}
    for leg in plan["legs"]:
        if leg["action"] == "HOLD":
            continue
        routed.append(route_signal({
            "assetClass": asset_class[leg["asset"]],
            "symbol": leg["asset"],
            "side": leg["action"].lower(),
            "notionalUsd": min(abs(leg["delta_usd"]),
                               PER_TRADE_CAP_USD)}))
    return {
        "source": "engine/muse_trading "
                  "(AI-Muse-Trading-Advanced-Elite-Agent)",
        "description": "Advanced AI trading agent combining Muse "
                       "natural language intelligence with a "
                       "GitHub-powered algorithmic engine. Seamlessly "
                       "connects to Coinbase Advanced to automate "
                       "portfolio rebalancing, execute multi-market "
                       "strategies, and manage risk 24/7 with secure "
                       "API infrastructure.",
        "intents": {name: parse_intent(text)
                    for name, text in INTENT_SCENARIOS.items()},
        "rebalance": plan,
        "rebalance_legs_routed": routed,
        "risk": {
            "per_trade_cap_usd": PER_TRADE_CAP_USD,
            "max_drawdown_pct": MAX_DRAWDOWN_PCT,
            "sample_ok": risk_check_order(400.0),
            "sample_over_cap": risk_check_order(750.0),
            "drawdown_watch": kill_switch(10000.0, 9200.0),
            "drawdown_trip": kill_switch(10000.0, 8800.0),
        },
        "coinbase": {
            "env_names": list(COINBASE_ENV_NAMES),
            "values_read": False,
            "connection": gate("coinbase_live_connection"),
            "live_trading": gate("coinbase_live_trading"),
        },
        "live_calls": 0,
    }


# ================================================================ 6. Sandbox chamber
# sandbox-api is Darion's fleet chamber, merged VERBATIM as the
# top-level sandbox_api.py next to this file (sha256
# 28b3365c0466027079a4985520840f6532d7d9a0c5b4239b840e561f06de54b0,
# byte-identical to lte-6g/lte6g/sandbox_api.py - no edits). Its job
# here: every incoming x402 capability payload is statically triaged
# in the chamber BEFORE the gateway routes it. Samples are DATA
# ONLY: executed_sample_code is always False and network_attempts
# is always 0. (The chamber telemetry also carries an elapsed_ms
# wall-clock field; this lab never prints it, so output stays
# byte-identical between runs.)

from sandbox_api import detonate_static as _chamber_run  # noqa: E402

SANDBOX_PATTERNS = [b'"mode":"live"', b"signer_key", b"private_key",
                    b"seed_phrase", b"exec(", b"eval(",
                    b"live_sample_detonation"]


def _triage_analyse(data):
    lowered = data.lower()
    hits = [p.decode() for p in SANDBOX_PATTERNS if p in lowered]
    return {"fingerprints": hits,
            "verdict": "HOLD_IN_SANDBOX" if hits else "ALLOW"}


def triage_payload(name, payload_obj):
    """Static chamber triage of one payload object (data only)."""
    data = canonical(payload_obj).encode()
    out = _chamber_run(name, data, _triage_analyse)
    tel = out["telemetry"]
    return {
        "sample": name,
        "verdict": out["report"]["verdict"],
        "fingerprints": out["report"]["fingerprints"],
        "sha256": tel["sha256"],
        "executed": tel["executed_sample_code"],
        "network_attempts": tel["network_attempts"],
        "budget_ok": tel["budget_ok"],
    }


GATEWAY_TRIAGE_SAMPLES = [
    ("payments-quote", {"capability": "payments",
                        "payload": {"amountAtomic": "10000"}}),
    ("trading-dry-run", {"capability": "trading",
                         "payload": {"pair": "MON/USDC",
                                     "mode": "dry_run"}}),
    ("research-topic", {"capability": "research",
                        "payload": {"topic": "monad-ecosystem"}}),
    ("trading-live-attempt", {"capability": "trading",
                              "payload": {"pair": "MON/USDC",
                                          "mode": "live"}}),
    ("signer-key-leak", {"capability": "data",
                         "payload": {"leak": "AGENT_SIGNER_KEY"}}),
    ("mcp-exec-attempt", {"capability": "mcp",
                          "payload": {"tool": "run",
                                      "code": "exec(open('x'))"}}),
]


def sandbox_report():
    rows = [triage_payload(name, obj)
            for name, obj in GATEWAY_TRIAGE_SAMPLES]
    return {
        "source": "sandbox-api chamber (verbatim sandbox_api.py)",
        "chamber_sha256_file": "28b3365c0466027079a4985520840f6532"
                               "d7d9a0c5b4239b840e561f06de54b0",
        "samples": rows,
        "allowed": sum(1 for r in rows if r["verdict"] == "ALLOW"),
        "held": sum(1 for r in rows
                    if r["verdict"] == "HOLD_IN_SANDBOX"),
        "any_executed": any(r["executed"] for r in rows),
        "network_attempts_total": sum(r["network_attempts"]
                                      for r in rows),
        "live_detonation": gate("live_sample_detonation"),
    }


# ================================================================ 7. HoneypotX
# Adapted from lte-6g/lte6g/honeypotx.py (Darion's honeyroot-x
# engine shape: class weights, regex classifiers, burst bonus, bait
# sessions), re-themed to the doors this agent actually has:
# signer-key harvesting, payment-header forgery probes, env/config
# scraping against the public endpoint. LOG ANALYSIS ONLY over
# synthetic TEST-NET-3 (198.51.100.0/24) records: listener_open is
# always False and access_granted is always False.

import re  # noqa: E402
from collections import Counter  # noqa: E402

_HONEYPOT_WEIGHTS = {"sqli_probe": 70, "lfi_probe": 75,
                     "env_harvest": 60, "upload_attempt": 90,
                     "scanner": 35}
_HONEYPOT_SQLI = re.compile(
    r"(union\s+select|'\s*or\s+1\s*=\s*1|or\s+1=1|sleep\s*\()", re.I)
_HONEYPOT_TRAVERSAL = re.compile(r"(\.\./|\.\.\\|%2e%2e|\.\.\.\.//)",
                                 re.I)
_HONEYPOT_ENV_PATHS = ("/.env", "/.git/", "/.aws", "/signer",
                       "/keys", "/config")
_HONEYPOT_ADMIN_PATHS = ("/phpmyadmin", "/admin", "/wp-login")

HONEYPOT_LOG = [
    {"ip": "198.51.100.23", "minute": 1, "method": "GET",
     "path": "/v1/execute", "query": "", "agent": "Mozilla/5.0"},
    {"ip": "198.51.100.23", "minute": 2, "method": "GET",
     "path": "/.env", "query": "", "agent": "curl/8"},
    {"ip": "198.51.100.23", "minute": 3, "method": "GET",
     "path": "/.git/config", "query": "", "agent": "curl/8"},
    {"ip": "198.51.100.23", "minute": 4, "method": "GET",
     "path": "/v1/keys/signer", "query": "", "agent": "curl/8"},
    {"ip": "198.51.100.23", "minute": 5, "method": "POST",
     "path": "/v1/upload", "query": "", "agent": "python-requests",
     "filename": "receipt.bin"},
    {"ip": "198.51.100.41", "minute": 6, "method": "GET",
     "path": "/v1/execute", "query": "file=../../../../etc/passwd",
     "agent": "Nikto"},
    {"ip": "198.51.100.41", "minute": 7, "method": "GET",
     "path": "/v1/data",
     "query": "id=1 UNION SELECT username,password FROM users",
     "agent": "sqlmap"},
    {"ip": "198.51.100.41", "minute": 8, "method": "GET",
     "path": "/v1/data", "query": "id=1' OR 1=1--",
     "agent": "sqlmap"},
    {"ip": "198.51.100.57", "minute": 9, "method": "GET",
     "path": "/admin/", "query": "", "agent": "zgrab"},
    {"ip": "198.51.100.57", "minute": 10, "method": "GET",
     "path": "/phpmyadmin/", "query": "", "agent": "Mozilla/5.0"},
    {"ip": "198.51.100.57", "minute": 11, "method": "GET",
     "path": "/v1/execute", "query": "file=....//....//etc/passwd",
     "agent": "Nikto"},
    {"ip": "198.51.100.99", "minute": 12, "method": "GET",
     "path": "/", "query": "", "agent": "Mozilla/5.0"},
]


def _honeypot_classify(entry):
    path = entry.get("path", "")
    query = entry.get("query", "")
    target = f"{path}?{query}"
    if entry.get("filename") or "upload" in path:
        return "upload_attempt"
    if _HONEYPOT_TRAVERSAL.search(target):
        return "lfi_probe"
    if _HONEYPOT_SQLI.search(query):
        return "sqli_probe"
    if any(p in path for p in _HONEYPOT_ENV_PATHS):
        return "env_harvest"
    return "scanner"


def honeypotx_report(entries=None):
    entries = list(HONEYPOT_LOG if entries is None else entries)
    classified = []
    for e in entries:
        cls = _honeypot_classify(e)
        score = _HONEYPOT_WEIGHTS[cls]
        if e.get("agent", "").lower() in ("sqlmap", "nikto", "zgrab"):
            score += 5
        classified.append({
            **e, "class": cls, "threat_score": min(100, score),
            "bait": any(p in e["path"] for p in
                        _HONEYPOT_ENV_PATHS + _HONEYPOT_ADMIN_PATHS)})
    counts = Counter(e["ip"] for e in entries)
    bursts = [{"ip": ip, "attempts": n}
              for ip, n in sorted(counts.items()) if n >= 4]
    burst_ips = {b["ip"] for b in bursts}
    for c in classified:
        if c["ip"] in burst_ips:
            c["threat_score"] = min(100, c["threat_score"] + 10)
    top = max(classified, key=lambda c: c["threat_score"])
    return {
        "source": "HoneypotX (honeyroot-x engine shape, gateway logs)",
        "mode": "log-analysis-only",
        "listener_open": False,
        "access_granted": False,
        "attempts": len(classified),
        "by_class": dict(Counter(c["class"] for c in classified)),
        "top_threat_score": top["threat_score"],
        "top_attempt_class": top["class"],
        "bursts": bursts,
        "bait_sessions": sum(1 for c in classified if c["bait"]),
        "entries": classified,
        "live_listener": gate("live_honeypot_listener"),
    }


# ================================================================ 8. x402 gateway
# The gateway from the video (agent/gateway, package
# "omni-agent-traderx-gateway", ethers + express in TypeScript) -
# the SAME logic in Python stdlib. Zero-config access: a client
# agent needs no account, API key or subscription; it calls
# POST /v1/execute, receives 402 terms, signs an off-chain USDC
# authorization, and the server verifies/settles via the Monad
# facilitator. Offline, the flow is simulated with a demo payment
# header; live verification/settlement are HOLD gates (TODO below).

def gateway_config():
    """Names-only env status. Secret VALUES are never read/printed."""
    demo = {"PORT": DEMO_PORT, "AGENT_PAY_TO": DEMO_PAY_TO,
            "USDC_MONAD": USDC_MONAD, "PRICE_ATOMIC": PRICE_ATOMIC,
            "AGENT_SIGNER_KEY": "DEMO in-file key (offline only)"}
    return {name: {"env": name,
                   "configured_by_name": bool(os.environ.get(name)),
                   "value_exposed": False,
                   "demo_effective": demo[name]}
            for name in GATEWAY_ENV_NAMES}


def payment_required(resource=EXECUTE_RESOURCE):
    """The x402 402 body, exactly the shape from the video."""
    return {
        "x402Version": X402_VERSION,
        "error": "Payment Required",
        "accepts": [{
            "scheme": X402_SCHEME,
            "network": X402_NETWORK,
            "maxAmountRequired": PRICE_ATOMIC,
            "resource": resource,
            "description": AGENT_DESCRIPTION,
            "payTo": DEMO_PAY_TO,
            "asset": USDC_MONAD,
        }],
    }


def facilitator_verify(payment_header):
    """TODO/HOLD: live path replaces the placeholder header check
    with POST https://x402-facilitator.molandak.org/verify (Monad
    mainnet eip155:143, Monad USDC). Offline this REFUSES."""
    return {"status": "HOLD", "gate": "facilitator_live_verify",
            "endpoint": FACILITATOR_BASE + "/verify",
            "chain": MONAD_CHAIN, "verified": False,
            "reason": "offline build - live facilitator verification "
                      "is a HOLD gate, never faked as working"}


def facilitator_settle(payment_header):
    """TODO/HOLD: live path settles via the facilitator /settle
    endpoint. Offline this REFUSES."""
    return {"status": "HOLD", "gate": "x402_live_settlement",
            "endpoint": FACILITATOR_BASE + "/settle",
            "chain": MONAD_CHAIN, "settled": False,
            "reason": "offline build - live settlement is a HOLD "
                      "gate, never faked as working"}


def run_capability(capability, payload=None):
    """Capability dispatch from the video's runCapability."""
    payload = dict(payload or {})
    if capability == "payments":
        return {"capability": "payments", "rail": "x402/monad-usdc",
                "quote": {
                    "recipient": DEMO_PAY_TO,
                    "amountAtomic": str(payload.get(
                        "amountAtomic", PRICE_ATOMIC)),
                    "asset": USDC_MONAD, "network": X402_NETWORK},
                "settlement": "HOLD (x402_live_settlement)",
                "status": "quoted"}
    if capability == "trading":
        dispatch = dispatch_to_monad_hft({
            "pair": payload.get("pair", "MON/USDC"),
            "side": payload.get("side", "quote_only"),
            "maxNotionalUsd": payload.get("maxNotionalUsd",
                                          DEFAULT_NOTIONAL_USD),
            "maxSlippageBps": payload.get("maxSlippageBps",
                                          DEFAULT_SLIPPAGE_BPS),
            "mode": payload.get("mode", "dry_run")})
        if dispatch.get("status") == "HOLD":
            raise ValueError(
                "HOLD: live_hft_execution - external x402 callers "
                "are limited to telemetry/quotes + dry_run")
        return {"capability": "trading", "dispatch": dispatch}
    if capability == "defi":
        dispatch = dispatch_to_monad_hft({
            "pool": payload.get("poolOrToken", "MON/USDC"),
            "depthUsd": payload.get("depthUsd", 10000.0),
            "liquidityCheck": "passed",
            "slippageGuardBps": DEFI_SLIPPAGE_GUARD_BPS,
            "mode": payload.get("mode", "dry_run")})
        if dispatch.get("status") == "HOLD":
            raise ValueError(
                "HOLD: live_hft_execution - defi routing is "
                "quotes + dry_run only for external callers")
        return {"capability": "defi", "dispatch": dispatch}
    if capability == "research":
        return {"capability": "research", "mode": "offline-stub",
                "topic": payload.get("topic", "monad-ecosystem"),
                "live_calls": 0,
                "finding": "deterministic offline stub - no live "
                           "research feed is wired"}
    if capability == "data":
        dataset = payload.get("dataset", "monad-chain-telemetry")
        rows = 100 + int(sha256_hex(dataset)[:4], 16) % 900
        return {"capability": "data", "mode": "offline-stub",
                "dataset": dataset, "rows": rows, "live_calls": 0}
    if capability == "mcp":
        return {"capability": "mcp", "mode": "offline-stub",
                "tool": payload.get("tool", "omni.quote"),
                "transport": "mcp-offline-stub", "live_calls": 0}
    raise ValueError(f"unknown capability: {capability}")


def sign_receipt(receipt_payload):
    """Deterministic OFFLINE receipt signing (DEMO).

    receiptDigest = sha256 of the canonical payload; signature =
    HMAC-SHA256 over the digest with the in-file DEMO key. This is
    NOT a wallet signature - the video's keccak256 / ethers Wallet
    signing is the live path and is HOLD-gated.
    """
    digest = hash_obj(receipt_payload)
    signature = hmac.new(DEMO_SIGNER_SECRET.encode(),
                         digest.encode(),
                         hashlib.sha256).hexdigest()
    return {**receipt_payload, "receiptDigest": digest,
            "signature": signature,
            "signer": "DEMO/OFFLINE (HMAC-SHA256, not a wallet "
                      "signature)",
            "live_settlement": "HOLD"}


def verify_receipt(receipt):
    payload = {k: receipt[k] for k in
               ("agent", "capability", "action", "paymentDigest",
                "requestHash", "resultHash", "timestamp")}
    expected = sign_receipt(payload)
    return (receipt.get("receiptDigest") == expected["receiptDigest"]
            and receipt.get("signature") == expected["signature"])


def handle_execute(headers, body):
    """POST /v1/execute flow as a pure function (no sockets).

    Order: sandbox chamber triage FIRST, then the payment check,
    then capability dispatch, then a signed receipt.
    Returns (status_code, response_dict).
    """
    body = dict(body or {})
    triage = triage_payload("gateway-execute", body)
    if triage["verdict"] != "ALLOW":
        return 400, {"ok": False,
                     "error": "sandbox chamber HOLD: fingerprints "
                              + ",".join(triage["fingerprints"])}
    normalised = {str(k).upper(): v for k, v in
                  (headers or {}).items()}
    payment = normalised.get("X-PAYMENT")
    if not payment:
        return 402, payment_required()
    if payment != DEMO_PAYMENT_HEADER:
        return 400, {"ok": False,
                     "error": "invalid payment header (offline "
                              "simulation accepts only the demo "
                              "header; live facilitator verification "
                              "is HOLD)"}
    capability = body.get("capability")
    action = body.get("action", capability)
    payment_digest = hash_obj({"header": payment,
                               "amountAtomic": PRICE_ATOMIC,
                               "asset": USDC_MONAD,
                               "payTo": DEMO_PAY_TO})
    try:
        result = run_capability(capability, body.get("payload"))
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    receipt = sign_receipt({
        "agent": AGENT_NAME, "capability": capability,
        "action": action, "paymentDigest": payment_digest,
        "requestHash": hash_obj(body),
        "resultHash": hash_obj(result),
        "timestamp": DEMO_TIMESTAMP})
    return 200, {"ok": True, "result": result, "receipt": receipt}


def gateway_report():
    no_pay = handle_execute({}, {"capability": "trading",
                                 "payload": {}})
    paid = {}
    for cap in CAPABILITIES:
        status, resp = handle_execute(
            {"X-PAYMENT": DEMO_PAYMENT_HEADER},
            {"capability": cap, "payload": {}})
        paid[cap] = {"status": status, "ok": resp.get("ok"),
                     "receipt_valid": verify_receipt(resp["receipt"])
                     if resp.get("receipt") else False}
    bad = handle_execute({"X-PAYMENT": DEMO_PAYMENT_HEADER},
                         {"capability": "nope", "payload": {}})
    return {
        "gateway": "omni-agent-traderx-gateway (Python stdlib "
                   "re-implementation of the video's TS scaffold)",
        "config": gateway_config(),
        "no_payment": {"status": no_pay[0], "body": no_pay[1]},
        "paid_executions": paid,
        "unknown_capability": {"status": bad[0], "body": bad[1]},
        "facilitator_verify": facilitator_verify(DEMO_PAYMENT_HEADER),
        "facilitator_settle": facilitator_settle(DEMO_PAYMENT_HEADER),
        "zero_config": "no accounts / API keys / subscriptions - "
                       "402 terms, off-chain USDC authorization, "
                       "facilitator verify/settle (live = HOLD)",
    }


# ================================================================ 9. ERC-8004 card
def agent_card():
    """The ERC-8004 agent card, generated in code. The on-chain
    mint against the Identity Registry is a HOLD gate - only this
    card JSON is produced, never a transaction."""
    return {
        "name": AGENT_NAME,
        "version": VERSION,
        "description": AGENT_DESCRIPTION + " - all-in-one agent for "
                       "MoltForest on Monad: regime-aware BEAR "
                       "inverse hedging, multi-asset routing, Muse "
                       "portfolio layer, x402 micropayments.",
        "capabilities": list(CAPABILITIES),
        "endpoints": {
            "execute": EXECUTE_RESOURCE,
            "mcp": "/mcp",
            "agent_card": "/.well-known/agent-card.json",
        },
        "x402": {
            "x402Version": X402_VERSION,
            "scheme": X402_SCHEME,
            "network": X402_NETWORK,
            "chain": MONAD_CHAIN,
            "asset": USDC_MONAD,
            "maxAmountRequired": PRICE_ATOMIC,
            "payTo": DEMO_PAY_TO,
            "resource": EXECUTE_RESOURCE,
            "facilitator": FACILITATOR_BASE,
        },
        "erc8004": {
            "identity_registry": IDENTITY_REGISTRY,
            "reputation_registry": REPUTATION_REGISTRY,
            "chain": MONAD_CHAIN,
            "mint": "HOLD (erc8004_live_mint)",
            "reputation_feedback": "HOLD "
                                   "(reputation_live_feedback)",
        },
        "merged_sources": [
            "Monad-Bearish-Bull", "Quantum-TraderX",
            "AI-Muse-Trading-Advanced-Elite-Agent", "0mni-B0t",
            "sandbox-api", "HoneypotX", "WEB3-insp3ct",
            "sol-plex-problems"],
        "signer": "DEMO/OFFLINE (HMAC-SHA256 receipts)",
        "live": "HOLD - offline simulation only",
    }


def erc8004_mint_attempt():
    return {"status": "HOLD", "gate": "erc8004_live_mint",
            "identity_registry": IDENTITY_REGISTRY,
            "reputation_registry": REPUTATION_REGISTRY,
            "chain": MONAD_CHAIN, "transaction_submitted": False,
            "reason": "only the agent card is generated offline; "
                      "the mint transaction is never submitted"}


# ================================================================ 10. 0mni-B0t broadcast
# From 0mni-B0t (forked from ddkellar01/0mni-B0t): "Reddit-Bot is a
# powerful omnichannel, voice-controlled automation tool designed
# to streamline your social media broadcasting. Built with Python,
# it uses PRAW and SpeechRecognition to translate spoken commands
# into seamless posts across targeted subreddits. Highly scalable,
# this bot transforms how you handle your daily community
# engagement routines."
# Here: (a) voice-command input - SIMULATED with fixed transcript
# strings fed to the Muse layer's deterministic intent parser;
# SpeechRecognition and PRAW are NOT run (live_calls = 0).
# (b) omnichannel broadcast - finished reports are QUEUED as
# dry-run broadcasts; live posting is HOLD (social_live_posting)
# and Reddit credentials are names only.

REDDIT_ENV_NAMES = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                    "REDDIT_USERNAME", "REDDIT_PASSWORD"]
VOICE_TRANSCRIPTS = {
    "voice_rebalance":
        "Rebalance my portfolio to target and reduce risk",
    "voice_hedge": "Buy MON and hedge with BEAR",
}


def broadcast_report():
    regime = regime_report()
    plan = rebalance_plan()
    _, paid = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "trading", "payload": {}})
    digest16 = paid["receipt"]["receiptDigest"][:16]
    queue = [
        {"id": "bcast-01", "kind": "regime_report",
         "channel": "r/Monad",
         "text": f"Regime {regime['regime']} | NSI {regime['nsi']} "
                 f"| BEAR ${regime['bear']['price_usd']:.2f} "
                 f"(paper, offline sim)",
         "status": "queued_dry_run"},
        {"id": "bcast-02", "kind": "rebalance_summary",
         "channel": "r/algotrading",
         "text": f"Paper rebalance | total ${plan['total_usd']:.2f} "
                 f"| gross turnover ${plan['gross_turnover_usd']:.2f} "
                 f"| net delta ${plan['net_delta_usd']:.2f} "
                 f"| orders submitted 0",
         "status": "queued_dry_run"},
        {"id": "bcast-03", "kind": "receipt_digest",
         "channel": "r/CryptoCurrency",
         "text": f"Signed execution receipt (DEMO offline) "
                 f"digest {digest16} | capability trading | "
                 f"settlement HOLD",
         "status": "queued_dry_run"},
    ]
    return {
        "source": "0mni-B0t (omnichannel voice/broadcast layer)",
        "description": "Reddit-Bot is a powerful omnichannel, "
                       "voice-controlled automation tool designed "
                       "to streamline your social media "
                       "broadcasting. Built with Python, it uses "
                       "PRAW and SpeechRecognition to translate "
                       "spoken commands into seamless posts across "
                       "targeted subreddits. Highly scalable, this "
                       "bot transforms how you handle your daily "
                       "community engagement routines.",
        "voice": {
            "input": "simulated fixed transcripts (SpeechRecognition "
                     "NOT run)",
            "transcripts": {name: parse_intent(text) for name, text
                            in VOICE_TRANSCRIPTS.items()},
            "speech_recognition_run": False,
            "praw_run": False,
            "live_calls": 0,
        },
        "broadcast_queue": queue,
        "queued": len(queue),
        "posts_sent": 0,
        "reddit": {"env_names": list(REDDIT_ENV_NAMES),
                   "values_read": False,
                   "live_posting": gate("social_live_posting")},
    }


# ================================================================ 11. WEB3-insp3ct
# From WEB3-insp3ct (forked from ddkellar01/WEB3-insp3ct): "WEB3-
# insp3ct is a unified developer suite and cross-browser extension
# designed to inspect, debug, and monitor live Web3 RPC calls, DOM
# trees, and network traffic across desktop and mobile browsers.
# It merges custom DevTools panels with automated CI/CD workflows
# to build and release APK and iOS packages seamlessly from a
# single repository."
# Here: an OFFLINE RPC trace inspector over a fixed synthetic trace
# log of the gateway's own Monad RPC traffic. No browser extension
# is shipped in this Python repo, no live browser is inspected, no
# live RPC call is made (network_attempts = 0, MONAD_RPC_URL is a
# name only). Live RPC monitoring is HOLD (live_rpc_monitoring).

RPC_ENV_NAME = "MONAD_RPC_URL"
KNOWN_CONTRACTS = {IDENTITY_REGISTRY, REPUTATION_REGISTRY,
                   USDC_MONAD}

RPC_TRACE_LOG = [
    {"id": 1, "kind": "rpc", "method": "eth_chainId",
     "result": "0x8f"},
    {"id": 2, "kind": "rpc", "method": "eth_blockNumber",
     "result": "0x2a4f1"},
    {"id": 3, "kind": "rpc", "method": "eth_call",
     "to": IDENTITY_REGISTRY, "result": "0x01"},
    {"id": 4, "kind": "rpc", "method": "eth_call",
     "to": REPUTATION_REGISTRY, "result": "0x01"},
    {"id": 5, "kind": "rpc", "method": "eth_call",
     "to": USDC_MONAD, "result": "0x01"},
    {"id": 6, "kind": "rpc", "method": "eth_call",
     "to": "0x000000000000000000000000000000000000dEaD",
     "result": "0x01"},
    {"id": 7, "kind": "rpc", "method": "eth_sendRawTransaction",
     "to": IDENTITY_REGISTRY, "result": None},
    {"id": 8, "kind": "http", "method": "POST",
     "url": FACILITATOR_BASE + "/verify", "status": "recorded"},
    {"id": 9, "kind": "rpc", "method": "eth_chainId",
     "result": "0x1"},
    {"id": 10, "kind": "rpc", "method": "eth_blockNumber",
     "result": "not-a-hex-quantity"},
]


def _is_hex_quantity(value):
    if not isinstance(value, str) or not value.startswith("0x"):
        return False
    try:
        int(value, 16)
        return len(value) > 2
    except ValueError:
        return False


def inspect_rpc_trace(entries=None):
    entries = list(RPC_TRACE_LOG if entries is None else entries)
    flags = []
    for e in entries:
        flag = None
        if e.get("method") == "eth_sendRawTransaction":
            flag = "live_send_attempt"
        elif e.get("method") == "eth_chainId":
            if not _is_hex_quantity(e.get("result")):
                flag = "malformed_response"
            elif int(e["result"], 16) != 143:
                flag = "chain_mismatch"
        elif e.get("method") == "eth_call":
            if e.get("to") not in KNOWN_CONTRACTS:
                flag = "unknown_contract"
        elif e.get("kind") == "rpc":
            if not _is_hex_quantity(e.get("result")):
                flag = "malformed_response"
        if flag:
            flags.append({"id": e["id"], "flag": flag,
                          "method": e.get("method")})
    return {
        "source": "WEB3-insp3ct (offline RPC trace inspector)",
        "description": "WEB3-insp3ct is a unified developer suite "
                       "and cross-browser extension designed to "
                       "inspect, debug, and monitor live Web3 RPC "
                       "calls, DOM trees, and network traffic "
                       "across desktop and mobile browsers. It "
                       "merges custom DevTools panels with automated "
                       "CI/CD workflows to build and release APK "
                       "and iOS packages seamlessly from a single "
                       "repository.",
        "expected_chain_id": 143,
        "expected_chain": MONAD_CHAIN,
        "traces_parsed": len(entries),
        "clean": len(entries) - len(flags),
        "flagged": len(flags),
        "flags": flags,
        "known_contracts": sorted(KNOWN_CONTRACTS),
        "network_attempts": 0,
        "rpc_env_name": RPC_ENV_NAME,
        "rpc_value_read": False,
        "browser_extension_shipped": False,
        "dom_inspection": "offline - recorded/synthetic trace "
                          "logs only, no live browser inspected",
        "live_monitoring": gate("live_rpc_monitoring"),
        "release_note": "CI/CD + APK/iOS side: this merged repo "
                        "keeps Darion's standard GitHub Actions CI "
                        "+ Docker Publish paste workflows (delivered "
                        "separately); no APK/iOS build is claimed",
    }


# ================================================================ 12. kNN classifier
# Features of a market situation: (nsi, volatility, bearish
# breadth). Labels come from the lab's own regime policy - the
# classifier interpolates the policy, it does not replace the
# computed NSI above. NSI dominates the distance by design.

def model_label(nsi, volatility, breadth):
    if nsi <= -20:
        return "bearish-hedge-on"
    if nsi >= 20:
        return "bullish-hedge-off"
    return "neutral-watch"


def _training_grid():
    rows = []
    for nsi in (-60, -40, -20, -10, 0, 10, 20, 40, 60):
        for vol in (0.2, 0.8):
            for breadth in (5, 30, 45):
                rows.append(((nsi, vol, breadth),
                             model_label(nsi, vol, breadth)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(feats):
    nsi, vol, breadth = feats
    return (nsi / 20.0, vol * 0.1, breadth / 500.0)


def classify_features(features, k=5):
    target = _scaled(features)
    ranked = []
    for feats, label in TRAINING_GRID:
        cand = _scaled(feats)
        dist = math.sqrt(sum((a - b) ** 2
                             for a, b in zip(target, cand)))
        ranked.append((dist, feats, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for dist, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0.0) + 1.0 / (dist + 1e-9)
    priority = {"bearish-hedge-on": 0, "neutral-watch": 1,
                "bullish-hedge-off": 2}
    return sorted(votes.items(),
                  key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


CLASSIFIER_SCENARIOS = {
    "bearish_deep": (-60, 0.2, 45),
    "bearish_edge": (-20, 0.8, 30),
    "neutral_flat": (0, 0.2, 5),
    "neutral_warm": (10, 0.8, 30),
    "bullish_edge": (20, 0.2, 30),
    "bullish_deep": (60, 0.8, 45),
}


def classifier_report():
    return {name: {"features": {"nsi": f[0], "volatility": f[1],
                                "breadth_bearish": f[2]},
                   "policy": model_label(*f),
                   "knn": classify_features(f)}
            for name, f in CLASSIFIER_SCENARIOS.items()}


# ================================================================ 13. Council seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="omni-agent-traderx-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs,
    never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic,
               "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "model_id": "gemini-argon-4",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value "
               "never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all live "
                    "gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
        "trace_input": payload,
    }


def argon4_stress_test():
    """STRESS negative control for the Argon 4 DECIDER seat.

    Every other seat says PROCEED on a live-trading request; the
    Argon STRESS stage must still land DECIDE = HOLD, because the
    requested action is itself a HOLD gate and Argon is
    tighten-only (strictest wins). The trace hash over the stress
    payload is returned so CHECKS can recompute it.
    """
    request = {"action": "live_trading", "mode": "live",
               "real_funds": True}
    payload = {"seat": "gemini-argon-4", "stage": "STRESS",
               "request": request}
    gated = request["action"] in HOLD_GATES
    decision = "HOLD" if gated else "PROCEED"
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "stage": "STRESS",
        "request": request,
        "other_seats": {"muse_advisor": "PROCEED",
                        "google_flow": "PROCEED",
                        "gateway_router": "PROCEED"},
        "argon_decision": decision,
        "final_decision": decision,
        "rule": "strictest wins - Argon 4 can tighten to HOLD, "
                "never lift one, even when every other seat "
                "says proceed",
        "trace_sha256_16": _trace(payload),
        "trace_input": payload,
    }


def claude_advisor(topic="omni-agent-traderx-demo"):
    """Muse advisor seat - upgraded by the AI-Muse-Trading merge:
    Muse is also the portfolio brain (intent parsing, paper
    rebalancing, 24/7 risk rules). It advises and computes paper
    plans; it can never override a HOLD and never trades live."""
    return {
        "seat": "Muse",
        "role": "ADVISOR + paper portfolio brain (Muse-Trading "
                "layer)",
        "model": "muse-spark-1.1 (names-only)",
        "key": "names-only (MODEL_API_KEY name checked, value "
               "never read)",
        "live_calls": 0,
        "advice": "Keep the fence in front of every number: the "
                  "gateway quotes and dry-runs for external x402 "
                  "callers, BEAR mint/burn stays blocked at supply "
                  "1, rebalancing is paper with a $500 per-trade "
                  "cap and a 10% drawdown kill-switch, and every "
                  "live path - settlement, mint, Coinbase, posting, "
                  "RPC monitoring - stays HOLD until Darion lifts "
                  "it in writing.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["the 402 handshake: a client agent meets the "
                  "price before the capability",
                  "NSI needles from four markets swinging bearish "
                  "while one BEAR token climbs",
                  "a paper rebalance: four allocation bars sliding "
                  "to target, net delta zero",
                  "the sandbox chamber: three payloads pass, three "
                  "are held, nothing executes",
                  "a receipt being signed offline, its digest "
                  "scrolling into a broadcast queue that never "
                  "sends"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan(), "flowx": flowx_plan(),
            "argon_stress": argon4_stress_test(),
            "flows": ["Gemini-FlowX", "Google Flow"],
            "both_flows_used": True}


# ================================================================ 14. sol-plex
# From sol-plex-problems (credkellar/sol-plex-problems) - Darion's
# repo described on Docker Hub as a "cloud cognitive engine for
# complex problem-solving with secure quantum logic" (1,922 pulls /
# 2 stars at the 2026-11-06 live check). NO local clone of the
# original exists: this section is a ROLE-LAYER RE-IMPLEMENTATION
# from that description, honestly labelled - not a source copy.
# Its job here: take ONE complex agent problem, classify it,
# decompose it into subproblems, route each subproblem to the
# engine in this file that actually owns it, order them by
# dependency, and aggregate a solution verdict.
# "Secure quantum logic" honestly: a deterministic
# quantum-inspired annealing search over the plan's discrete
# choices, scored by a cost function, with a brute-force referee
# over the same space asserting the same optimum - the style of
# Darion's quantum labs. No quantum hardware, no cloud: "cloud
# cognitive engine" is the source's framing; this runs offline
# (live cloud calls are HOLD: solplex_live_cloud).

SOLPLEX_SOURCE_DESCRIPTION = (
    "cloud cognitive engine for complex problem-solving with "
    "secure quantum logic")
SOLPLEX_PROBLEM = (
    "under a BEARISH regime, hedge the book, rebalance the paper "
    "portfolio, route a paid trading capability through the "
    "gateway, and broadcast the report - without tripping any "
    "HOLD gate")

_SOLPLEX_DOMAIN_KEYWORDS = {
    "regime_risk": ("bearish", "regime", "hedge"),
    "portfolio": ("rebalance", "portfolio"),
    "payments_gateway": ("paid", "gateway", "capability"),
    "communications": ("broadcast", "report"),
    "safety_constraints": ("hold gate", "without tripping"),
}


def _solplex_domains(problem):
    text = problem.lower()
    return [domain for domain, words in
            _SOLPLEX_DOMAIN_KEYWORDS.items()
            if any(w in text for w in words)]


# Discrete choice space for the plan. The cost function is
# separable per dimension (each term grades one choice against
# the merged scenario's requirements), so neighbour-descent
# annealing provably reaches the global optimum here - and the
# brute-force referee below verifies that claim by enumeration.
SOLPLEX_TARGET_HEDGE_RATIO = BEARISH_HEDGE_RATIO  # 0.60, regime-set
SOLPLEX_CHOICE_SPACE = {
    "hedge_ratio": [0.0, 0.25, 0.5, 0.6, 0.75],
    "notional_usd": [250.0, 500.0, 750.0, 1000.0],
    "gateway_mode": ["quote_only", "dry_run", "live"],
    "broadcast": ["queue_only", "skip"],
}


def _solplex_cost(choice):
    cost = abs(choice["hedge_ratio"]
               - SOLPLEX_TARGET_HEDGE_RATIO) * 100.0
    cost += abs(choice["notional_usd"]
                - BEARISH_NOTIONAL_CAP_USD) / 25.0
    if choice["notional_usd"] > BEARISH_NOTIONAL_CAP_USD:
        cost += 50.0  # breaches the bearish notional cap
    if choice["gateway_mode"] == "quote_only":
        cost += 5.0  # quotes only: the paid routing never completes
    elif choice["gateway_mode"] == "live":
        cost += 1000.0  # trips a HOLD gate - disqualifying
    if choice["broadcast"] == "skip":
        cost += 10.0  # the report never reaches the queue
    return round(cost, 2)


def _solplex_all_choices():
    keys = list(SOLPLEX_CHOICE_SPACE)
    for values in itertools.product(
            *(SOLPLEX_CHOICE_SPACE[k] for k in keys)):
        yield dict(zip(keys, values))


def solplex_brute_force():
    """Referee: enumerate the whole space, keep the best plan."""
    best, evaluated = None, 0
    for choice in _solplex_all_choices():
        evaluated += 1
        cost = _solplex_cost(choice)
        if best is None or cost < best["cost"]:
            best = {"choice": choice, "cost": cost}
    return {"method": "brute-force enumeration (referee)",
            "space_size": evaluated, "evaluated": evaluated,
            "best_choice": best["choice"], "best_cost": best["cost"]}


def _splitmix64(seed):
    state = seed & 0xFFFFFFFFFFFFFFFF
    while True:
        state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        yield z ^ (z >> 31)


def solplex_anneal(restarts=8, max_steps=50):
    """Quantum-inspired deterministic annealing (offline).

    Each restart starts from a splitmix64-seeded state and descends
    by single-coordinate neighbour moves, accepting the best
    neighbour while the temperature schedule cools from 1.0; the
    best plan seen across restarts is kept. Deterministic: the
    same seed stream reproduces the same search byte-for-byte.
    """
    keys = list(SOLPLEX_CHOICE_SPACE)
    rng = _splitmix64(20261118)
    best, evaluations = None, 0
    temperatures = []
    for restart in range(restarts):
        idx = [next(rng) % len(SOLPLEX_CHOICE_SPACE[k]) for k in keys]
        temperature = 1.0
        for _step in range(max_steps):
            temperatures.append(round(temperature, 4))
            current = {k: SOLPLEX_CHOICE_SPACE[k][i]
                       for k, i in zip(keys, idx)}
            current_cost = _solplex_cost(current)
            evaluations += 1
            if best is None or current_cost < best["cost"]:
                best = {"choice": current, "cost": current_cost}
            if current_cost == 0.0:
                break  # 0 is the cost lower bound - provably optimal
            moved = False
            for pos, key in enumerate(keys):
                for delta in (-1, 1):
                    nxt = idx[pos] + delta
                    if not 0 <= nxt < len(SOLPLEX_CHOICE_SPACE[key]):
                        continue
                    trial = list(idx)
                    trial[pos] = nxt
                    trial_choice = {
                        k: SOLPLEX_CHOICE_SPACE[k][i]
                        for k, i in zip(keys, trial)}
                    trial_cost = _solplex_cost(trial_choice)
                    evaluations += 1
                    if trial_cost < current_cost:
                        idx, moved = trial, True
                        break
                if moved:
                    break
            temperature *= 0.8
            if not moved:
                break
    return {"method": "quantum-inspired deterministic annealing "
                      "(offline, no quantum hardware)",
            "restarts": restarts,
            "evaluations": evaluations,
            "temperature_first": temperatures[0],
            "temperature_last": temperatures[-1],
            "best_choice": best["choice"], "best_cost": best["cost"]}


def solplex_solve_problem(problem=SOLPLEX_PROBLEM):
    """Decompose the problem, route every subproblem to the real
    engine that owns it, solve the plan choices, aggregate."""
    regime = regime_report()
    hedge = hedge_decision(regime["regime"], 800.0)
    triage = triage_payload(
        "solplex-trading",
        {"capability": "trading",
         "payload": {"pair": "MON/USDC", "mode": "dry_run"}})
    gw_status, gw_resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "trading",
         "payload": {"maxNotionalUsd": hedge["effective_notional_usd"],
                     "mode": "dry_run"}})
    plan = rebalance_plan()
    risk = risk_check_order(hedge["effective_notional_usd"])
    watch = kill_switch(10000.0, 9200.0)
    inspector = inspect_rpc_trace()
    broadcast = broadcast_report()
    subproblems = [
        {"id": "assess_regime", "task": "read the market regime",
         "owner": "regime engine (Monad-Bearish-Bull)",
         "owner_function": "regime_report", "depends_on": [],
         "outcome": {"regime": regime["regime"],
                     "nsi": regime["nsi"],
                     "bear_price_usd": regime["bear"]["price_usd"],
                     "ok": regime["regime"] == "BEARISH_REGIME"}},
        {"id": "size_inverse_hedge",
         "task": "size the BEAR inverse hedge under the regime cap",
         "owner": "Regime & Inverse Hedging Module",
         "owner_function": "hedge_decision",
         "depends_on": ["assess_regime"],
         "outcome": {"hedge": hedge["hedge"],
                     "effective_notional_usd":
                         hedge["effective_notional_usd"],
                     "bear_hedge_usd": hedge["bear_hedge_usd"],
                     "ok": hedge["hedge"] == "ON"
                     and hedge["bear_hedge_usd"] == 300.00}},
        {"id": "triage_gateway_payload",
         "task": "statically triage the gateway payload first",
         "owner": "sandbox-api chamber (verbatim)",
         "owner_function": "triage_payload",
         "depends_on": [],
         "outcome": {"verdict": triage["verdict"],
                     "executed": triage["executed"],
                     "ok": triage["verdict"] == "ALLOW"
                     and triage["executed"] is False}},
        {"id": "route_paid_trading_capability",
         "task": "route a paid trading capability through the "
                 "gateway and collect a signed receipt",
         "owner": "x402 gateway (MoltForest)",
         "owner_function": "handle_execute",
         "depends_on": ["triage_gateway_payload",
                        "size_inverse_hedge"],
         "outcome": {"http_status": gw_status,
                     "receipt_valid": verify_receipt(
                         gw_resp["receipt"]),
                     "dispatch_notional_usd": gw_resp["result"]
                     ["dispatch"]["max_notional_usd"],
                     "ok": gw_status == 200
                     and verify_receipt(gw_resp["receipt"])}},
        {"id": "rebalance_paper_portfolio",
         "task": "rebalance the paper portfolio to target",
         "owner": "Muse portfolio layer "
                  "(AI-Muse-Trading-Advanced-Elite-Agent)",
         "owner_function": "rebalance_plan",
         "depends_on": ["assess_regime"],
         "outcome": {"net_delta_usd": plan["net_delta_usd"],
                     "gross_turnover_usd":
                         plan["gross_turnover_usd"],
                     "orders_submitted": plan["orders_submitted"],
                     "ok": plan["net_delta_usd"] == 0.0
                     and plan["orders_submitted"] == 0}},
        {"id": "enforce_risk_limits",
         "task": "enforce per-trade cap and drawdown kill-switch",
         "owner": "Muse 24/7 risk manager",
         "owner_function": "risk_check_order + kill_switch",
         "depends_on": ["size_inverse_hedge",
                        "rebalance_paper_portfolio"],
         "outcome": {"hedge_notional_approved": risk["approved"],
                     "kill_switch_tripped": watch["tripped"],
                     "ok": risk["approved"] is True
                     and watch["tripped"] is False}},
        {"id": "inspect_rpc_trace",
         "task": "grade the gateway's recorded RPC traces",
         "owner": "WEB3-insp3ct offline inspector",
         "owner_function": "inspect_rpc_trace",
         "depends_on": ["route_paid_trading_capability"],
         "outcome": {"traces_parsed": inspector["traces_parsed"],
                     "flagged": inspector["flagged"],
                     "network_attempts":
                         inspector["network_attempts"],
                     "ok": inspector["network_attempts"] == 0}},
        {"id": "broadcast_report",
         "task": "queue the finished report for broadcast",
         "owner": "0mni-B0t broadcast layer",
         "owner_function": "broadcast_report",
         "depends_on": ["route_paid_trading_capability",
                        "rebalance_paper_portfolio",
                        "enforce_risk_limits", "inspect_rpc_trace"],
         "outcome": {"queued": broadcast["queued"],
                     "posts_sent": broadcast["posts_sent"],
                     "ok": broadcast["queued"] == 3
                     and broadcast["posts_sent"] == 0}},
    ]
    order, done, pending = [], set(), list(subproblems)
    while pending:
        ready = [s for s in pending
                 if all(d in done for d in s["depends_on"])]
        if not ready:
            raise ValueError("subproblem graph has a cycle")
        for s in ready:
            order.append(s["id"])
            done.add(s["id"])
            pending.remove(s)
    anneal = solplex_anneal()
    referee = solplex_brute_force()
    agrees = (anneal["best_choice"] == referee["best_choice"]
              and anneal["best_cost"] == referee["best_cost"])
    all_ok = all(s["outcome"]["ok"] for s in subproblems)
    verdict = ("PROCEED - problem solved on paper, no HOLD gate "
               "tripped" if all_ok and agrees else
               "HOLD - a subproblem or the solver referee failed")
    return {
        "source": "sol-plex-problems (role-layer re-implementation, "
                  "not a source copy - no local clone exists)",
        "source_description": SOLPLEX_SOURCE_DESCRIPTION,
        "source_repo": "credkellar/sol-plex-problems (Docker Hub "
                       "description on record; 1,922 pulls / 2 "
                       "stars at the 2026-11-06 live check)",
        "problem": problem,
        "domain": "multi-domain agent operations",
        "domains_detected": _solplex_domains(problem),
        "subproblems": subproblems,
        "subproblem_count": len(subproblems),
        "routed_count": sum(1 for s in subproblems if s["owner"]),
        "execution_order": order,
        "solver": anneal,
        "brute_force_referee": referee,
        "solver_agrees_with_referee": agrees,
        "choice_space_size": referee["space_size"],
        "verdict": verdict,
        "hold_gates_tripped": [],
        "live_cloud_calls": 0,
        "live_cloud_gate": gate("solplex_live_cloud"),
        "runtime": "offline local - 'cloud cognitive engine' is "
                   "the source's framing; no cloud and no quantum "
                   "hardware is used here",
    }


# ================================================================ 15. FlowX planner
# Gemini-FlowX (Darion's house pattern, from
# monad-bearish-bull/bearishbull/flows.py): a subtask-graph
# planner DISTINCT from the Google Flow video seat in section 13.
# It splits one full omni-agent run into subtasks with
# dependencies, levels them so everything in a level runs in
# parallel, and recommends exactly the widest-level number of
# agents - that finishes at zero queue latency; extra agents buy
# nothing. Engine underneath is Gemini 2.5 Pro extended thinking
# when GEMINI_API_KEY is set (names-only here); the deterministic
# offline graph is authoritative either way. Together with the
# Google Flow video seat (plan-only, rendered = False), this repo
# carries BOTH Google flows.

FLOWX_MODEL_ID = "google/gemini-flowx-pro-thinking"
FLOWX_ENGINE = "gemini-2.5-pro"
FLOWX_THINKING_BUDGET = 32768

FLOWX_GRAPH = {
    "regime_scan": [],
    "chamber_triage": [],
    "capability_routing": ["chamber_triage"],
    "hedge": ["regime_scan"],
    "rebalance": ["regime_scan"],
    "hft_quote": ["capability_routing"],
    "rpc_inspection": ["capability_routing"],
    "receipt_signing": ["hft_quote"],
    "broadcast": ["receipt_signing", "rebalance", "hedge",
                  "rpc_inspection"],
}


def flowx_plan(graph=None):
    """Level the graph; recommended agents = widest level."""
    graph = FLOWX_GRAPH if graph is None else graph
    levels, done, remaining = [], set(), dict(graph)
    while remaining:
        level = sorted([n for n, deps in remaining.items()
                        if all(d in done for d in deps)])
        if not level:
            raise ValueError("graph has a cycle or missing "
                             "dependency")
        levels.append(level)
        done.update(level)
        for n in level:
            del remaining[n]
    return {
        "flow": "Gemini-FlowX",
        "role": "planner for one full omni-agent run (DISTINCT "
                "from the Google Flow video seat)",
        "model_id": FLOWX_MODEL_ID,
        "engine": FLOWX_ENGINE,
        "thinking_budget": FLOWX_THINKING_BUDGET,
        "key": "names-only (GEMINI_API_KEY name only, value "
               "never read)",
        "live_calls": 0,
        "offline_authoritative": True,
        "subtasks": len(graph),
        "levels": levels,
        "level_count": len(levels),
        "level_sizes": [len(l) for l in levels],
        "recommended_agents": max(len(l) for l in levels),
        "queue_wait": 0,
        "critical_path_steps": len(levels),
        "wall_clock_steps": len(levels),
    }


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. NSI / regime / BEAR pricing - recomputed, not printed faith
    chk("nsi_weights_sum_one",
        abs(sum(NSI_WEIGHTS.values()) - 1.0) < 1e-12
        and NSI_WEIGHTS == {"crypto": 0.30, "stocks": 0.30,
                            "forex": 0.20, "prediction": 0.20})
    chk("nsi_bearish_sample_recomputed",
        compute_nsi(SAMPLE_PARTS_BEARISH) == -53.47
        and abs(-62.0 * 0.30 + -58.0 * 0.30 + -41.35 * 0.20
                + -46.0 * 0.20 - -53.47) < 1e-9)
    chk("nsi_bullish_sample_recomputed",
        compute_nsi(SAMPLE_PARTS_BULLISH) == 45.0)
    chk("nsi_neutral_sample_recomputed",
        compute_nsi(SAMPLE_PARTS_NEUTRAL) == 1.8
        and regime_for_nsi(compute_nsi(SAMPLE_PARTS_NEUTRAL))
        == "NEUTRAL_REGIME")
    chk("regime_thresholds",
        regime_for_nsi(-53.47) == "BEARISH_REGIME"
        and regime_for_nsi(-20) == "BEARISH_REGIME"
        and regime_for_nsi(45.0) == "BULLISH_REGIME"
        and regime_for_nsi(20) == "BULLISH_REGIME"
        and regime_for_nsi(0) == "NEUTRAL_REGIME")
    bear = bear_pricing(-53.47)
    chk("bear_multiplier_sample",
        bear["multiplier"] == 1.802
        and abs(bear["multiplier_raw"] - 1.80205) < 1e-9)
    chk("bear_price_sample_half_up",
        bear["price_usd"] == 180.21
        and bear["market_cap_usd"] == 180.21
        and bear["supply"] == 1 and bear["stance"] == "BULLISH")
    chk("bear_price_bullish_sample",
        bear_pricing(45.0)["price_usd"] == 32.50
        and bear_pricing(45.0)["stance"] == "BEARISH")
    chk("bear_multiplier_clamps",
        bear_pricing(90.0)["multiplier"] == 0.25
        and bear_pricing(90.0)["price_usd"] == 25.00
        and bear_pricing(-200.0)["multiplier"] == 3.0
        and bear_pricing(-200.0)["price_usd"] == 300.00)
    chk("bear_mint_burn_blocked",
        bear_mint_attempt()["status"] == "HOLD"
        and bear_burn_attempt()["status"] == "HOLD"
        and bear_mint_attempt()["supply"] == 1)

    # 2. Hedge module - both branches asserted
    hb = hedge_decision("BEARISH_REGIME", 800.0)
    chk("hedge_bearish_branch",
        hb["hedge"] == "ON" and hb["notional_cap_usd"] == 500.0
        and hb["effective_notional_usd"] == 500.0
        and hb["bear_hedge_usd"] == 300.00
        and hb["leg"] == "BEAR inverse token (paper)")
    hu = hedge_decision("BULLISH_REGIME", 800.0)
    chk("hedge_bullish_branch",
        hu["hedge"] == "OFF" and hu["notional_cap_usd"] == 1000.0
        and hu["effective_notional_usd"] == 800.0
        and hu["bear_hedge_usd"] == 0.0)
    hn = hedge_decision("NEUTRAL_REGIME", 800.0)
    chk("hedge_neutral_branch",
        hn["hedge"] == "REDUCED" and hn["effective_notional_usd"]
        == 750.0 and hn["bear_hedge_usd"] == 187.50)
    hrep = hedge_report()
    chk("hedge_report_uses_regime_engine",
        hrep["branches"]["bearish"]["regime"] == "BEARISH_REGIME"
        and hrep["branches"]["bullish"]["regime"]
        == "BULLISH_REGIME")

    # 3. Multi-asset routing
    ma = multi_asset_report()
    chk("multi_asset_universe_four_classes",
        sorted(ma["universe"]) == ["crypto", "equities", "forex",
                                   "prediction"]
        and all(len(v) == 4 or k == "prediction"
                for k, v in ma["universe"].items()))
    chk("multi_asset_total_routed",
        ma["total_routed_usd"] == 2500.0 and ma["live_orders"] == 0)
    chk("multi_asset_oversized_clamped",
        ma["signals"][-1]["requested_notional_usd"] == 5000.0
        and ma["signals"][-1]["routed_notional_usd"] == 1000.0
        and ma["signals"][-1]["capped"] is True)
    chk("multi_asset_live_held",
        route_signal({"assetClass": "crypto", "symbol": "BTC",
                      "mode": "live"})["status"] == "HOLD")

    # 4. HFT bridge - caps clamp, live held, no key exposure
    hft = hft_report()
    chk("hft_quote_shape",
        hft["quote"]["status"] == "quoted"
        and hft["quote"]["mode"] == "dry_run"
        and hft["quote"]["order_submitted"] is False
        and hft["quote"]["telemetry"]["pair"] == "MON/USDC")
    chk("hft_caps_clamp",
        hft["oversized_clamped"]["max_notional_usd"] == 1000.0
        and hft["oversized_clamped"]["max_slippage_bps"] == 100)
    chk("hft_live_held_no_key",
        hft["live_attempt"]["status"] == "HOLD"
        and hft["live_attempt"]["gate"] == "live_hft_execution"
        and hft["live_attempt"]["private_key_exposed"] is False)

    # 5. Muse trading layer - intents, rebalance, risk
    mt = muse_trading_report()
    chk("intent_rebalance_defensive",
        mt["intents"]["rebalance_defensive"]["intent"]
        == "rebalance_portfolio"
        and mt["intents"]["rebalance_defensive"]["risk_mode"]
        == "defensive"
        and mt["intents"]["rebalance_defensive"]["live_calls"] == 0)
    chk("intent_buy_mon_hedge",
        mt["intents"]["buy_mon_hedge"]["intent"] == "buy"
        and mt["intents"]["buy_mon_hedge"]["assets"] == ["MON"]
        and mt["intents"]["buy_mon_hedge"]["hedge"] is True)
    chk("intent_sell_and_monitor",
        mt["intents"]["sell_btc"]["intent"] == "sell"
        and mt["intents"]["sell_btc"]["assets"] == ["BTC"]
        and mt["intents"]["monitor"]["intent"] == "monitor")
    plan = mt["rebalance"]
    legs = {l["asset"]: l for l in plan["legs"]}
    chk("rebalance_totals",
        plan["total_usd"] == 10000.0
        and abs(sum(TARGET_ALLOCATIONS.values()) - 1.0) < 1e-12)
    chk("rebalance_deltas_exact",
        legs["BTC"]["delta_usd"] == -700.0
        and legs["BTC"]["action"] == "SELL"
        and legs["ETH"]["delta_usd"] == 400.0
        and legs["MON"]["delta_usd"] == 300.0
        and legs["USDC"]["delta_usd"] == 0.0
        and legs["USDC"]["action"] == "HOLD")
    chk("rebalance_net_zero_gross",
        plan["net_delta_usd"] == 0.0
        and plan["gross_turnover_usd"] == 1400.0
        and plan["orders_submitted"] == 0
        and plan["live_gate"] == "HOLD")
    chk("rebalance_legs_routed_paper",
        len(mt["rebalance_legs_routed"]) == 3
        and all(r["status"] == "routed_dry_run"
                and r["orderSubmitted"] is False
                for r in mt["rebalance_legs_routed"]))
    chk("risk_per_trade_cap",
        mt["risk"]["sample_ok"]["approved"] is True
        and mt["risk"]["sample_over_cap"]["approved"] is False
        and risk_check_order(500.0)["approved"] is True
        and risk_check_order(0.0)["approved"] is False
        and risk_check_order(100.0, halted=True)["approved"]
        is False)
    chk("risk_kill_switch",
        mt["risk"]["drawdown_watch"]["drawdown_pct"] == 8.0
        and mt["risk"]["drawdown_watch"]["tripped"] is False
        and mt["risk"]["drawdown_trip"]["drawdown_pct"] == 12.0
        and mt["risk"]["drawdown_trip"]["tripped"] is True
        and mt["risk"]["drawdown_trip"]["auto_clear"] is False)
    chk("coinbase_names_only_held",
        mt["coinbase"]["values_read"] is False
        and mt["coinbase"]["env_names"] == COINBASE_ENV_NAMES
        and mt["coinbase"]["connection"] == "HOLD"
        and mt["coinbase"]["live_trading"] == "HOLD")

    # 6. Sandbox chamber triage
    sb = sandbox_report()
    chk("sandbox_counts",
        sb["allowed"] == 3 and sb["held"] == 3
        and len(sb["samples"]) == 6)
    chk("sandbox_never_executes_no_network",
        sb["any_executed"] is False
        and sb["network_attempts_total"] == 0
        and all(s["budget_ok"] for s in sb["samples"]))
    chk("sandbox_held_are_the_bad_three",
        [s["sample"] for s in sb["samples"]
         if s["verdict"] == "HOLD_IN_SANDBOX"]
        == ["trading-live-attempt", "signer-key-leak",
            "mcp-exec-attempt"])

    # 7. HoneypotX
    hp = honeypotx_report()
    chk("honeypot_counts",
        hp["attempts"] == 12
        and hp["by_class"] == {"scanner": 4, "env_harvest": 3,
                               "lfi_probe": 2, "sqli_probe": 2,
                               "upload_attempt": 1})
    chk("honeypot_top_and_burst",
        hp["top_threat_score"] == 100
        and hp["top_attempt_class"] == "upload_attempt"
        and len(hp["bursts"]) == 1
        and hp["bursts"][0]["attempts"] == 5)
    chk("honeypot_no_listener_no_access",
        hp["listener_open"] is False
        and hp["access_granted"] is False
        and hp["bait_sessions"] == 5)

    # 8. x402 gateway - 402 shape, receipts, routing, errors
    gw = gateway_report()
    chk("gateway_402_shape",
        gw["no_payment"]["status"] == 402
        and gw["no_payment"]["body"]["x402Version"] == 1
        and gw["no_payment"]["body"]["error"] == "Payment Required"
        and gw["no_payment"]["body"]["accepts"][0]["scheme"]
        == "exact"
        and gw["no_payment"]["body"]["accepts"][0]["network"]
        == "monad-mainnet"
        and gw["no_payment"]["body"]["accepts"][0]
        ["maxAmountRequired"] == PRICE_ATOMIC
        and gw["no_payment"]["body"]["accepts"][0]["description"]
        == "All-in-One omni-agent-traderx"
        and gw["no_payment"]["body"]["accepts"][0]["asset"]
        == USDC_MONAD)
    chk("gateway_all_six_capabilities_paid",
        all(v["status"] == 200 and v["ok"] and v["receipt_valid"]
            for v in gw["paid_executions"].values())
        and sorted(gw["paid_executions"]) == sorted(CAPABILITIES))
    chk("gateway_unknown_capability_400",
        gw["unknown_capability"]["status"] == 400
        and gw["unknown_capability"]["body"]["ok"] is False)
    status, resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "payments", "payload": {}})
    chk("gateway_payments_rail",
        status == 200
        and resp["result"]["rail"] == "x402/monad-usdc"
        and resp["result"]["quote"]["recipient"] == DEMO_PAY_TO)
    status, resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "trading",
         "payload": {"maxNotionalUsd": 99999.0,
                     "maxSlippageBps": 999}})
    chk("gateway_trading_caps_clamp_through_gateway",
        status == 200
        and resp["result"]["dispatch"]["max_notional_usd"] == 1000.0
        and resp["result"]["dispatch"]["max_slippage_bps"] == 100
        and resp["result"]["dispatch"]["pair"] == "MON/USDC"
        and resp["result"]["dispatch"]["side"] == "quote_only"
        and resp["result"]["dispatch"]["mode"] == "dry_run")
    status, resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "defi", "payload": {}})
    chk("gateway_defi_defaults",
        status == 200
        and resp["result"]["dispatch"]["pool"] == "MON/USDC"
        and resp["result"]["dispatch"]["liquidity_check"]
        == "passed"
        and resp["result"]["dispatch"]["slippage_guard_bps"] == 50)
    status, resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "trading", "payload": {"mode": "live"}})
    chk("gateway_live_trading_refused_400",
        status == 400 and resp["ok"] is False
        and "HOLD" in resp["error"])
    status, resp = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "data",
         "payload": {"leak": "AGENT_SIGNER_KEY"}})
    chk("gateway_chamber_blocks_before_routing",
        status == 400 and "sandbox chamber HOLD" in resp["error"])
    status, resp = handle_execute(
        {"X-PAYMENT": "forged-header"},
        {"capability": "trading", "payload": {}})
    chk("gateway_forged_header_400",
        status == 400 and resp["ok"] is False)
    _, paid = handle_execute(
        {"X-PAYMENT": DEMO_PAYMENT_HEADER},
        {"capability": "research", "payload": {"topic": "monad"}})
    chk("receipt_fields_and_verify",
        paid["ok"] is True and verify_receipt(paid["receipt"])
        and paid["receipt"]["agent"] == AGENT_NAME
        and paid["receipt"]["timestamp"] == DEMO_TIMESTAMP
        and "DEMO/OFFLINE" in paid["receipt"]["signer"])
    tampered = dict(paid["receipt"])
    tampered["resultHash"] = "0" * 64
    chk("receipt_tamper_fails_verify",
        verify_receipt(tampered) is False)
    chk("facilitator_stubs_refuse_offline",
        gw["facilitator_verify"]["status"] == "HOLD"
        and gw["facilitator_verify"]["verified"] is False
        and gw["facilitator_verify"]["endpoint"]
        == "https://x402-facilitator.molandak.org/verify"
        and gw["facilitator_settle"]["settled"] is False
        and gw["facilitator_settle"]["endpoint"]
        == "https://x402-facilitator.molandak.org/settle")
    chk("gateway_config_names_only",
        sorted(gw["config"]) == sorted(GATEWAY_ENV_NAMES)
        and all(v["value_exposed"] is False
                for v in gw["config"].values()))

    # 9. ERC-8004 agent card
    card = agent_card()
    chk("agent_card_fields",
        card["name"] == "omni-agent-traderx"
        and card["capabilities"] == CAPABILITIES
        and card["x402"]["chain"] == "eip155:143"
        and card["x402"]["asset"] == USDC_MONAD
        and card["erc8004"]["identity_registry"]
        == "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
        and card["erc8004"]["reputation_registry"]
        == "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63")
    chk("erc8004_mint_held",
        erc8004_mint_attempt()["status"] == "HOLD"
        and erc8004_mint_attempt()["transaction_submitted"]
        is False)

    # 10. 0mni-B0t broadcast layer
    bc = broadcast_report()
    chk("broadcast_queue_queued_nothing_sent",
        bc["queued"] == 3 and bc["posts_sent"] == 0
        and all(q["status"] == "queued_dry_run"
                for q in bc["broadcast_queue"])
        and bc["broadcast_queue"][0]["kind"] == "regime_report"
        and "BEARISH_REGIME" in bc["broadcast_queue"][0]["text"])
    chk("broadcast_voice_simulated_into_parser",
        bc["voice"]["speech_recognition_run"] is False
        and bc["voice"]["praw_run"] is False
        and bc["voice"]["transcripts"]["voice_rebalance"]["intent"]
        == "rebalance_portfolio"
        and bc["voice"]["transcripts"]["voice_hedge"]["intent"]
        == "buy")
    chk("broadcast_reddit_names_only_held",
        bc["reddit"]["values_read"] is False
        and bc["reddit"]["env_names"] == REDDIT_ENV_NAMES
        and bc["reddit"]["live_posting"] == "HOLD")

    # 11. WEB3-insp3ct inspector
    wi = inspect_rpc_trace()
    chk("inspector_counts",
        wi["traces_parsed"] == 10 and wi["clean"] == 6
        and wi["flagged"] == 4)
    chk("inspector_flag_kinds",
        [f["flag"] for f in wi["flags"]]
        == ["unknown_contract", "live_send_attempt",
            "chain_mismatch", "malformed_response"]
        and wi["expected_chain_id"] == 143)
    chk("inspector_offline_names_only",
        wi["network_attempts"] == 0
        and wi["browser_extension_shipped"] is False
        and wi["rpc_value_read"] is False
        and wi["live_monitoring"] == "HOLD"
        and IDENTITY_REGISTRY in wi["known_contracts"])

    # 12. Classifier: kNN matches the lab's own policy
    rep = classifier_report()
    chk("classifier_scenarios",
        rep["bearish_deep"]["knn"] == "bearish-hedge-on"
        and rep["bearish_edge"]["knn"] == "bearish-hedge-on"
        and rep["neutral_flat"]["knn"] == "neutral-watch"
        and rep["bullish_edge"]["knn"] == "bullish-hedge-off"
        and rep["bullish_deep"]["knn"] == "bullish-hedge-off")
    chk("classifier_grid_consistency",
        all(classify_features(feats) == label
            for feats, label in TRAINING_GRID)
        and all(row["knn"] == row["policy"] for row in rep.values()))

    # 13. Gates + seats
    chk("hold_gates_21", len(HOLD_GATES) == 21
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_spot_checks",
        gate("live_trading") == "HOLD"
        and gate("bear_mint_burn") == "HOLD"
        and gate("coinbase_live_trading") == "HOLD"
        and gate("social_live_posting") == "HOLD"
        and gate("live_honeypot_listener") == "HOLD"
        and gate("live_sample_detonation") == "HOLD"
        and gate("live_rpc_monitoring") == "HOLD"
        and gate("solplex_live_cloud") == "HOLD"
        and gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override",
        brains["decider"]["can_override_hold"] is False
        and brains["decider"]["model_id"] == "gemini-argon-4")
    chk("argon4_trace_recomputes",
        brains["decider"]["trace_sha256_16"]
        == _trace(brains["decider"]["trace_input"])
        and brains["decider"]["pipeline"]
        == ["MAP", "MODEL", "STRESS", "DECIDE"]
        and brains["decider"]["tiers"] == [2048, 8192, 32768])
    chk("argon4_stress_negative_control",
        brains["argon_stress"]["other_seats"]
        == {"muse_advisor": "PROCEED", "google_flow": "PROCEED",
            "gateway_router": "PROCEED"}
        and brains["argon_stress"]["argon_decision"] == "HOLD"
        and brains["argon_stress"]["final_decision"] == "HOLD"
        and brains["argon_stress"]["trace_sha256_16"]
        == _trace(brains["argon_stress"]["trace_input"]))
    chk("claude_no_override",
        brains["advisor"]["can_override_hold"] is False
        and brains["advisor"]["live_calls"] == 0)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)

    # 14. sol-plex-problems - decomposition, routing, solver
    sp = solplex_solve_problem()
    chk("solplex_decomposition_and_routing",
        sp["subproblem_count"] == 8 and sp["routed_count"] == 8
        and sp["domains_detected"] == [
            "regime_risk", "portfolio", "payments_gateway",
            "communications", "safety_constraints"]
        and sp["domain"] == "multi-domain agent operations"
        and all(s["owner_function"] for s in sp["subproblems"]))
    pos = {name: i for i, name in enumerate(sp["execution_order"])}
    chk("solplex_execution_order_respects_dependencies",
        len(sp["execution_order"]) == 8
        and all(pos[d] < pos[s["id"]]
                for s in sp["subproblems"]
                for d in s["depends_on"]))
    chk("solplex_subproblem_outcomes_real",
        all(s["outcome"]["ok"] for s in sp["subproblems"])
        and sp["subproblems"][0]["outcome"]["nsi"] == -53.47
        and sp["subproblems"][1]["outcome"]["bear_hedge_usd"]
        == 300.00
        and sp["subproblems"][3]["outcome"]["http_status"] == 200
        and sp["subproblems"][3]["outcome"]["receipt_valid"]
        is True
        and sp["subproblems"][4]["outcome"]["net_delta_usd"] == 0.0
        and sp["subproblems"][7]["outcome"]["posts_sent"] == 0)
    chk("solplex_solver_matches_brute_force",
        sp["solver_agrees_with_referee"] is True
        and sp["solver"]["best_choice"]
        == sp["brute_force_referee"]["best_choice"]
        and sp["solver"]["best_cost"]
        == sp["brute_force_referee"]["best_cost"] == 0.0
        and sp["solver"]["best_choice"] == {
            "hedge_ratio": 0.6, "notional_usd": 500.0,
            "gateway_mode": "dry_run", "broadcast": "queue_only"}
        and sp["choice_space_size"] == 120
        and sp["brute_force_referee"]["evaluated"] == 120)
    chk("solplex_verdict_no_hold_tripped_offline",
        sp["verdict"].startswith("PROCEED")
        and sp["hold_gates_tripped"] == []
        and sp["live_cloud_calls"] == 0
        and sp["live_cloud_gate"] == "HOLD")

    # 15. Gemini-FlowX planner (both Google flows present)
    fx = flowx_plan()
    chk("flowx_graph_levels",
        fx["subtasks"] == 9 and fx["level_count"] == 5
        and sum(fx["level_sizes"]) == fx["subtasks"]
        and fx["level_sizes"] == [2, 3, 2, 1, 1]
        and fx["levels"][0] == ["chamber_triage", "regime_scan"]
        and fx["levels"][-1] == ["broadcast"])
    chk("flowx_recommended_agents_and_queue",
        fx["recommended_agents"] == 3
        and fx["recommended_agents"] == max(fx["level_sizes"])
        and fx["queue_wait"] == 0
        and fx["wall_clock_steps"] == fx["critical_path_steps"]
        == 5 and fx["live_calls"] == 0)
    chk("both_google_flows_present",
        brains["both_flows_used"] is True
        and brains["flows"] == ["Gemini-FlowX", "Google Flow"]
        and brains["flowx"]["flow"] == "Gemini-FlowX"
        and brains["flow"]["seat"] == "Google Flow"
        and brains["flow"]["rendered"] is False)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("omni-agent-traderx - all-in-one Monad agent (OFFLINE SIM)")
    print("by Darion Kellar | MIT | pure stdlib | zero network")
    print("MoltForest gateway + BEAR regime engine + multi-asset "
          "routing")
    print("Muse portfolio layer + sandbox chamber + HoneypotX "
          "+ broadcast + RPC inspector")
    print("sol-plex problem solver + Gemini-FlowX planner + "
          "Argon 4 DECIDER (both Google flows)")
    print("=" * 68)
    print("\n[1] Regime engine (Monad-Bearish-Bull) - NSI + BEAR")
    rep = regime_report()
    bear = rep["bear"]
    print(f"    parts {rep['parts']} weights crypto .30 / stocks "
          f".30 / forex .20 / prediction .20")
    print(f"    NSI {rep['nsi']} -> regime {rep['regime']}")
    print(f"    BEAR supply {bear['supply']} | multiplier "
          f"x{bear['multiplier']:.3f} (raw {bear['multiplier_raw']})"
          f" | price ${bear['price_usd']:.2f} | stance "
          f"{bear['stance']} | mint/burn BLOCKED")
    bull = regime_report(SAMPLE_PARTS_BULLISH)
    print(f"    bullish sample: NSI {bull['nsi']} -> "
          f"{bull['regime']} | BEAR ${bull['bear']['price_usd']:.2f}")
    print("\n[2] Regime & Inverse Hedging Module (requested $800)")
    for label, row in hedge_report()["branches"].items():
        print(f"    {label:8s} NSI {row['nsi']:7.2f} hedge "
              f"{row['hedge']:7s} cap ${row['notional_cap_usd']:.0f}"
              f" effective ${row['effective_notional_usd']:.0f} "
              f"BEAR hedge ${row['bear_hedge_usd']:.2f} (paper)")
    print("\n[3] Multi-asset engine (Quantum-TraderX) - paper routing")
    ma = multi_asset_report()
    for s in ma["signals"]:
        print(f"    {s['assetClass']:10s} {s['symbol']:16s} "
              f"{s['side']:4s} requested ${s['requested_notional_usd']:.0f}"
              f" -> routed ${s['routed_notional_usd']:.0f} "
              f"({s['status']})")
    print(f"    total routed ${ma['total_routed_usd']:.2f} | live "
          f"orders {ma['live_orders']}")
    print("\n[4] HFT bridge - telemetry/quotes + dry_run only")
    hft = hft_report()
    q = hft["quote"]
    print(f"    {q['pair']} mid {q['telemetry']['mid_price']} | "
          f"bid depth ${q['telemetry']['bid_depth_usd']:,} | "
          f"spread {q['telemetry']['spread_bps']} bps | mode "
          f"{q['mode']} | order submitted {q['order_submitted']}")
    print(f"    caps clamp: $99,999 -> "
          f"${hft['oversized_clamped']['max_notional_usd']:.0f}, "
          f"999 bps -> {hft['oversized_clamped']['max_slippage_bps']}"
          f" bps | live attempt: {hft['live_attempt']['status']}")
    print("\n[5] Muse trading layer (AI-Muse-Trading) - paper brain")
    mt = muse_trading_report()
    for name, intent in mt["intents"].items():
        print(f"    intent {name:20s} -> {intent['intent']} "
              f"assets {intent['assets']} risk {intent['risk_mode']}")
    plan = mt["rebalance"]
    for leg in plan["legs"]:
        print(f"    rebalance {leg['asset']:4s} current "
              f"${leg['current_usd']:.0f} -> target "
              f"${leg['target_usd']:.0f} delta "
              f"${leg['delta_usd']:+.0f} {leg['action']}")
    print(f"    net delta ${plan['net_delta_usd']:.2f} | gross "
          f"turnover ${plan['gross_turnover_usd']:.2f} | orders "
          f"submitted {plan['orders_submitted']} | Coinbase live: "
          f"{mt['coinbase']['live_trading']}")
    print(f"    risk: per-trade cap ${mt['risk']['per_trade_cap_usd']:.0f}"
          f" | $400 approved {mt['risk']['sample_ok']['approved']}"
          f" | $750 approved "
          f"{mt['risk']['sample_over_cap']['approved']} | drawdown "
          f"12.0% kill-switch tripped "
          f"{mt['risk']['drawdown_trip']['tripped']}")
    print("\n[6] Sandbox chamber (sandbox-api, verbatim) - triage "
          "before routing")
    sb = sandbox_report()
    for s in sb["samples"]:
        print(f"    {s['sample']:20s} {s['verdict']:15s} "
              f"fingerprints {s['fingerprints']} executed "
              f"{s['executed']} network {s['network_attempts']}")
    print(f"    allowed {sb['allowed']} | held {sb['held']} | any "
          f"executed {sb['any_executed']} | network attempts "
          f"{sb['network_attempts_total']}")
    print("\n[7] HoneypotX - log analysis only, no listener")
    hp = honeypotx_report()
    print(f"    attempts {hp['attempts']} by class {hp['by_class']}")
    print(f"    top threat {hp['top_threat_score']} "
          f"({hp['top_attempt_class']}) | bursts {len(hp['bursts'])}"
          f" | bait sessions {hp['bait_sessions']} | listener open "
          f"{hp['listener_open']} | access granted "
          f"{hp['access_granted']}")
    print("\n[8] x402 gateway (MoltForest / ERC-8004) - offline sim")
    gw = gateway_report()
    print(f"    no payment header -> HTTP "
          f"{gw['no_payment']['status']} "
          f"{gw['no_payment']['body']['error']} | price "
          f"{PRICE_ATOMIC} atomic USDC | payTo demo placeholder")
    for cap, row in gw["paid_executions"].items():
        print(f"    paid {cap:10s} -> HTTP {row['status']} ok "
              f"{row['ok']} receipt valid {row['receipt_valid']}")
    print(f"    unknown capability -> HTTP "
          f"{gw['unknown_capability']['status']} | facilitator "
          f"verify: {gw['facilitator_verify']['status']} (TODO "
          f"live, HOLD) | settle: "
          f"{gw['facilitator_settle']['status']}")
    card = agent_card()
    print(f"    agent card: {card['name']} | capabilities "
          f"{len(card['capabilities'])} | chain "
          f"{card['x402']['chain']} | ERC-8004 mint "
          f"{card['erc8004']['mint']}")
    print("\n[9] 0mni-B0t broadcast layer - queued, never sent")
    bc = broadcast_report()
    for item in bc["broadcast_queue"]:
        print(f"    {item['id']} {item['kind']:18s} -> "
              f"{item['channel']:18s} [{item['status']}]")
    print(f"    queued {bc['queued']} | posts sent "
          f"{bc['posts_sent']} | voice simulated "
          f"(SpeechRecognition/PRAW not run) | live posting "
          f"{bc['reddit']['live_posting']}")
    print("\n[10] WEB3-insp3ct - offline RPC trace inspector")
    wi = inspect_rpc_trace()
    print(f"    traces parsed {wi['traces_parsed']} | clean "
          f"{wi['clean']} | flagged {wi['flagged']} "
          f"{[f['flag'] for f in wi['flags']]}")
    print(f"    expected chain {wi['expected_chain_id']} "
          f"({wi['expected_chain']}) | network attempts "
          f"{wi['network_attempts']} | live monitoring "
          f"{wi['live_monitoring']} | extension shipped "
          f"{wi['browser_extension_shipped']}")
    print("\n[11] Regime classifier (TinyML kNN, policy-labelled)")
    for name, row in classifier_report().items():
        print(f"    {name:16s} -> {row['knn']}")
    print("\n[12] sol-plex-problems - cognitive problem solver "
          "(offline re-implementation)")
    sp = solplex_solve_problem()
    print(f"    problem: {sp['problem']}")
    print(f"    domains {sp['domains_detected']}")
    for s in sp["subproblems"]:
        print(f"    subproblem {s['id']:28s} -> "
              f"{s['owner_function']:28s} ok "
              f"{s['outcome']['ok']}")
    print(f"    subproblems {sp['subproblem_count']} | routed "
          f"{sp['routed_count']} | order "
          f"{' -> '.join(sp['execution_order'][:3])} -> ...")
    print(f"    solver (annealing) best "
          f"{sp['solver']['best_choice']} cost "
          f"{sp['solver']['best_cost']} | brute-force referee "
          f"agrees {sp['solver_agrees_with_referee']} | space "
          f"{sp['choice_space_size']} plans")
    print(f"    verdict: {sp['verdict']} | HOLD gates tripped "
          f"{sp['hold_gates_tripped']} | live cloud calls "
          f"{sp['live_cloud_calls']} ({sp['live_cloud_gate']})")
    print("\n[13] Gemini-FlowX planner + advisory seats (both "
          "Google flows)")
    brains = brains_report()
    fx = brains["flowx"]
    for i, level in enumerate(fx["levels"]):
        print(f"    flowx level {i}: {level}")
    print(f"    flowx subtasks {fx['subtasks']} | levels "
          f"{fx['level_count']} | recommended agents "
          f"{fx['recommended_agents']} | queue wait "
          f"{fx['queue_wait']} | wall clock "
          f"{fx['wall_clock_steps']} steps")
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    argon STRESS control: other seats PROCEED -> "
          f"final {brains['argon_stress']['final_decision']}")
    print(f"    advisor can_override_hold = "
          f"{brains['advisor']['can_override_hold']} | flow "
          f"rendered = {brains['flow']['rendered']} | both flows "
          f"{brains['flows']}")
    print(f"\n[14] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD "
          f"gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}"
              f"/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "regime":
        print(json.dumps(regime_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "hedge":
        print(json.dumps(hedge_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "gateway":
        print(json.dumps(gateway_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "agent-card":
        print(json.dumps(agent_card(), indent=2, sort_keys=True))
        return 0
    if cmd == "muse":
        print(json.dumps(muse_trading_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "sandbox":
        print(json.dumps(sandbox_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "honeypot":
        print(json.dumps(honeypotx_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "broadcast":
        print(json.dumps(broadcast_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "inspect":
        print(json.dumps(inspect_rpc_trace(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "solplex":
        print(json.dumps(solplex_solve_problem(), indent=2,
                         sort_keys=True))
        return 0
    if cmd == "flowx":
        print(json.dumps(flowx_plan(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "live_trading"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
