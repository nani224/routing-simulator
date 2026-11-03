"""Gate H Guarding Test: No Unsupported Evasion Claims.

Enforces that any UI, demo, or evidence report text that references evasion,
stealth, or undetectability is strictly conditional on measured results and
cites a verified JSON metric key (e.g. censor_auc, tpr_at_1pct_fpr, stealth_score).
Fails immediately if marketing or aspirational claims appear without citation.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_gate_h_no_unsupported_evasion_claims_in_report() -> None:
    report_file = REPO_ROOT / "evidence" / "REPORT.md"
    assert report_file.exists(), "evidence/REPORT.md must exist"

    text = report_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    banned_keywords = ["evade", "evasion", "undetectable", "stealth"]
    valid_citation_keys = [
        "censor_auc",
        "tpr_at_1pct_fpr",
        "stealth_score",
        "results.learned_policy",
        "results.morphing",
        "paired_comparisons",
        "evidence/ml",
        "evidence/bench",
        "ROOT_CAUSE.md",
    ]

    violations: list[str] = []

    for line_num, line in enumerate(lines, start=1):
        # Ignore comments or markdown image badges
        if line.strip().startswith("<!--") or line.strip().startswith("[!"):
            continue

        lower_line = line.lower()
        for kw in banned_keywords:
            if kw in lower_line:
                # Check if the line or immediate context cites a metric key
                has_citation = any(key.lower() in lower_line for key in valid_citation_keys)
                # Or if it's explicitly stating a negative result / lack of evasion
                is_negative_finding = any(
                    phrase in lower_line
                    for phrase in [
                        "does not",
                        "no evasion",
                        "failed to",
                        "transient",
                        "cannot support",
                        "neither",
                        "unsupported",
                        "arms race",
                        "recovers",
                    ]
                )

                if not (has_citation or is_negative_finding):
                    msg = (
                        f"Line {line_num}: Contains '{kw}' without cited metric "
                        f"key or negative finding qualification: {line.strip()}"
                    )
                    violations.append(msg)

    assert not violations, "Gate H Violations found in REPORT.md:\n" + "\n".join(violations)
