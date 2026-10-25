import Lake
open Lake DSL

package «irp27-decision-governance» where
  version := v!"0.1.0"

@[default_target]
lean_lib DecisionGov where
  roots := #[`DecisionGov]
