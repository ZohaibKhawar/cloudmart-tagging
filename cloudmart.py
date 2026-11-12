"""Shared helpers for the CloudMart tagging activity (used by app.py).

The notebook (eda.ipynb) does the same steps inline so each one can be read.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

# Tag fields scored in the completeness score (3.1).
TAG_FIELDS = ["Department", "Project", "Environment", "Owner", "CostCenter", "CreatedBy"]
# A resource counts as "Tagged" only when all of these are filled in.
# This rule reproduces the dataset's own Tagged column exactly.
REQUIRED_TAGS = ["Department", "Project", "Environment", "Owner", "CostCenter"]
# Columns that keep their place at the end of a row that is short of fields.
TRAILING = ["CreatedBy", "MonthlyCostUSD", "Tagged"]

MISSING_LABEL = "(missing)"


def _read_text(source) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).read_text(encoding="utf-8-sig")
    data = source.read() if hasattr(source, "read") else source
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig")
    return data


def load_raw(source):
    """Read the CloudMart CSV and repair its two format problems.

    1. Every line is wrapped in one pair of quotes, so a plain pd.read_csv sees a
       single column. Such lines are unwrapped and split again.
    2. Some rows are short of fields (``...,us-west-1,,,,Manual,45,No``). The last
       three values are always CreatedBy, MonthlyCostUSD and Tagged, so they are
       kept at the end and the missing tag fields are left blank.

    Returns (dataframe, notes) where notes describes what was repaired.
    """
    text = _read_text(source)
    header, rows = None, []
    unwrapped = short = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        vals = next(csv.reader([line]))
        if len(vals) == 1 and "," in vals[0]:
            vals = next(csv.reader([vals[0]]))
            unwrapped += 1
        vals = [v.strip() for v in vals]
        if header is None:
            header = vals
            continue
        if len(vals) < len(header):
            short += 1
            lead = header.index("Department")
            n_tail = len(header) - header.index(TRAILING[0])
            middle = vals[lead:len(vals) - n_tail]
            middle += [""] * (len(header) - lead - n_tail - len(middle))
            vals = vals[:lead] + middle + vals[len(vals) - n_tail:]
        rows.append(vals[: len(header)])

    df = pd.DataFrame(rows, columns=header)
    df = df.replace("", pd.NA)
    df["MonthlyCostUSD"] = pd.to_numeric(df["MonthlyCostUSD"], errors="coerce").fillna(0.0)
    df["Tagged"] = df["Tagged"].fillna("No").str.strip().str.capitalize()
    notes = {
        "rows_read": len(df),
        "lines_unwrapped": unwrapped,
        "short_rows_fixed": short,
        "duplicate_rows": int(df.duplicated().sum()),
    }
    return df, notes


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows (each resource appears once)."""
    return df.drop_duplicates().reset_index(drop=True)


def load(source):
    raw, notes = load_raw(source)
    return clean(raw), notes


def completeness(df: pd.DataFrame) -> pd.Series:
    """How many of the six tag fields are filled in (0-6)."""
    fields = [c for c in TAG_FIELDS if c in df.columns]
    return df[fields].notna().sum(axis=1)


def recompute_tagged(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    req = [c for c in REQUIRED_TAGS if c in out.columns]
    filled = out[req].apply(lambda s: s.astype("string").str.strip().fillna("") != "")
    owner_ok = out["Owner"].astype("string").str.contains("@", na=False) if "Owner" in out else True
    out["Tagged"] = (filled.all(axis=1) & owner_ok).map({True: "Yes", False: "No"})
    return out


def summary(df: pd.DataFrame) -> dict:
    total = float(df["MonthlyCostUSD"].sum())
    unt = df["Tagged"].eq("No")
    unt_cost = float(df.loc[unt, "MonthlyCostUSD"].sum())
    n = len(df)
    return {
        "resources": n,
        "tagged": int((~unt).sum()),
        "untagged": int(unt.sum()),
        "untagged_pct": (unt.sum() / n * 100) if n else 0.0,
        "total_cost": total,
        "tagged_cost": total - unt_cost,
        "untagged_cost": unt_cost,
        "untagged_cost_pct": (unt_cost / total * 100) if total else 0.0,
        "visibility_pct": ((total - unt_cost) / total * 100) if total else 0.0,
    }


def _mode_map(df: pd.DataFrame, key: str, value: str) -> dict:
    sub = df[[key, value]].dropna()
    if sub.empty:
        return {}
    return sub.groupby(key)[value].agg(lambda s: s.mode().iloc[0]).to_dict()


def suggest_tags(df: pd.DataFrame):
    """Fill missing tags from what the tagged resources already tell us.

    Rules, in order:
      1. Department and CostCenter from the AccountID (each linked account
         belongs to one department and one cost center).
      2. Owner from the Department (each department has one named owner).
      3. Project from a tagged resource in the same account, service and region.
      4. Environment: when the same account/service/region/project already has
         a Prod resource, this second copy is treated as Dev (the dataset's
         xxx-001 Prod / xxx-002 Dev pattern). Flagged for the owner to confirm.

    Returns (filled dataframe, log dataframe).
    """
    out = df.copy()
    tagged = out[out["Tagged"] == "Yes"]
    acct_dept = _mode_map(out, "AccountID", "Department")
    acct_cc = _mode_map(out, "AccountID", "CostCenter")
    dept_owner = _mode_map(tagged, "Department", "Owner")
    log = []

    def setv(i, col, val, rule, confirm=False):
        log.append({
            "ResourceID": out.at[i, "ResourceID"],
            "Field": col,
            "Before": "" if pd.isna(out.at[i, col]) else out.at[i, col],
            "After": val,
            "Rule": rule,
            "NeedsOwnerConfirmation": "Yes" if confirm else "No",
        })
        out.at[i, col] = val

    for i in out.index:
        acct = out.at[i, "AccountID"]
        if pd.isna(out.at[i, "Department"]) and acct in acct_dept:
            setv(i, "Department", acct_dept[acct], f"Account {acct} belongs to {acct_dept[acct]}")
        if pd.isna(out.at[i, "CostCenter"]) and acct in acct_cc:
            setv(i, "CostCenter", acct_cc[acct], f"Account {acct} bills to {acct_cc[acct]}")
        dept = out.at[i, "Department"]
        if pd.isna(out.at[i, "Owner"]) and dept in dept_owner:
            setv(i, "Owner", dept_owner[dept], f"Owner of the {dept} department")
        if pd.isna(out.at[i, "Project"]):
            sib = tagged[(tagged["AccountID"] == acct)
                         & (tagged["Service"] == out.at[i, "Service"])
                         & (tagged["Region"] == out.at[i, "Region"])]
            if not sib.empty:
                proj = sib["Project"].mode().iloc[0]
                setv(i, "Project", proj,
                     f"Same account, service and region as {sib['ResourceID'].iloc[0]} ({proj})",
                     confirm=True)
        if pd.isna(out.at[i, "Environment"]):
            sib = out[(out.index != i)
                      & (out["AccountID"] == acct)
                      & (out["Service"] == out.at[i, "Service"])
                      & (out["Region"] == out.at[i, "Region"])
                      & (out["Project"] == out.at[i, "Project"])]
            if (sib["Environment"] == "Prod").any():
                twin = sib.loc[sib["Environment"] == "Prod", "ResourceID"].iloc[0]
                setv(i, "Environment", "Dev",
                     f"Second copy of Prod resource {twin} (xxx-001 Prod / xxx-002 Dev pattern)",
                     confirm=True)

    return recompute_tagged(out), pd.DataFrame(log)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
