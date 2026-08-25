# DarkPipe 0.4 — validación instrumental AION

Decisión preregistrada: **PASS_BOUNDED**.

## Qué se ha probado

DarkPipe verificó 27/27 archivos seleccionados del depósito AION, evaluó la recuperación de siete modulaciones de fase intencionalmente inyectadas y comparó los derivados de incertidumbre de fase diferencial con bajo y alto ruido láser. Es una validación acotada de evidencia instrumental real; no es una detección de materia oscura ni de ondas gravitacionales.

## E1 — recuperación de frecuencia

| Dataset | f verdadera (mHz) | f recuperada (mHz) | error × T | decisión |
|---|---:|---:|---:|---|
| 0p1_mhz | 0.0999875 | 0.100087 | 0.00881054 | PASS |
| 0p3_mhz | 0.300013 | 0.300396 | 0.0356766 | PASS |
| 1_mhz | 0.999921 | 1.00215 | 0.0454454 | PASS |
| 3_mhz | 3.00001 | 2.99965 | 0.0168914 | PASS |
| 10_mhz | 10 | 10.0004 | 0.00926611 | PASS |
| 30_mhz | 30 | 30.0005 | 0.0259062 | PASS |
| 100_mhz | 100 | 100.001 | 0.0422852 | PASS |

E1: **PASS** (7/7 dentro de una celda de Fourier).

## E2 — consistencia HLN frente a LLN

- Diferencia HLN−LLN: 14.2767 µrad.
- Incertidumbre combinada: 19.283 µrad.
- IC normal bilateral 95%: [-23.518, 52.0714] µrad.
- E2: **PASS**; el intervalo incluye cero.

Un PASS sólo significa que no se resuelve un exceso HLN–LLN dentro de esta representación upstream de incertidumbre. No demuestra equivalencia ni agota sistemáticos.

## Límites obligatorios

- blind-search false-positive rate: `NOT_ESTIMABLE`
- global dark-matter or gravitational-wave significance: `NOT_ESTIMABLE`
- transfer to AION-10 or AION-km sensitivity: `NOT_ESTIMABLE`
- independent full raw-HDF5 marginal-likelihood reproduction: `NOT_ESTIMABLE`

Consulte `report.json`, `validation.png`, `manifest.json` y el preregistro `DP-AION-0.4-20260825` para los números, hashes y reglas exactas.
