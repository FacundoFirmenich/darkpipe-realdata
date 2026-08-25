"""Offline tests for the preregistered GPS network operator."""

from datetime import date, datetime, timezone

import numpy as np

from darkpipe.gps_network import (
    SearchConfig,
    clock_difference_matrix,
    datetime_to_jpl_second,
    exact_rank_pvalue,
    inject_plane_impulse,
    jpl_second_to_datetime,
    parse_clock_tdp,
    parse_position_goa,
    product_url,
    score_surface,
    search_segment,
    sobol_velocity_bank,
    template_delays,
)


def test_jpl_product_urls_and_time_roundtrip():
    day = date(2024, 12, 13)
    assert product_url(day, "hr.tdp").endswith("/2024/2024-12-13_hr.tdp.gz")
    assert product_url(day, "pos").endswith("/2024/2024-12-13.pos.gz")
    value = datetime(2024, 12, 13, 0, 0, tzinfo=timezone.utc)
    assert jpl_second_to_datetime(datetime_to_jpl_second(value)) == value
    assert jpl_second_to_datetime(787309200) == datetime(2024, 12, 12, 20, 59, 42, tzinfo=timezone.utc)


def test_real_format_parsers():
    clock_text = "\n".join(
        [
            "787309200 0.0 2.0677e5 3.4e-2 .Satellite.GPS43.Clk.Bias",
            "787309230 0.0 2.0678e5 3.5e-2 .Satellite.GPS43.Clk.Bias",
            "787309200 0.0 -2.575e4 4.0e-2 .Satellite.GPS44.Clk.Bias",
            "787309200 0.0 1.0 2.0 .Receiver.REF.Clk.Bias",
        ]
    )
    clock = parse_clock_tdp(clock_text)
    assert clock.shape == (3, 4)
    assert set(clock["node"]) == {"GPS43", "GPS44"}

    position_text = "\n".join(
        [
            "E GPS43 787309200 0.0 1.0 2.0 3.0 0 0 0",
            "E GPS44 787309200 0.0 4.0 5.0 6.0 0 0 0",
            "I GPS43 787309200 0.0 9.0 9.0 9.0 0 0 0",
        ]
    )
    position = parse_position_goa(position_text)
    assert position.shape == (2, 5)
    assert position.loc[position["node"] == "GPS44", "z_km"].iloc[0] == 6.0


def test_first_difference_does_not_bridge_gap():
    clock = parse_clock_tdp(
        "\n".join(
            [
                "0 0 10 1 .Satellite.GPS01.Clk.Bias",
                "30 0 13 1 .Satellite.GPS01.Clk.Bias",
                "90 0 20 1 .Satellite.GPS01.Clk.Bias",
            ]
        )
    )
    matrix = clock_difference_matrix(clock, cadence_seconds=30.0)
    assert matrix.loc[30.0, "GPS01"] == 3.0
    assert np.isnan(matrix.loc[90.0, "GPS01"])


def test_exact_family_rank():
    assert exact_rank_pvalue(1.0, [0.0] * 42) == 1.0 / 43.0
    assert exact_rank_pvalue(0.0, [0.0] * 42) == 1.0


def test_sobol_bank_is_deterministic_and_bounded():
    config = SearchConfig(template_count=32)
    first = sobol_velocity_bank(config)
    second = sobol_velocity_bank(config)
    assert np.array_equal(first, second)
    speed = np.linalg.norm(first, axis=1)
    assert speed.min() >= config.velocity_min_km_s
    assert speed.max() <= config.velocity_max_km_s


def test_vectorized_surface_matches_single_template():
    times = np.arange(0.0, 600.0, 30.0)
    values = np.column_stack(
        [np.sin(times / 100.0), np.cos(times / 100.0)]
    )
    centers = times[2:-2]
    delays = np.array([[5.0, -4.0], [-7.0, 3.0]])
    weight = np.array([0.6, 0.8])
    surface = score_surface(times, values, delays, weight, centers)
    assert surface.shape == (len(centers), 2)
    manual = []
    for center in centers:
        manual.append(
            0.6 * np.interp(center + 5.0, times, values[:, 0])
            + 0.8 * np.interp(center - 7.0, times, values[:, 1])
        )
    assert np.allclose(surface[:, 0], manual)


def test_injected_plane_impulse_is_temporally_recovered():
    times = np.arange(0.0, 9000.0, 30.0)
    values = np.zeros((len(times), 4), dtype=float)
    positions = np.array(
        [
            [26000.0, 0.0, 0.0],
            [-26000.0, 0.0, 0.0],
            [0.0, 26000.0, 0.0],
            [0.0, -26000.0, 0.0],
        ]
    )
    velocity = np.array([200.0, 50.0, -20.0])
    injected = inject_plane_impulse(
        values, times, positions, velocity, 4500.0, 8.0
    )
    hit = search_segment(
        times,
        injected,
        positions,
        velocity[None, :],
        np.ones(4) / 2.0,
        start_second=0.0,
        stop_second=9000.0,
        guard_seconds=600.0,
    )
    assert abs(hit.center_second - 4500.0) <= 30.0
    assert hit.statistic > 5.0


def test_template_delay_is_translation_invariant():
    position = np.array([[1.0, 2.0, 3.0], [4.0, 8.0, 12.0]])
    velocity = np.array([[100.0, 0.0, 0.0]])
    shifted = position + np.array([999.0, -400.0, 8.0])
    assert np.allclose(
        template_delays(position, velocity),
        template_delays(shifted, velocity),
    )
