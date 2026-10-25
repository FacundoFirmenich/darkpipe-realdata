#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any
import jsonschema

PROVIDER_ORDER = ("jev", "laya", "nimble", "bifrost_custom")

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()

def validate(contract: dict[str, Any], schema: dict[str, Any]) -> None:
    jsonschema.validate(contract, schema)
    if contract["authority"]["provider_conveys_authority"] is not False:
        raise ValueError("provider_conveys_authority must be false")
    if contract["authority"]["automatic_execution"] is not False:
        raise ValueError("automatic_execution must be false")
    if contract["authority"]["automatic_publication"] is not False:
        raise ValueError("automatic_publication must be false")
    if contract["lease"]["future_only"] is not True:
        raise ValueError("lease must be future-only")
    for qid, question in contract["questions"].items():
        criteria = question["criteria"]
        if question["type"] == "noul" and set(criteria) != {"true", "false"}:
            raise ValueError(f"noul {qid} must have true/false criteria")
        if question["type"] in {"choice", "score"} and len(criteria) < 2:
            raise ValueError(f"{qid} requires >=2 criteria")

def jev_request(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": {field: f"{{{{{field}}}}}" for field in contract["state"]["required_fields"]},
        "questions": contract["questions"],
        "metadata": {"contract_id": contract["contract_id"], "contract_hash": sha(contract), "authority": "NONE"},
    }

def laya_adapter(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "python_package": "laya",
        "interface": "Router.predict(state, questions, model=checkpoint)",
        "request": jev_request(contract),
        "checkpoints": ["english", "multilingual", "typed-decisions"],
        "authority": "NONE",
    }

def nimble_schema(contract: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    postprocess: dict[str, Any] = {}
    for qid, q in contract["questions"].items():
        labels = list(q["criteria"])
        if q["type"] == "noul":
            properties[qid] = {"type": "boolean", "description": q["instructions"]}
        else:
            properties[qid] = {"type": "string", "enum": labels, "description": q["instructions"]}
            if q["type"] == "score":
                postprocess[qid] = {"ordered_levels": labels, "expected_level": True}
    return {
        "context_template": contract["state"]["template"],
        "schema": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False},
        "postprocess": postprocess,
        "semantic_limit": "Nimble output must not be treated as authority or execution permission.",
    }

def bifrost_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "custom_typesafe",
        "base_format": "typesafe",
        "endpoint_env": "IRP27_DECISION_PROVIDER_URL",
        "path": "/v1/systemone",
        "contract_hash": sha(contract),
        "automatic_execution": False,
        "automatic_publication": False,
    }

def risk_template(contract: dict[str, Any]) -> dict[str, Any]:
    r = contract["risk_thresholds_permille"]
    return {
        "contract_id": contract["contract_id"],
        "contract_hash": sha(contract),
        "observed": {"supportPrecisionLCB": None, "refutePrecisionLCB": None, "supportCoverage": None, "refuteCoverage": None, "swapAcceptance": None, "unsafeConflictCommits": None, "classConditionalCoverage": None},
        "required": r,
        "status": "NOT_EVALUATED",
        "authority": "NONE",
    }

def receipt_template(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_hash": sha(contract),
        "provider": None,
        "provider_version": None,
        "checkpoint": None,
        "state_hash": None,
        "request_hash": None,
        "response_hash": None,
        "risk_certificate_hash": None,
        "route": "SHADOW_ONLY",
        "human_authorized": False,
        "execution_lease": None,
        "automatic_execution": False,
        "automatic_publication": False,
        "previous_receipt_hash": None,
        "receipt_hash": None,
    }

def lean_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", value)

def lean_obligations(contract: dict[str, Any]) -> str:
    name = lean_name(contract["contract_id"])
    h = sha(contract)
    return f'''import DecisionGov.Kernel

namespace IRP27.DecisionGov.Compiled

def contractId : String := "{contract['contract_id']}"
def contractHash : String := "{h}"
def providerConveysAuthority : Bool := false
def automaticExecution : Bool := false
def automaticPublication : Bool := false
def leaseFutureOnly : Bool := true

theorem {name}_provider_no_authority : providerConveysAuthority = false := by rfl
theorem {name}_no_auto_execution : automaticExecution = false := by rfl
theorem {name}_no_auto_publication : automaticPublication = false := by rfl
theorem {name}_future_only : leaseFutureOnly = true := by rfl

theorem {name}_provider_invariant (input : GovernanceInput) (p q : Provider) :
    readyToExecute {{ input with proposal := replaceProvider input.proposal p }} =
    readyToExecute {{ input with proposal := replaceProvider input.proposal q }} := by
  exact providerIndependence input p q

theorem {name}_conflict_blocked (input : GovernanceInput)
    (h : input.proposal.evidence = .conflicting) : readyToExecute input = false := by
  exact conflictNeverReady input h

theorem {name}_insufficient_blocked (input : GovernanceInput)
    (h : input.proposal.evidence = .insufficient) : readyToExecute input = false := by
  exact insufficientNeverReady input h

end IRP27.DecisionGov.Compiled
'''

def compile_contract(contract_path: Path, schema_path: Path, output: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text())
    schema = json.loads(schema_path.read_text())
    validate(contract, schema)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "jev_request.template.json": jev_request(contract),
        "laya_adapter.json": laya_adapter(contract),
        "nimble_schema.json": nimble_schema(contract),
        "bifrost_manifest.json": bifrost_manifest(contract),
        "risk_certificate.template.json": risk_template(contract),
        "decision_receipt.template.json": receipt_template(contract),
    }
    hashes = {}
    for name, obj in artifacts.items():
        path = output / name
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    lean = output / "CompiledContract.lean"
    lean.write_text(lean_obligations(contract))
    hashes[lean.name] = hashlib.sha256(lean.read_bytes()).hexdigest()
    manifest = {
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "contract_hash": sha(contract),
        "compiler_version": "2.0.0",
        "providers": list(contract["providers"]),
        "artifacts": hashes,
        "semantic_invariants": {"provider_conveys_authority": False, "automatic_execution": False, "automatic_publication": False, "future_only_lease": True},
    }
    (output / "compiler_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--contract", type=Path, required=True); p.add_argument("--schema", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); print(json.dumps(compile_contract(a.contract, a.schema, a.output), indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
