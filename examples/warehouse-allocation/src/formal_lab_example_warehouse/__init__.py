"""Warehouse resource allocation example: a second, independently implemented semantic profile
(`warehouse_alloc_v1`) with its driver, frontend, rule strategy and scorer — reached by the platform only through
plugin interfaces (P2-012)."""

from .model import NAMESPACE, PROFILE, SCHEMA_ID, WarehouseModel, demo_model


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import driver, plugins

    return [
        PluginRegistration(driver.DESCRIPTOR, driver.create),
        PluginRegistration(plugins.FRONTEND, plugins.create_frontend),
        PluginRegistration(plugins.RULES, plugins.create_rules),
        PluginRegistration(plugins.SCORER, plugins.create_scorer),
    ]


__all__ = ["NAMESPACE", "PROFILE", "SCHEMA_ID", "WarehouseModel", "demo_model", "registrations"]
