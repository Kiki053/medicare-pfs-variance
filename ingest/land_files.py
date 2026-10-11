"""Turn the raw CMS files into tidy landing tables.

CMS publishes each relative value file with five lines of title and copyright
text and a column header split across five more rows, and the layout shifts
between years (2026 adds a PRIC IND column). This step rebuilds each column
name from its header rows, maps it to one stable snake_case name, and writes
everything as text to data/landing/*.parquet. Typing, filtering, and every
business rule happen later, in the dbt models.

Usage:
    python ingest/land_files.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LANDING = ROOT / "data" / "landing"

# release, calendar year, RVU file, conversion factor track, GPCI file
RELEASES = [
    ("RVU22A", 2022, "PPRRVU22_JAN.csv", "single", "GPCI2022.csv"),
    ("RVU23A", 2023, "PPRRVU23_JAN.csv", "single", "GPCI2023.csv"),
    ("RVU24A", 2024, "PPRRVU24_JAN.csv", "single", "GPCI2024.csv"),
    ("RVU24AR", 2024, "PPRRVU24_JAN.csv", "single", "GPCI2024.csv"),
    ("RVU25A", 2025, "PPRRVU25_JAN.csv", "single", "GPCI2025.csv"),
    ("RVU26A", 2026, "PPRRVU2026_Jan_nonQPP.csv", "non_qp", "GPCI2026.csv"),
    ("RVU26A", 2026, "PPRRVU2026_Jan_QPP.csv", "qp", None),
]

RVU_COLUMNS = {
    "HCPCS": "hcpcs",
    "MOD": "modifier",
    "DESCRIPTION": "description",
    "STATUS CODE": "status_code",
    "NOT USED FOR MEDICARE PAYMENT": "not_used_for_medicare_payment",
    "WORK RVU": "work_rvu",
    "NON-FAC PE RVU": "nonfac_pe_rvu",
    "NON-FAC NA INDICATOR": "nonfac_na_indicator",
    "FACILITY PE RVU": "fac_pe_rvu",
    "FACILITY NA INDICATOR": "fac_na_indicator",
    "MP RVU": "mp_rvu",
    "NON-FACILITY TOTAL": "nonfac_total_rvu",
    "FACILITY TOTAL": "fac_total_rvu",
    "PCTC IND": "pctc_indicator",
    "GLOB DAYS": "global_days",
    "PRE OP": "pre_op_share",
    "INTRA OP": "intra_op_share",
    "POST OP": "post_op_share",
    "MULT PROC": "multiple_procedure_indicator",
    "BILAT SURG": "bilateral_surgery_indicator",
    "ASST SURG": "assistant_surgery_indicator",
    "CO- SURG": "co_surgery_indicator",
    "TEAM SURG": "team_surgery_indicator",
    "PRIC IND": "pricing_indicator",
    "ENDO BASE": "endo_base",
    "CONV FACTOR": "conversion_factor",
    "PHYSICIAN SUPERVISION OF DIAGNOSTIC PROCEDURES": "physician_supervision",
    "CALCULATION FLAG": "calculation_flag",
    "DIAGNOSTIC IMAGING FAMILY INDICATOR": "diagnostic_imaging_family",
    "NON-FACILITY PE USED FOR OPPS PAYMENT AMOUNT": "nonfac_pe_opps",
    "FACILITY PE USED FOR OPPS PAYMENT AMOUNT": "fac_pe_opps",
    "MP USED FOR OPPS PAYMENT AMOUNT": "mp_opps",
}


def read_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return list(csv.reader(text.splitlines()))


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def land_rvu(release: str, year: int, filename: str, track: str) -> pd.DataFrame:
    path = RAW / release / "files" / filename
    rows = read_rows(path)
    header = next(i for i, row in enumerate(rows) if row and row[0].strip() == "HCPCS")
    width = len(rows[header])
    names = []
    for col in range(width):
        parts = [rows[r][col] for r in range(header - 4, header + 1) if col < len(rows[r])]
        name = squash(" ".join(p for p in parts if p.strip()))
        if name not in RVU_COLUMNS:
            raise KeyError(f"{filename}: unexpected column {name!r}")
        names.append(RVU_COLUMNS[name])
    released = next((squash(r[2]) for r in rows[:header] if len(r) > 2 and "RELEASED" in r[2]), "")
    data = [r[:width] + [""] * (width - len(r)) for r in rows[header + 1 :] if r and r[0].strip()]
    frame = pd.DataFrame(data, columns=names)
    for column in RVU_COLUMNS.values():
        if column not in frame:
            frame[column] = ""
    frame = frame[list(RVU_COLUMNS.values())].apply(lambda s: s.str.strip())
    frame.insert(0, "release_id", release)
    frame.insert(1, "calendar_year", str(year))
    frame.insert(2, "cf_track", track)
    frame.insert(3, "released_on", released.replace("RELEASED", "").strip())
    frame.insert(4, "source_file", filename)
    return frame


def land_gpci(release: str, year: int, filename: str) -> pd.DataFrame:
    rows = read_rows(RAW / release / "files" / filename)
    header = next(i for i, r in enumerate(rows) if any("Locality Number" in c for c in r))
    names = []
    for cell in rows[header]:
        label = squash(cell)
        if "Administrative Contractor" in label:
            names.append("mac")
        elif label == "State":
            names.append("state")
        elif label == "Locality Number":
            names.append("locality_number")
        elif label == "Locality Name":
            names.append("locality_name")
        elif "PW GPCI (without" in label:
            names.append("pw_gpci_no_floor")
        elif "PW GPCI" in label:
            names.append("pw_gpci")
        elif "PE GPCI" in label:
            names.append("pe_gpci")
        elif "MP GPCI" in label:
            names.append("mp_gpci")
        else:
            names.append(f"unused_{len(names)}")
    data = [
        r[: len(names)] + [""] * (len(names) - len(r))
        for r in rows[header + 1 :]
        if len(r) > 1 and re.fullmatch(r"[A-Z]{2}", r[1].strip())
    ]
    frame = pd.DataFrame(data, columns=names).apply(lambda s: s.str.strip())
    frame = frame[[c for c in names if not c.startswith("unused_")]]
    if "pw_gpci_no_floor" not in frame:
        frame["pw_gpci_no_floor"] = ""
    frame["locality_name"] = frame["locality_name"].str.replace("*", "", regex=False).str.strip()
    frame.insert(0, "release_id", release)
    frame.insert(1, "calendar_year", str(year))
    return frame[
        ["release_id", "calendar_year", "mac", "state", "locality_number", "locality_name",
         "pw_gpci", "pw_gpci_no_floor", "pe_gpci", "mp_gpci"]
    ]


def land_efficiency_adjustment() -> tuple[pd.DataFrame, pd.DataFrame]:
    folder = RAW / "EFFADJ26" / "files"
    subject = pd.read_csv(
        next(folder.glob("*Sheet1.txt")), sep="\t", dtype=str, keep_default_na=False
    ).rename(columns={
        "hcpcs": "hcpcs", "HCPCS": "hcpcs", "mfs_mod": "modifier", "Work RVU": "work_rvu_before",
        "Total Time": "total_time_before", "Adjusted Work": "work_rvu_after",
        "Adjusted Time": "total_time_after",
    })
    excluded = pd.read_csv(
        next(folder.glob("*Sheet2.txt")), sep="\t", dtype=str, keep_default_na=False
    ).rename(columns={"HCPCS": "hcpcs"})
    return subject.apply(lambda s: s.str.strip()), excluded.apply(lambda s: s.str.strip())


def main() -> None:
    LANDING.mkdir(parents=True, exist_ok=True)

    rvu = pd.concat([land_rvu(rel, yr, f, track) for rel, yr, f, track, _ in RELEASES])
    rvu.to_parquet(LANDING / "pprrvu.parquet", index=False)
    print(f"pprrvu: {len(rvu):,} rows")

    gpci = pd.concat([land_gpci(rel, yr, g) for rel, yr, _, _, g in RELEASES if g])
    gpci.to_parquet(LANDING / "gpci.parquet", index=False)
    print(f"gpci: {len(gpci):,} rows")

    subject, excluded = land_efficiency_adjustment()
    subject.to_parquet(LANDING / "efficiency_adjustment_2026.parquet", index=False)
    excluded.to_parquet(LANDING / "efficiency_exclusions_2026.parquet", index=False)
    print(f"efficiency adjustment: {len(subject):,} codes subject, {len(excluded):,} excluded")

    usage = pd.read_csv(RAW / "MUPGEO24" / "MUPGEO24.csv", dtype=str, keep_default_na=False)
    usage.columns = [c.lower() for c in usage.columns]
    usage.to_parquet(LANDING / "utilization_geo_2024.parquet", index=False)
    print(f"utilization by geography and service (2024): {len(usage):,} rows")


if __name__ == "__main__":
    main()
