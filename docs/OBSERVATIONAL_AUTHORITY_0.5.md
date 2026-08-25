# DarkPipe 0.5 — contrato de autoridad observacional

## Objetivo y evidencia de origen

El contrato impide que una operación acotada adquiera autoridad que sus datos no contienen. No modifica retrospectivamente v0.4.

Se recuperaron a EOF dos conversaciones: `observational_certainty_genealogy` (22 turnos) y `aad_tcs_adjacent_genealogy` (94). Total: 13 páginas, 116 turnos y 221 elementos. Un mensaje temprano del asistente conserva exactamente 20.000 caracteres con `truncated=true`; su cola es desconocida y no se reconstruye. Diez adjuntos fueron hasheados, pero no se publican sus bytes.

Los JSON crudos quedan en custodia privada e ignorados por Git. El manifiesto público contiene hashes, conteos y la pérdida adversa, sin IDs nativos en claro ni texto de conversación.

## Precedencia aplicada

Las correcciones posteriores explícitas del usuario prevalecen sobre síntesis anteriores:

1. El Principio de Certidumbre Observacional se usa como disciplina de observación/autoridad, no como inversión de Heisenberg.
2. Un desacople observado no establece causa, duración, significado, intención ni provisionalidad.
3. Observar no autoriza automáticamente sensores, medición o intervención.
4. La conducencia es contextual y vectorial; `NOT_ESTIMABLE` y `NOT_APPLICABLE` no son cero.
5. Una hipótesis sin autoridad se conserva future-only; no se borra ni promociona por recurrencia.
6. Datos reales, shadow y evidencia verificada mantienen jurisdicciones separadas.
7. Evidencia posterior sólo actualiza estados futuros; no reescribe decisiones históricas.

## Exclusiones

No entran como física o matemática establecida de DarkPipe: `neoHEOM` y elementos posteriores descartados; teorema universal de tríada; multifractalidad por definición; `PCO = U^-1` literal; holoquanto como sustituto del quantum; cosmologías o biologías especulativas; cifras sin artefacto reproducible.

`FEE` y `FEE+` son los términos exactos; `Fi` queda excluido. DarkPipe 0.5 no se autodeclara FEE+. Ángulo/spin y factometría quedan como genealogía adyacente, no runtime.

## Contrato ejecutable

`ObservationEnvelope` declara fuente, observable, inicio/fin/base temporal, escala, capa, resolución, preprocesamiento y procedencia.

`ObservedDecoupling` sólo admite lados, estadístico, valor, unidad y envolventes. No tiene campos interpretativos.

`ClaimLedger` distingue `OBSERVATION`, `ASSOCIATION`, `CAUSAL`, `DETECTION`, `GENERALIZATION` e `INTERVENTION`. Un recibo observacional sólo promociona los dos primeros; los demás generan `AuthorityError`.

Estados: `OPEN`, `OBSERVED`, `SUPPORTED`, `CONTRADICTED`, `NOT_ESTIMABLE`, `NOT_APPLICABLE` y `ABSTAIN`. Claims sin evidencia quedan retenidos con blockers y `future_only=true`.

`ConducenceVector` preserva contexto y ejes; `scalar_score()` genera `AuthorityError`.

## Aplicación

AION conserva E1/E2. Integridad y recuperación: `SUPPORTED`. Intervalo HLN−LLN: `OBSERVED`. “El ruido añadido no causa efecto”, detección, transferencia e intervención: `NOT_ESTIMABLE`.

NOAA–USGS registra ventana caracterizada como `SUPPORTED` y asociación de la ventana como `OBSERVED`. Causalidad, detección, generalización e intervención permanecen `NOT_ESTIMABLE`.

## Consecuencia

Un PASS sigue visible y cuantificado sin convertirse en claim mayor. Un `NOT_ESTIMABLE` sigue visible sin confundirse con fracaso o cero. El contrato mejora auditabilidad; no añade evidencia física ni sustituye la próxima campaña ciega/holdout.
