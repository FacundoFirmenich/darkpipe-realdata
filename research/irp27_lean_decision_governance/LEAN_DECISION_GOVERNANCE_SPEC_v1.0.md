# IRP-27 Lean Decision Governance Kernel v1.0

## 1. Purpose

This gate introduces a formally verified decision-governance plane between statistical or System-One signals and any authority-bearing action. The kernel does not attempt to prove that a model is empirically correct. It proves that a model output cannot, by itself, acquire permission, authority, execution power, or publication power.

The architecture treats Jev, Laya, Nimble, OpenJev and future compatible models as swappable **decision sensors**. Their outputs may be useful statistical features. They are never authority objects.

## 2. Constitutional separation

IRP-27 preserves six independent concepts:

1. **Capability** — what a component can compute.
2. **Support** — what empirical evidence supports.
3. **Permission** — what an actor or process may attempt.
4. **Authority** — who may bind the system or institution.
5. **Execution** — what was materially run under a valid lease.
6. **Training** — what may update future successors only.

No numerical score may silently collapse those concepts.

## 3. Decision planes

### 3.1 Observation plane

Materializes state, source spans, model version, question, response and hashes.

### 3.2 Typed statistical signal plane

Accepts bounded primitives:

- `Choice`: one option from a declared finite set plus the full distribution;
- `Score`: a position over declared ordered levels plus the full distribution;
- `Noul`: probability that a declared yes/no proposition is true.

A Noul probability is not a degree. A Score is not a probability of truth. The type system keeps them distinct.

### 3.3 Statistical qualification plane

Computes:

- held-out directional precision bounds;
- class coverage;
- swap acceptance;
- unsafe conflict commitments;
- class-conditional conformal coverage;
- missingness and transport boundaries.

These calculations generate a `RiskCertificate`. They do not generate authority.

### 3.4 Lean proof plane

Lean proves structural invariants:

- no provider conveys authority;
- a `Noul` cannot be used as a `Score` constructor;
- conflicting and insufficient evidence cannot be execution-ready;
- readiness requires an admissible evidence state, a passed risk gate, human authorization and a valid execution lease;
- publication requires verified execution, a publication signature and an explicit human publication request;
- no direct transition exists from proposal to execution or closure;
- a closed state can only move to a successor, never mutate retrospectively.

### 3.5 Human authority plane

Requires named domain, statistical and policy authorities. The model does not sign its own decision.

### 3.6 KCH execution plane

Execution requires an external, future-only lease and produces an append-only receipt. The governance kernel can declare `READY_TO_EXECUTE`; it does not execute tools itself.

### 3.7 Successor-only learning plane

A closed decision remains immutable. Corrections and learning live in a successor with explicit genealogy. No retrospective rewriting is permitted.

## 4. Risk thresholds inherited from Gate SOTA-009

```text
support precision LCB95       >= 0.95
refute precision LCB95        >= 0.95
support coverage              >= 0.05
refute coverage               >= 0.05
counterfactual swap acceptance <= 0.005
unsafe conflict commitments   == 0
class-conditional coverage    >= 0.90
```

Missing values fail closed.

## 5. Governance routes

```text
BLOCKED_PREREQUISITE
ABSTAIN
HUMAN_REVIEW
QUALIFIED_AWAITING_AUTHORITY
AUTHORIZED_AWAITING_LEASE
READY_TO_EXECUTE
```

Publication is a separate human action and never follows automatically from `READY_TO_EXECUTE`.

## 6. Relationship to Jev and open mirrors

Jev publicly exposes typed decisions through `Choice`, `Score` and `Noul`. Laya and other open implementations reproduce parts of that interface. This compatibility is useful for experimentation, provider substitution and statistical feature extraction.

It does not imply:

- identical calibration;
- identical semantics;
- identical training distributions;
- independent replication of vendor claims;
- permission to execute;
- institutional authority.

Provider identity is therefore absent from all authority predicates in the Lean kernel.

## 7. Statistical programming and statistical computation

IRP-27 uses **statistical programming** to mean the design of executable statistical decision contracts: estimands, observables, thresholds, loss functions, abstention regions, provenance and revision rules are first-class program objects.

It uses **statistical computation** to mean the material computation of those objects over observed data: exact bounds, calibration, sensitivity, partial identification, simulation under declared assumptions and generation of auditable receipts.

Decision governance is the constitutional layer that determines which computed objects may change state.

## 8. Limits

This gate proves governance invariants and exercises them against real SOTA-008 and SOTA-009 states. It does not validate Jev, Laya, Nimble or OpenJev on IRP-27 tasks. It does not prove empirical calibration. It makes no live model calls. It does not authorize model training, evidence promotion, execution or publication.

## 9. Gate state

```text
LEAN KERNEL                         IMPLEMENTED
FORMAL INVARIANTS                   COMPILE-TIME VERIFIED
STATISTICAL RUNTIME                 IMPLEMENTED
REAL SOTA-008/009 INPUTS            INTEGRATED
PROVIDER-INVARIANCE TEST            IMPLEMENTED
LIVE SYSTEM-ONE MODEL COMPARISON    NOT EXECUTED
HUMAN AUTHORITY                     REQUIRED
AUTOMATIC EXECUTION                 FALSE
AUTOMATIC PUBLICATION               FALSE
```
