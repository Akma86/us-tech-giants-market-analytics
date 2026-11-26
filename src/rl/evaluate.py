"""Performance evaluation, multi-regime attribution, and JSON/CSV export for the RL Portfolio Engine."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.rl.baselines import evaluate_all_baselines
from src.rl.config import RLConfig
from src.rl.features import MacroPortfolioDataset
from src.rl.ppo_agent import PPOMultiSeedEnsemble


def compute_ledger_metrics(
    ledger: List[Dict[str, Any]],
    rebalance_freq_days: int = 5,
) -> Dict[str, float]:
    """Calculates annualized return, volatility, Sharpe, Sortino, Max Drawdown, Calmar, and turnover."""
    if not ledger:
        return {}

    rets = np.array([row["net_return"] for row in ledger], dtype=np.float64)
    rf_rets = np.array([row["rf_return"] for row in ledger], dtype=np.float64)
    turnovers = np.array([row["one_way_turnover"] for row in ledger], dtype=np.float64)
    costs = np.array([row["tx_cost"] for row in ledger], dtype=np.float64)

    n_steps = len(rets)
    steps_per_year = 252.0 / float(rebalance_freq_days)
    years = max(n_steps / steps_per_year, 1e-6)

    terminal_nav = float(ledger[-1]["nav"])
    total_return_pct = (terminal_nav - 1.0) * 100.0
    cagr_pct = ((terminal_nav ** (1.0 / years)) - 1.0) * 100.0

    ann_vol_pct = float(np.std(rets, ddof=1) * np.sqrt(steps_per_year) * 100.0) if n_steps > 1 else 0.0
    excess = rets - rf_rets
    ann_excess = float(np.mean(excess) * steps_per_year)
    ann_vol = float(np.std(excess, ddof=1) * np.sqrt(steps_per_year)) if n_steps > 1 else 1e-6
    sharpe = ann_excess / max(ann_vol, 1e-6)

    downside = np.minimum(0.0, excess)
    downside_vol = float(np.sqrt(np.mean(downside ** 2) * steps_per_year))
    sortino = ann_excess / max(downside_vol, 1e-6)

    nav_curve = np.array([row["nav"] for row in ledger], dtype=np.float64)
    peaks = np.maximum.accumulate(np.insert(nav_curve, 0, 1.0))[1:]
    drawdowns = (nav_curve / np.maximum(peaks, 1e-12)) - 1.0
    max_dd_pct = float(np.min(drawdowns) * 100.0)

    calmar = (cagr_pct / abs(max_dd_pct)) if abs(max_dd_pct) > 1e-4 else 0.0
    win_rate_pct = float(np.mean(rets > 0.0) * 100.0)
    ann_turnover_pct = float(np.mean(turnovers) * steps_per_year * 100.0)
    total_cost_drag_pct = float(np.sum(costs) * 100.0)

    return {
        "terminal_wealth_100": round(terminal_nav * 100.0, 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
        "ann_vol_pct": round(ann_vol_pct, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "calmar": round(calmar, 3),
        "win_rate_pct": round(win_rate_pct, 1),
        "ann_turnover_pct": round(ann_turnover_pct, 1),
        "total_cost_drag_pct": round(total_cost_drag_pct, 2),
        "steps": int(n_steps),
    }


def _slice_ledger_by_dates(
    ledger: List[Dict[str, Any]], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    sub = [row for row in ledger if start_date <= row["date"] <= end_date]
    if not sub:
        return []
    # Rebase NAV to 1.0 at start of sub-window
    rebased: List[Dict[str, Any]] = []
    nav = 1.0
    peak = 1.0
    for r in sub:
        nav *= 1.0 + float(r["net_return"])
        peak = max(peak, nav)
        copy_r = dict(r)
        copy_r["nav"] = nav
        copy_r["drawdown"] = (nav / peak) - 1.0
        rebased.append(copy_r)
    return rebased


def build_complete_evaluation_payload(
    full_dataset: MacroPortfolioDataset,
    train_dataset: MacroPortfolioDataset,
    val_dataset: MacroPortfolioDataset,
    test_dataset: MacroPortfolioDataset,
    ensemble: PPOMultiSeedEnsemble,
    seed_train_summaries: List[Dict[str, Any]],
    config: Optional[RLConfig] = None,
) -> Dict[str, Any]:
    """Generates full Train/Val/OOS evaluation metrics, regime breakdowns, and chart series."""
    cfg = config or RLConfig()

    oos_rl_ledger, oos_seed_ledgers = ensemble.rollout_ensemble(test_dataset)
    oos_baselines = evaluate_all_baselines(test_dataset, cfg)

    val_rl_ledger, _ = ensemble.rollout_ensemble(val_dataset)
    val_baselines = evaluate_all_baselines(val_dataset, cfg)

    full_rl_ledger, _ = ensemble.rollout_ensemble(full_dataset)
    full_baselines = evaluate_all_baselines(full_dataset, cfg)

    # Multi-seed dispersion metrics on Out-of-Sample
    seed_metrics = [
        compute_ledger_metrics(l, cfg.rebalance_freq_days) for l in oos_seed_ledgers
    ]
    seed_sharpes = [m["sharpe"] for m in seed_metrics]
    seed_cagrs = [m["cagr_pct"] for m in seed_metrics]
    seed_max_dds = [m["max_drawdown_pct"] for m in seed_metrics]

    strategy_order = [
        ("PPO Macro-RL Ensemble", oos_rl_ledger),
        ("60/40 Benchmark (^GSPC/IEF)", oos_baselines["60/40 Benchmark (^GSPC/IEF)"]),
        ("Inverse-Vol Risk Parity", oos_baselines["Inverse-Vol Risk Parity"]),
        ("Equal-Weight (1/N)", oos_baselines["Equal-Weight (1/N)"]),
        ("S&P 500 Buy & Hold (^GSPC)", oos_baselines["S&P 500 Buy & Hold (^GSPC)"]),
    ]

    oos_leaderboard: List[Dict[str, Any]] = []
    for name, led in strategy_order:
        m = compute_ledger_metrics(led, cfg.rebalance_freq_days)
        m["strategy"] = name
        oos_leaderboard.append(m)

    val_leaderboard: List[Dict[str, Any]] = []
    for name, led in [
        ("PPO Macro-RL Ensemble", val_rl_ledger),
        ("60/40 Benchmark (^GSPC/IEF)", val_baselines["60/40 Benchmark (^GSPC/IEF)"]),
        ("Inverse-Vol Risk Parity", val_baselines["Inverse-Vol Risk Parity"]),
        ("Equal-Weight (1/N)", val_baselines["Equal-Weight (1/N)"]),
        ("S&P 500 Buy & Hold (^GSPC)", val_baselines["S&P 500 Buy & Hold (^GSPC)"]),
    ]:
        m = compute_ledger_metrics(led, cfg.rebalance_freq_days)
        m["strategy"] = name
        val_leaderboard.append(m)

    # Sub-regime analysis across the 2022-2026 Out-of-Sample window
    regime_windows = [
        ("2022 Rate & Inflation Shock", "2022-01-01", "2022-12-31", "Fed +425 bps tightening, CPI > 8%, stock-bond correlation spike"),
        ("2023–2024 AI Expansion & Disinflation", "2023-01-01", "2024-12-31", "Mega-cap AI capex surge, inverted curve, disinflation trend"),
        ("2025–2026 Higher Neutral & Policy Normalization", "2025-01-01", "2026-12-31", "10Y yield ~4.9–5.1%, positive real yields, selective dispersion"),
    ]
    regime_breakdown: List[Dict[str, Any]] = []
    for label, s_dt, e_dt, desc in regime_windows:
        rl_sub = _slice_ledger_by_dates(oos_rl_ledger, s_dt, e_dt)
        b60_sub = _slice_ledger_by_dates(oos_baselines["60/40 Benchmark (^GSPC/IEF)"], s_dt, e_dt)
        sp_sub = _slice_ledger_by_dates(oos_baselines["S&P 500 Buy & Hold (^GSPC)"], s_dt, e_dt)
        ew_sub = _slice_ledger_by_dates(oos_baselines["Equal-Weight (1/N)"], s_dt, e_dt)
        if not rl_sub:
            continue
        rl_m = compute_ledger_metrics(rl_sub, cfg.rebalance_freq_days)
        b60_m = compute_ledger_metrics(b60_sub, cfg.rebalance_freq_days)
        sp_m = compute_ledger_metrics(sp_sub, cfg.rebalance_freq_days)
        ew_m = compute_ledger_metrics(ew_sub, cfg.rebalance_freq_days)

        # Average sleeve allocations during this regime
        tech_w = np.mean([
            sum(r["weights"][a] for a in cfg.single_equities) for r in rl_sub
        ]) * 100.0
        sp_w = np.mean([r["weights"]["^GSPC"] for r in rl_sub]) * 100.0
        bond_w = np.mean([r["weights"]["IEF"] + r["weights"]["TLT"] for r in rl_sub]) * 100.0
        cash_w = np.mean([r["weights"]["SHY"] for r in rl_sub]) * 100.0

        regime_breakdown.append(
            {
                "regime": label,
                "start_date": rl_sub[0]["date"],
                "end_date": rl_sub[-1]["date"],
                "description": desc,
                "rl_return_pct": rl_m["total_return_pct"],
                "rl_max_dd_pct": rl_m["max_drawdown_pct"],
                "rl_sharpe": rl_m["sharpe"],
                "bench_60_40_return_pct": b60_m["total_return_pct"],
                "bench_60_40_max_dd_pct": b60_m["max_drawdown_pct"],
                "sp500_return_pct": sp_m["total_return_pct"],
                "ew_return_pct": ew_m["total_return_pct"],
                "avg_tech_weight_pct": round(float(tech_w), 1),
                "avg_sp500_weight_pct": round(float(sp_w), 1),
                "avg_bond_weight_pct": round(float(bond_w), 1),
                "avg_cash_shy_weight_pct": round(float(cash_w), 1),
            }
        )

    # Compact OOS series for interactive charts (base 100.0)
    b60_led = oos_baselines["60/40 Benchmark (^GSPC/IEF)"]
    rp_led = oos_baselines["Inverse-Vol Risk Parity"]
    ew_led = oos_baselines["Equal-Weight (1/N)"]
    sp_led = oos_baselines["S&P 500 Buy & Hold (^GSPC)"]

    oos_series: List[Dict[str, Any]] = []
    csv_rows: List[Dict[str, Any]] = []
    for i, row in enumerate(oos_rl_ledger):
        w_dict = row["weights"]
        tech_sleeve = sum(w_dict[a] for a in cfg.single_equities) * 100.0
        sp_sleeve = w_dict["^GSPC"] * 100.0
        bond_sleeve = (w_dict["IEF"] + w_dict["TLT"]) * 100.0
        cash_sleeve = w_dict["SHY"] * 100.0

        point = {
            "d": row["date"],
            "rl": round(float(row["nav"] * 100.0), 2),
            "b60": round(float(b60_led[i]["nav"] * 100.0), 2),
            "rp": round(float(rp_led[i]["nav"] * 100.0), 2),
            "ew": round(float(ew_led[i]["nav"] * 100.0), 2),
            "sp": round(float(sp_led[i]["nav"] * 100.0), 2),
            "rl_dd": round(float(row["drawdown"] * 100.0), 2),
            "b60_dd": round(float(b60_led[i]["drawdown"] * 100.0), 2),
            "sp_dd": round(float(sp_led[i]["drawdown"] * 100.0), 2),
            "w_tech": round(float(tech_sleeve), 1),
            "w_sp": round(float(sp_sleeve), 1),
            "w_bond": round(float(bond_sleeve), 1),
            "w_cash": round(float(cash_sleeve), 1),
            "to": round(float(row["one_way_turnover"] * 100.0), 1),
            "weights": {k: round(float(v * 100.0), 2) for k, v in w_dict.items()},
        }
        oos_series.append(point)

        csv_row = {
            "date": row["date"],
            "ppo_rl_nav_100": point["rl"],
            "bench_60_40_nav_100": point["b60"],
            "risk_parity_nav_100": point["rp"],
            "equal_weight_nav_100": point["ew"],
            "sp500_nav_100": point["sp"],
            "ppo_rl_drawdown_pct": point["rl_dd"],
            "bench_60_40_drawdown_pct": point["b60_dd"],
            "one_way_turnover_pct": point["to"],
        }
        for sym in cfg.assets:
            csv_row[f"weight_{sym}_pct"] = round(float(w_dict[sym] * 100.0), 2)
        csv_rows.append(csv_row)

    # Sample full walk-forward trajectory (2005-2026) every 2 rebalance steps (~bi-weekly) to keep JSON compact
    full_b60 = full_baselines["60/40 Benchmark (^GSPC/IEF)"]
    full_sp = full_baselines["S&P 500 Buy & Hold (^GSPC)"]
    walk_forward_series: List[Dict[str, Any]] = []
    for i, row in enumerate(full_rl_ledger):
        if i % 2 != 0 and i != len(full_rl_ledger) - 1:
            continue
        dt = row["date"]
        split = "TRAIN" if dt <= cfg.train_end else ("VAL" if dt <= cfg.val_end else "OOS")
        walk_forward_series.append(
            {
                "d": dt,
                "split": split,
                "rl": round(float(row["nav"] * 100.0), 2),
                "b60": round(float(full_b60[i]["nav"] * 100.0), 2),
                "sp": round(float(full_sp[i]["nav"] * 100.0), 2),
            }
        )

    latest_oos = oos_rl_ledger[-1]
    latest_weights_pct = {
        sym: round(float(latest_oos["weights"][sym] * 100.0), 2) for sym in cfg.assets
    }

    payload: Dict[str, Any] = {
        "available": True,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "architecture": {
            "algorithm": "Proximal Policy Optimization (PPO) Actor-Critic + Macro Structural Residual",
            "framework": f"PyTorch {seed_train_summaries[0]['device'].upper()} Multi-Seed Ensemble",
            "seeds": list(cfg.seeds),
            "assets": list(cfg.assets),
            "rebalance_freq_days": cfg.rebalance_freq_days,
            "transaction_cost_bps": cfg.cost_bps,
            "max_single_stock_weight_pct": round(cfg.max_single_stock_weight * 100.0, 1),
            "macro_publication_lag_days": cfg.macro_publication_lag_days,
            "obs_dimension": int(test_dataset.features.shape[1] + cfg.num_assets + 1),
            "feature_count": int(test_dataset.features.shape[1]),
        },
        "splits": {
            "train": {
                "start": str(train_dataset.dates[0].date()),
                "end": str(train_dataset.dates[-1].date()),
                "rebalance_steps": len(train_dataset.dates),
            },
            "validation": {
                "start": str(val_dataset.dates[0].date()),
                "end": str(val_dataset.dates[-1].date()),
                "rebalance_steps": len(val_dataset.dates),
            },
            "oos_test": {
                "start": str(test_dataset.dates[0].date()),
                "end": str(test_dataset.dates[-1].date()),
                "rebalance_steps": len(test_dataset.dates),
            },
        },
        "multi_seed_stability": {
            "seeds": list(cfg.seeds),
            "oos_sharpe_mean": round(float(np.mean(seed_sharpes)), 3),
            "oos_sharpe_std": round(float(np.std(seed_sharpes)), 3),
            "oos_cagr_mean_pct": round(float(np.mean(seed_cagrs)), 2),
            "oos_cagr_std_pct": round(float(np.std(seed_cagrs)), 2),
            "oos_max_dd_mean_pct": round(float(np.mean(seed_max_dds)), 2),
            "per_seed_oos": [
                {"seed": s, **m} for s, m in zip(cfg.seeds, seed_metrics)
            ],
            "training_summaries": seed_train_summaries,
        },
        "oos_leaderboard": oos_leaderboard,
        "val_leaderboard": val_leaderboard,
        "regime_breakdown": regime_breakdown,
        "latest_allocation": {
            "as_of_date": latest_oos["date"],
            "weights_pct": latest_weights_pct,
            "tech_equities_pct": round(
                sum(latest_weights_pct[a] for a in cfg.single_equities), 1
            ),
            "sp500_index_pct": round(latest_weights_pct["^GSPC"], 1),
            "treasury_bonds_pct": round(
                latest_weights_pct["IEF"] + latest_weights_pct["TLT"], 1
            ),
            "cash_shy_pct": round(latest_weights_pct["SHY"], 1),
        },
        "methodology": (
            "Walk-Forward Multi-Seed PPO Actor-Critic trained on 2005–2017 with checkpoint selection on "
            "2018–2021 Validation Sortino Ratio and evaluated strictly Out-of-Sample on 2022–2026. "
            "Monthly BLS/BEA inflation series (CPI, Core PCE) carry a mandatory +35 calendar-day publication "
            "lag; all continuous features use causal 252-day rolling z-scores; weekly rebalancing includes "
            "10 bps one-way transaction costs and a 25% single-stock concentration cap."
        ),
        "oos_series": oos_series,
        "walk_forward_series": walk_forward_series,
    }

    cfg.output_json_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    pd.DataFrame(csv_rows).to_csv(cfg.output_csv_path, index=False)

    cfg.portfolio_json_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg.output_json_path, cfg.portfolio_json_path)
    shutil.copy2(cfg.output_csv_path, cfg.portfolio_csv_path)

    return payload
