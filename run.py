"""Command line entry point.

Example (mock backend, no GPU, no network):
  python run.py --backend mock --models obedient,careful --defenses none,spotlight,allowlist,monitor --runs 3 --out results/mock
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from bench.defenses import DEFENSE_NAMES  # noqa: E402
from bench.report import plot_attack_success, summarize, write_summary_csv  # noqa: E402
from bench.runner import count_runs, estimate_cost, run_experiment, write_results_csv  # noqa: E402
from bench.scenario import load_scenarios  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Indirect prompt injection benchmark for tool-using agents.")
    p.add_argument("--backend", choices=["mock", "ollama", "anthropic"], required=True)
    p.add_argument("--models", required=True, help="comma-separated model names")
    p.add_argument("--defenses", default="none", help="comma-separated: " + ",".join(DEFENSE_NAMES))
    p.add_argument("--runs", type=int, default=3, help="runs per scenario")
    p.add_argument("--out", default="results/latest", help="output folder")
    p.add_argument("--scenarios", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios"))
    p.add_argument("--monitor-model", default=None, help="model for the monitor defense (default: same model; mock: careful)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    defenses = [d.strip() for d in a.defenses.split(",") if d.strip()]
    bad = [d for d in defenses if d not in DEFENSE_NAMES]
    if bad:
        print("unknown defense(s): " + ", ".join(bad))
        return 2
    scenarios = load_scenarios(a.scenarios)
    n_attack = sum(1 for s in scenarios if s.is_attack)
    total = count_runs(models, defenses, scenarios, a.runs)

    print("Plan")
    print("  backend:   %s" % a.backend)
    print("  models:    %s" % ", ".join(models))
    print("  defenses:  %s" % ", ".join(defenses))
    print("  scenarios: %d (%d attack, %d control)" % (len(scenarios), n_attack, len(scenarios) - n_attack))
    print("  runs each: %d" % a.runs)
    print("  agent runs in total: %d" % total)
    print("  output:    %s" % a.out)
    if a.dry_run:
        if a.backend == "anthropic":
            print("Rough API cost (assumed rates, check current pricing):")
            grand = 0.0
            for m in models:
                est = estimate_cost(m, defenses, len(scenarios), a.runs, a.monitor_model)
                grand += est["usd"]
                print("  %s: about %d input and %d output tokens, about $%.2f"
                      % (m, est["input_tokens"], est["output_tokens"], est["usd"]))
            print("  total: about $%.2f" % grand)
        print("Dry run only. Nothing was executed.")
        return 0

    os.makedirs(a.out, exist_ok=True)
    rows = run_experiment(a.backend, models, defenses, scenarios, a.runs, seed=a.seed,
                          monitor_model=a.monitor_model, max_steps=a.max_steps,
                          temperature=a.temperature, ollama_url=a.ollama_url, progress=print)
    summary = summarize(rows)
    write_results_csv(rows, os.path.join(a.out, "results.csv"))
    write_summary_csv(summary, os.path.join(a.out, "summary.csv"))
    plot_attack_success(summary, os.path.join(a.out, "attack_success.png"))

    print("\nmodel / defense: attack success (95% interval), task success clean, false refusals")
    for s in summary:
        print("  %-10s %-10s %5.1f%% (%4.1f-%4.1f)  clean task %5.1f%%  false refusal %5.1f%%" % (
            s["model"], s["defense"], s["attack_success_rate"] * 100, s["attack_ci_low"] * 100,
            s["attack_ci_high"] * 100, s["clean_task_success_rate"] * 100, s["false_refusal_rate"] * 100))
    errors = sum(1 for r in rows if r["error"])
    if errors:
        print("Note: %d runs ended with a backend error (see the error column)." % errors)
    print("Wrote results.csv, summary.csv, attack_success.png to " + a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
