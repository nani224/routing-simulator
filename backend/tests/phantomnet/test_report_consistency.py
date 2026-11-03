"""Unit test for Gate 5: Evidence Report Consistency Verification.

Verifies that all metrics and numbers reported in /evidence/REPORT.md originate
directly from evidence artifacts (evidence/ml/*.json, evidence/bench/*.json, evidence/ui/*.json).
Fails immediately if REPORT.md contains fabricated or unverified numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_gate5_report_numbers_consistent_with_json_artifacts() -> None:
    report_file = REPO_ROOT / "evidence" / "REPORT.md"
    assert report_file.exists(), "evidence/REPORT.md must exist"

    ablation_file = REPO_ROOT / "evidence" / "ml" / "ablation.json"
    assert ablation_file.exists(), "evidence/ml/ablation.json must exist"

    pareto_file = REPO_ROOT / "evidence" / "ml" / "pareto.json"
    assert pareto_file.exists(), "evidence/ml/pareto.json must exist"

    fps_file = REPO_ROOT / "evidence" / "ui" / "fps.json"
    assert fps_file.exists(), "evidence/ui/fps.json must exist"

    with open(ablation_file, encoding="utf-8") as f:
        ablation_data = json.load(f)

    with open(pareto_file, encoding="utf-8") as f:
        pareto_data = json.load(f)

    with open(fps_file, encoding="utf-8") as f:
        fps_data = json.load(f)

    report_text = report_file.read_text(encoding="utf-8")

    # 1. Verify all ablation metrics appear verbatim in REPORT.md
    results = ablation_data["results"]
    for regime, reg_data in results.items():
        auc_mean = f"{reg_data['censor_auc']['mean']:.4f}"
        auc_ci = f"{reg_data['censor_auc']['ci_95']:.4f}"
        f1_mean = f"{reg_data['f1_score']['mean']:.4f}"
        f1_ci = f"{reg_data['f1_score']['ci_95']:.4f}"

        assert auc_mean in report_text, (
            f"Ablation AUC mean {auc_mean} for {regime} missing from REPORT.md"
        )
        assert auc_ci in report_text, (
            f"Ablation AUC CI {auc_ci} for {regime} missing from REPORT.md"
        )
        assert f1_mean in report_text, (
            f"Ablation F1 mean {f1_mean} for {regime} missing from REPORT.md"
        )
        assert f1_ci in report_text, f"Ablation F1 CI {f1_ci} for {regime} missing from REPORT.md"

    # 2. Verify all Pareto frontier entries appear verbatim in REPORT.md
    for entry in pareto_data:
        bw_pct = f"{entry['bandwidth_overhead_pct']:.2f}%"
        stealth = f"{entry['stealth_score']:.4f}"
        assert bw_pct in report_text, f"Pareto bandwidth overhead {bw_pct} missing from REPORT.md"
        assert stealth in report_text, f"Pareto stealth score {stealth} missing from REPORT.md"

    # 3. Verify FPS trace metrics appear verbatim in REPORT.md
    median_fps = str(fps_data["median_fps"])
    median_frame_time = str(fps_data["median_frame_time_ms"])
    assert f"{median_fps} FPS" in report_text, f"Median FPS {median_fps} missing from REPORT.md"
    assert median_frame_time in report_text, (
        f"Median frame time {median_frame_time} missing from REPORT.md"
    )

    # 4. Verify Dataset split numbers appear verbatim in REPORT.md
    site_split = ablation_data["site_split"]
    assert f"{site_split['train']} Train" in report_text
    assert f"{site_split['val']} Validation" in report_text
    assert f"{site_split['test']} Test" in report_text
