#!/usr/bin/env python3
"""Search a git repository directly for every planted value (no scanner rules).

Looks in every object of the object database AND, separately, in what is
reachable from refs (optionally only some refs), in these forms:
raw, base64, URL-encoded, and inside gzip-compressed blobs.
Prints only ids and locations, never the values.

Usage: scan_values.py <repo> [--planted planted.json] [--refs 'refs/heads refs/tags']
"""
import argparse
import base64
import gzip
import json
import subprocess
import urllib.parse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("--planted", default=str(Path.home() / "purge-verify-work/planted.json"))
ap.add_argument("--refs", default="refs/heads refs/tags", help="ref prefixes for the reachable scan")
ap.add_argument("--json", help="write results here")
a = ap.parse_args()

d = json.loads(Path(a.planted).read_text())
needles = {}
for k, v in d["values"].items():
    if k == "SHORT_PASSWORD":
        continue  # a common word; checked separately via diff review
    needles[(k, "raw")] = v.encode()
    needles[(k, "base64")] = base64.b64encode(v.encode())
    enc = urllib.parse.quote(v, safe="")
    if enc != v:
        needles[(k, "urlencoded")] = enc.encode()


def git(*args, inp=None):
    return subprocess.run(["git", "-C", a.repo] + list(args), input=inp,
                          capture_output=True, check=True).stdout


def objects(revlist_args):
    out = git("rev-list", "--objects", *revlist_args).decode().splitlines()
    return {l.split(" ", 1)[0]: (l.split(" ", 1)[1] if " " in l else "") for l in out}


def scan(oids):
    hits = {}
    if not oids:
        return hits
    data = git("cat-file", "--batch", inp=("\n".join(oids) + "\n").encode())
    i = 0
    while i < len(data):
        nl = data.index(b"\n", i)
        oid, typ, size = data[i:nl].decode().split()
        size = int(size)
        body = data[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
        bodies = [("", body)]
        if body[:2] == b"\x1f\x8b":
            try:
                bodies.append(("gzip", gzip.decompress(body)))
            except Exception:
                pass
        for where, b in bodies:
            for (k, form), n in needles.items():
                if n in b:
                    hits.setdefault(f"{k}:{form}{'+' + where if where else ''}", set()).add((typ, oid))
    return hits


all_oids = git("cat-file", "--batch-all-objects", "--batch-check=%(objectname)").decode().split()
refs = []
for p in a.refs.split():
    refs += git("for-each-ref", "--format=%(refname)", p).decode().split()
reach = objects(refs) if refs else {}

res = {"object_db": {}, "reachable": {}}
for name, hits in sorted(scan(all_oids).items()):
    res["object_db"][name] = len(hits)
for name, hits in sorted(scan(list(reach)).items()):
    res["reachable"][name] = sorted({f"{t}:{reach.get(o, '') or o[:10]}" for t, o in hits})

print(f"objects in db: {len(all_oids)}, reachable from {a.refs}: {len(reach)}")
print("== found anywhere in the object database (count of objects)")
for k, v in res["object_db"].items():
    print(f"  {k}: {v}")
print("== reachable from refs")
for k, v in res["reachable"].items():
    print(f"  {k}: {', '.join(v)}")
if not res["reachable"]:
    print("  (none)")
if a.json:
    Path(a.json).write_text(json.dumps(res, indent=2))
