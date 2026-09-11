import json
import tempfile
import unittest
from pathlib import Path

from scripts.make_paper_figures import read_batch, table_rows, write_artifacts


def batch(stage="evaluation", ci=True):
    summary = {"plans": 3, "delta_wait_mean_of_plan_means": -2.5,
               "ci_low": -3.0 if ci else None, "ci_high": -2.0 if ci else None,
               "safeguards": {"wait_p95": {"plans": 3, "mean_of_plan_deltas": -1.2,
                                             "ci_low": None, "ci_high": None},
                              "clearance_sec": {"plans": 3, "mean_of_plan_deltas": 4.0,
                                                 "ci_low": 3.0, "ci_high": 5.0}}}
    return {"study_stage": stage, "plans_total": 3, "plans_valid": 3,
            "independent_replicates_included": 3,
            "analysis": {"baseline": "fixed", "schema_version": 3},
            "cohort_errors": [],
            "per_scenario": {"even_low_100": {"fixed_vs_priority": summary}}}


class PaperFigureDataTests(unittest.TestCase):
    def test_rows_keep_scenario_plan_and_arm_labels(self):
        rows = table_rows(batch())
        primary = next(row for row in rows if row["endpoint"] == "stopped_delay")
        self.assertEqual((primary["scenario"], primary["plans"], primary["baseline"], primary["arm"]),
                         ("even_low_100", 3, "fixed", "priority"))
        self.assertEqual(primary["ci_status"], "95% CI")

    def test_missing_ci_is_insufficient_replication_not_zero(self):
        rows = table_rows(batch(ci=False))
        primary = next(row for row in rows if row["endpoint"] == "stopped_delay")
        self.assertIsNone(primary["ci_low"])
        self.assertEqual(primary["ci_status"], "insufficient replication")

    def test_development_requires_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(json.dumps(batch(stage="development")))
            with self.assertRaises(ValueError):
                read_batch(path)
            self.assertEqual(read_batch(path, development=True)["study_stage"], "development")

    def test_incompatible_cohorts_require_selection(self):
        source = batch()
        source["cohort_errors"] = ["incompatible"]
        source["per_cohort"] = {"cohort-a": source["per_scenario"]["even_low_100"]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(json.dumps(source))
            with self.assertRaises(ValueError):
                read_batch(path)
            read_batch(path, cohort="cohort-a")

    def test_artifacts_do_not_overwrite_and_no_render_is_pure_data(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "batch.json"
            source.write_text(json.dumps(batch()))
            out = Path(temp) / "figures"
            write_artifacts(batch(), out, source, render=False)
            self.assertTrue((out / "primary_stopped_delay.csv").exists())
            with self.assertRaises(FileExistsError):
                write_artifacts(batch(), out, source, render=False)


if __name__ == "__main__":
    unittest.main()
