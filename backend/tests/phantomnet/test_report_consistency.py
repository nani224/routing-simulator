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

    leakage_file = REPO_ROOT / "evidence" / "ml" / "leakage.json"
    assert leakage_file.exists(), "evidence/ml/leakage.json must exist"

    ablation_file = REPO_ROOT / "evidence" / "ml" / "ablation.json"
    assert ablation_file.exists(), "evidence/ml/ablation.json must exist"

    pareto_file = REPO_ROOT / "evidence" / "ml" / "pareto.json"
    assert pareto_file.exists(), "evidence/ml/pareto.json must exist"

    fps_file = REPO_ROOT / "evidence" / "ui" / "fps.json"
    assert fps_file.exists(), "evidence/ui/fps.json must exist"

    with open(leakage_file, encoding="utf-8") as f:
        leakage_data = json.load(f)

    with open(ablation_file, encoding="utf-8") as f:
        ablation_data = json.load(f)

    with open(pareto_file, encoding="utf-8") as f:
        pareto_data = json.load(f)

    with open(fps_file, encoding="utf-8") as f:
        fps_data = json.load(f)

    report_text = report_file.read_text(encoding="utf-8")

    # 1. Verify all Gate B leakage ablation metrics appear verbatim in REPORT.md
    for cond_name, cond_info in leakage_data["ablations"].items():
        auc_str = f"{cond_info['test_auc']:.4f}"
        ci_str = f"[{cond_info['ci_95'][0]:.4f}, {cond_info['ci_95'][1]:.4f}]"
        assert cond_name in report_text, f"Leakage condition {cond_name} missing"
        assert auc_str in report_text, f"Leakage AUC {auc_str} for {cond_name} missing"
        assert ci_str in report_text, f"Leakage CI {ci_str} for {cond_name} missing"

    # 2. Verify all Gate C & Gate E ablation metrics appear verbatim in REPORT.md
    results = ablation_data["results"]
    for regime, reg_data in results.items():
        s_auc = f"{reg_data['static_censor']['auc']:.4f}"
        s_ci = (
            f"[{reg_data['static_censor']['ci_95'][0]:.4f}, "
            f"{reg_data['static_censor']['ci_95'][1]:.4f}]"
        )
        s_tpr = f"{reg_data['static_censor']['tpr_at_1pct_fpr']:.4f}"

        r_auc = f"{reg_data['retrained_censor']['auc']:.4f}"
        r_ci = (
            f"[{reg_data['retrained_censor']['ci_95'][0]:.4f}, "
            f"{reg_data['retrained_censor']['ci_95'][1]:.4f}]"
        )
        r_tpr = f"{reg_data['retrained_censor']['tpr_at_1pct_fpr']:.4f}"

        bw_pct = f"{reg_data['bandwidth_overhead']['percentage']:.2f}%"
        lat_ms = f"{reg_data['latency_penalty_ms']['mean']:.3f} ms"

        assert regime in report_text, f"Regime {regime} missing from REPORT.md"
        assert s_auc in report_text, f"Static AUC {s_auc} for {regime} missing from REPORT.md"
        assert s_ci in report_text, f"Static CI {s_ci} for {regime} missing from REPORT.md"
        assert s_tpr in report_text, f"Static TPR {s_tpr} for {regime} missing from REPORT.md"

        assert r_auc in report_text, f"Retrained AUC {r_auc} for {regime} missing from REPORT.md"
        assert r_ci in report_text, f"Retrained CI {r_ci} for {regime} missing from REPORT.md"
        assert r_tpr in report_text, f"Retrained TPR {r_tpr} for {regime} missing from REPORT.md"

        assert bw_pct in report_text, f"Bandwidth {bw_pct} for {regime} missing from REPORT.md"
        assert lat_ms in report_text, f"Latency {lat_ms} for {regime} missing from REPORT.md"

    # 3. Verify all Pareto frontier entries appear verbatim in REPORT.md
    for entry in pareto_data:
        bw_pct = f"{entry['bandwidth_overhead_pct']:.2f}%"
        lat_ms = f"{entry['latency_cost_ms']:.3f} ms"
        assert bw_pct in report_text, f"Pareto bandwidth overhead {bw_pct} missing from REPORT.md"
        assert lat_ms in report_text, f"Pareto latency {lat_ms} missing from REPORT.md"

    # 4. Verify FPS trace metrics appear verbatim in REPORT.md
    median_fps = str(fps_data["median_fps"])
    median_frame_time = str(fps_data["median_frame_time_ms"])
    assert f"{median_fps} FPS" in report_text, f"Median FPS {median_fps} missing from REPORT.md"
    assert median_frame_time in report_text, (
        f"Median frame time {median_frame_time} missing from REPORT.md"
    )

    # 5. Verify Dataset split numbers appear verbatim in REPORT.md
    site_split = ablation_data["site_split"]
    assert f"{site_split['train']} Train" in report_text
    assert f"{site_split['val']} Val" in report_text
    assert f"{site_split['test']} Test" in report_text
