"""Domain admission broker (phase 3B, D2): signed VerificationReceipts, typed event-condition-action rules, red/blue
role boundaries, and an ExecutionGate that admits a side-effect action only against a verified receipt bound to the
current state. Rejection has zero side effects (it rides on G2's send extension point). Reusable across domains
(MAL D1/D3, the local service D4, CAGE D5)."""

from __future__ import annotations

from .broker import DESCRIPTOR, BrokerDecision, BrokerGate, ReceiptStore, RequestBinding, admit
from .receipt import (
    CheckBasis,
    HmacSigner,
    HmacVerifier,
    KeyStore,
    ReceiptBindings,
    VerificationReceipt,
    digest_params,
    sign_receipt,
    signature_ok,
)
from .roles import RoleBoundary, red_blue_boundaries
from .rules import Handling, Rule, RuleSet, RuleStatus, condition, evaluate


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import broker

    return [PluginRegistration(broker.DESCRIPTOR, broker.create_gate)]


__all__ = [
    "DESCRIPTOR",
    "BrokerDecision",
    "BrokerGate",
    "CheckBasis",
    "Handling",
    "HmacSigner",
    "HmacVerifier",
    "KeyStore",
    "ReceiptBindings",
    "ReceiptStore",
    "RequestBinding",
    "RoleBoundary",
    "Rule",
    "RuleSet",
    "RuleStatus",
    "VerificationReceipt",
    "admit",
    "condition",
    "digest_params",
    "evaluate",
    "red_blue_boundaries",
    "registrations",
    "sign_receipt",
    "signature_ok",
]
