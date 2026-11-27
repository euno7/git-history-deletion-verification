#!/usr/bin/env python3
"""Build a large LOCAL-ONLY dummy repository with git fast-import and time
filter-repo / gitleaks on it. Never pushed.

Usage: bench_large.py --commits 10000 --files 2000 --out ~/purge-verify-work/bench
"""
import argparse
import json
import os
import secrets
import shutil
import string
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--commits", type=int, default=10000)
ap.add_argument("--files", type=int, default=2000)
ap.add_argument("--blob-kb", type=int, default=4)
ap.add_argument("--out", default=str(Path.home() / "purge-verify-work/bench"))
ap.add_argument("--gitleaks-config", required=True)
a = ap.parse_args()

out = Path(a.out).expanduser() / f"c{a.commits}"
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
src = out / "src.git"
env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
subprocess.run(["git", "init", "-q", "--bare", str(src)], check=True, env=env)
key = "FAKESECRET_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

t0 = time.time()
p = subprocess.Popen(["git", "-C", str(src), "fast-import", "--quiet"], stdin=subprocess.PIPE, env=env)
w = p.stdin.write
filler = ("x" * 63 + "\n") * (a.blob_kb * 16)
ts = 1767225600
for i in range(1, a.commits + 1):
    path = f"src/mod{i % a.files:05d}.py"
    content = f"# revision {i}\n" + filler
    if i in (a.commits // 10, a.commits // 2):
        content += f'KEY = "{key}"\n'
    data = content.encode()
    msg = f"Change {path} ({i})".encode()
    w(b"commit refs/heads/main\n")
    w(f"committer Bench <bench@users.noreply.example.invalid> {ts + i * 60} +0000\n".encode())
    w(f"data {len(msg)}\n".encode() + msg + b"\n")
    w(f"M 100644 inline {path}\n".encode())
    w(f"data {len(data)}\n".encode() + data + b"\n")
    if i == a.commits // 10:
        env_data = f"SECRET={key}\n".encode()
        w(b"M 100644 inline .env\n" + f"data {len(env_data)}\n".encode() + env_data + b"\n")
p.stdin.close()
p.wait()
build = time.time() - t0
subprocess.run(["git", "-C", str(src), "gc", "-q", "--aggressive"], env=env)
size = subprocess.run(["git", "-C", str(src), "count-objects", "-vH"], capture_output=True, text=True, env=env).stdout


def timed(label, cmd, cwd=None):
    t = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    dt = time.time() - t
    print(f"{label}: {dt:.2f}s (exit {r.returncode})")
    return dt, r


res = {"commits": a.commits, "files": a.files, "build_s": round(build, 1)}
mirror = out / "mirror.git"
res["clone_mirror_s"], _ = timed("clone --mirror (local)", ["git", "clone", "-q", "--mirror", str(src), str(mirror)])
repl = out.parent / f"repl-{a.commits}.txt"
repl.write_text(f"{key}==>REMOVED_SECRET\n")
res["gitleaks_before_s"], _ = timed("gitleaks before", ["gitleaks", "git", "--config", a.gitleaks_config,
                                    "--log-opts=--all", "--redact", "--no-banner", str(mirror)])
res["replace_text_s"], _ = timed("filter-repo --replace-text", ["git", "filter-repo", "--force", "--replace-text", str(repl)], cwd=mirror)
res["invert_paths_s"], _ = timed("filter-repo --invert-paths", ["git", "filter-repo", "--force", "--invert-paths", "--path", ".env"], cwd=mirror)
res["gitleaks_after_s"], r = timed("gitleaks after", ["gitleaks", "git", "--config", a.gitleaks_config,
                                    "--log-opts=--all", "--redact", "--no-banner", str(mirror)])
res["gitleaks_after_exit"] = r.returncode
res["size"] = {l.split(":")[0]: l.split(":")[1].strip() for l in size.splitlines() if ":" in l}
repl.unlink()
print(json.dumps(res, indent=2))
(out / "result.json").write_text(json.dumps(res, indent=2))
