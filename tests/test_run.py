import csv
import os

import run as cli
from bench.runner import estimate_cost


def test_full_mock_run_writes_csv_and_png(tmp_path):
    out = str(tmp_path / "mock")
    code = cli.main(["--backend", "mock", "--models", "obedient,careful",
                     "--defenses", "none,spotlight,allowlist,monitor", "--runs", "2", "--out", out])
    assert code == 0
    for name in ("results.csv", "summary.csv", "attack_success.png"):
        assert os.path.getsize(os.path.join(out, name)) > 0
    with open(os.path.join(out, "results.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 * 4 * 13 * 2
    with open(os.path.join(out, "summary.csv"), newline="", encoding="utf-8") as f:
        summ = {(r["model"], r["defense"]): r for r in csv.DictReader(f)}
    assert float(summ[("careful", "none")]["attack_success_rate"]) == 0.0
    assert float(summ[("obedient", "none")]["attack_success_rate"]) == 1.0
    assert float(summ[("obedient", "allowlist")]["attack_success_rate"]) < 1.0
    assert float(summ[("obedient", "monitor")]["attack_success_rate"]) < 1.0
    assert float(summ[("careful", "none")]["clean_task_success_rate"]) == 1.0
    assert float(summ[("careful", "monitor")]["false_refusal_rate"]) == 0.0


def test_dry_run_runs_nothing(tmp_path, capsys):
    out = str(tmp_path / "nothing")
    code = cli.main(["--backend", "anthropic", "--models", "claude-haiku-x", "--defenses", "none,monitor",
                     "--runs", "2", "--out", out, "--dry-run"])
    text = capsys.readouterr().out
    assert code == 0 and "Rough API cost" in text and "Dry run only" in text
    assert not os.path.exists(out)


def test_cost_estimate_grows_with_runs():
    a = estimate_cost("claude-sonnet-x", ["none"], 13, 1)
    b = estimate_cost("claude-sonnet-x", ["none"], 13, 4)
    assert b["usd"] > a["usd"] > 0
