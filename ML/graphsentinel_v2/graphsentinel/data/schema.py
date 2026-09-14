"""
CICIDS2017 schema detection and column normalisation.

CICIDS2017 ships in two distributions that share the *same five filenames*:

    MachineLearningCVE/   79 cols, first column " Destination Port"  -- NO IPs
    TrafficLabelling_/    85 cols, first column "Flow ID"            -- has IPs

The original notebook was pointed at MachineLearningCVE, which is why it ended
up building a sequence graph out of flow rows: there were no IP addresses in
the data to make nodes out of. This module detects which variant is present and
fails loudly with an actionable message rather than silently degrading.

It also normalises the notoriously inconsistent leading spaces in CICIDS2017
column names ("Total Length of Fwd Packets" has no leading space, its 78
neighbours do), so the rest of the codebase can use clean names.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Canonical (space-stripped) names for the columns an IP-as-node graph needs.
IP_COLUMNS = ["Source IP", "Destination IP"]
FLOW_ID_COLUMNS = ["Flow ID", "Source Port", "Destination Port", "Protocol"]
TIMESTAMP_COLUMN = "Timestamp"
LABEL_COLUMN = "Label"

# Aliases seen across CICIDS2017 releases and community re-exports.
COLUMN_ALIASES: Dict[str, str] = {
    "src ip": "Source IP",
    "source ip": "Source IP",
    "src_ip": "Source IP",
    "srcip": "Source IP",
    "dst ip": "Destination IP",
    "destination ip": "Destination IP",
    "dst_ip": "Destination IP",
    "dstip": "Destination IP",
    "src port": "Source Port",
    "source port": "Source Port",
    "src_port": "Source Port",
    "dst port": "Destination Port",
    "destination port": "Destination Port",
    "dst_port": "Destination Port",
    "protocol": "Protocol",
    "proto": "Protocol",
    "timestamp": "Timestamp",
    "flow id": "Flow ID",
    "label": "Label",
}


class SchemaError(RuntimeError):
    """Raised when the CSVs cannot support the requested graph construction."""


@dataclass
class SchemaReport:
    variant: str  # "traffic_labelling" | "machine_learning_cve" | "unknown"
    has_ips: bool
    has_timestamp: bool
    has_protocol: bool
    n_columns: int
    rename_map: Dict[str, str]
    missing: List[str]
    path: str

    @property
    def supports_ip_graph(self) -> bool:
        return self.has_ips and self.has_timestamp

    def describe(self) -> str:
        lines = [
            f"file    : {Path(self.path).name}",
            f"variant : {self.variant}",
            f"columns : {self.n_columns}",
            f"IPs     : {'yes' if self.has_ips else 'NO'}",
            f"time    : {'yes' if self.has_timestamp else 'NO'}",
            f"protocol: {'yes' if self.has_protocol else 'NO'}",
        ]
        if self.missing:
            lines.append(f"missing : {self.missing}")
        return "\n".join("  " + ln for ln in lines)


def normalise_columns(columns) -> Dict[str, str]:
    """Map raw CSV column names -> canonical stripped names.

    Returns a rename dict suitable for ``df.rename(columns=...)``.
    """
    rename: Dict[str, str] = {}
    for col in columns:
        stripped = str(col).strip()
        canonical = COLUMN_ALIASES.get(stripped.lower(), stripped)
        if canonical != col:
            rename[col] = canonical
    return rename


def inspect_csv(path: str | Path) -> SchemaReport:
    """Read only the header row and classify the file."""
    path = str(path)
    header = pd.read_csv(path, nrows=0, low_memory=False, encoding_errors="replace")
    rename = normalise_columns(header.columns)
    canonical = {rename.get(c, str(c).strip()) for c in header.columns}

    has_ips = all(c in canonical for c in IP_COLUMNS)
    has_ts = TIMESTAMP_COLUMN in canonical
    has_proto = "Protocol" in canonical

    if has_ips and "Flow ID" in canonical:
        variant = "traffic_labelling"
    elif not has_ips and "Destination Port" in canonical:
        variant = "machine_learning_cve"
    else:
        variant = "unknown"

    missing = [c for c in IP_COLUMNS + [TIMESTAMP_COLUMN] if c not in canonical]

    return SchemaReport(
        variant=variant,
        has_ips=has_ips,
        has_timestamp=has_ts,
        has_protocol=has_proto,
        n_columns=len(header.columns),
        rename_map=rename,
        missing=missing,
        path=path,
    )


MLCVE_HELP = """
-------------------------------------------------------------------------
  WRONG CICIDS2017 DISTRIBUTION
-------------------------------------------------------------------------
The CSVs in your dataset directory are the 'MachineLearningCVE' export.
Its first column is ' Destination Port' and it contains 79 columns.
It has no Source IP, no Destination IP and no Timestamp.

An IP-as-node / flow-as-edge graph cannot be built from it. Neither can
per-host memory, subnet aggregation, or SDN drop rules -- all three need
an address to key on.

FIX: download the 'GeneratedLabelledFlows' / 'TrafficLabelling_' export of
the same dataset. The five filenames are identical, so it drops straight
into the same folder:

    Tuesday-WorkingHours.pcap_ISCX.csv
    Wednesday-workingHours.pcap_ISCX.csv
    Friday-WorkingHours-Morning.pcap_ISCX.csv
    Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv
    Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv

That export has 85 columns starting with:
    Flow ID, Source IP, Source Port, Destination IP, Destination Port,
    Protocol, Timestamp, ...

Source: https://www.unb.ca/cic/datasets/ids-2017.html
        (the "GeneratedLabelledFlows.zip" download, not "MachineLearningCSV.zip")

Note: TrafficLabelling_ CSVs are latin-1 encoded and the Thursday
afternoon file has a malformed header row. The loader in this package
already handles both.
-------------------------------------------------------------------------
""".strip()


def validate_dataset(
    dataset_dir: str | Path,
    csv_files: List[str],
    require_ips: bool = True,
    verbose: bool = True,
) -> Dict[str, SchemaReport]:
    """Inspect every expected CSV; raise with guidance if the variant is wrong."""
    dataset_dir = Path(dataset_dir)
    reports: Dict[str, SchemaReport] = {}
    missing_files: List[str] = []

    for fname in csv_files:
        fpath = dataset_dir / fname
        if not fpath.exists():
            missing_files.append(fname)
            continue
        reports[fname] = inspect_csv(fpath)

    if verbose:
        print("=" * 70)
        print("DATASET SCHEMA REPORT")
        print("=" * 70)
        for fname, rep in reports.items():
            print(rep.describe())
            print("-" * 70)
        if missing_files:
            print(f"MISSING FILES: {missing_files}")

    if not reports:
        raise SchemaError(
            f"No CSVs found in {dataset_dir}. Expected: {csv_files}"
        )

    variants = {r.variant for r in reports.values()}
    if require_ips and not all(r.supports_ip_graph for r in reports.values()):
        offenders = [f for f, r in reports.items() if not r.supports_ip_graph]
        msg = MLCVE_HELP if "machine_learning_cve" in variants else ""
        raise SchemaError(
            f"These files cannot support an IP-as-node graph: {offenders}\n\n{msg}"
        )

    if missing_files and verbose:
        print(f"WARNING: continuing without {len(missing_files)} missing file(s).")

    return reports
