"""The Log4Shell (CVE-2021-44228) attack/defence model: the vulnerable Log4j 2.14.1 reaches RCE, the fixed 2.16.0
does not, and because the published attack chain is sequential any single control in it breaks the chain (defence in
depth). Ground truth is the Z3 verifier on the formal model."""

from __future__ import annotations

import pytest
from formal_lab_contracts import CheckQuery
from formal_lab_domain_mal.cve_2021_44228 import MITIGATIONS, log4shell_model
from formal_lab_solver_z3.verifier import Z3Verifier

BOUND = {"max_steps": 20, "timeout_ms": 15000}


def _rce(version, mitigations=frozenset()):
    m = log4shell_model(version=version, mitigations=frozenset(mitigations))
    v = Z3Verifier().check(m.package(), CheckQuery(kind="GOAL_REACHABILITY", property_id="rce_achieved", bound=BOUND))
    return str(getattr(v.verdict, "value", v.verdict)) == "WITNESS"


def test_vulnerable_2_14_1_reaches_rce():
    assert _rce("2.14.1") is True


@pytest.mark.parametrize("version", ["2.15.0", "2.16.0", "2.17.1"])
def test_fixed_versions_block_rce(version):
    assert _rce(version) is False  # the fix flips message_lookups / jndi so the chain cannot complete


def test_fixed_version_no_rce_invariant_holds():
    m = log4shell_model(version="2.16.0")
    v = Z3Verifier().check(m.package(), CheckQuery(kind="INVARIANT_VIOLATION", property_id="no_rce", bound=BOUND))
    assert str(getattr(v.verdict, "value", v.verdict)) == "NO_WITNESS_WITHIN_BOUND"


@pytest.mark.parametrize("mitigation", ["formatMsgNoLookups", "disable_jndi", "remove_jndi_class",
                                        "block_egress", "input_validation", "remove_gadget"])
def test_any_single_mitigation_breaks_the_chain(mitigation):
    assert mitigation in MITIGATIONS
    assert _rce("2.14.1", {mitigation}) is False  # one control anywhere on the sequential chain stops RCE
