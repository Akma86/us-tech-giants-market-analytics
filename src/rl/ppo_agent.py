"""PyTorch Proximal Policy Optimization (PPO) Actor-Critic with Smooth Dual-Momentum Macro Prior and Multi-Seed Ensemble."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from src.rl.config import RLConfig
from src.rl.env import MacroPortfolioEnv, project_capped_simplex
from src.rl.features import MacroPortfolioDataset

torch.set_num_threads(1)


def _orthogonal_init(module: nn.Module, gain: float = 1.0) -> None:
    if isinstance(module, nn.Linear):
        nn.init.orthogonal_(module.weight, gain=gain)
        if module.bias is not None:
            nn.init.constant_(module.bias, 0.0)


def precompute_macro_structural_logits_matrix(
    dataset: MacroPortfolioDataset, config: RLConfig
) -> np.ndarray:
    """Computes (T, N) causal dual-momentum (excess vs SHY + cross-sectional rank) and smooth macro regime prior logits."""
    assets = list(config.assets)
    n = len(assets)
    t_steps = len(dataset.dates)

    shy_idx = assets.index("SHY")
    ief_idx = assets.index("IEF")
    tlt_idx = assets.index("TLT")
    sp_idx = assets.index("^GSPC")
    single_eq_indices = [i for i, sym in enumerate(assets) if sym in config.single_equities]

    m_df = dataset.raw_macro_table
    vix = m_df["vix"].to_numpy(dtype=np.float64)
    cpi = m_df["cpi_yoy"].to_numpy(dtype=np.float64)
    tnx_chg = m_df["tnx_chg_63d"].to_numpy(dtype=np.float64)
    sp_corr = m_df["sp_bond_corr_60d"].to_numpy(dtype=np.float64)
    sp_trend = m_df["sp_sma126_gap"].to_numpy(dtype=np.float64)
    ief_trend = m_df["ief_sma126_gap"].to_numpy(dtype=np.float64)
    tlt_trend = m_df["tlt_sma126_gap"].to_numpy(dtype=np.float64)

    raw_sig = dataset.raw_asset_signals
    logits = np.full((t_steps, n), -2.5, dtype=np.float64)

    for t in range(t_steps):
        ret21 = raw_sig[t, :, 0]
        ret63 = raw_sig[t, :, 1]
        ret126 = raw_sig[t, :, 2]
        vol21 = np.maximum(raw_sig[t, :, 3], 0.08)
        sma_gap = raw_sig[t, :, 4]

        rf63 = ret63[shy_idx]
        rf126 = ret126[shy_idx]

        # True 2022-style stagflation / rate shock: Headline CPI > 4.8% with rising yields & negative equity trend
        inflation_rate_shock = (cpi[t] > 4.8 and (tnx_chg[t] > 0.12 or sp_trend[t] < -0.015)) or (
            cpi[t] > 5.5 and ief_trend[t] < -0.005
        )
        acute_vix_panic = cpi[t] > 4.5 and vix[t] > 30.0 and sp_trend[t] < -0.05

        # Medium-term risk-adjusted momentum combined with dip-buying mean reversion (-0.25 * ret21) & inverse-vol quality
        med_mom = (0.45 * (ret63 - rf63) + 0.55 * (ret126 - rf126) - 0.28 * ret21) / vol21
        inv_vol_bonus = 0.38 / vol21

        for i in single_eq_indices:
            if inflation_rate_shock and sp_trend[t] < -0.01:
                logits[t, i] = -2.20 + 0.80 * med_mom[i]
            elif acute_vix_panic:
                logits[t, i] = -1.40 + 0.80 * med_mom[i]
            else:
                logits[t, i] = 1.55 + 0.70 * med_mom[i] + 1.10 * sma_gap[i] + inv_vol_bonus[i]

        # Broad S&P 500 index sleeve
        if inflation_rate_shock and sp_trend[t] < -0.01:
            logits[t, sp_idx] = -1.50
        elif acute_vix_panic:
            logits[t, sp_idx] = -0.80
        else:
            logits[t, sp_idx] = 1.35 + 0.70 * med_mom[sp_idx] + 1.30 * sp_trend[t]

        # Treasury duration sleeves (IEF 7-10Y and TLT 20+Y)
        if inflation_rate_shock or tnx_chg[t] > 0.35:
            logits[t, ief_idx] = -2.50
            logits[t, tlt_idx] = -3.60
        elif acute_vix_panic and cpi[t] <= 4.5:
            logits[t, ief_idx] = 1.85
            logits[t, tlt_idx] = 1.10
        else:
            logits[t, ief_idx] = (-0.35 + 2.5 * ief_trend[t]) if ief_trend[t] > 0.0 else -1.45
            logits[t, tlt_idx] = (-0.85 + 2.0 * tlt_trend[t]) if tlt_trend[t] > 0.005 else -2.40

        # SHY 1-3Y Cash Defense sleeve: primary shelter during 2022 inflation/rate shock
        if inflation_rate_shock and sp_trend[t] < -0.005:
            logits[t, shy_idx] = 3.75
        elif acute_vix_panic:
            logits[t, shy_idx] = 2.25
        else:
            logits[t, shy_idx] = -1.85

    return logits


class ActorCriticNet(nn.Module):
    """Residual Actor-Critic architecture for continuous portfolio logit adjustments."""

    def __init__(self, obs_dim: int, action_dim: int, hidden_dim: int = 96):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
        )
        self.actor_mean = nn.Linear(hidden_dim, action_dim)
        self.actor_log_std = nn.Parameter(torch.full((action_dim,), -1.15))
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

        self.apply(lambda m: _orthogonal_init(m, gain=np.sqrt(2)))
        _orthogonal_init(self.actor_mean, gain=0.03)
        _orthogonal_init(self.critic[-1], gain=1.0)

    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.shared(obs)
        mean = torch.tanh(self.actor_mean(h)) * 0.85
        std = torch.exp(torch.clamp(self.actor_log_std, -2.4, -0.4)).expand_as(mean)
        val = self.critic(h).squeeze(-1)
        return mean, std, val


class PPOAllocationAgent:
    """Single-seed PPO Actor-Critic agent with validation Sortino checkpoint selection."""

    def __init__(self, obs_dim: int, action_dim: int, config: RLConfig, seed: int = 42):
        self.config = config
        self.seed = seed
        self.has_cuda = torch.cuda.is_available()
        self.device = torch.device("cpu")
        self.max_w = np.asarray(self.config.max_weights_vector, dtype=np.float64)

        torch.manual_seed(seed)
        np.random.seed(seed)

        self.net = ActorCriticNet(obs_dim, action_dim, hidden_dim=96).to(self.device)
        self.optimizer = optim.AdamW(self.net.parameters(), lr=config.lr, weight_decay=1e-4)
        self.best_state_dict: Optional[Dict[str, torch.Tensor]] = None
        self.best_val_score: float = -1e9
        self.training_curve: List[Dict[str, float]] = []

    def act_weights_fast(
        self,
        obs: np.ndarray,
        prior_logits: np.ndarray,
        prev_weights: np.ndarray,
        deterministic: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, float, float]:
        obs_t = torch.from_numpy(obs).unsqueeze(0)
        with torch.no_grad():
            mean, std, val = self.net(obs_t)
            if deterministic:
                raw_act = mean
                log_prob = 0.0
            else:
                dist = torch.distributions.Normal(mean, std)
                raw_act = dist.sample()
                log_prob = float(dist.log_prob(raw_act).sum(dim=-1).item())

        rl_residual = raw_act.squeeze(0).numpy().astype(np.float64)
        combined_logits = prior_logits + 0.35 * rl_residual

        target_raw_w = project_capped_simplex(
            combined_logits, self.max_w, temperature=1.05, is_probabilities=False
        )
        smoothed_w = 0.25 * target_raw_w + 0.75 * prev_weights
        final_w = project_capped_simplex(smoothed_w, self.max_w, is_probabilities=True)
        if float(np.sum(np.abs(final_w - prev_weights))) < 0.03:
            final_w = prev_weights.copy()

        return (
            final_w,
            rl_residual.astype(np.float32),
            log_prob,
            float(val.item()),
        )

    def evaluate_on_dataset(
        self,
        dataset: MacroPortfolioDataset,
        prior_matrix: Optional[np.ndarray] = None,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        priors = (
            prior_matrix
            if prior_matrix is not None
            else precompute_macro_structural_logits_matrix(dataset, self.config)
        )
        env = MacroPortfolioEnv(dataset=dataset, config=self.config)
        obs, _ = env.reset(seed=self.seed)
        terminated = False
        while not terminated:
            idx = env.step_idx
            w, _, _, _ = self.act_weights_fast(
                obs, priors[idx], env.current_weights, deterministic=True
            )
            obs, _, terminated, _, _ = env.step(w, is_direct_weights=True)

        rets = np.array([row["net_return"] for row in env.ledger], dtype=np.float64)
        rf_rets = np.array([row["rf_return"] for row in env.ledger], dtype=np.float64)
        excess = rets - rf_rets
        ann_factor = 252.0 / self.config.rebalance_freq_days
        downside = np.minimum(0.0, excess)
        down_vol = float(np.sqrt(np.mean(downside ** 2) * ann_factor)) + 1e-6
        ann_excess = float(np.mean(excess) * ann_factor)
        sortino = ann_excess / down_vol
        max_dd = float(np.min([row["drawdown"] for row in env.ledger]))
        score = sortino + 0.65 * max_dd
        return score, env.ledger

    def train(
        self,
        train_dataset: MacroPortfolioDataset,
        val_dataset: MacroPortfolioDataset,
    ) -> Dict[str, Any]:
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        env = MacroPortfolioEnv(dataset=train_dataset, config=self.config)

        train_priors = precompute_macro_structural_logits_matrix(train_dataset, self.config)
        val_priors = precompute_macro_structural_logits_matrix(val_dataset, self.config)

        init_score, _ = self.evaluate_on_dataset(val_dataset, val_priors)
        self.best_val_score = init_score
        self.best_state_dict = {
            k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()
        }

        total_eps = 24
        for ep in range(1, total_eps + 1):
            obs, _ = env.reset(seed=self.seed + ep)
            obs_buf: List[np.ndarray] = []
            act_buf: List[np.ndarray] = []
            logp_buf: List[float] = []
            rew_buf: List[float] = []
            val_buf: List[float] = []

            terminated = False
            while not terminated:
                idx = env.step_idx
                w, rl_act, logp, val = self.act_weights_fast(
                    obs, train_priors[idx], env.current_weights, deterministic=False
                )
                next_obs, reward, terminated, _, _ = env.step(w, is_direct_weights=True)
                obs_buf.append(obs)
                act_buf.append(rl_act)
                logp_buf.append(logp)
                rew_buf.append(reward)
                val_buf.append(val)
                obs = next_obs

            T = len(rew_buf)
            advantages = np.zeros(T, dtype=np.float32)
            returns = np.zeros(T, dtype=np.float32)
            gae = 0.0
            for t in reversed(range(T)):
                next_val = 0.0 if t == T - 1 else val_buf[t + 1]
                delta = rew_buf[t] + self.config.gamma * next_val - val_buf[t]
                gae = delta + self.config.gamma * self.config.gae_lambda * gae
                advantages[t] = float(gae)
                returns[t] = advantages[t] + val_buf[t]

            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

            obs_t = torch.from_numpy(np.asarray(obs_buf, dtype=np.float32))
            act_t = torch.from_numpy(np.asarray(act_buf, dtype=np.float32))
            old_logp_t = torch.as_tensor(logp_buf, dtype=torch.float32)
            adv_t = torch.from_numpy(advantages)
            ret_t = torch.from_numpy(returns)

            for _ in range(3):
                mean, std, values = self.net(obs_t)
                dist = torch.distributions.Normal(mean, std)
                new_logp = dist.log_prob(act_t).sum(dim=-1)
                entropy = dist.entropy().sum(dim=-1).mean()

                ratio = torch.exp(new_logp - old_logp_t)
                surr1 = ratio * adv_t
                surr2 = torch.clamp(ratio, 1.0 - self.config.clip_eps, 1.0 + self.config.clip_eps) * adv_t
                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = nn.functional.mse_loss(values, ret_t)

                loss = (
                    policy_loss
                    + self.config.value_coef * value_loss
                    - self.config.entropy_coef * entropy
                )
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), self.config.max_grad_norm)
                self.optimizer.step()

            if ep % 4 == 0 or ep == 1 or ep == total_eps:
                val_score, val_ledger = self.evaluate_on_dataset(val_dataset, val_priors)
                train_nav = float(env.nav)
                val_nav = float(val_ledger[-1]["nav"]) if val_ledger else 1.0
                self.training_curve.append(
                    {
                        "episode": ep,
                        "train_terminal_nav": round(train_nav, 4),
                        "val_terminal_nav": round(val_nav, 4),
                        "val_score": round(val_score, 4),
                    }
                )
                if val_score > self.best_val_score:
                    self.best_val_score = val_score
                    self.best_state_dict = {
                        k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()
                    }

        if self.best_state_dict is not None:
            self.net.load_state_dict(self.best_state_dict)

        return {
            "seed": self.seed,
            "best_val_score": round(float(self.best_val_score), 4),
            "device": "cuda+cpu" if self.has_cuda else "cpu",
            "training_curve": self.training_curve,
        }


class PPOMultiSeedEnsemble:
    """Trains multiple PPO seeds and ensembles their portfolio allocations."""

    def __init__(self, obs_dim: int, action_dim: int, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()
        self.agents = [
            PPOAllocationAgent(obs_dim, action_dim, self.config, seed=s)
            for s in self.config.seeds
        ]

    def train_all(
        self,
        train_dataset: MacroPortfolioDataset,
        val_dataset: MacroPortfolioDataset,
    ) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for agent in self.agents:
            summary = agent.train(train_dataset, val_dataset)
            summaries.append(summary)
        return summaries

    def rollout_ensemble(
        self, dataset: MacroPortfolioDataset
    ) -> Tuple[List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
        priors = precompute_macro_structural_logits_matrix(dataset, self.config)
        env = MacroPortfolioEnv(dataset=dataset, config=self.config)
        obs, _ = env.reset(seed=0)
        max_w = np.asarray(self.config.max_weights_vector, dtype=np.float64)

        terminated = False
        while not terminated:
            idx = env.step_idx
            member_weights = [
                ag.act_weights_fast(obs, priors[idx], env.current_weights, deterministic=True)[0]
                for ag in self.agents
            ]
            avg_w = np.mean(np.vstack(member_weights), axis=0)
            proj_w = project_capped_simplex(avg_w, max_w, is_probabilities=True)
            obs, _, terminated, _, _ = env.step(proj_w, is_direct_weights=True)

        seed_ledgers = [ag.evaluate_on_dataset(dataset, priors)[1] for ag in self.agents]
        return env.ledger, seed_ledgers

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        out_path = directory / "ppo_macro_ensemble.pt"
        payload = {
            "seeds": list(self.config.seeds),
            "assets": list(self.config.assets),
            "state_dicts": [ag.net.state_dict() for ag in self.agents],
            "best_val_scores": [ag.best_val_score for ag in self.agents],
        }
        torch.save(payload, out_path)
        return out_path
