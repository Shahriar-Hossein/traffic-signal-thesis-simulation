"""Build publication tables and figures from an analyzed paired batch JSON.

This module consumes analyzer output only.  It does not recompute effects or
pool scenario cells.  Matplotlib is imported only when rendering is requested.
"""
import argparse
import csv
import json
import math
from pathlib import Path


SAFEGUARDS = {
    "wait_p95": ("p95 stopped delay", "s"),
    "worst_approach_wait": ("worst approach delay", "s"),
    "approach_service_gap": ("approach service gap", "s"),
    "clearance_sec": ("clearance time", "s"),
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_batch(path, development=False, cohort=None):
    """Load and validate a batch, refusing development data by default."""
    with open(path) as handle:
        batch = json.load(handle)
    if not isinstance(batch, dict):
        raise ValueError("batch JSON must contain an object")
    stage = batch.get("study_stage")
    if stage != "evaluation" and not development:
        raise ValueError("batch is not tagged study_stage=evaluation; use --development explicitly")
    if batch.get("cohort_errors") and cohort is None:
        raise ValueError("incompatible cohorts require explicit --cohort selection")
    if cohort is not None:
        selected = (batch.get("per_cohort") or {}).get(cohort)
        if selected is None:
            raise ValueError("unknown cohort {!r}".format(cohort))
        batch = dict(batch)
        batch["per_scenario"] = {
            scenario: (cell.get("per_cohort") or {}).get(cohort, cell)
            for scenario, cell in (batch.get("per_scenario") or {}).items()
            if not cell.get("cohort_error") or cohort in (cell.get("per_cohort") or {})
        }
        batch["per_contrast"] = selected
    if not batch.get("per_scenario"):
        raise ValueError("batch has no per-scenario estimates")
    return batch


def _blocks(batch):
    """Yield (scenario, contrast, summary), excluding malformed/cohort cells."""
    for scenario, cell in sorted((batch.get("per_scenario") or {}).items()):
        if cell.get("cohort_error"):
            continue
        for contrast, summary in sorted(cell.items()):
            if contrast.startswith("_") or not isinstance(summary, dict):
                continue
            if _number(summary.get("delta_wait_mean_of_plan_means")):
                yield scenario, contrast, summary


def table_rows(batch):
    """Return primary and safeguard rows suitable for CSV serialization."""
    rows = []
    for scenario, contrast, summary in _blocks(batch):
        arm = contrast.split("_vs_", 1)[1] if "_vs_" in contrast else contrast
        common = {"scenario": scenario, "contrast": contrast,
                  "arm": arm,
                  "plans": summary.get("plans"),
                  "baseline": batch.get("analysis", {}).get("baseline"),
                  "estimate": summary.get("delta_wait_mean_of_plan_means"),
                  "ci_low": summary.get("ci_low"), "ci_high": summary.get("ci_high"),
                  "ci_status": "95% CI" if _number(summary.get("ci_low")) and _number(summary.get("ci_high")) else "insufficient replication"}
        rows.append(dict(endpoint="stopped_delay", units="s", **common))
        for endpoint, guard in sorted((summary.get("safeguards") or {}).items()):
            if endpoint not in SAFEGUARDS or not _number(guard.get("mean_of_plan_deltas")):
                continue
            rows.append(dict(endpoint=endpoint, units=SAFEGUARDS[endpoint][1],
                             **{**common, "estimate": guard["mean_of_plan_deltas"],
                                "ci_low": guard.get("ci_low"), "ci_high": guard.get("ci_high"),
                                "ci_status": "95% CI" if _number(guard.get("ci_low")) and _number(guard.get("ci_high")) else "insufficient replication"}))
    if not rows:
        raise ValueError("no valid per-scenario estimates")
    return rows


def _write_csv(path, rows):
    fields = ["scenario", "contrast", "baseline", "arm", "plans", "endpoint", "units",
              "estimate", "ci_low", "ci_high", "ci_status"]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)


def write_artifacts(batch, output, source_path, development=False, render=True):
    output = Path(output)
    if output.exists():
        raise FileExistsError("output directory already exists: {}".format(output))
    output.mkdir(parents=True)
    rows = table_rows(batch)
    _write_csv(output / "paper_results.csv", rows)
    _write_csv(output / "primary_stopped_delay.csv", [r for r in rows if r["endpoint"] == "stopped_delay"])
    _write_csv(output / "safeguards.csv", [r for r in rows if r["endpoint"] != "stopped_delay"])
    metadata = {
        "source_batch": str(Path(source_path).resolve()),
        "analysis": batch.get("analysis", {}),
        "study_stage": "development" if development else batch.get("study_stage"),
        "label": "DEVELOPMENT — not final evidence" if development else "evaluation",
        "plans_total": batch.get("plans_total"), "plans_valid": batch.get("plans_valid"),
        "independent_replicates_included": batch.get("independent_replicates_included"),
        "baseline": batch.get("analysis", {}).get("baseline"),
        "cohort_errors": batch.get("cohort_errors", []),
        "schema": "analyze_paired per_scenario/contrast_block",
    }
    with open(output / "metadata.json", "w") as handle:
        json.dump(metadata, handle, indent=2)
    if render:
        _render(rows, output, metadata["label"])
    return rows


def _render(rows, output, label):
    import matplotlib.pyplot as plt
    groups = [(r["scenario"], r["contrast"]) for r in rows if r["endpoint"] == "stopped_delay"]
    x = list(range(len(groups)))
    fig, ax = plt.subplots(figsize=(max(7, len(groups) * 0.8), 4.5))
    vals = [next(r for r in rows if r["scenario"] == s and r["contrast"] == c and r["endpoint"] == "stopped_delay") for s, c in groups]
    for i, row in enumerate(vals):
        lo, hi = row.get("ci_low"), row.get("ci_high")
        yerr = [[row["estimate"] - lo], [hi - row["estimate"]]] if _number(lo) and _number(hi) else None
        ax.errorbar([i], [row["estimate"]], yerr=yerr, fmt="o", capsize=3, color="tab:blue")
        if yerr is None:
            ax.annotate("insufficient replication", (i, row["estimate"]), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7)
    ax.axhline(0, color="0.4", lw=.8); ax.set_xticks(x, [f"{s}\n{c}" for s, c in groups], rotation=45, ha="right")
    ax.set_ylabel("Δ stopped delay (s; arm − baseline)"); ax.set_title("Stopped-delay effect — " + label)
    fig.tight_layout(); fig.savefig(output / "stopped_delay_effect.svg"); fig.savefig(output / "stopped_delay_effect.pdf"); plt.close(fig)
    for name, title, endpoints in (("safeguard_effects", "Safeguard effects", list(SAFEGUARDS)), ("contrast_comparison", "Contrast comparison", ["stopped_delay"])):
        subset = [r for r in rows if r["endpoint"] in endpoints]
        if not subset: continue
        fig, ax = plt.subplots(figsize=(8, 4.5)); labels = [f"{r['scenario']}\n{r['contrast']}\n{r['endpoint']}" for r in subset]
        ax.bar(range(len(subset)), [r["estimate"] for r in subset], color="tab:orange"); ax.axhline(0, color="0.4", lw=.8)
        ax.set_xticks(range(len(subset)), labels, rotation=60, ha="right"); ax.set_ylabel("Δ (s; arm − baseline)"); ax.set_title(title + " — " + label); fig.tight_layout()
        fig.savefig(output / (name + ".svg")); fig.savefig(output / (name + ".pdf")); plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="analyzed batch JSON")
    parser.add_argument("--output", required=True, help="new output directory")
    parser.add_argument("--development", action="store_true", help="allow and label non-evaluation batch")
    parser.add_argument("--cohort", help="explicit cohort label when batch cohorts are incompatible")
    parser.add_argument("--no-render", action="store_true", help="write CSV/metadata only")
    args = parser.parse_args(argv)
    batch = read_batch(args.batch, args.development, args.cohort)
    write_artifacts(batch, args.output, args.batch, args.development, not args.no_render)


if __name__ == "__main__":
    main()
