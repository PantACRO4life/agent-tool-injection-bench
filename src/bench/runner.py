"""Run the experiment grid: model x defense x scenario x run."""
from __future__ import annotations

import csv
import json
from typing import Any, Callable, Dict, List, Optional

from .agent import run_agent
from .backends import make_backend
from .defenses import make_defense
from .scoring import score_run

RESULT_FIELDS = [
    "model", "defense", "scenario", "scenario_type", "goal", "placement", "format",
    "run", "seed", "steps", "attack_success", "attack_attempted", "task_success",
    "false_refusal", "blocked_calls", "calls", "final_answer", "error",
]

# Rough, assumed USD per million tokens (input, output). Check current pricing.
PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (5.0, 25.0)}
DEFAULT_PRICE = (3.0, 15.0)
EST_IN_TOKENS_PER_RUN = 3600   # system prompt + task + resource, re-sent each step
EST_OUT_TOKENS_PER_RUN = 250
EST_MONITOR_IN_PER_CALL = 220
EST_MONITOR_CALLS_PER_RUN = 2


def count_runs(models, defenses, scenarios, runs) -> int:
    return len(models) * len(defenses) * len(scenarios) * runs


def estimate_cost(model: str, defenses: List[str], n_scenarios: int, runs: int,
                  monitor_model: Optional[str] = None) -> Dict[str, float]:
    """Very rough token and USD estimate for one agent model on the API."""
    def price(m: str):
        return next((p for k, p in PRICES.items() if k in m.lower()), DEFAULT_PRICE)

    agent_runs = len(defenses) * n_scenarios * runs
    tin, tout = agent_runs * EST_IN_TOKENS_PER_RUN, agent_runs * EST_OUT_TOKENS_PER_RUN
    usd = tin * price(model)[0] / 1e6 + tout * price(model)[1] / 1e6
    if "monitor" in defenses:
        mruns = n_scenarios * runs
        mcalls = mruns * EST_MONITOR_CALLS_PER_RUN
        min_, mout = mcalls * EST_MONITOR_IN_PER_CALL, mcalls * 5
        mp = price(monitor_model or model)
        usd += min_ * mp[0] / 1e6 + mout * mp[1] / 1e6
        tin, tout = tin + min_, tout + mout
    return {"input_tokens": tin, "output_tokens": tout, "usd": usd}


def run_experiment(backend_kind: str, models: List[str], defenses: List[str], scenarios: List[Any],
                   runs: int, seed: int = 0, monitor_model: Optional[str] = None,
                   max_steps: int = 6, temperature: float = 0.7,
                   ollama_url: str = "http://127.0.0.1:11434",
                   backend_factory: Optional[Callable[..., Any]] = None,
                   progress: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    factory = backend_factory or make_backend
    rows: List[Dict[str, Any]] = []
    for model in models:
        agent = factory(backend_kind, model, ollama_url=ollama_url, temperature=temperature)
        mon_name = monitor_model or ("careful" if backend_kind == "mock" else model)
        monitor = factory(backend_kind, mon_name, ollama_url=ollama_url, temperature=0.0)
        for defense_name in defenses:
            for sc in scenarios:
                for i in range(runs):
                    run_seed = seed + i
                    defense = make_defense(defense_name, sc, monitor)
                    trace = run_agent(agent, sc, defense, seed=run_seed, max_steps=max_steps)
                    score = score_run(sc, trace)
                    inj = sc.injection
                    rows.append({
                        "model": model, "defense": defense_name, "scenario": sc.id,
                        "scenario_type": "attack" if sc.is_attack else "control",
                        "goal": inj.goal if inj else "", "placement": inj.placement if inj else "",
                        "format": inj.format if inj else "",
                        "run": i, "seed": run_seed, "steps": trace.steps,
                        "attack_success": score["attack_success"],
                        "attack_attempted": score["attack_attempted"],
                        "task_success": score["task_success"],
                        "false_refusal": score["false_refusal"],
                        "blocked_calls": sum(1 for c in trace.calls if c.status in ("blocked", "vetoed")),
                        "calls": json.dumps([[c.tool, c.status] for c in trace.calls]),
                        "final_answer": trace.final_answer.replace("\n", " ")[:300],
                        "error": trace.error,
                    })
            if progress:
                progress("done: model=%s defense=%s" % (model, defense_name))
    return rows


def write_results_csv(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in RESULT_FIELDS})
