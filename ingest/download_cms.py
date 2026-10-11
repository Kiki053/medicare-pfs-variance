"""Download the CMS files this project is built on.

Every file comes straight from cms.gov. Each release lands in its own folder
under data/raw/, is unzipped next to the original, and is logged in
data/raw/manifest.json with its source URL, size, and SHA-256 hash so anyone
can confirm they are analyzing the same bytes.

The hashes the published numbers were built from are kept in
ingest/checksums.json. If CMS reposts a file with different contents, the
script says so, because results built from it can differ slightly.

Usage:
    python ingest/download_cms.py                    # download anything missing
    python ingest/download_cms.py --force            # re-download everything
    python ingest/download_cms.py --write-checksums  # record current hashes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

CMS = "https://www.cms.gov"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
CHECKSUMS = Path(__file__).resolve().parent / "checksums.json"
HEADERS = {"User-Agent": "medicare-pfs-variance (+https://github.com/kiki0053/medicare-pfs-variance)"}

# PFS Relative Value Files. The January ("A") release of each year is the fee
# schedule as it took effect on January 1. 2024 also has a revised January
# release (AR), kept so the choice between them is explicit.
# Listing: https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files
SOURCES = {
    "RVU22A": CMS + "/files/zip/rvu22a.zip",
    "RVU23A": CMS + "/files/zip/rvu23a-updated-01/31/2023.zip",
    "RVU24A": CMS + "/files/zip/rvu24a-updated-04/01/2024.zip",
    "RVU24AR": CMS + "/files/zip/rvu24ar-posted-04/01/2024.zip",
    "RVU25A": CMS + "/files/zip/rvu25a-updated-01/10/2025.zip",
    "RVU26A": CMS + "/files/zip/rvu26a-updated-12-29-2025.zip",
    # Codes CMS listed as subject to the CY 2026 -2.5% efficiency adjustment.
    "EFFADJ26": CMS + "/files/zip/cy-2026-pfs-final-rule-codes-subject-efficiency-adjustment-updated-11-03-2025.zip",
    # Medicare Physician & Other Practitioners by Geography and Service, data
    # year 2024 (national and state service counts by HCPCS and setting).
    # Landing page: https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-geography-and-service
    "MUPGEO24": "https://data.cms.gov/sites/default/files/2026-05/e534c74b-79b8-4892-8a95-5a17e2dfec9f/MUP_PHY_R26_P05_V10_D24_Geo.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: Path, dest: Path) -> list[str]:
    """Unzip without letting any member escape `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    names = []
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError(f"Unsafe path in {archive.name}: {member.filename}")
            if member.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as out:
                out.write(src.read())
            names.append(member.filename)
    return names


def fetch(url: str, target: Path, attempts: int = 3) -> None:
    """Stream `url` to `target`. Bytes go to a .part file that is renamed only
    once the download finishes, so an interrupted run never looks complete."""
    partial = target.with_name(target.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            with requests.get(url, stream=True, timeout=300, headers=HEADERS) as response:
                response.raise_for_status()
                with partial.open("wb") as out:
                    for chunk in response.iter_content(1 << 20):
                        out.write(chunk)
            partial.replace(target)
            return
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            wait = 10 * attempt
            print(f"  attempt {attempt} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)


def download(release: str, url: str, force: bool) -> dict:
    folder = RAW / release
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(url).suffix.lower()
    target = folder / f"{release}{suffix}"
    if force or not target.exists():
        print(f"Downloading {release} from {url}")
        fetch(url, target)
    else:
        print(f"{release} already downloaded")
    members = safe_extract(target, folder / "files") if suffix == ".zip" else [target.name]
    return {
        "release": release,
        "url": url,
        "bytes": target.stat().st_size,
        "sha256": sha256(target),
        "members": members,
    }


def compare_to_published(entries: list[dict]) -> None:
    """Flag any file whose bytes differ from the ones the published numbers used."""
    if not CHECKSUMS.exists():
        return
    published = json.loads(CHECKSUMS.read_text())
    for entry in entries:
        expected = published.get(entry["release"])
        if expected and expected != entry["sha256"]:
            print(
                f"Note: {entry['release']} differs from the file the published numbers were "
                "built from. CMS may have reposted it, so results can differ slightly."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download every file")
    parser.add_argument(
        "--write-checksums", action="store_true", help="save the current hashes to ingest/checksums.json"
    )
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    entries = [download(release, path, args.force) for release, path in SOURCES.items()]
    manifest = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": entries,
    }
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {RAW / 'manifest.json'}")
    if args.write_checksums:
        hashes = {entry["release"]: entry["sha256"] for entry in entries}
        CHECKSUMS.write_text(json.dumps(hashes, indent=2) + "\n")
        print(f"Wrote {CHECKSUMS}")
    else:
        compare_to_published(entries)


if __name__ == "__main__":
    main()
