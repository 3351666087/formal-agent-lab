#!/usr/bin/env python3
"""Refuse a heavy step (image builds, kind clusters, offline bundles) that would fill the disk.

    python3 scripts/disk_guard.py --need 12 [--label "helm upgrade"] [--trim]

Two filesystems matter and both are read from inside the VM:
- the host disk: the repository is shared from macOS (virtiofs), so statvfs() on it reports the Mac's free space —
  and the Colima VM disks are sparse files on that same disk, so everything Docker writes in the VM grows there too;
- /var/lib/docker inside the VM.
Exit 1 (with the numbers) when either has less than --need GiB free. `--trim` first returns blocks freed inside the
VM to the host (`sudo fstrim`), the only way deleted images give space back to macOS. On 2026-09-28 a full host disk
aborted the VM's Docker-disk journal (write errors, lost image layers); this guard exists so that cannot recur.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_gib(path: str | Path) -> float | None:
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    return round(st.f_bavail * st.f_frsize / 2**30, 1)


def trim() -> str:
    targets = [m for m in ("/mnt/lima-colima", "/") if os.path.ismount(m)]
    if not targets or not shutil.which("fstrim"):
        return "fstrim not available"
    out = []
    for target in targets:  # fstrim takes one mount point per call
        res = subprocess.run(["sudo", "-n", "fstrim", "-v", target], capture_output=True, text=True)
        out.append((res.stdout or res.stderr).strip())
    return "; ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", type=float, required=True, help="GiB the step may write (plus a reserve)")
    ap.add_argument("--label", default="this step")
    ap.add_argument("--trim", action="store_true")
    args = ap.parse_args()
    if args.trim:
        print(f"disk-guard: {trim()}")
    readings = {"host (repository filesystem)": free_gib(ROOT), "docker data (/var/lib/docker)": free_gib("/var/lib/docker")}
    short = {k: v for k, v in readings.items() if v is not None and v < args.need}
    shown = ", ".join(f"{k} {v} GiB free" for k, v in readings.items() if v is not None)
    if short:
        print(f"disk-guard: refusing {args.label}: needs {args.need} GiB; {shown}. Free space on the host "
              f"(and run `sudo fstrim -av` in the VM) first.", file=sys.stderr)
        return 1
    print(f"disk-guard: {args.label}: {shown} (needs {args.need} GiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
