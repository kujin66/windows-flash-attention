"""Compare the PEP 517 wheel/sdist with current sources, without importing CUDA."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

REPO = Path(__file__).resolve().parents[1]


def normalized(data):
    return data.replace(b"\r\n", b"\n")


def audit(dist, installed=None):
    wheel, = dist.glob("*.whl")
    sdist, = dist.glob("*.tar.gz")
    sources = REPO / "flash_attn/cute"
    expected = {p.name: p.read_bytes() for p in sources.glob("*.py")}
    issues = []
    with zipfile.ZipFile(wheel) as archive:
        files = {Path(n).name: archive.read(n) for n in archive.namelist()
                 if n.startswith("flash_attn/cute/") and n.endswith(".py")}
    with tarfile.open(sdist) as archive:
        packaged = {Path(m.name).name: archive.extractfile(m).read()
                    for m in archive.getmembers() if m.isfile()
                    and (m.name.endswith(".py") or Path(m.name).name in ("pyproject.toml", "WINDOWS.md"))}
    for label, actual in (("wheel", files), ("sdist", packaged)):
        if set(expected) - actual.keys():
            issues.append(f"{label}: missing {sorted(set(expected) - actual.keys())}")
        for name, data in expected.items():
            if name in actual and normalized(data) != normalized(actual[name]):
                issues.append(f"{label}: source differs: {name}")
    if set(files) != set(expected):
        issues.append("wheel: Python file inventory differs from source")
    for name in ("pyproject.toml", "WINDOWS.md"):
        if normalized(packaged.get(name, b"")) != normalized((sources / name).read_bytes()):
            issues.append(f"sdist: source differs: {name}")
    if installed is not None:
        installed_files = {p.name: p.read_bytes() for p in installed.glob("*.py")}
        if set(installed_files) != set(expected):
            issues.append("installed: Python file inventory differs from source")
        for name, data in expected.items():
            if normalized(installed_files.get(name, b"")) != normalized(data):
                issues.append(f"installed: source differs: {name}")
    return dict(passed=not issues, issues=issues, python_files=len(expected),
                wheel=str(wheel), wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                sdist=str(sdist), sdist_sha256=hashlib.sha256(sdist.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--installed", type=Path)
    args = parser.parse_args()
    result = audit(args.dist, args.installed)
    (args.dist / "source-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
