"""Typed observational authority for DarkPipe receipts.

This module keeps measured quantities separate from causal, detection and
intervention claims. It does not infer authority from a large statistic, a low
p-value, repeated terminology or the status of a neighbouring claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class AuthorityError(ValueError):
    """Raised when an operation would exceed the declared evidence authority."""


class ClaimKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    ASSOCIATION = "ASSOCIATION"
    CAUSAL = "CAUSAL"
    DETECTION = "DETECTION"
    GENERALIZATION = "GENERALIZATION"
    INTERVENTION = "INTERVENTION"


class ClaimStatus(str, Enum):
    OPEN = "OPEN"
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ABSTAIN = "ABSTAIN"


_OBSERVATIONAL_KINDS = frozenset({ClaimKind.OBSERVATION, ClaimKind.ASSOCIATION})
_CONDUCENCE_STATUSES = frozenset(
    {
        ClaimStatus.SUPPORTED,
        ClaimStatus.CONTRADICTED,
        ClaimStatus.NOT_ESTIMABLE,
        ClaimStatus.NOT_APPLICABLE,
    }
)


def _required(label: str, value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{label} must be non-empty")
    return cleaned


@dataclass(frozen=True)
class ObservationEnvelope:
    """The complete declared regime under which an observation was formed."""

    envelope_id: str
    source: str
    observable: str
    time_start: str
    time_stop: str
    time_basis: str
    scale: str
    layer: str
    resolution: str
    preprocessing: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "envelope_id",
            "source",
            "observable",
            "time_start",
            "time_stop",
            "time_basis",
            "scale",
            "layer",
            "resolution",
        ):
            object.__setattr__(self, name, _required(name, getattr(self, name)))
        if self.time_start > self.time_stop:
            raise ValueError("time_start must not follow time_stop")

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "source": self.source,
            "observable": self.observable,
            "time_start": self.time_start,
            "time_stop": self.time_stop,
            "time_basis": self.time_basis,
            "scale": self.scale,
            "layer": self.layer,
            "resolution": self.resolution,
            "preprocessing": list(self.preprocessing),
            "provenance_refs": list(self.provenance_refs),
        }


@dataclass(frozen=True)
class ObservedDecoupling:
    """A difference registered under one or more observation envelopes.

    Cause, duration, meaning, intent and provisionality are intentionally not
    representable fields. They require separate claims and separate evidence.
    """

    decoupling_id: str
    left: str
    right: str
    statistic: str
    value: float
    unit: str
    envelope_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("decoupling_id", "left", "right", "statistic", "unit"):
            object.__setattr__(self, name, _required(name, getattr(self, name)))
        if not self.envelope_refs:
            raise ValueError("an observed decoupling requires at least one envelope")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decoupling_id": self.decoupling_id,
            "left": self.left,
            "right": self.right,
            "statistic": self.statistic,
            "value": float(self.value),
            "unit": self.unit,
            "envelope_refs": list(self.envelope_refs),
        }


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    statement: str
    kind: ClaimKind
    status: ClaimStatus
    jurisdiction: str
    evidence_refs: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    future_only: bool = True

    def __post_init__(self) -> None:
        for name in ("claim_id", "statement", "jurisdiction"):
            object.__setattr__(self, name, _required(name, getattr(self, name)))
        if self.status in {
            ClaimStatus.OBSERVED,
            ClaimStatus.SUPPORTED,
            ClaimStatus.CONTRADICTED,
        } and not self.evidence_refs:
            raise ValueError(f"{self.status.value} claims require evidence_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "kind": self.kind.value,
            "status": self.status.value,
            "jurisdiction": self.jurisdiction,
            "evidence_refs": list(self.evidence_refs),
            "blocking_reasons": list(self.blocking_reasons),
            "future_only": self.future_only,
        }


@dataclass
class ClaimLedger:
    """Append-only typed claim collection for one bounded receipt."""

    jurisdiction: str
    records: list[ClaimRecord] = field(default_factory=list)

    def append(self, claim: ClaimRecord) -> None:
        if claim.jurisdiction != self.jurisdiction:
            raise AuthorityError("claim jurisdiction does not match ledger jurisdiction")
        if any(existing.claim_id == claim.claim_id for existing in self.records):
            raise ValueError(f"duplicate claim_id: {claim.claim_id}")
        self.records.append(claim)

    def observational_promotion(
        self,
        *,
        claim_id: str,
        statement: str,
        kind: ClaimKind,
        status: ClaimStatus,
        evidence_refs: Iterable[str],
    ) -> ClaimRecord:
        """Record only authority available from an observational receipt."""
        if kind not in _OBSERVATIONAL_KINDS:
            raise AuthorityError(
                f"observational evidence cannot automatically promote {kind.value} claims"
            )
        if status not in {
            ClaimStatus.OBSERVED,
            ClaimStatus.SUPPORTED,
            ClaimStatus.CONTRADICTED,
        }:
            raise AuthorityError(f"{status.value} is not an observational promotion status")
        claim = ClaimRecord(
            claim_id=claim_id,
            statement=statement,
            kind=kind,
            status=status,
            jurisdiction=self.jurisdiction,
            evidence_refs=tuple(evidence_refs),
        )
        self.append(claim)
        return claim

    def retain_unresolved(
        self,
        *,
        claim_id: str,
        statement: str,
        kind: ClaimKind,
        blocking_reasons: Iterable[str],
        evidence_refs: Iterable[str] = (),
    ) -> ClaimRecord:
        """Retain a claim without granting it current authority."""
        reasons = tuple(blocking_reasons)
        if not reasons:
            raise ValueError("NOT_ESTIMABLE claims require blocking_reasons")
        claim = ClaimRecord(
            claim_id=claim_id,
            statement=statement,
            kind=kind,
            status=ClaimStatus.NOT_ESTIMABLE,
            jurisdiction=self.jurisdiction,
            evidence_refs=tuple(evidence_refs),
            blocking_reasons=reasons,
        )
        self.append(claim)
        return claim

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "jurisdiction": self.jurisdiction,
            "automatic_promotion": False,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class ConducenceVector:
    """Contextual, typed assessments that cannot collapse to one universal score."""

    context: Mapping[str, str]
    axes: Mapping[str, ClaimStatus]

    def __post_init__(self) -> None:
        if not self.context:
            raise ValueError("conducence requires an explicit context")
        if not self.axes:
            raise ValueError("conducence requires at least one axis")
        invalid = {status for status in self.axes.values() if status not in _CONDUCENCE_STATUSES}
        if invalid:
            raise ValueError(
                f"invalid conducence statuses: {sorted(item.value for item in invalid)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": dict(self.context),
            "axes": {name: status.value for name, status in self.axes.items()},
            "scalar_summary": None,
        }

    def scalar_score(self) -> float:
        raise AuthorityError(
            "conducence is vectorial and contextual; scalar collapse is undefined"
        )


def serialize_authority(
    *,
    envelopes: Iterable[ObservationEnvelope],
    ledger: ClaimLedger,
    decouplings: Iterable[ObservedDecoupling] = (),
    conducence: ConducenceVector | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "observation_envelopes": [item.to_dict() for item in envelopes],
        "observed_decouplings": [item.to_dict() for item in decouplings],
        "claim_ledger": ledger.to_dict(),
        "forbidden_automatic_inferences": [
            "cause",
            "duration",
            "meaning",
            "intent",
            "provisionality",
            "detection",
            "intervention",
            "universality",
        ],
    }
    if conducence is not None:
        payload["conducence"] = conducence.to_dict()
    return payload


def aion_authority_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a typed authority receipt without changing frozen AION endpoints."""
    jurisdiction = str(report.get("campaign_id", "DP-AION-UNKNOWN"))
    ledger = ClaimLedger(jurisdiction)
    gate_passed = bool(report.get("gate_0", {}).get("passed"))
    gate_status = ClaimStatus.SUPPORTED if gate_passed else ClaimStatus.CONTRADICTED
    ledger.observational_promotion(
        claim_id="aion.selected_evidence_integrity",
        statement="The selected AION evidence satisfies the frozen byte and schema contract.",
        kind=ClaimKind.OBSERVATION,
        status=gate_status,
        evidence_refs=("source_manifest.json", "gate_0"),
    )

    e1 = report.get("endpoint_e1")
    e2 = report.get("endpoint_e2")
    decouplings: list[ObservedDecoupling] = []
    if e1 is not None:
        ledger.observational_promotion(
            claim_id="aion.injected_frequency_recovery",
            statement="Seven intentional injected frequencies satisfy the preregistered recovery rule.",
            kind=ClaimKind.OBSERVATION,
            status=ClaimStatus.SUPPORTED if e1.get("passed") else ClaimStatus.CONTRADICTED,
            evidence_refs=("endpoint_e1",),
        )
    else:
        ledger.retain_unresolved(
            claim_id="aion.injected_frequency_recovery",
            statement="Intentional injected frequencies satisfy the preregistered recovery rule.",
            kind=ClaimKind.OBSERVATION,
            blocking_reasons=("integrity gate prevented endpoint evaluation",),
            evidence_refs=("gate_0",),
        )

    if e2 is not None:
        ledger.observational_promotion(
            claim_id="aion.hln_lln_interval",
            statement="The frozen HLN-minus-LLN interval includes zero.",
            kind=ClaimKind.ASSOCIATION,
            status=ClaimStatus.OBSERVED if e2.get("passed") else ClaimStatus.CONTRADICTED,
            evidence_refs=("endpoint_e2",),
        )
        decouplings.append(
            ObservedDecoupling(
                decoupling_id="aion.hln_minus_lln",
                left="HLN whole-dataset phase uncertainty",
                right="LLN whole-dataset phase uncertainty",
                statistic="difference",
                value=float(e2["difference_rad"]),
                unit="rad",
                envelope_refs=("aion.selected.deposit",),
            )
        )
    else:
        ledger.retain_unresolved(
            claim_id="aion.hln_lln_interval",
            statement="The frozen HLN-minus-LLN interval includes zero.",
            kind=ClaimKind.ASSOCIATION,
            blocking_reasons=("integrity gate prevented endpoint evaluation",),
            evidence_refs=("gate_0",),
        )

    unresolved = (
        (
            "aion.added_laser_noise_no_effect",
            "Added laser phase noise has no causal effect on the instrument.",
            ClaimKind.CAUSAL,
            "an interval including zero does not establish causal equivalence",
        ),
        (
            "aion.dark_sector_detection",
            "The selected controls detect a dark-sector signal.",
            ClaimKind.DETECTION,
            "the selected evidence contains controls, not a blind candidate search",
        ),
        (
            "aion.facility_transfer",
            "The tabletop result generalizes to AION-10, AION-km or another facility.",
            ClaimKind.GENERALIZATION,
            "no independent facility or transfer-function validation is present",
        ),
        (
            "aion.intervention",
            "The receipt authorizes an instrument intervention.",
            ClaimKind.INTERVENTION,
            "observation does not itself authorize intervention",
        ),
    )
    for claim_id, statement, kind, reason in unresolved:
        ledger.retain_unresolved(
            claim_id=claim_id,
            statement=statement,
            kind=kind,
            blocking_reasons=(reason,),
            evidence_refs=("endpoint_e1", "endpoint_e2") if e1 is not None else ("gate_0",),
        )

    axes = {
        "selected_evidence_integrity": gate_status,
        "injected_frequency_recovery": (
            ClaimStatus.SUPPORTED if e1 and e1.get("passed") else
            ClaimStatus.CONTRADICTED if e1 else ClaimStatus.NOT_ESTIMABLE
        ),
        "hln_lln_consistency": (
            ClaimStatus.SUPPORTED if e2 and e2.get("passed") else
            ClaimStatus.CONTRADICTED if e2 else ClaimStatus.NOT_ESTIMABLE
        ),
        "blind_discovery": ClaimStatus.NOT_ESTIMABLE,
        "facility_transfer": ClaimStatus.NOT_ESTIMABLE,
    }
    envelope = ObservationEnvelope(
        envelope_id="aion.selected.deposit",
        source="AION Zenodo record 19592552 selected evidence",
        observable="differential atom-interferometer excitation and phase-noise derivatives",
        time_start="not supplied as absolute UTC",
        time_stop="not supplied as absolute UTC",
        time_basis="upstream relative timestamps and derived block ensembles",
        scale="1 mm tabletop gradiometer controls",
        layer="instrument validation",
        resolution="dataset-specific Fourier resolution and upstream 141-shot blocks",
        preprocessing=("comment-aware CSV parsing", "frozen MLE final-iteration selection"),
        provenance_refs=("source_manifest.json",),
    )
    conducence = ConducenceVector(
        context={
            "campaign": jurisdiction,
            "instrument": "AION 1 mm tabletop gradiometer",
            "evidence_slice": "27 selected files",
        },
        axes=axes,
    )
    return serialize_authority(
        envelopes=(envelope,),
        ledger=ledger,
        decouplings=decouplings,
        conducence=conducence,
    )


def environmental_authority_payload(
    analysis: Mapping[str, Any],
    *,
    station: str,
    source_refs: Iterable[str],
) -> dict[str, Any]:
    """Build authority boundaries for one live NOAA-USGS observation window."""
    jurisdiction = (
        f"NOAA-USGS environmental foreground window at {station.upper()} "
        f"{analysis['time_start_utc']}--{analysis['time_stop_utc']}"
    )
    ledger = ClaimLedger(jurisdiction)
    ledger.observational_promotion(
        claim_id="environment.window_characterized",
        statement="The bounded NOAA-USGS window was aligned and characterized.",
        kind=ClaimKind.OBSERVATION,
        status=ClaimStatus.SUPPORTED,
        evidence_refs=("analysis", *tuple(source_refs)),
    )
    ledger.observational_promotion(
        claim_id="environment.bz_geomagnetic_association",
        statement="Lagged correlation and coherence statistics were observed in this window.",
        kind=ClaimKind.ASSOCIATION,
        status=ClaimStatus.OBSERVED,
        evidence_refs=("bz_to_geomag_lag_scan", "bz_to_geomag_coherence"),
    )
    for claim_id, statement, kind, reason in (
        (
            "environment.solar_wind_causation",
            "Solar-wind variation caused the observed geomagnetic residual structure.",
            ClaimKind.CAUSAL,
            "descriptive lag and coherence do not identify cause",
        ),
        (
            "environment.dark_sector_detection",
            "The projected residual is a dark-sector detection.",
            ClaimKind.DETECTION,
            "no blind detection statistic or calibrated null ensemble was executed",
        ),
        (
            "environment.cross_epoch_generalization",
            "This short-window relation generalizes across epochs, sites or instruments.",
            ClaimKind.GENERALIZATION,
            "one station and one short window cannot establish transfer",
        ),
        (
            "environment.sensor_intervention",
            "The observed relation authorizes sensor or acquisition intervention.",
            ClaimKind.INTERVENTION,
            "observation does not itself authorize measurement or intervention",
        ),
    ):
        ledger.retain_unresolved(
            claim_id=claim_id,
            statement=statement,
            kind=kind,
            blocking_reasons=(reason,),
            evidence_refs=("analysis",),
        )
    envelope = ObservationEnvelope(
        envelope_id="environment.live.window",
        source="NOAA SWPC RTSW and USGS Geomagnetism",
        observable="solar-wind channels and first difference of geomagnetic F",
        time_start=str(analysis["time_start_utc"]),
        time_stop=str(analysis["time_stop_utc"]),
        time_basis="UTC",
        scale="one-minute cadence",
        layer="environmental foreground",
        resolution="60 s nominal; merge tolerance declared by pipeline",
        preprocessing=(
            "nearest-time alignment",
            "standardized linear nuisance projection",
            "Welch spectral diagnostics",
        ),
        provenance_refs=tuple(source_refs),
    )
    conducence = ConducenceVector(
        context={
            "station": station.upper(),
            "time_start_utc": str(analysis["time_start_utc"]),
            "time_stop_utc": str(analysis["time_stop_utc"]),
        },
        axes={
            "window_characterization": ClaimStatus.SUPPORTED,
            "causal_attribution": ClaimStatus.NOT_ESTIMABLE,
            "dark_sector_detection": ClaimStatus.NOT_ESTIMABLE,
            "cross_epoch_generalization": ClaimStatus.NOT_ESTIMABLE,
        },
    )
    return serialize_authority(envelopes=(envelope,), ledger=ledger, conducence=conducence)
