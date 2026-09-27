"""Local order service example (P2-060 … P2-069): an independent business service (FastAPI + SQLite) with its
environment adapter, lifecycle manager, probe, rule strategy and scorer, next to a pure-data model of the same
order handling. Importing this package does not import the platform (the service container needs only FastAPI)."""


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import env, plugins

    return [
        PluginRegistration(env.DESCRIPTOR, env.create),
        PluginRegistration(plugins.PROBE, plugins.create_probe),
        PluginRegistration(plugins.RULES, plugins.create_rules),
        PluginRegistration(plugins.SCORER, plugins.create_scorer),
    ]


__all__ = ["registrations"]
