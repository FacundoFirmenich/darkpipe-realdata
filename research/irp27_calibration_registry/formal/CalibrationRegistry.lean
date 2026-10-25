import DecisionGov.Kernel

namespace IRP27.DecisionGov.CalibrationRegistry

structure CalibrationKey where
  contractHash : String
  provider : String
  providerVersion : String
  checkpoint : String
  primitive : String
  domain : String
  language : String
  hardware : String
  dataVintage : String
  evaluationMode : String
  deriving DecidableEq, Repr

structure CalibrationEntry where
  key : CalibrationKey
  goldFrozen : Bool
  translationReviewed : Bool
  humanAnnotationsComplete : Bool
  externalReplicationComplete : Bool
  providerConveysAuthority : Bool := false
  automaticExecution : Bool := false
  automaticPublication : Bool := false
  deriving Repr

def sameCell (left right : CalibrationEntry) : Prop := left.key = right.key

def eligibleForPromotion (entry : CalibrationEntry) : Bool :=
  entry.goldFrozen && entry.translationReviewed &&
  entry.humanAnnotationsComplete && entry.externalReplicationComplete &&
  (!entry.providerConveysAuthority) && (!entry.automaticExecution) &&
  (!entry.automaticPublication)

theorem noCrossCellTransport (left right : CalibrationEntry)
    (h : left.key ≠ right.key) : ¬ sameCell left right := by
  intro hs
  exact h hs

theorem goldRequired (entry : CalibrationEntry)
    (h : entry.goldFrozen = false) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem translationReviewRequired (entry : CalibrationEntry)
    (h : entry.translationReviewed = false) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem humanAnnotationsRequired (entry : CalibrationEntry)
    (h : entry.humanAnnotationsComplete = false) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem replicationRequired (entry : CalibrationEntry)
    (h : entry.externalReplicationComplete = false) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem providerCannotConveyAuthority (entry : CalibrationEntry)
    (h : entry.providerConveysAuthority = true) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem executionRemainsManual (entry : CalibrationEntry)
    (h : entry.automaticExecution = true) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

theorem publicationRemainsManual (entry : CalibrationEntry)
    (h : entry.automaticPublication = true) : eligibleForPromotion entry = false := by
  simp [eligibleForPromotion, h]

end IRP27.DecisionGov.CalibrationRegistry
