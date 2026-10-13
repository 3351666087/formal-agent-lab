"""The Struts/Equifax breach model (CVE-2017-5638): the multi-stage breach reaches exfiltration on an undefended,
vulnerable deployment, deploying every control stops it, and because each stage has two branches the minimum set of
controls that prevents the breach is two (cut both branches of any one stage). Ground truth is the Z3 verifier."""

from __future__ import annotations

from itertools import combinations

from formal_lab_contracts import CheckQuery
from formal_lab_domain_mal.cve_2017_5638 import GAME_SPEC, STAGE_VARS, all_controls, equifax_model
from formal_lab_solver_z3.verifier import Z3Verifier

BOUND = {"max_steps": 20, "timeout_ms": 15000}


def _breach(deployed=frozenset()):
    m = equifax_model(deployed=frozenset(deployed))
    v = Z3Verifier().check(m.package(), CheckQuery(kind="GOAL_REACHABILITY", property_id="data_exfiltrated",
                                                   bound=BOUND))
    return str(getattr(v.verdict, "value", v.verdict)) == "WITNESS"


def test_six_stages_and_twelve_controls():
    assert STAGE_VARS[0] == "foothold" and STAGE_VARS[-1] == "exfiltrated" and len(GAME_SPEC) == 6
    assert len(all_controls()) == 12


def test_unpatched_vulnerable_deployment_is_breached():
    assert _breach(frozenset()) is True  # the Equifax configuration: vulnerable Struts, no controls


def test_full_defence_prevents_breach():
    assert _breach(frozenset(all_controls())) is False


def test_breach_prevented_invariant_holds_when_fully_defended():
    m = equifax_model(deployed=frozenset(all_controls()))
    v = Z3Verifier().check(m.package(), CheckQuery(kind="INVARIANT_VIOLATION", property_id="breach_prevented",
                                                   bound=BOUND))
    assert str(getattr(v.verdict, "value", v.verdict)) == "NO_WITNESS_WITHIN_BOUND"


def test_minimum_two_controls_prevent_the_breach():
    ctrls = all_controls()
    assert all(_breach(frozenset([c])) for c in ctrls)  # no single control cuts every path (each stage has 2 branches)
    two = next((combo for combo in combinations(ctrls, 2) if not _breach(frozenset(combo))), None)
    assert two is not None  # some pair (both branches of one stage) stops it
