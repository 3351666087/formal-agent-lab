"""CAGE Challenge 4 (phase 3B D5, phase 4B B2): CybORG 4.0 in an isolated venv reached through typed subprocesses.

- `bridge`     — one-shot worker commands (versions, the official scripted baseline, describe, the native direct path);
- `model`      — the `cage4_v1` blue-interface model and its semantic driver (`formal-lab.driver.cage4`);
- `adapter`    — the platform environment `formal-lab.env.cage4` (one joint batch = one native world step);
- `strategies` — blue planners: mapped native baselines (sleep, monitor) and a platform rule (react);
- `metrics`    — `formal-lab.cage4.metrics`: CybORG's native score apart from platform metrics;
- `trajectory` — native direct path vs platform path, world step by world step.

CybORG's dependencies never enter the platform environment: only `_worker.py` (run by the venv's Python) imports it.
"""

from __future__ import annotations

from . import bridge

__all__ = ["bridge", "registrations"]


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import adapter, metrics, model, strategies

    return [PluginRegistration(model.DESCRIPTOR, model.create_driver),
            PluginRegistration(adapter.DESCRIPTOR, adapter.create),
            PluginRegistration(strategies.SLEEP, strategies.create_sleep),
            PluginRegistration(strategies.MONITOR, strategies.create_monitor),
            PluginRegistration(strategies.REACT, strategies.create_react),
            PluginRegistration(metrics.DESCRIPTOR, metrics.create)]
