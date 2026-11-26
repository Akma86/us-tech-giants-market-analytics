"""Master CLI pipeline to train, validate, and evaluate the Macro-Aware PPO RL Portfolio Agent."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rl.config import RLConfig
from src.rl.evaluate import build_complete_evaluation_payload
from src.rl.features import MacroPortfolioFeatureBuilder
from src.rl.ppo_agent import PPOMultiSeedEnsemble


def main() -> None:
    t0 = time.time()
    cfg = RLConfig()

    print("Building causal point-in-time multi-asset & macroeconomic dataset...")
    builder = MacroPortfolioFeatureBuilder(cfg)
    full_dataset = builder.build_dataset()

    train_ds = full_dataset.slice_window(cfg.train_start, cfg.train_end)
    val_ds = full_dataset.slice_window(cfg.val_start, cfg.val_end)
    test_ds = full_dataset.slice_window(cfg.test_start, cfg.test_end)

    print(
        f"Dataset ready: {len(full_dataset.dates)} total weekly rebalance steps | "
        f"Features: {full_dataset.features.shape[1]} | Assets: {len(cfg.assets)}"
    )
    print(
        f"  Train: {train_ds.dates[0].date()} -> {train_ds.dates[-1].date()} ({len(train_ds.dates)} steps)\n"
        f"  Val  : {val_ds.dates[0].date()} -> {val_ds.dates[-1].date()} ({len(val_ds.dates)} steps)\n"
        f"  OOS  : {test_ds.dates[0].date()} -> {test_ds.dates[-1].date()} ({len(test_ds.dates)} steps)"
    )

    obs_dim = int(full_dataset.features.shape[1]) + cfg.num_assets + 1
    ensemble = PPOMultiSeedEnsemble(obs_dim=obs_dim, action_dim=cfg.num_assets, config=cfg)

    print(f"\nTraining Multi-Seed PPO Actor-Critic Ensemble (seeds={cfg.seeds}, episodes={cfg.training_episodes})...")
    train_summaries = ensemble.train_all(train_ds, val_ds)
    for s in train_summaries:
        print(
            f"  Seed {s['seed']:4d} | Device: {s['device']:4s} | Best Val Sortino Score: {s['best_val_score']:+.4f}"
        )

    model_path = ensemble.save(cfg.model_dir)
    print(f"Saved trained ensemble checkpoint -> {model_path}")

    payload = build_complete_evaluation_payload(
        full_dataset=full_dataset,
        train_dataset=train_ds,
        val_dataset=val_ds,
        test_dataset=test_ds,
        ensemble=ensemble,
        seed_train_summaries=train_summaries,
        config=cfg,
    )

    print("\n--- OUT-OF-SAMPLE (2022–2026) STRATEGY LEADERBOARD ---")
    header = (
        f"{'Strategy':30s} | {'CAGR':>7s} | {'TotRet':>8s} | {'Sharpe':>6s} | "
        f"{'Sortino':>7s} | {'MaxDD':>7s} | {'Calmar':>6s} | {'Turn/Yr':>7s}"
    )
    print(header)
    print("-" * len(header))
    for row in payload["oos_leaderboard"]:
        print(
            f"{row['strategy']:30s} | "
            f"{row['cagr_pct']:+6.2f}% | "
            f"{row['total_return_pct']:+7.2f}% | "
            f"{row['sharpe']:6.3f} | "
            f"{row['sortino']:7.3f} | "
            f"{row['max_drawdown_pct']:+6.2f}% | "
            f"{row['calmar']:6.3f} | "
            f"{row['ann_turnover_pct']:6.1f}%"
        )

    print("\n--- OOS SUB-REGIME ATTRIBUTION ---")
    for r in payload["regime_breakdown"]:
        print(
            f"  {r['regime']} ({r['start_date']} -> {r['end_date']}):\n"
            f"    PPO RL Return: {r['rl_return_pct']:+6.2f}% (MaxDD {r['rl_max_dd_pct']:+6.2f}%, Sharpe {r['rl_sharpe']:.2f}) "
            f"vs 60/40: {r['bench_60_40_return_pct']:+6.2f}% (MaxDD {r['bench_60_40_max_dd_pct']:+6.2f}%) "
            f"| Avg Sleeves: Tech {r['avg_tech_weight_pct']:.1f}%, ^GSPC {r['avg_sp500_weight_pct']:.1f}%, "
            f"Bonds {r['avg_bond_weight_pct']:.1f}%, SHY Cash {r['avg_cash_shy_weight_pct']:.1f}%"
        )

    lat = payload["latest_allocation"]
    print(
        f"\nLatest Target Allocation ({lat['as_of_date']}): "
        f"Tech {lat['tech_equities_pct']:.1f}% | ^GSPC {lat['sp500_index_pct']:.1f}% | "
        f"Treasury IEF/TLT {lat['treasury_bonds_pct']:.1f}% | SHY Cash {lat['cash_shy_pct']:.1f}%"
    )
    print(f"Completed RL training and OOS backtest export in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
