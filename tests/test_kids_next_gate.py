"""Execution-readiness receipts must not promote software into science."""
import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kids_next_gate", ROOT / "run_darkpipe_next_gate_v018.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_authentic_frozen_inputs_pass_but_science_gate_remains_blocked():
    result = module.audit(ROOT)
    assert result["input_integrity_passed"]
    assert len(result["files"]) == 4
    assert result["gate"] == "BLOCKED_EXECUTION_AND_PAIRED_COVARIANCE"
    assert result["scientific_result"] is False
    assert "PAIRED_SIGNAL_RANDOM_SPATIAL_REPLICATES_NOT_AVAILABLE" in result["blockers"]
    assert result["remote_resource_proposal"]["full_campaign_automatic_launch"] is False


def test_tampered_frozen_input_forces_integrity_abstention(tmp_path):
    for relative in module.FROZEN:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    target = tmp_path / next(iter(module.FROZEN))
    target.write_bytes(target.read_bytes() + b"\n")
    result = module.audit(tmp_path)
    assert result["gate"] == "ABSTAIN_INPUT_INTEGRITY"
    assert result["failures"] == [f"frozen hash differs: {next(iter(module.FROZEN))}"]
    assert result["scientific_result"] is False
