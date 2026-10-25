namespace IRP27.DecisionGov

/-!
A small proof kernel for IRP-27 decision governance.

Statistical and System-One models may propose typed probabilistic signals. They do
not carry permission, authority, execution power, or publication authority. Those
capabilities live in separate types and must be supplied explicitly.
-/

inductive Primitive where
  | choice
  | score
  | noul
deriving Repr, DecidableEq

inductive Provider where
  | jev
  | laya
  | nimble
  | openJev
  | deterministic
  | other (name : String)
deriving Repr, DecidableEq

structure Probability where
  permille : Nat
  bounded : permille ≤ 1000
deriving Repr

inductive TypedSignal where
  | choice
      (options : List String)
      (selected : String)
      (probabilities : List Probability)
  | score
      (levels : List String)
      (milliScore : Nat)
      (probabilities : List Probability)
  | noul
      (yesProbability : Probability)
deriving Repr

inductive EvidenceState where
  | candidate
  | context
  | support
  | refute
  | conflicting
  | insufficient
deriving Repr, DecidableEq

structure Provenance where
  provider : Provider
  modelVersion : String
  questionId : String
  stateHash : String
  responseHash : String
deriving Repr

structure Proposal where
  signal : TypedSignal
  evidence : EvidenceState
  provenance : Provenance
deriving Repr

/- All rates use permille. 950 means 0.95; 50 means 0.05. -/
structure RiskCertificate where
  supportPrecisionLCB : Nat
  refutePrecisionLCB : Nat
  supportCoverage : Nat
  refuteCoverage : Nat
  swapAcceptance : Nat
  unsafeConflictCommits : Nat
  classConditionalCoverage : Nat
deriving Repr

def riskPass (risk : RiskCertificate) : Prop :=
  950 ≤ risk.supportPrecisionLCB ∧
  950 ≤ risk.refutePrecisionLCB ∧
  50 ≤ risk.supportCoverage ∧
  50 ≤ risk.refuteCoverage ∧
  risk.swapAcceptance ≤ 5 ∧
  risk.unsafeConflictCommits = 0 ∧
  900 ≤ risk.classConditionalCoverage

def riskPassB (risk : RiskCertificate) : Bool :=
  decide (riskPass risk)

def evidenceAdmissibleB : EvidenceState → Bool
  | .support => true
  | .refute => true
  | _ => false

/- The provider is deliberately absent from every authority predicate. -/
def modelConveysAuthority (_ : Provider) : Bool := false

theorem noProviderConveysAuthority (provider : Provider) :
    modelConveysAuthority provider = false := by
  rfl

theorem noulIsNotScore
    (probability : Probability)
    (levels : List String)
    (milliScore : Nat)
    (probabilities : List Probability) :
    TypedSignal.noul probability ≠
      TypedSignal.score levels milliScore probabilities := by
  intro equality
  cases equality

structure GovernanceInput where
  proposal : Proposal
  risk : RiskCertificate
  humanAuthorized : Bool
  executionLease : Bool
deriving Repr

def readyToExecute (input : GovernanceInput) : Bool :=
  evidenceAdmissibleB input.proposal.evidence &&
    (riskPassB input.risk &&
      (input.humanAuthorized && input.executionLease))

theorem readyRequiresAdmissibleEvidence
    (input : GovernanceInput)
    (ready : readyToExecute input = true) :
    evidenceAdmissibleB input.proposal.evidence = true := by
  simp [readyToExecute] at ready
  exact ready.1

theorem readyRequiresRiskPass
    (input : GovernanceInput)
    (ready : readyToExecute input = true) :
    riskPassB input.risk = true := by
  simp [readyToExecute] at ready
  exact ready.2.1

theorem readyRequiresHumanAuthorization
    (input : GovernanceInput)
    (ready : readyToExecute input = true) :
    input.humanAuthorized = true := by
  simp [readyToExecute] at ready
  exact ready.2.2.1

theorem readyRequiresExecutionLease
    (input : GovernanceInput)
    (ready : readyToExecute input = true) :
    input.executionLease = true := by
  simp [readyToExecute] at ready
  exact ready.2.2.2

theorem conflictNeverReady
    (input : GovernanceInput)
    (conflict : input.proposal.evidence = .conflicting) :
    readyToExecute input = false := by
  simp [readyToExecute, evidenceAdmissibleB, conflict]

theorem insufficientNeverReady
    (input : GovernanceInput)
    (insufficient : input.proposal.evidence = .insufficient) :
    readyToExecute input = false := by
  simp [readyToExecute, evidenceAdmissibleB, insufficient]

def replaceProvider (proposal : Proposal) (provider : Provider) : Proposal :=
  { proposal with provenance := { proposal.provenance with provider := provider } }

theorem providerIndependence
    (input : GovernanceInput)
    (left right : Provider) :
    readyToExecute
        { input with proposal := replaceProvider input.proposal left } =
      readyToExecute
        { input with proposal := replaceProvider input.proposal right } := by
  rfl

structure PublicationInput where
  executionVerified : Bool
  publicationSigned : Bool
  explicitPublishRequest : Bool
deriving Repr

def readyToPublish (input : PublicationInput) : Bool :=
  input.executionVerified &&
    (input.publicationSigned && input.explicitPublishRequest)

theorem publicationRequiresVerifiedExecution
    (input : PublicationInput)
    (ready : readyToPublish input = true) :
    input.executionVerified = true := by
  simp [readyToPublish] at ready
  exact ready.1

theorem publicationRequiresSignature
    (input : PublicationInput)
    (ready : readyToPublish input = true) :
    input.publicationSigned = true := by
  simp [readyToPublish] at ready
  exact ready.2.1

theorem publicationRequiresExplicitRequest
    (input : PublicationInput)
    (ready : readyToPublish input = true) :
    input.explicitPublishRequest = true := by
  simp [readyToPublish] at ready
  exact ready.2.2

structure QualifiedDecision where
  proposal : Proposal
  risk : RiskCertificate
  riskProof : riskPass risk
  evidenceProof :
    proposal.evidence = .support ∨ proposal.evidence = .refute

structure HumanAuthorization where
  domainReviewer : String
  statisticalReviewer : String
  policyAuthority : String
  authorizationHash : String
deriving Repr

structure AuthorizedDecision where
  qualified : QualifiedDecision
  authorization : HumanAuthorization

structure ExecutionLease where
  leaseId : String
  futureOnly : Bool
  futureOnlyProof : futureOnly = true
  expiresAt : String

deriving Repr

structure ExecutedDecision where
  authorized : AuthorizedDecision
  lease : ExecutionLease
  executionReceiptHash : String

structure PublicationAuthorization where
  publicationAuthority : String
  explicitRequest : Bool
  explicitRequestProof : explicitRequest = true
  signatureHash : String

deriving Repr

structure PublishedDecision where
  executed : ExecutedDecision
  publication : PublicationAuthorization

 theorem qualifiedIsNotConflict (decision : QualifiedDecision) :
    decision.proposal.evidence ≠ .conflicting := by
  rcases decision.evidenceProof with support | refute <;> simp [support, refute]

 theorem qualifiedIsNotInsufficient (decision : QualifiedDecision) :
    decision.proposal.evidence ≠ .insufficient := by
  rcases decision.evidenceProof with support | refute <;> simp [support, refute]

 theorem executionCarriesRiskProof (decision : ExecutedDecision) :
    riskPass decision.authorized.qualified.risk :=
  decision.authorized.qualified.riskProof

 theorem executionCarriesHumanAuthorization (decision : ExecutedDecision) :
    ∃ authorization : HumanAuthorization,
      decision.authorized.authorization = authorization := by
  exact ⟨decision.authorized.authorization, rfl⟩

 theorem executionIsFutureOnly (decision : ExecutedDecision) :
    decision.lease.futureOnly = true :=
  decision.lease.futureOnlyProof

 theorem publicationCarriesExplicitHumanRequest
    (decision : PublishedDecision) :
    decision.publication.explicitRequest = true :=
  decision.publication.explicitRequestProof

inductive Stage where
  | observed
  | proposed
  | qualified
  | authorized
  | leased
  | executed
  | closed
  | successor
  | abstained
  | review
deriving Repr, DecidableEq

inductive CanTransition : Stage → Stage → Prop where
  | observePropose : CanTransition .observed .proposed
  | proposeQualify : CanTransition .proposed .qualified
  | proposeAbstain : CanTransition .proposed .abstained
  | proposeReview : CanTransition .proposed .review
  | qualifyAuthorize : CanTransition .qualified .authorized
  | authorizeLease : CanTransition .authorized .leased
  | leaseExecute : CanTransition .leased .executed
  | executeClose : CanTransition .executed .closed
  | closeSuccessor : CanTransition .closed .successor

 theorem noProposalToExecution :
    ¬ CanTransition .proposed .executed := by
  intro transition
  cases transition

 theorem noProposalToPublication :
    ¬ CanTransition .proposed .closed := by
  intro transition
  cases transition

 theorem closedStateOnlyAdvancesToSuccessor
    {target : Stage}
    (transition : CanTransition .closed target) :
    target = .successor := by
  cases transition
  rfl

 theorem executionNeedsLeaseTransition :
    CanTransition .leased .executed :=
  CanTransition.leaseExecute

end IRP27.DecisionGov
