"""Write the phase-6A study definitions (fal-research-study/v1) from recorded data — never by hand-copying numbers.

  research/studies/p6a-protocol/   machinery validation against the loopback protocol test service (not a model):
                                   one ordinary-business task (implementation_conformance) and four harmless synthetic
                                   planning tasks in two representations (synthetic_representation)
  research/studies/p6a-real/       the minimal real calls: the ordinary-business task only, GPT-6 Astra through the
                                   configured relay and Claude Opus 5.5 through its native API (blocked without an
                                   authorized credential)

The ordinary task comes from case orders-p2-speed (phase 5A): the belief model's mechanics, the instance and the
recorded run's differences are quoted from the case; the operating condition that produced them (the answer) stays
in the scorer's reference only. Synthetic tasks use formal_lab_model.samples (a lamp counter, a short route); their
reference lengths are computed by breadth-first search on the reference interpreter.

    scripts/in-vm.sh 'uv run --frozen python scripts/p6a_studies.py'
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "research" / "cases" / "orders-p2-speed"
STUDIES = ROOT / "research" / "studies"

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {"constant": {"type": "string"}, "station": {"type": "string"}, "value": {"type": "boolean"},
                   "rationale": {"type": "string"}},
    "required": ["constant", "station", "value"], "additionalProperties": False,
}
PLAN_SCHEMA = {
    "type": "object",
    "properties": {"reachable": {"type": "boolean"}, "plan": {"type": "array", "items": {"type": "string"}},
                   "rationale": {"type": "string"}},
    "required": ["reachable", "plan"], "additionalProperties": False,
}
DIAGNOSIS_PURPOSE = ("explain why a formal model of a local order-processing service mispredicts the real service, by "
                     "proposing one revision of a model constant (software model verification)")
PLAN_PURPOSE = ("solve a small, harmless planning problem stated in a given representation (a study of how the "
                "representation of the same problem affects answers)")
PROSE = {
    "lamp": ("A lamp is off and its toggle counter is 0. The counter can only hold the values 0 to 3.\n\n"
             "Actions:\n"
             "- toggle — switches the lamp (off to on, on to off) and adds 1 to the counter. It cannot be done when "
             "the counter is already 3.\n"
             "- reset — sets the counter to 0 and switches the lamp off. It can only be done when the counter is "
             "above 0.\n\n"
             "Goal three_toggles: the counter equals 3.\n"),
    "shortcut": ("A traveller is at position 0 of a route with positions 0 to 3 and has taken 0 express rides (the "
                 "ride count can hold 0 to 3).\n\n"
                 "Actions:\n"
                 "- express — only possible at position 0; moves the traveller to position 3 and adds 1 to the express "
                 "rides. It costs 10.\n"
                 "- walk — possible while the position is below 3; moves the traveller forward by 1. It costs 1.\n\n"
                 "Goal arrived: the position equals 3. (The question asks for the fewest actions, not the lowest "
                 "cost.)\n"),
}
SYNTHETIC = [("lamp", "three_toggles", 6), ("shortcut", "arrived", 4)]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def orders_brief() -> tuple[str, str, dict]:
    """(brief, candidates, reference) for the deviation-diagnosis task, from the 5A case artifacts."""
    case = json.loads((CASE / "case.json").read_text())
    art = {a["id"]: a for a in case["artifacts"]}
    model = json.loads((CASE / art["model-v1"]["path"]).read_text())
    conf = json.loads((CASE / art["conf-v1"]["path"]).read_text())
    fixture = json.loads((CASE / art["fixture-deviation"]["path"]).read_text())
    inst = fixture["instance"]  # the operating conditions (the answer) are NOT quoted
    actions: dict[int, str] = {}
    for item in conf["items"]:
        actions.setdefault(item["step"], item["action"])
    diffs = [i for i in conf["items"] if i["status"] == "DIFFERENT"]
    consts = {c["name"]: c for c in model["payload"]["ir"]["constants"]}
    slow = consts["slow"]
    rows = "\n".join(f"| {o['order_id']} | {o['proc_time']} | {o['arrive_at']} | {o['due']} | {o['sku']} | {o['qty']} |"
                     for o in inst["orders"])
    seq = ", ".join(f"{s} {a}" for s, a in sorted(actions.items()))
    drows = "\n".join(f"| {d['step']} | {d['action']} | {d['element']} | {d['predicted']} | {d['observed']} |"
                      for d in diffs)
    brief = f"""# Order service: a formal model that mispredicts the real service

## The service and its model (belief model `{model['package_id']}` version {model['version']})
A local order-processing service handles orders on processing stations {', '.join(inst['stations'])}. Its formal
model (deterministic, finite) has the actions reserve(o), enqueue(o), start(o, st), tick() and restock(sku):

- start(o, st): the head of the queue starts on a free station; its remaining processing time is set to the
  order's processing time.
- tick(): logical time advances by 1 and every processing order advances — its remaining time decreases by 1,
  except on a station whose constant slow[st] is true, which advances only on every other tick (when tick_parity
  is true). An order whose remaining time runs out completes and leaves its station.

Model constants: sku_of[order], qty[order], arrive_at[order], due[order] (instance data) and slow[station]
(boolean — "{slow.get('description', '')}"). In this model version slow is false for every station.

## Instance (case `{inst['case']}`, seed {inst['seed']})
| order | processing time | arrives at | due | sku | qty |
|---|---|---|---|---|---|
{rows}

## The recorded run on the real service, replayed on the model
Actions in order: {seq}.

Where the model's prediction and the service's reported state differ (every other compared field matches):

| step | action | location | model predicted | service reported |
|---|---|---|---|---|
{drows}
"""
    candidates = json.dumps({
        "assistance": "candidate revisions filtered by a rule: boolean constants indexed by station that the tick "
                      "action's progress condition reads, set to the value this model version does not use",
        "candidates": [{"constant": "slow", "station": st, "value": True} for st in inst["stations"]],
    }, indent=1) + "\n"
    reference = {
        "case_id": case["identity"]["case_id"], "case_version": case["identity"]["case_version"],
        "belief_model": {"path": f"research/cases/orders-p2-speed/{art['model-v1']['path']}",
                         "sha256": art["model-v1"]["sha256"]},
        "observation": {"path": f"research/cases/orders-p2-speed/{art['obs-run']['path']}",
                        "sha256": art["obs-run"]["sha256"]},
        "expected": {"constant": "slow", "station": fixture["conditions"]["slow_stations"][0], "value": True},
        "criterion": "the model revised by the answer corresponds with the recorded program run (replayed, every "
                     "compared field); the expected revision is reported alongside, not used as the criterion",
    }
    return brief, candidates, reference


def build(study_id: str, title: str, purpose: str, providers: list[dict], *, synthetic: bool, replicates: int,
          limits: dict, comparisons: list[dict]) -> Path:
    from formal_lab_contracts.research import ResearchStudy
    from formal_lab_eval.research_scorers import _loaded, sample_package, shortest_length

    d = STUDIES / study_id
    brief, candidates, reference = orders_brief()
    write(d / "inputs" / "orders-brief.md", brief)
    write(d / "assistance" / "orders-candidates.json", candidates)
    write(d / "reference" / "orders-deviation.json", json.dumps(reference, indent=1) + "\n")
    tasks = [{"task_id": "orders-deviation", "track": "implementation_conformance", "case_id": "orders-p2-speed",
              "case_version": 1, "representation_id": "brief-md", "purpose": DIAGNOSIS_PURPOSE,
              "inputs": ["inputs/orders-brief.md"], "assisted_inputs": ["assistance/orders-candidates.json"],
              "question": "Which single revision of one boolean model constant indexed by station would make the "
                          "model agree with the recorded run? Give the constant, the station and the new value.",
              "answer_format": "json", "answer_schema": DIAGNOSIS_SCHEMA, "reference": "reference/orders-deviation.json",
              "scorer_id": "orders.deviation-diagnosis", "scorer_version": "1", "bound": {"recorded_steps": 26}}]
    if synthetic:
        for sample, goal, bound in SYNTHETIC:
            pkg = sample_package(sample)
            shortest = shortest_length(_loaded(pkg), goal, bound)
            write(d / "inputs" / f"{sample}.ir.json", pkg.ir.model_dump_json(indent=1, exclude_none=True) + "\n")
            write(d / "inputs" / f"{sample}.prose.md", PROSE[sample])
            write(d / "reference" / f"{sample}.json", json.dumps(
                {"sample": sample, "goal": goal, "bound": bound, "shortest_length": shortest,
                 "model_digest": pkg.digest.value,
                 "criterion": "the plan is replayed on the reference interpreter: valid and reaching the goal; "
                              "CORRECT when it is as short as the breadth-first shortest plan, PARTIAL when longer"},
                indent=1) + "\n")
            for rep, path in (("ir-json", f"inputs/{sample}.ir.json"), ("prose", f"inputs/{sample}.prose.md")):
                tasks.append({"task_id": f"{sample}-{rep}", "track": "synthetic_representation",
                              "representation_id": rep, "purpose": PLAN_PURPOSE, "inputs": [path],
                              "question": f"Starting from the initial state, find a plan with the fewest actions that "
                                          f"makes the goal `{goal}` true, using at most {bound} actions. Say whether "
                                          "the goal is reachable and give the plan as action names in order.",
                              "answer_format": "json", "answer_schema": PLAN_SCHEMA,
                              "reference": f"reference/{sample}.json", "scorer_id": "synthetic.shortest-plan",
                              "scorer_version": "1", "bound": {"max_actions": bound}})
    study = ResearchStudy.model_validate({
        "study_id": study_id, "title": title, "purpose": purpose, "tasks": tasks, "providers": providers,
        "assistance_modes": ["STATIC_UNASSISTED", "ASSISTED"], "replicates": replicates,
        "rubric_id": "fal-research-rubric", "rubric_version": "1", "primary_metric": "correct",
        "secondary_metrics": ["format_valid", "refused", "responded", "program_corresponds", "output_tokens"],
        "limits": limits, "comparisons": comparisons,
        "missing_policy": "every planned unit keeps a record; units without a model-produced response are MISSING "
                          "in the model metrics (never 0 or 1) and counted by call outcome over the planned "
                          "denominator; a refusal is never retried; only transport faults, lost responses, 429 and "
                          "5xx are retried (fixed allowance); on resume an unanswered unit is called again as a new "
                          "sample"})
    write(d / "study.json", study.model_dump_json(indent=1, exclude_none=True) + "\n")
    return d


def main() -> int:
    ptest = {"provider": "protocol-test", "route": "LOOPBACK_TEST", "base_url_setting": "FAL_PTEST_BASE_URL",
             "api_key_setting": "FAL_PTEST_API_KEY", "model": "protocol-test-v1", "params": {"max_tokens": 512},
             "comparability_note": "the loopback protocol test service — not a model"}
    build("p6a-protocol", "Phase 6A protocol validation (loopback test service, not a model)",
          "validate research calls, raw-first records, the two result axes, scoring, reuse and the two-track report "
          "against scripted provider behaviours", [
              {**ptest, "provider_config_id": "ptest-openai", "api": "openai.chat.completions", "api_version": "v1"},
              {**ptest, "provider_config_id": "ptest-anthropic", "api": "anthropic.messages",
               "api_version": "2023-06-01"}],
          synthetic=True, replicates=2,
          limits={"max_calls": 60, "max_http_attempts": 120, "max_output_tokens_per_call": 512, "network_retries": 2},
          comparisons=[{"vary": "provider", "a": "ptest-openai", "b": "ptest-anthropic",
                        "note": "two protocol shapes of the same test service: a machinery check, not a model "
                                "comparison"},
                       {"vary": "representation", "a": "ir-json", "b": "prose"},
                       {"vary": "assistance", "a": "STATIC_UNASSISTED", "b": "ASSISTED"}])
    relay = {"route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL"}
    build("p6a-real", "Phase 6A minimal real calls (ordinary business task)",
          "verify the provider adapters against real endpoints with the minimal ordinary-business task, within the "
          "configured and authorized test quota (relay test keys given by the user on 2026-10-12; the first two GPT "
          "samples in the ledger were made earlier with the previously configured relay key and are kept as history; "
          "the call cap was raised from 8 to 12 on 2026-10-12 at the user's request to retry Claude Opus 5.5 after "
          "the relay answered 503 'no available accounts' and then 404 'model not supported' for it)",
          [{**relay, "provider_config_id": "gpt-6-astra-relay", "provider": "openai", "api": "openai.chat.completions",
            "api_version": "v1", "api_key_setting": "FAL_RESEARCH_GPT_API_KEY", "model": "gpt-6-astra",
            "params": {"max_completion_tokens": 6000},
            "comparability_note": "OpenAI-compatible protocol through the relay: the returned model name is the "
                                  "relay's report and cannot be verified as OpenAI's own"},
           {**relay, "provider_config_id": "claude-opus-5-5-relay", "provider": "anthropic",
            "api": "anthropic.messages", "api_version": "2023-06-01", "api_key_setting": "FAL_RESEARCH_CLAUDE_API_KEY",
            "model": "claude-opus-5-5", "params": {"max_tokens": 6000},
            "comparability_note": "the native Messages protocol through the relay: stop_reason / refusal semantics "
                                  "are kept, but the returned model name is the relay's report"},
           {"provider_config_id": "claude-opus-5-5-native", "provider": "anthropic", "api": "anthropic.messages",
            "api_version": "2023-06-01", "route": "OFFICIAL_NATIVE", "api_key_setting": "FAL_ANTHROPIC_API_KEY",
            "model": "claude-opus-5-5", "params": {"max_tokens": 6000},
            "comparability_note": "native Messages API at api.anthropic.com; needs FAL_ANTHROPIC_API_KEY (a "
                                  "provider's own environment variable is never read)"}],
          synthetic=False, replicates=1,
          limits={"max_calls": 12, "max_http_attempts": 24, "max_output_tokens_per_call": 6000,
                  "max_total_output_tokens": 48000, "network_retries": 1},
          comparisons=[{"vary": "provider", "a": "gpt-6-astra-relay", "b": "claude-opus-5-5-relay",
                        "note": "both through the same relay: identities are relay-reported, so this is an engineering "
                                "reading of two routes, not a verified provider comparison"},
                       {"vary": "assistance", "a": "STATIC_UNASSISTED", "b": "ASSISTED"}])
    for s in ("p6a-protocol", "p6a-real"):
        from formal_lab_eval.research import load_study, plan_units

        units, not_run = plan_units(load_study(STUDIES / s))
        print(f"{s}: {len(units)} unit(s), {len(not_run)} condition(s) not run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
