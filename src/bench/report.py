"""Summary table (rates with Wilson intervals) and the bar chart."""
from __future__ import annotations

import csv
from typing import Any, Dict, List

from .scoring import wilson_interval

SUMMARY_FIELDS = [
    "model", "defense",
    "attack_runs", "attack_successes", "attack_success_rate", "attack_ci_low", "attack_ci_high",
    "attack_attempt_rate",
    "task_success_under_attack_rate",
    "clean_runs", "clean_task_success_rate", "clean_task_ci_low", "clean_task_ci_high",
    "false_refusal_rate", "false_refusal_ci_low", "false_refusal_ci_high",
]


def _rate(k: int, n: int):
    lo, hi = wilson_interval(k, n)
    return (k / n if n else 0.0), lo, hi


def summarize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["model"], r["defense"]), []).append(r)
    out = []
    for (model, defense), rs in groups.items():
        att = [r for r in rs if r["scenario_type"] == "attack"]
        clean = [r for r in rs if r["scenario_type"] == "control"]
        a_k = sum(int(r["attack_success"]) for r in att)
        rate, lo, hi = _rate(a_k, len(att))
        attempt = sum(int(r["attack_attempted"]) for r in att)
        t_att = sum(int(r["task_success"]) for r in att)
        t_cl = sum(int(r["task_success"]) for r in clean)
        fr = sum(int(r["false_refusal"]) for r in clean)
        ct, ctl, cth = _rate(t_cl, len(clean))
        fr_r, fr_lo, fr_hi = _rate(fr, len(clean))
        out.append({
            "model": model, "defense": defense,
            "attack_runs": len(att), "attack_successes": a_k,
            "attack_success_rate": round(rate, 4),
            "attack_ci_low": round(lo, 4), "attack_ci_high": round(hi, 4),
            "attack_attempt_rate": round(_rate(attempt, len(att))[0], 4),
            "task_success_under_attack_rate": round(_rate(t_att, len(att))[0], 4),
            "clean_runs": len(clean), "clean_task_success_rate": round(ct, 4),
            "clean_task_ci_low": round(ctl, 4), "clean_task_ci_high": round(cth, 4),
            "false_refusal_rate": round(fr_r, 4),
            "false_refusal_ci_low": round(fr_lo, 4), "false_refusal_ci_high": round(fr_hi, 4),
        })
    return out


def write_summary_csv(summary: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(summary)


def plot_attack_success(summary: List[Dict[str, Any]], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    defenses: List[str] = []
    models: List[str] = []
    for s in summary:
        if s["defense"] not in defenses:
            defenses.append(s["defense"])
        if s["model"] not in models:
            models.append(s["model"])
    lookup = {(s["model"], s["defense"]): s for s in summary}
    palette = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
    width = 0.8 / max(1, len(models))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for mi, model in enumerate(models):
        xs, vals, lows, highs = [], [], [], []
        for di, d in enumerate(defenses):
            s = lookup.get((model, d))
            if s is None:
                continue
            xs.append(di + (mi - (len(models) - 1) / 2) * width)
            vals.append(s["attack_success_rate"] * 100)
            lows.append((s["attack_success_rate"] - s["attack_ci_low"]) * 100)
            highs.append((s["attack_ci_high"] - s["attack_success_rate"]) * 100)
        ax.bar(xs, vals, width * 0.92, yerr=[lows, highs], capsize=3,
               color=palette[mi % len(palette)], label=model)
        for x, v, hi in zip(xs, vals, highs):
            ax.text(x, v + hi + 1.5, "%.0f" % v, ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(defenses)))
    ax.set_xticklabels(defenses)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Attack success rate (%)")
    ax.set_title("Attack success by defense (bars: 95% Wilson interval)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(title="model", frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
