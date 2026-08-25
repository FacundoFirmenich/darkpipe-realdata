# DarkPipe 0.6 — replay holdout AION sellado

Decisión: **PASS_BOUNDED**.

El mapa de ocho casos se comprometió mediante SHA-256 después del commit de prerregistro y se reveló sólo después de escribir las predicciones. El fondo de ruido procede de los controles LLN/HLN AION auténticos; únicamente la perturbación de fase diferencial es sintética y está declarada.

| Caso | Verdad revelada | Pico predicho | p global | Frecuencias detectadas | Gate |
|---|---|---|---:|---|---|
| f6b1d36179ba21f7 | 0p1_mhz | 0p1_mhz | 0.000244141 | 0p1_mhz | PASS |
| 9f4ae372a6cf1796 | NULL | 1_mhz | 0.385742 | none | PASS |
| 7f8ba77908f78da1 | 10_mhz | 10_mhz | 0.000244141 | 10_mhz | PASS |
| 350e9e4edd88ad61 | 0p3_mhz | 0p3_mhz | 0.000244141 | 0p3_mhz | PASS |
| db4f342d99866f65 | 100_mhz | 100_mhz | 0.000244141 | 100_mhz | PASS |
| dd4d4113b85e7ea4 | 1_mhz | 1_mhz | 0.000244141 | 1_mhz | PASS |
| 95215dec97ba41d8 | 3_mhz | 3_mhz | 0.000244141 | 3_mhz | PASS |
| 7ca816d867007d78 | 30_mhz | 30_mhz | 0.000244141 | 30_mhz | PASS |

- Gate nulo holdout: **PASS**.
- Gate de identificación: **PASS** (7/7).
- Calibración: 4095 rotaciones circulares de residuo de desarrollo, alfa familiar 0.05.

## Autoridad de claims

- fixed_grid_single_holdout_false_alarm: **SUPPORTED** — one seed-committed null replay over seven fixed AION frequencies
- fixed_grid_signal_identification_0p6rad: **SUPPORTED** — 7/7 tangent-space injections identified in this holdout
- independent_repeated_false_positive_rate: **NOT_ESTIMABLE** — one reused holdout background is not an independent repeated campaign
- continuous_band_blind_search: **NOT_ESTIMABLE** — only seven preregistered target frequencies were tested
- dark_matter_or_gravitational_wave_detection: **NOT_ESTIMABLE** — signals are declared software injections, not unknown physical events
- nonlinear_raw_likelihood_equivalence: **NOT_ESTIMABLE** — the injected perturbation is the first-order fringe tangent model

El resultado no es una detección física, no estima una búsqueda continua ni una tasa frecuentista de falsa alarma sobre repeticiones instrumentales independientes.
