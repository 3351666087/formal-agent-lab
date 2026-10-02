"""Subprocess environment adapter example (phase 4A, A4): `adapter` (the plugin, parent side) and `world` (the child
process). See the adapter's module docstring for what a later process-backed adapter has to make explicit."""

from .adapter import DESCRIPTOR, ENV_ID, ENV_VERSION, SubprocessWorldEnvironment, create

__all__ = ["DESCRIPTOR", "ENV_ID", "ENV_VERSION", "SubprocessWorldEnvironment", "create", "registrations"]


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    return [PluginRegistration(DESCRIPTOR, create)]
