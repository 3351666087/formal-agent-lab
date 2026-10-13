# Phase 8 handoff — real attack models in the security project

A self-initiated, user-driven expansion of the security domain. After several rounds of feedback the security work
converged on **real attack models** — meaningful security state and attack techniques, verified by Z3 — and anything
that was not a real attack model was removed from the platform and the repository.

Task book: [`../execution/phase-8.md`](../execution/phase-8.md). Earlier closeout: [`phase7.md`](phase7.md).

## What a "real attack model" is here

Not a flat graph of `compromised[step]`/`hardened[step]` (a reachability abstraction), but a model whose **state is
real security posture** and whose **actions are attack techniques** with genuine preconditions and effects. Defences
are model constants that gate techniques. The attacker's goal is reached by a **Z3 plan**, and the ground truth for
every question is the Z3 verifier on the model.

### 1. Enterprise attack model — `packages/domain-mal/attack_model.py`
`enterprise_attack_model(scale, defenses)`: state is `reach_dmz`/`reach_internal`, `foothold_<host>`, `admin_<host>`,
`stolen_<cred>`, `exfiltrated`; techniques are exploit / phish / steal-credential / authenticate / escalate /
kerberoast / leak-CI-secrets / exfiltrate; defences (patching / MFA / segmentation) are constants. At scale 3: **32
state variables, 33 techniques**, two independent paths to the DB-admin credential so the minimum defence set is
non-trivial. Seeded into the security project with a red-team scenario and an executed run (`scripts/
seed_security_enterprise.py`).

### 2. Log4Shell — a real CVE — `packages/domain-mal/cve_2021_44228.py`
A formal attack/defence model of **CVE-2021-44228** in **Apache Log4j 2** (github.com/apache/logging-log4j2). The
published chain as techniques — attacker input logged → JNDI lookup triggered → attacker endpoint contacted →
malicious reference returned → remote class loaded → RCE — with the version and operator mitigations as constants.
Z3 ground truth, confirmed by `test_cve_log4shell.py`:
- **RCE is reachable in the vulnerable 2.14.1** and **blocked in 2.15.0 / 2.16.0 / 2.17.1** (the fix flips message
  lookups / JNDI).
- The 6-step chain is sequential, so **any one of six single controls** (`formatMsgNoLookups`, `disable_jndi`,
  `remove_jndi_class`, `block_egress`, `input_validation`, `remove_gadget`) alone stops RCE — defence in depth,
  proven, not asserted.

Seeded into the security project (`scripts/seed_cve_log4shell.py`): the **vulnerable 2.14.1** red-team run reaches RCE
(SUCCEEDED); the **fixed 2.16.0** run cannot (BUDGET_EXHAUSTED) — the fix holds, on the platform.

## The LLM study (over the real model)

`research/studies/cyber-attackmodel` — hard, Z3-grounded questions over the real enterprise attack model: shortest
attack plan to exfiltration (offence), reachability under a deployed defence set (defence), minimum defences to stop
exfiltration (defence), technique applicability in a given state. Two strong relay models (`gpt-6-astra`,
`claude-opus-5-5`). The scorer is `attackgraph.analysis@1`; the check is `scripts/cyber_attackmodel_check.py`
(group `p8`): the study validates and is data-separated, a committed attack model is Z3-solvable to exfiltration, the
Log4Shell model is faithful (vulnerable→RCE, fixed→blocked), and the scorer is loopback-verified.

## Removed (not a real attack model)

The earlier attack-**graph** work (the `compromised`/`hardened` reachability abstraction) was deleted from the
platform (old security project dropped, recreated clean) **and** the repository: `analysis.py`, the attack-graph study
/ check / run scripts, and the `cyber-attackgraph` / `cyber-enterprise` studies and results. Only real attack models
remain.

## Caveats (unchanged)

- The models are abstract formal models for **defensive** analysis — named conditions, not exploits.
- The LLM study's two models answer through a relay (relay-reported identity), so it is a discriminating,
  verifier-grounded experiment, not a verified provider ranking.

```bash
uv run --frozen pytest packages/domain-mal/tests/test_cve_log4shell.py   # the CVE model
make research-check ARGS="--group p8"                                    # the attack-model + CVE check
uv run --frozen python scripts/seed_security_enterprise.py               # seed the enterprise attack model + run
uv run --frozen python scripts/seed_cve_log4shell.py                     # seed Log4Shell vulnerable + fixed + runs
```
