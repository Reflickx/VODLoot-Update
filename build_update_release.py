from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(payload: dict) -> bytes:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_payload(source: Path, payload: Path, version: str) -> None:
    shutil.copytree(source / "app", payload / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(source / "src", payload / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(source / "pyproject.toml", payload / "pyproject.toml")
    (payload / "version.json").write_text(
        json.dumps(
            {
                "version": version,
                "channel": "stable",
                "installed_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and sign one VODLoot automatic-update release")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--sync-environment", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    try:
        version_parts = tuple(int(piece) for piece in args.version.split("."))
    except ValueError as exc:
        raise SystemExit("--version must contain only dot-separated integers") from exc
    if not 2 <= len(version_parts) <= 4 or any(piece < 0 for piece in version_parts):
        raise SystemExit("--version must be a two- to four-part semantic version")
    parsed_base = urlparse(args.base_url)
    if parsed_base.scheme != "https" or not parsed_base.netloc:
        raise SystemExit("--base-url must be a complete HTTPS URL")
    for required in ("app/clipforge_app.py", "src/clipforge", "pyproject.toml"):
        if not (source / required).exists():
            raise SystemExit(f"Source tree is missing {required}")
    if not args.private_key.is_file():
        raise SystemExit("The private signing key was not found")
    output.mkdir(parents=True, exist_ok=True)
    filename = f"VODLoot-update-{args.version}.zip"
    package = output / filename
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        payload = root / "payload"
        payload.mkdir()
        copy_payload(source, payload, args.version)
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())

    manifest = {
        "schema": 1,
        "channel": "stable",
        "version": args.version,
        "minimum_updater_version": "1.0.0",
        "package_url": args.base_url.rstrip("/") + "/" + filename,
        "sha256": sha256(package),
        "release_notes": args.note,
        "mandatory": args.mandatory,
        "sync_environment": args.sync_environment,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("The release key is not an Ed25519 private key")
    manifest["signature"] = base64.b64encode(key.sign(canonical(manifest))).decode("ascii")
    (output / "stable.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(package)
    print(output / "stable.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
