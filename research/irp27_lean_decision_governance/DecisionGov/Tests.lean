import DecisionGov.Kernel

open IRP27.DecisionGov

namespace IRP27.DecisionGov.Tests

def p500 : Probability :=
  { permille := 500, bounded := by decide }

def p900 : Probability :=
  { permille := 900, bounded := by decide }

def passingRisk : RiskCertificate :=
  {
    supportPrecisionLCB := 950
    refutePrecisionLCB := 950
    supportCoverage := 50
    refuteCoverage := 50
    swapAcceptance := 5
    unsafeConflictCommits := 0
    classConditionalCoverage := 900
  }

def failingRisk : RiskCertificate :=
  {
    supportPrecisionLCB := 0
    refutePrecisionLCB := 0
    supportCoverage := 0
    refuteCoverage := 0
    swapAcceptance := 1000
    unsafeConflictCommits := 1
    classConditionalCoverage := 0
  }

def provenance (provider : Provider) : Provenance :=
  {
    provider := provider
    modelVersion := "contract-test"
    questionId := "evidence_relation"
    stateHash := "state-hash"
    responseHash := "response-hash"
  }

def supportProposal (provider : Provider) : Proposal :=
  {
    signal := TypedSignal.choice
      ["support", "refute", "context", "insufficient"]
      "support"
      [p900, p500, p500, p500]
    evidence := .support
    provenance := provenance provider
  }

def conflictProposal : Proposal :=
  {
    signal := TypedSignal.choice
      ["support", "refute", "context", "insufficient"]
      "context"
      [p500, p500, p500, p500]
    evidence := .conflicting
    provenance := provenance .jev
  }

def readyInput (provider : Provider) : GovernanceInput :=
  {
    proposal := supportProposal provider
    risk := passingRisk
    humanAuthorized := true
    executionLease := true
  }

def unsignedInput : GovernanceInput :=
  {
    proposal := supportProposal .jev
    risk := passingRisk
    humanAuthorized := false
    executionLease := true
  }

def failedRiskInput : GovernanceInput :=
  {
    proposal := supportProposal .jev
    risk := failingRisk
    humanAuthorized := true
    executionLease := true
  }

example : riskPass passingRisk := by decide

example : riskPassB passingRisk = true := by decide

example : riskPassB failingRisk = false := by decide

example : readyToExecute (readyInput .jev) = true := by decide

example : readyToExecute unsignedInput = false := by decide

example : readyToExecute failedRiskInput = false := by decide

example :
    readyToExecute (readyInput .jev) =
      readyToExecute (readyInput .laya) := by
  rfl

example :
    readyToExecute (readyInput .nimble) =
      readyToExecute (readyInput .openJev) := by
  rfl

example : readyToExecute
    {
      proposal := conflictProposal
      risk := passingRisk
      humanAuthorized := true
      executionLease := true
    } = false := by decide

example :
    readyToPublish
      {
        executionVerified := true
        publicationSigned := true
        explicitPublishRequest := false
      } = false := by decide

example :
    readyToPublish
      {
        executionVerified := true
        publicationSigned := true
        explicitPublishRequest := true
      } = true := by decide

example :
    ¬ CanTransition .proposed .executed :=
  noProposalToExecution

example :
    ¬ CanTransition .proposed .closed :=
  noProposalToPublication

end IRP27.DecisionGov.Tests
