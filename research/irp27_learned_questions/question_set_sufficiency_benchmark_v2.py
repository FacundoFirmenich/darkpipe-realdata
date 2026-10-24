#!/usr/bin/env python3
"""Compatibility correction for Gate SOTA-006.

The initial runner referenced the canonical text normalizer through an unbound
module-global name in evidence_state. This wrapper binds it explicitly to the
already-tested normalizer from the learned-question core and delegates the full
benchmark without altering its scientific design or calibration grid.
"""
from __future__ import annotations

import question_set_sufficiency_benchmark as benchmark

benchmark.fold = benchmark.core.fold


if __name__ == "__main__":
    raise SystemExit(benchmark.main())
