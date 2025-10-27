# ai-generators/generate_files_from_xlsx.py
import os
import sys
import re
import json
import math
import argparse
from datetime import datetime, date
from typing import Any, Dict, List

import pandas as pd
import numpy as np

# =========================
# Helpers
# =========================

def slugify(text: Any) -> str:
    """Generate clean, URL-friendly slug from text."""
    if text is None:
        return "untitled"
    s = str(text).strip().lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s or "untitled"

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def is_nanlike(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == "")

def to_json_compatible(value: Any) -> Any:
    """Convert Pandas/NumPy/Timestamp objects to JSON-safe primitives."""
    if isinstance(value, (pd.Timestamp, datetime, date)):
        # ISO date or datetime
        # If timestamp has time component:
        try:
            if isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
        except Exception:
            pass
        # If midnight and no tz, keep date-only string
        try:
            if isinstance(value, datetime) and (value.hour != 0 or value.minute != 0 or value.second != 0):
                return value.isoformat()
            if isinstance(value, (datetime, date)):
                return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
        except Exception:
            return str(value)

    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(value, (np.bool_)):
        return bool(value)

    if isinstance(value, pd.Series):
        return to_json_compatible(value.to_dict())

    if isinstance(value, dict):
        return {str(k): to_json_compatible(v) for k, v in value.items()}

    if isinstance(value, list):
        return [to_json_compatible(v) for v in value]

    return value

def row_to_clean_dict(row: pd.Series) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for col in row.index:
        val = row[col]
        if pd.isna(val):
            continue
        # Convert Excel numbers that are actually ints
        if hasattr(val, "item"):
            try:
                val = val.item()
            except Exception:
                pass
        val = to_json_compatible(val)
        if val is None:
            continue
        out[str(col)] = val
    return out

def write_json(path: str, payload: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def write_md_with_frontmatter(path: str, fm: Dict[str, Any], body: str) -> None:
    ensure_dir(os.path.dirname(path))
    # Make frontmatter strings JSON-safe
    fm_clean = {k: to_json_compatible(v) for k, v in fm.items() if not is_nanlike(v)}
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        for k, v in fm_clean.items():
            # write simple YAML scalars/arrays
            if isinstance(v, list):
                f.write(f"{k}:\n")
                for item in v:
                    f.write(f"  - {item}\n")
            else:
                f.write(f"{k}: {v}\n")
        f.write("---\n\n")
        f.write(body or "")

def cleaned_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip]()
