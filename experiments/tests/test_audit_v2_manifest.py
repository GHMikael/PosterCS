from pathlib import Path

from experiments.audit.manifest_v2 import build_manifest, ANNOTATION_COLS


def test_manifest_has_60_unique_with_required_fields():
    rows = build_manifest()
    assert len(rows) == 60, f"expected 60 papers, got {len(rows)}"
    titles = {r["title_norm"] for r in rows}
    assert len(titles) == 60, "titles must be unique (deduped sample)"
    required = ("run_folder", "title", "title_norm", "template", "iter1_png", "iter1_sha256")
    for r in rows:
        for k in required:
            assert r.get(k), f"row missing/empty field {k!r}: {r.get('run_folder')}"
        assert r["iter1_png"].endswith("pptx/iter_1.png"), "must use the real PPTX render, not preview"
        assert Path(r["iter1_png"]).exists(), f"missing image: {r['iter1_png']}"


def test_templates_are_expected_set():
    rows = build_manifest()
    templates = {r["template"] for r in rows}
    # 4 known templates; minimal may be rare (n=1) but must be a known name
    assert templates <= {"template_classic", "template_storyflow", "template_dashboard", "template_minimal"}, templates


def test_annotation_cols_have_label_fields():
    for col in ("primary_issue", "secondary_issues", "other_description", "confidence"):
        assert col in ANNOTATION_COLS
