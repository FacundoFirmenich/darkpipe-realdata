import DecisionGov.Kernel

namespace IRP27.DecisionGov.HumanGold

structure GoldPrerequisites where
  curationComplete : Bool
  translationComplete : Bool
  semanticComplete : Bool
  provenanceComplete : Bool
  adjudicationComplete : Bool
  signaturesComplete : Bool
  externalReplicationComplete : Bool
  sourceRegistryVerified : Bool
  blindingAuditPassed : Bool
  duplicatePairsResolved : Bool
  automaticMajorityAsGold : Bool := false
  automaticExecution : Bool := false
  automaticPublication : Bool := false
  deriving Repr

def freezeEligible (p : GoldPrerequisites) : Bool :=
  p.curationComplete && p.translationComplete &&
  p.semanticComplete && p.provenanceComplete &&
  p.adjudicationComplete && p.signaturesComplete &&
  p.externalReplicationComplete && p.sourceRegistryVerified &&
  p.blindingAuditPassed && p.duplicatePairsResolved &&
  (!p.automaticMajorityAsGold) &&
  (!p.automaticExecution) && (!p.automaticPublication)

theorem curationRequired (p : GoldPrerequisites)
    (h : p.curationComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem translationRequired (p : GoldPrerequisites)
    (h : p.translationComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem semanticRequired (p : GoldPrerequisites)
    (h : p.semanticComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem provenanceRequired (p : GoldPrerequisites)
    (h : p.provenanceComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem adjudicationRequired (p : GoldPrerequisites)
    (h : p.adjudicationComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem signaturesRequired (p : GoldPrerequisites)
    (h : p.signaturesComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem replicationRequired (p : GoldPrerequisites)
    (h : p.externalReplicationComplete = false) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem majorityCannotFreeze (p : GoldPrerequisites)
    (h : p.automaticMajorityAsGold = true) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem executionRemainsManual (p : GoldPrerequisites)
    (h : p.automaticExecution = true) : freezeEligible p = false := by
  simp [freezeEligible, h]

theorem publicationRemainsManual (p : GoldPrerequisites)
    (h : p.automaticPublication = true) : freezeEligible p = false := by
  simp [freezeEligible, h]

end IRP27.DecisionGov.HumanGold
