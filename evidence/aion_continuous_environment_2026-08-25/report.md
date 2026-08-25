# Cierre sustantivo — DarkPipe AION continuo 0.7

Decisión: **NO_HOLDOUT_CANDIDATE**.

## Resultado observado

La banda continua se exploró únicamente en desarrollo; sus candidatos quedaron
fijados antes de evaluar el holdout. La tabla contiene p-valores familiares
obtenidos mediante rotaciones circulares del holdout sobre la familia congelada.

| Candidato | Frecuencia [mHz] | Estadístico | p FWER | Confirmado |
|---|---:|---:|---:|---|
| c001 | 38.0921 | 0.013 | 0.984619 | no |
| c002 | 15.0516 | 0.0107311 | 0.995117 | no |
| c003 | 41.8114 | 0.0192977 | 0.929199 | no |
| c004 | 18.9051 | 0.00469209 | 0.999756 | no |
| c005 | 47.5447 | 0.0408529 | 0.405518 | no |
| c006 | 47.6252 | 0.0162374 | 0.96582 | no |
| c007 | 42.0799 | 0.0258869 | 0.782471 | no |
| c008 | 63.4824 | 0.0144694 | 0.978027 | no |

Estado del contraste geomagnético local: **NOT_APPLICABLE**.
Hartland es un control ambiental medido; OMNI se conserva como contexto
heliosférico y no actúa como veto causal.
Hartland es un observatorio regional, no un magnetómetro co-localizado con AION;
su no asociación no excluye perturbaciones estrictamente locales.

## Significado

NO_HOLDOUT_CANDIDATE significa que ningún pico seleccionado en desarrollo se
replicó bajo la regla congelada. LOCAL_GEOMAGNETIC_ASSOCIATION significa que
al menos un candidato confirmado comparte coherencia por bloques con Hartland.
UNEXPLAINED_SENSOR_CANDIDATE describe una anomalía instrumental que superó
este gate y no quedó asociada a Hartland; no identifica su naturaleza física.

## Autoridad de claims

- split_sample_continuous_search_executed: **SUPPORTED** - development scan and nonempty-family holdout confirmation on one AION epoch
- holdout_candidate_in_frozen_family: **CONTRADICTED** - 0/8 candidates passed familywise alpha 0.05
- local_geomagnetic_association: **NOT_APPLICABLE** - regional Hartland one-second block coherence; association is not causation
- independent_epoch_replication: **NOT_ESTIMABLE** - v0.7 reuses the single 2025-12-19/22 AION control epoch
- morphosyntactic_plasma_dark_matter_hypothesis: **NOT_ESTIMABLE** - no specific physical coupling model or independent replication
- frequency_band_75_to_100_mhz: **NOT_ESTIMABLE** - excluded above the lower development median-cadence nominal Nyquist

La campaña reutiliza una sola época AION y no contiene un modelo físico que
conecte la conjetura del plasma morfo-sintáctico con la materia oscura. Por ello
una detección física y una tasa de falsa
alarma entre campañas independientes permanecen NOT_ESTIMABLE.
