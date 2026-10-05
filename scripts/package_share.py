"""Package repository files, optionally adding a ZIP-only private specification."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--spec", type=Path)
args = parser.parse_args()
if (root / ".git").exists():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    paths = sorted(p for p in paths if p)
else:
    paths = (root / "PACKAGE-FILES.txt").read_text().splitlines()
for path in paths:
    if Path(path).suffix.lower() in {".docx", ".doc", ".zip", ".pem", ".key"} or path.startswith("private/"):
        raise SystemExit(f"Refusing private file: {path}")
args.output.parent.mkdir(parents=True, exist_ok=True)
prefix = "liturgy-lab-share/"
with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(root / path, prefix + path)
    if args.spec:
        archive.write(args.spec, prefix + "private/ADS Pilot Specification.docx")
with zipfile.ZipFile(args.output) as archive:
    assert archive.testzip() is None
    expected = {prefix + path for path in paths}
    if args.spec:
        expected.add(prefix + "private/ADS Pilot Specification.docx")
    assert set(archive.namelist()) == expected
    for path in paths:
        assert hashlib.sha256(archive.read(prefix + path)).digest() == hashlib.sha256((root / path).read_bytes()).digest(), path
print(f"Verified {len(paths)} identical repository files; ZIP size {args.output.stat().st_size / 1048576:.1f} MiB")
