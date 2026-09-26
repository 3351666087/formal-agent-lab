"""Z3 adapter: IR compiler, bounded verifier and bounded planner."""

from formal_lab_contracts.interfaces import PluginRegistration


def registrations() -> list[PluginRegistration]:
    from . import planner, verifier

    return [PluginRegistration(verifier.DESCRIPTOR, verifier.create),
            PluginRegistration(planner.DESCRIPTOR, planner.create)]
