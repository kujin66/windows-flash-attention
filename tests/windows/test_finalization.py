"""Incomplete, reduced or stale evidence must never authorize a Draft PR."""
import importlib
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("problem", [None, "incomplete", "failed", "stale", "reduced", "x64"])
def test_draft_requires_full_current_source_arm64_acceptance(tmp_path, monkeypatch, problem):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "tools"))
    finalizer = importlib.import_module("windows_finalize")
    monkeypatch.setattr(finalizer, "source_fingerprint", lambda: "a" * 64)
    result = dict(passed=True, issues=[], files_expected=36, files_audited=36, source_sha256="a" * 64)
    manifest = dict(suite="full", sequence_cap=0, architecture="arm64", source_sha256="a" * 64)
    if problem == "incomplete":
        result["files_audited"] = 35
    elif problem == "failed":
        result["passed"] = False
    elif problem == "stale":
        manifest["source_sha256"] = "b" * 64
    elif problem == "reduced":
        manifest["sequence_cap"] = 256
    elif problem == "x64":
        manifest["architecture"] = "amd64"
    (tmp_path / "independent-audit.json").write_text(json.dumps(result))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    if problem:
        with pytest.raises(RuntimeError, match="Draft PR blocked"):
            finalizer.require_full_acceptance(tmp_path)
    else:
        assert finalizer.require_full_acceptance(tmp_path) == (result, manifest)
