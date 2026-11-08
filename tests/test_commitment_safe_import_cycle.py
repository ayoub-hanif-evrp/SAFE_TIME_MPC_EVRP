"""Clean-process import regressions (CI smoke circular-import guard)."""

from __future__ import annotations

import subprocess
import sys


def test_episode_imports_in_clean_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from safe_time_evrp.controllers.episode import run_episode; print(run_episode.__name__)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "run_episode" in proc.stdout


def test_public_snapshot_imports_without_episode():
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot; print('ok')",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
