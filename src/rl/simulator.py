"""Day-by-day interactive capital simulator for the trained PPO Macro-RL Portfolio Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import torch

from src.rl.config import RLConfig
from src.rl.env import project_capped_simplex
from src.rl.features import MacroPortfolioDataset, MacroPortfolioFeatureBuilder
from src.rl.ppo_agent import ActorCriticNet, precompute_macro_structural_logits_matrix

torch.set_num_threads(1)


class DailyRLTradingSimulator:
    """Simulates day-by-day trading of a custom dollar capital amount (e.g. $1,000) across any date window."""

    def __init__(self, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()
        self._daily_dates: Optional[pd.DatetimeIndex] = None
        self._daily_returns: Optional[np.ndarray] = None
        self._daily_features: Optional[np.ndarray] = None
        self._daily_priors: Optional[np.ndarray] = None
        self._daily_macro_df: Optional[pd.DataFrame] = None
        self._daily_raw_sig: Optional[np.ndarray] = None
        self._nets: List[ActorCriticNet] = []

    def _ensure_loaded(self) -> None:
        if self._daily_dates is not None:
            return

        builder = MacroPortfolioFeatureBuilder(self.config)
        prices = builder.load_daily_asset_prices()
        assets = list(self.config.assets)
        asset_px = prices[assets].copy()
        daily_rets_df = asset_px.pct_change().fillna(0.0)

        macro_df = builder.load_lagged_macro_series(prices.index)
        vix_series = prices["^VIX"] if "^VIX" in prices.columns else pd.Series(18.0, index=prices.index)
        tnx_series = prices["^TNX"] if "^TNX" in prices.columns else pd.Series(4.0, index=prices.index)

        raw_feats: Dict[str, pd.Series] = {}
        for sym in assets:
            px = asset_px[sym]
            ret1 = daily_rets_df[sym]
            raw_feats[f"{sym}_ret_5d"] = np.log(px / px.shift(5))
            raw_feats[f"{sym}_ret_21d"] = np.log(px / px.shift(21))
            raw_feats[f"{sym}_ret_63d"] = np.log(px / px.shift(63))
            raw_feats[f"{sym}_ret_126d"] = np.log(px / px.shift(126))
            raw_feats[f"{sym}_vol_21d"] = ret1.rolling(21, min_periods=10).std() * np.sqrt(252.0)
            sma126 = px.rolling(126, min_periods=25).mean()
            raw_feats[f"{sym}_sma126_gap"] = (px / sma126) - 1.0
            roll_max = px.rolling(126, min_periods=20).max()
            raw_feats[f"{sym}_dd_126d"] = (px / roll_max) - 1.0

        raw_feats["macro_vix_level"] = vix_series
        raw_feats["macro_vix_chg_21d"] = vix_series - vix_series.shift(21)
        raw_feats["macro_tnx_level"] = tnx_series
        raw_feats["macro_tnx_chg_21d"] = tnx_series - tnx_series.shift(21)
        raw_feats["macro_tnx_chg_63d"] = tnx_series - tnx_series.shift(63)

        for col in [
            "cpi_headline_yoy_pct",
            "pce_core_yoy_pct",
            "fed_funds_rate_pct",
            "real_policy_rate_pct",
            "yield_curve_10y_2y_pct",
            "spread_10y_3m",
            "real_10y_yield",
        ]:
            raw_feats[f"macro_{col}"] = (
                macro_df[col] if col in macro_df.columns else pd.Series(0.0, index=prices.index)
            )

        sp_ret = daily_rets_df[self.config.benchmark_equity_ticker]
        bond_ret = daily_rets_df[self.config.benchmark_bond_ticker]
        raw_feats["macro_sp_bond_corr_60d"] = sp_ret.rolling(60, min_periods=20).corr(bond_ret).fillna(0.0)

        feat_df = pd.DataFrame(raw_feats, index=prices.index).ffill().fillna(0.0)
        win = self.config.zscore_window_days
        min_p = self.config.zscore_min_periods
        roll_mean = feat_df.rolling(win, min_periods=min_p).mean()
        roll_std = feat_df.rolling(win, min_periods=min_p).std().replace(0.0, 1.0).fillna(1.0)
        norm_df = ((feat_df - roll_mean) / (roll_std + 1e-8)).fillna(0.0).clip(
            -self.config.zscore_clip, self.config.zscore_clip
        )

        warmup = 140
        valid_dates = prices.index[warmup:]
        n_days = len(valid_dates)

        raw_sig = np.zeros((n_days, len(assets), 5), dtype=np.float64)
        for i_sym, sym in enumerate(assets):
            raw_sig[:, i_sym, 0] = feat_df[f"{sym}_ret_21d"].iloc[warmup:].to_numpy(dtype=np.float64)
            raw_sig[:, i_sym, 1] = feat_df[f"{sym}_ret_63d"].iloc[warmup:].to_numpy(dtype=np.float64)
            raw_sig[:, i_sym, 2] = feat_df[f"{sym}_ret_126d"].iloc[warmup:].to_numpy(dtype=np.float64)
            raw_sig[:, i_sym, 3] = feat_df[f"{sym}_vol_21d"].iloc[warmup:].to_numpy(dtype=np.float64)
            raw_sig[:, i_sym, 4] = feat_df[f"{sym}_sma126_gap"].iloc[warmup:].to_numpy(dtype=np.float64)

        macro_table = pd.DataFrame(
            {
                "vix": vix_series.iloc[warmup:].to_numpy(dtype=np.float64),
                "tnx_10y": tnx_series.iloc[warmup:].to_numpy(dtype=np.float64),
                "tnx_chg_63d": feat_df["macro_tnx_chg_63d"].iloc[warmup:].to_numpy(dtype=np.float64),
                "cpi_yoy": feat_df["macro_cpi_headline_yoy_pct"].iloc[warmup:].to_numpy(dtype=np.float64),
                "core_pce_yoy": feat_df["macro_pce_core_yoy_pct"].iloc[warmup:].to_numpy(dtype=np.float64),
                "spread_10y_3m": feat_df["macro_spread_10y_3m"].iloc[warmup:].to_numpy(dtype=np.float64),
                "spread_10y_2y": feat_df["macro_yield_curve_10y_2y_pct"].iloc[warmup:].to_numpy(dtype=np.float64),
                "sp_bond_corr_60d": feat_df["macro_sp_bond_corr_60d"].iloc[warmup:].to_numpy(dtype=np.float64),
                "sp_sma126_gap": feat_df[f"{self.config.benchmark_equity_ticker}_sma126_gap"].iloc[warmup:].to_numpy(dtype=np.float64),
                "ief_sma126_gap": feat_df[f"{self.config.benchmark_bond_ticker}_sma126_gap"].iloc[warmup:].to_numpy(dtype=np.float64),
                "tlt_sma126_gap": feat_df["TLT_sma126_gap"].iloc[warmup:].to_numpy(dtype=np.float64),
            },
            index=valid_dates,
        )

        temp_ds = MacroPortfolioDataset(
            dates=valid_dates,
            daily_dates=valid_dates,
            daily_returns=daily_rets_df.iloc[warmup:].copy(),
            step_returns=daily_rets_df.iloc[warmup:].to_numpy(dtype=np.float64),
            features=norm_df.iloc[warmup:].to_numpy(dtype=np.float32),
            raw_macro_table=macro_table,
            feature_names=list(norm_df.columns),
            assets=self.config.assets,
            raw_asset_signals=raw_sig,
        )

        self._daily_dates = valid_dates
        self._daily_returns = temp_ds.step_returns
        self._daily_features = temp_ds.features
        self._daily_macro_df = macro_table
        self._daily_raw_sig = raw_sig
        self._daily_priors = precompute_macro_structural_logits_matrix(temp_ds, self.config)

        obs_dim = int(self._daily_features.shape[1]) + self.config.num_assets + 1
        ckpt_path = self.config.model_dir / "ppo_macro_ensemble.pt"
        self._nets = []
        if ckpt_path.exists():
            ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
            for sd in ckpt.get("state_dicts", []):
                net = ActorCriticNet(obs_dim, self.config.num_assets, hidden_dim=96)
                net.load_state_dict(sd)
                net.eval()
                self._nets.append(net)
        if not self._nets:
            net = ActorCriticNet(obs_dim, self.config.num_assets, hidden_dim=96)
            net.eval()
            self._nets.append(net)

    def simulate(
        self,
        initial_capital: float = 1000.0,
        start_date: str = "2025-01-02",
        end_date: str = "2026-11-18",
        rebalance_every_n_days: int = 5,
        cost_bps: float = 10.0,
    ) -> Dict[str, Any]:
        """Runs a day-by-day dollar simulation across every trading day in [start_date, end_date]."""
        self._ensure_loaded()
        assert self._daily_dates is not None
        assert self._daily_returns is not None
        assert self._daily_features is not None
        assert self._daily_priors is not None
        assert self._daily_macro_df is not None
        assert self._daily_raw_sig is not None

        assets = list(self.config.assets)
        n_assets = len(assets)
        max_w = np.asarray(self.config.max_weights_vector, dtype=np.float64)
        cost_rate = float(cost_bps) * 1e-4

        sp_idx = assets.index("^GSPC")
        ief_idx = assets.index("IEF")
        tlt_idx = assets.index("TLT")
        shy_idx = assets.index("SHY")
        tech_indices = [assets.index(s) for s in self.config.single_equities]

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        mask = (self._daily_dates >= start_ts) & (self._daily_dates <= end_ts)
        indices = np.where(mask)[0]
        if len(indices) < 2:
            raise ValueError(f"Insufficient trading days between {start_date} and {end_date}")

        cap = float(max(initial_capital, 1.0))
        rl_val = cap
        rl_peak = cap
        sp_val = cap
        b60_val = cap
        ew_val = cap

        current_w = np.zeros(n_assets, dtype=np.float64)
        b60_w = np.zeros(n_assets, dtype=np.float64)
        b60_w[sp_idx] = 0.60
        b60_w[ief_idx] = 0.40
        ew_w = np.ones(n_assets, dtype=np.float64) / n_assets

        total_fees_usd = 0.0
        total_trade_events = 0

        daily_logs: List[Dict[str, Any]] = []
        daily_rets_list: List[float] = []
        rf_rets_list: List[float] = []

        for step_num, global_idx in enumerate(indices):
            dt_str = str(self._daily_dates[global_idx].date())
            # Use causal state at (global_idx - 1) to decide weights active during day global_idx
            sig_idx = max(0, global_idx - 1)
            feat_vec = self._daily_features[sig_idx]
            prior_vec = self._daily_priors[sig_idx]
            macro_row = self._daily_macro_df.iloc[sig_idx]
            raw_sig = self._daily_raw_sig[sig_idx]
            asset_rets = self._daily_returns[global_idx]

            cur_dd = (rl_val / max(rl_peak, 1e-12)) - 1.0
            obs = np.concatenate(
                [
                    feat_vec,
                    (current_w if step_num > 0 else ew_w).astype(np.float32),
                    np.array([cur_dd], dtype=np.float32),
                ],
                axis=0,
            ).astype(np.float32)

            obs_t = torch.from_numpy(obs).unsqueeze(0)
            residuals = []
            with torch.no_grad():
                for net in self._nets:
                    mean, _, _ = net(obs_t)
                    residuals.append(mean.squeeze(0).numpy().astype(np.float64))
            avg_res = np.mean(np.vstack(residuals), axis=0)
            combined_logits = prior_vec + 0.35 * avg_res
            raw_target_w = project_capped_simplex(
                combined_logits, max_w, temperature=1.05, is_probabilities=False
            )

            is_rebalance_day = (step_num == 0) or (step_num % max(rebalance_every_n_days, 1) == 0)
            trades_executed: List[Dict[str, Any]] = []
            fee_usd = 0.0
            one_way_to = 0.0
            action_type = "HOLD"

            pre_day_val = rl_val

            if step_num == 0:
                target_w = raw_target_w.copy()
                one_way_to = 0.5
                fee_usd = rl_val * cost_rate * 1.0
                rl_val -= fee_usd
                total_fees_usd += fee_usd
                total_trade_events += 1
                action_type = "INITIAL_DEPLOY"
                for i, sym in enumerate(assets):
                    if target_w[i] >= 0.01:
                        trades_executed.append(
                            {
                                "symbol": sym,
                                "side": "BUY",
                                "delta_weight_pct": round(float(target_w[i] * 100.0), 2),
                                "trade_usd": round(float(target_w[i] * rl_val), 2),
                            }
                        )
            elif is_rebalance_day:
                smoothed = 0.25 * raw_target_w + 0.75 * current_w
                candidate_w = project_capped_simplex(smoothed, max_w, is_probabilities=True)
                l1_diff = float(np.sum(np.abs(candidate_w - current_w)))
                if l1_diff >= 0.03:
                    target_w = candidate_w
                    one_way_to = 0.5 * l1_diff
                    fee_usd = rl_val * cost_rate * l1_diff
                    rl_val -= fee_usd
                    total_fees_usd += fee_usd
                    total_trade_events += 1

                    old_def = current_w[ief_idx] + current_w[tlt_idx] + current_w[shy_idx]
                    new_def = target_w[ief_idx] + target_w[tlt_idx] + target_w[shy_idx]
                    action_type = "DEFENSIVE_SHIFT" if (new_def - old_def) > 0.04 else "REBALANCE"

                    deltas = target_w - current_w
                    order_idx = np.argsort(-np.abs(deltas))
                    for i in order_idx:
                        dw = float(deltas[i])
                        if abs(dw) >= 0.008:
                            trades_executed.append(
                                {
                                    "symbol": assets[i],
                                    "side": "BUY" if dw > 0 else "SELL",
                                    "delta_weight_pct": round(dw * 100.0, 2),
                                    "trade_usd": round(dw * rl_val, 2),
                                }
                            )
                else:
                    target_w = current_w.copy()
            else:
                target_w = current_w.copy()

            # Realize day global_idx market return on target_w
            gross_ret = float(np.dot(target_w, asset_rets))
            rl_val = rl_val * (1.0 + gross_ret)
            rl_peak = max(rl_peak, rl_val)
            daily_pnl_usd = rl_val - pre_day_val
            daily_ret_pct = ((rl_val / max(pre_day_val, 1e-9)) - 1.0) * 100.0

            daily_rets_list.append(daily_ret_pct / 100.0)
            rf_rets_list.append(float(asset_rets[shy_idx]))

            sp_val *= 1.0 + float(asset_rets[sp_idx])
            b60_val *= 1.0 + float(np.dot(b60_w, asset_rets))
            ew_val *= 1.0 + float(np.dot(ew_w, asset_rets))

            grown = target_w * (1.0 + asset_rets)
            g_sum = float(np.sum(grown))
            current_w = grown / g_sum if g_sum > 1e-12 else target_w.copy()

            vix_val = float(macro_row["vix"])
            tnx_val = float(macro_row["tnx_10y"])
            cpi_val = float(macro_row["cpi_yoy"])
            sp_gap_pct = float(macro_row["sp_sma126_gap"]) * 100.0

            tech_w_pct = float(sum(current_w[i] for i in tech_indices) * 100.0)
            sp_w_pct = float(current_w[sp_idx] * 100.0)
            bond_w_pct = float((current_w[ief_idx] + current_w[tlt_idx]) * 100.0)
            cash_w_pct = float(current_w[shy_idx] * 100.0)

            eq_rank = [(assets[i], float(raw_sig[i, 1] * 100.0), float(current_w[i] * 100.0)) for i in tech_indices]
            eq_rank.sort(key=lambda x: x[2], reverse=True)
            top1, top2 = eq_rank[0], eq_rank[1]

            if cash_w_pct + bond_w_pct >= 45.0:
                regime_tag = "Defensive Volatility / Rate Shield"
                reason_txt = (
                    f"VIX {vix_val:.1f} · S&P vs SMA126 {sp_gap_pct:+.1f}% · 10Y {tnx_val:.2f}% -> "
                    f"Protective posture ({bond_w_pct + cash_w_pct:.1f}% Treasury/SHY)"
                )
            elif tech_w_pct >= 52.0:
                regime_tag = "AI & Tech Momentum Overweight"
                reason_txt = (
                    f"VIX {vix_val:.1f} · S&P vs SMA126 {sp_gap_pct:+.1f}% -> "
                    f"Overweight {top1[0]} ({top1[2]:.1f}%) & {top2[0]} ({top2[2]:.1f}%)"
                )
            else:
                regime_tag = "Balanced Core Equity Expansion"
                reason_txt = (
                    f"VIX {vix_val:.1f} · 10Y {tnx_val:.2f}% · CPI {cpi_val:.1f}% -> "
                    f"Core ^GSPC ({sp_w_pct:.1f}%) + Tech ({tech_w_pct:.1f}%)"
                )

            holdings_usd = {
                sym: round(float(current_w[i] * rl_val), 2) for i, sym in enumerate(assets)
            }
            weights_pct = {
                sym: round(float(current_w[i] * 100.0), 2) for i, sym in enumerate(assets)
            }

            if trades_executed:
                top_trades_str = " · ".join(
                    f"{t['side']} {t['symbol']} ${abs(t['trade_usd']):.2f} ({t['delta_weight_pct']:+.1f}%)"
                    for t in trades_executed[:3]
                )
            else:
                top_trades_str = "HOLD (No rebalance trade · $0.00 fee)"

            daily_logs.append(
                {
                    "day_num": step_num + 1,
                    "date": dt_str,
                    "action_type": action_type,
                    "regime": regime_tag,
                    "reason": reason_txt,
                    "rl_usd": round(rl_val, 2),
                    "sp500_usd": round(sp_val, 2),
                    "b60_40_usd": round(b60_val, 2),
                    "ew_usd": round(ew_val, 2),
                    "daily_pnl_usd": round(daily_pnl_usd, 2),
                    "daily_ret_pct": round(daily_ret_pct, 2),
                    "cum_pnl_usd": round(rl_val - cap, 2),
                    "cum_ret_pct": round(((rl_val / cap) - 1.0) * 100.0, 2),
                    "drawdown_pct": round(((rl_val / max(rl_peak, 1e-12)) - 1.0) * 100.0, 2),
                    "fee_usd": round(fee_usd, 2),
                    "one_way_turnover_pct": round(one_way_to * 100.0, 2),
                    "w_tech_pct": round(tech_w_pct, 1),
                    "w_sp_pct": round(sp_w_pct, 1),
                    "w_bond_pct": round(bond_w_pct, 1),
                    "w_cash_pct": round(cash_w_pct, 1),
                    "vix": round(vix_val, 2),
                    "tnx_10y": round(tnx_val, 2),
                    "cpi_yoy": round(cpi_val, 2),
                    "trades_summary": top_trades_str,
                    "trades": trades_executed,
                    "holdings_usd": holdings_usd,
                    "weights_pct": weights_pct,
                }
            )

        rets_arr = np.asarray(daily_rets_list, dtype=np.float64)
        rf_arr = np.asarray(rf_rets_list, dtype=np.float64)
        excess = rets_arr - rf_arr
        n_days = len(daily_logs)
        years = max(n_days / 252.0, 1e-6)

        rl_tot_ret_pct = ((rl_val / cap) - 1.0) * 100.0
        rl_cagr_pct = (((rl_val / cap) ** (1.0 / years)) - 1.0) * 100.0
        ann_vol = float(np.std(excess, ddof=1) * np.sqrt(252.0)) if n_days > 1 else 1e-6
        ann_excess = float(np.mean(excess) * 252.0)
        sharpe = ann_excess / max(ann_vol, 1e-6)
        downside = np.minimum(0.0, excess)
        down_vol = float(np.sqrt(np.mean(downside ** 2) * 252.0))
        sortino = ann_excess / max(down_vol, 1e-6)
        max_dd_pct = float(min(row["drawdown_pct"] for row in daily_logs))
        win_days = int(sum(1 for r in daily_logs if r["daily_pnl_usd"] > 0))

        return {
            "available": True,
            "params": {
                "initial_capital_usd": round(cap, 2),
                "start_date": daily_logs[0]["date"],
                "end_date": daily_logs[-1]["date"],
                "trading_days": n_days,
                "rebalance_every_n_days": rebalance_every_n_days,
                "cost_bps": cost_bps,
            },
            "summary": {
                "initial_capital_usd": round(cap, 2),
                "final_rl_usd": round(rl_val, 2),
                "net_profit_usd": round(rl_val - cap, 2),
                "total_return_pct": round(rl_tot_ret_pct, 2),
                "cagr_pct": round(rl_cagr_pct, 2),
                "sharpe": round(sharpe, 3),
                "sortino": round(sortino, 3),
                "max_drawdown_pct": round(max_dd_pct, 2),
                "win_days": win_days,
                "win_rate_pct": round((win_days / max(n_days, 1)) * 100.0, 1),
                "rebalance_events": total_trade_events,
                "total_fees_usd": round(total_fees_usd, 2),
                "final_sp500_usd": round(sp_val, 2),
                "sp500_return_pct": round(((sp_val / cap) - 1.0) * 100.0, 2),
                "final_b60_40_usd": round(b60_val, 2),
                "b60_40_return_pct": round(((b60_val / cap) - 1.0) * 100.0, 2),
                "final_ew_usd": round(ew_val, 2),
                "ew_return_pct": round(((ew_val / cap) - 1.0) * 100.0, 2),
                "alpha_vs_sp500_usd": round(rl_val - sp_val, 2),
                "alpha_vs_60_40_usd": round(rl_val - b60_val, 2),
            },
            "daily_logs": daily_logs,
        }
