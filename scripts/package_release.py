"""Build a review ZIP from the source allowlist, never the whole workspace."""

import hashlib
import zipfile
from pathlib import Path

from check_release import ROOT, check


def package():
    files = check()
    destination = ROOT / "release"
    destination.mkdir(exist_ok=True)
    archive = destination / "kinetic-scholar.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in files:
            output.write(path, Path("kinetic-scholar") / path.relative_to(ROOT))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"Review package: {archive}\nSHA256: {digest}")


if __name__ == "__main__":
    package()
