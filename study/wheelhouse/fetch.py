"""Download locked binary dependencies only; never install or import wheels."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def manifest(directory, metadata):
    expected = {item["filename"]: item for item in metadata}
    actual = {p.name for p in directory.iterdir()}
    if actual != set(expected):
        raise ValueError("wheelhouse does not exactly match the reviewed inventory")
    rows = []
    for name, item in sorted(expected.items()):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.suffix != ".whl":
            raise ValueError("only regular wheels allowed")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != item["sha256"]:
            raise ValueError("wheel differs from reviewed hash: " + name)
        rows.append({"filename": name, "sha256": sha, "license": item["license"]})
    with (directory / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["filename", "sha256", "license"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def download(directory, profile="contrail"):
    if profile not in {"contrail", "meow-now"}:
        raise ValueError("unknown reviewed wheel profile")
    root = Path(__file__).resolve().parent
    constraints = "constraints.txt" if profile == "contrail" else "constraints-meow-now.txt"
    metadata = "LOCK_METADATA.json" if profile == "contrail" else "LOCK_METADATA-meow-now.json"
    directory.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="study-pip-home-") as home:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": home,
               "PIP_CONFIG_FILE": os.devnull, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        if os.name == "nt":
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        command = [sys.executable, "-I", "-m", "pip", "--isolated", "download",
                   "--index-url", "https://pypi.org/simple", "--no-cache-dir",
                   "--require-hashes", "--only-binary=:all:", "--python-version", "3.12",
                   "--implementation", "cp", "--abi", "cp312",
                   "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux2014_x86_64",
                   "-c", str(root / constraints), "-r", str(root / f"requirements-{profile}.lock"),
                   "-d", str(directory.resolve())]
        subprocess.run(command, env=env, cwd=home, check=True, timeout=600)
    return manifest(directory, json.loads((root / metadata).read_text(encoding="utf-8"))["wheels"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path("wheelhouse"))
    parser.add_argument("--profile", choices=("contrail", "meow-now"), default="contrail")
    args = parser.parse_args()
    print(json.dumps({"downloaded_wheels": len(download(args.dest, args.profile))}))
