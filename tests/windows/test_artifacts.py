"""CI must reject packages that differ from the checked-out source."""
import importlib.util
import io
from pathlib import Path
import tarfile
import zipfile

import pytest


@pytest.mark.parametrize("changed", [None, "wheel", "sdist", "installed"])
def test_artifact_source_comparison(tmp_path, monkeypatch, changed):
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("artifacts_test", repo / "tools/windows_artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO", tmp_path)
    source = tmp_path / "flash_attn/cute"
    source.mkdir(parents=True)
    for name, data in {"__init__.py": b"value = 1\n", "pyproject.toml": b"[project]\n", "WINDOWS.md": b"Windows\n"}.items():
        (source / name).write_bytes(data)
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "test.whl", "w") as archive:
        archive.writestr("flash_attn/cute/__init__.py", b"value = 2\n" if changed == "wheel" else b"value = 1\r\n")
    with tarfile.open(dist / "test.tar.gz", "w:gz") as archive:
        for path in source.iterdir():
            data = b"changed" if changed == "sdist" and path.suffix == ".py" else path.read_bytes()
            member = tarfile.TarInfo("test/" + path.name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "__init__.py").write_bytes(b"value = 2\n" if changed == "installed" else b"value = 1\n")
    result = module.audit(dist, installed)
    assert result["passed"] is (changed is None)
    if changed:
        assert any(issue.startswith(changed + ":") for issue in result["issues"])
