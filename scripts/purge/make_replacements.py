#!/usr/bin/env python3
"""Write a git filter-repo --replace-text file from planted.json.

--mode naive    : what an operator would typically list: the raw values that
                  the scanner reported (decoded), plus the short admin password.
--mode complete : also lists encoded variants (base64, URL-encoded).
--mode revised  : complete + the short value only in its assignment context (regex).
--no-short      : leave out the short value ("password") to avoid collateral damage.
The output file contains secret values: keep it outside the repository and
delete it afterwards.
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--planted", default=str(Path.home() / "purge-verify-work/planted.json"))
ap.add_argument("--out", required=True)
ap.add_argument("--mode", choices=["naive", "complete", "revised"], default="naive")
ap.add_argument("--no-short", action="store_true")
a = ap.parse_args()
d = json.loads(Path(a.planted).read_text())
v = d["values"]
ids = ["CLOUD_KEY", "WEBHOOK_TOKEN", "DB_PASSWORD", "SESSION_SECRET", "LEGACY_EXPORT_KEY",
       "STG_TOKEN", "B64_SECRET", "CLIENT_SECRET", "NOTEBOOK_KEY", "BINARY_KEY", "PR_B_KEY"]
lines = [f"{v[i]}==>REMOVED_SECRET" for i in ids]
if a.mode in ("complete", "revised"):
    lines += [f"{d['derived'][k]}==>REMOVED_SECRET" for k in
              ("DB_PASSWORD_urlencoded", "B64_SECRET_base64")]
if a.mode == "revised":
    # short value: replace only in its assignment context, never as a bare word
    lines.append('regex:(ADMIN_PASSWORD\\s*=\\s*)"' + v['SHORT_PASSWORD'] + '"==>\\1"REMOVED_SECRET"')
elif not a.no_short:
    # literal replacement of a short, common word: collateral damage expected
    lines.append(f"{v['SHORT_PASSWORD']}==>REMOVED_SECRET")
Path(a.out).write_text("\n".join(lines) + "\n")
Path(a.out).chmod(0o600)
print(f"wrote {len(lines)} replacement rules to {a.out}")
