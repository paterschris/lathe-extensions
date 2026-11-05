#!/usr/bin/env python3
"""Validate, package, and index the extensions listed in extensions.toml.

Subcommands:
  validate  Check extensions.toml against each extension's own manifest and
            against the published index.
  publish   Package every extension version that is not already published,
            then write the complete index.json for the site.

Only the Python standard library is used so CI needs no extra setup.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

INDEX_SCHEMA = 1
ROOT = Path(__file__).resolve().parent.parent
EXTENSION_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
# Host requirements an extension may declare with `requires` in extension.toml.
# Must match SUPPORTED_REQUIREMENTS in Lathe's crates/extension_host/src/registry.rs.
KNOWN_REQUIREMENTS = {"lathe"}


@dataclass
class Listing:
    id: str
    submodule: Path
    path: Path
    version: str

    @property
    def source_dir(self) -> Path:
        return ROOT / self.submodule / self.path

    @property
    def archive_name(self) -> str:
        return f"{self.id}-{self.version}.tar.gz"


class RegistryError(Exception):
    pass


def load_listings() -> list[Listing]:
    with open(ROOT / "extensions.toml", "rb") as file:
        data = tomllib.load(file)

    listings = []
    for extension_id, entry in sorted(data.items()):
        if not isinstance(entry, dict):
            raise RegistryError(f"[{extension_id}] must be a table")
        unknown = set(entry) - {"submodule", "path", "version"}
        if unknown:
            raise RegistryError(f"[{extension_id}] has unknown keys: {sorted(unknown)}")
        try:
            listings.append(
                Listing(
                    id=extension_id,
                    submodule=Path(entry["submodule"]),
                    path=Path(entry.get("path", ".")),
                    version=entry["version"],
                )
            )
        except KeyError as missing:
            raise RegistryError(f"[{extension_id}] is missing {missing}") from None
    return listings


def submodule_commit(listing: Listing) -> str:
    output = subprocess.run(
        ["git", "-C", str(ROOT / listing.submodule), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return output.stdout.strip()


def load_extension_manifest(listing: Listing) -> dict:
    manifest_path = listing.source_dir / "extension.toml"
    if not manifest_path.is_file():
        raise RegistryError(f"{listing.id}: no extension.toml at {manifest_path}")
    with open(manifest_path, "rb") as file:
        return tomllib.load(file)


def load_index(path: Path | None) -> dict[str, dict]:
    if path is None or not path.is_file():
        return {}
    index = json.loads(path.read_text())
    if index.get("schema") != INDEX_SCHEMA:
        raise RegistryError(f"{path} has schema {index.get('schema')}, expected {INDEX_SCHEMA}")
    return {entry["id"]: entry for entry in index.get("extensions", [])}


def validate(listings: list[Listing], published: dict[str, dict]) -> list[str]:
    errors = []
    for listing in listings:
        prefix = listing.id
        if not EXTENSION_ID.match(listing.id):
            errors.append(f"{prefix}: id must be lowercase kebab-case")
        if not SEMVER.match(listing.version):
            errors.append(f"{prefix}: version {listing.version!r} is not semver")
        if listing.path.is_absolute() or ".." in listing.path.parts:
            errors.append(f"{prefix}: path must be relative and inside the submodule")
            continue
        if not (ROOT / listing.submodule / ".git").exists():
            errors.append(f"{prefix}: submodule {listing.submodule} is not checked out")
            continue

        try:
            manifest = load_extension_manifest(listing)
        except (RegistryError, tomllib.TOMLDecodeError) as error:
            errors.append(f"{prefix}: {error}")
            continue

        if manifest.get("id") != listing.id:
            errors.append(f"{prefix}: extension.toml id is {manifest.get('id')!r}")
        if manifest.get("version") != listing.version:
            errors.append(
                f"{prefix}: extensions.toml says {listing.version}, "
                f"extension.toml says {manifest.get('version')}"
            )
        if not manifest.get("repository"):
            errors.append(f"{prefix}: extension.toml must set repository")
        requires = manifest.get("requires", [])
        if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
            errors.append(f"{prefix}: requires must be a list of strings")
        elif unknown := sorted(set(requires) - KNOWN_REQUIREMENTS):
            errors.append(f"{prefix}: unknown requirements {unknown}")

        previous = published.get(listing.id)
        if (
            previous
            and previous["version"] == listing.version
            and previous.get("source_commit") not in (None, submodule_commit(listing))
        ):
            errors.append(
                f"{prefix}: source changed but version is still {listing.version}; "
                "bump the version in extension.toml and extensions.toml"
            )
    return errors


def package(listing: Listing, extension_cli: str, dist_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as scratch, tempfile.TemporaryDirectory() as output:
        subprocess.run(
            [
                extension_cli,
                "--source-dir",
                str(listing.source_dir),
                "--scratch-dir",
                scratch,
                "--output-dir",
                output,
            ],
            check=True,
        )
        manifest = json.loads((Path(output) / "manifest.json").read_text())
        # extension_cli's manifest.json has no Lathe-specific fields.
        manifest["requires"] = load_extension_manifest(listing).get("requires", [])
        archive = dist_dir / listing.archive_name
        shutil.copyfile(Path(output) / "archive.tar.gz", archive)

    return {
        "manifest": manifest,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


def index_entry(listing: Listing, packaged: dict, download_base_url: str) -> dict:
    manifest = packaged["manifest"]
    return {
        "id": listing.id,
        "name": manifest["name"],
        "version": manifest["version"],
        "description": manifest.get("description"),
        "authors": manifest.get("authors", []),
        "repository": manifest["repository"],
        "schema_version": manifest.get("schema_version"),
        "wasm_api_version": manifest.get("wasm_api_version"),
        "provides": manifest.get("provides", []),
        "requires": manifest.get("requires", []),
        "download_url": f"{download_base_url.rstrip('/')}/{listing.archive_name}",
        "sha256": packaged["sha256"],
        "source_commit": submodule_commit(listing),
        "published_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def command_validate(args: argparse.Namespace) -> int:
    listings = load_listings()
    errors = validate(listings, load_index(args.published_index))
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1

    if args.extension_cli:
        published = load_index(args.published_index)
        with tempfile.TemporaryDirectory() as dist:
            for listing in listings:
                previous = published.get(listing.id)
                if previous and previous["version"] == listing.version:
                    continue
                print(f"building {listing.id} {listing.version}")
                package(listing, args.extension_cli, Path(dist))
    print(f"ok: {len(listings)} extensions")
    return 0


def command_publish(args: argparse.Namespace) -> int:
    listings = load_listings()
    published = load_index(args.published_index)
    errors = validate(listings, published)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1

    args.dist.mkdir(parents=True, exist_ok=True)
    entries = []
    for listing in listings:
        previous = published.get(listing.id)
        if previous and previous["version"] == listing.version:
            entries.append(previous)
            continue
        print(f"packaging {listing.id} {listing.version}")
        packaged = package(listing, args.extension_cli, args.dist)
        entries.append(index_entry(listing, packaged, args.download_base_url))

    index = {
        "schema": INDEX_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "extensions": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {args.out} with {len(entries)} extensions")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_parser = subcommands.add_parser("validate")
    validate_parser.add_argument("--published-index", type=Path)
    validate_parser.add_argument(
        "--extension-cli", help="also build every unpublished version with this binary"
    )
    validate_parser.set_defaults(handler=command_validate)

    publish_parser = subcommands.add_parser("publish")
    publish_parser.add_argument("--published-index", type=Path)
    publish_parser.add_argument("--extension-cli", required=True)
    publish_parser.add_argument("--download-base-url", required=True)
    publish_parser.add_argument("--dist", type=Path, required=True)
    publish_parser.add_argument("--out", type=Path, required=True)
    publish_parser.set_defaults(handler=command_publish)

    args = parser.parse_args()
    try:
        return args.handler(args)
    except RegistryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
