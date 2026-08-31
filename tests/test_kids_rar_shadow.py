from __future__ import annotations

import numpy as np
import pandas as pd

from darkpipe.kids_rar_shadow import derive_rar_shadows, descriptive_summary, mond_rar_acceleration


def test_shadow_is_exact_log_ratio_and_keeps_no_ontology() -> None:
    table = pd.DataFrame(
        {
            "log10_gbar_m_s2": [-12.0],
            "log10_gobs_m_s2": [-11.0],
            "sigma_stat_log10_gobs": [0.1],
            "sigma_deprojection_systematic_log10_gobs": [0.2],
        }
    )
    shadows = derive_rar_shadows(table)
    assert shadows.loc[0, "eta_log10_gobs_over_gbar"] == 1.0
    assert np.isclose(shadows.loc[0, "effective_acceleration_enhancement"], 10.0)
    assert descriptive_summary(shadows)["ontology"] == "NOT_IDENTIFIED"


def test_mond_mapping_is_positive_and_asymptotically_enhanced() -> None:
    gbar = np.array([1e-14, 1e-10, 1e-8])
    mapped = mond_rar_acceleration(gbar)
    assert np.all(mapped > gbar)
    assert mapped[-1] / gbar[-1] < 1.001
