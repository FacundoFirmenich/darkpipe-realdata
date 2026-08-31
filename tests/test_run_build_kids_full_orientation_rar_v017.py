from __future__ import annotations

import numpy as np
import pytest

from run_build_kids_full_orientation_rar_v017 import effective_lens_range


def test_effective_lens_range_uses_stack_inverse_variance_contract() -> None:
    assert effective_lens_range({"effective_lenses": np.array([7, 11, 9])}) == (7, 11)


def test_effective_lens_range_rejects_empty_surface() -> None:
    with pytest.raises(ValueError, match="non-empty one-dimensional"):
        effective_lens_range({"effective_lenses": np.array([], dtype=np.int64)})
