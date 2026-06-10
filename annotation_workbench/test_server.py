import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server


FIELDNAMES = [
    "run_folder",
    "title",
    "template",
    "iter1_png",
    "primary_issue",
    "secondary_issues",
    "other_description",
    "guard_notes",
    "confidence",
    "free_notes",
]


class AnnotationWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.image = self.root / "poster.png"
        self.image.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.csv_path = self.root / "labels.csv"
        self._write_csv(
            [
                {
                    "run_folder": "run_1",
                    "title": "Paper One",
                    "template": "template_classic",
                    "iter1_png": str(self.image),
                    "primary_issue": "",
                    "secondary_issues": "",
                    "other_description": "",
                    "guard_notes": "",
                    "confidence": "",
                    "free_notes": "",
                },
                {
                    "run_folder": "run_2",
                    "title": "Paper Two",
                    "template": "template_dashboard",
                    "iter1_png": str(self.image),
                    "primary_issue": "none",
                    "secondary_issues": "",
                    "other_description": "",
                    "guard_notes": "",
                    "confidence": "0.9",
                    "free_notes": "layout is acceptable",
                },
            ]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_csv(self, rows):
        with self.csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    def test_load_state_finds_first_unlabeled_row_and_missing_images(self):
        state = server.load_state(self.csv_path)

        self.assertEqual(state["total"], 2)
        self.assertEqual(state["completed"], 1)
        self.assertEqual(state["first_unlabeled_index"], 0)
        self.assertEqual(state["missing_images"], [])
        self.assertEqual(state["rows"][0]["title"], "Paper One")

    def test_validate_annotation_requires_open_coding_and_other_description(self):
        with self.assertRaisesRegex(server.ValidationError, "free_notes"):
            server.validate_annotation(
                {
                    "primary_issue": "space_imbalance",
                    "secondary_issues": [],
                    "confidence": "0.8",
                    "free_notes": "",
                    "other_description": "",
                    "guard_notes": "",
                }
            )

        with self.assertRaisesRegex(server.ValidationError, "other_description"):
            server.validate_annotation(
                {
                    "primary_issue": "other",
                    "secondary_issues": [],
                    "confidence": "0.8",
                    "free_notes": "The decorative number is too dominant.",
                    "other_description": "",
                    "guard_notes": "",
                }
            )

    def test_validate_annotation_rejects_invalid_secondary_and_confidence(self):
        with self.assertRaisesRegex(server.ValidationError, "secondary_issues"):
            server.validate_annotation(
                {
                    "primary_issue": "space_imbalance",
                    "secondary_issues": ["none"],
                    "confidence": "0.8",
                    "free_notes": "The panel is sparse.",
                    "other_description": "",
                    "guard_notes": "",
                }
            )

        with self.assertRaisesRegex(server.ValidationError, "confidence"):
            server.validate_annotation(
                {
                    "primary_issue": "space_imbalance",
                    "secondary_issues": [],
                    "confidence": "1.5",
                    "free_notes": "The panel is sparse.",
                    "other_description": "",
                    "guard_notes": "",
                }
            )

    def test_save_annotation_creates_backup_and_preserves_csv_columns(self):
        payload = {
            "primary_issue": "structure_alignment_error",
            "secondary_issues": ["space_imbalance", "asset_too_small"],
            "confidence": "0.85",
            "free_notes": "The right side has a large blank block.",
            "other_description": "",
            "guard_notes": "Possible low contrast in footer.",
        }

        result = server.save_annotation(self.csv_path, 0, payload)

        self.assertEqual(result["completed"], 2)
        backups = list(self.root.glob("labels.csv.bak-*"))
        self.assertEqual(len(backups), 1)

        with self.csv_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        self.assertEqual(rows[0]["primary_issue"], "structure_alignment_error")
        self.assertEqual(rows[0]["secondary_issues"], "space_imbalance,asset_too_small")
        self.assertEqual(rows[0]["confidence"], "0.85")
        self.assertEqual(list(rows[0].keys()), FIELDNAMES)


if __name__ == "__main__":
    unittest.main()
