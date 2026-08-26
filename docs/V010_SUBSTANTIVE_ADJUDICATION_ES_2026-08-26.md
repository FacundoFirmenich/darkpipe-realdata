# DarkPipe 0.10 — adjudicación sustantiva de shadows e inobservables

## Resultado que cambia la posición del proyecto

DarkPipe dispone por primera vez de una cadena experimental completa y
cronológicamente gobernada:

`observables reales -> shadow firmada -> inobservables derivados condicionados`.

El diseño se congeló en `5372d5f`, se fusionó en `main` mediante el PR 16 y la
única ejecución oficial fue GitHub Actions `32975513896`, sobre el commit
`4819501a0b10709f6128cbd992ad2e9fac830359`. El job terminó con éxito y publicó
un único artefacto de 743,707 bytes, digest SHA-256
`8e31b5dacd12342255e47a5a2c62e4c6eeabeb0292d60cf59276df888f92083f`.
No hubo relanzamiento ni ajuste posterior al resultado.

## Qué se observó

De 3,391 radios SPARC disponibles, los cortes preregistrados conservaron 2,700
radios pertenecientes a 149 galaxias. Todos los valores numéricos son finitos y
no existen pares galaxia-radio duplicados. La clasificación puntual posterior
fue:

| Estado de la shadow/inobservable | Radios | Fracción |
|---|---:|---:|
| discrepancia positiva sostenida al 95% | 1,917 | 71.00% |
| signo ambiguo al 95% | 775 | 28.70% |
| discrepancia negativa sostenida al 95% | 8 | 0.30% |

La estructura no se reduce al recuento puntual. De las 149 galaxias, 145
contienen al menos un radio positivo sostenido y 76 son positivas en todos sus
radios seleccionados. En el radio más externo de cada galaxia hay 144 perfiles
positivos y 5 ambiguos, sin perfiles negativos sostenidos. Esta regularidad
radial es descriptiva bajo el operador congelado; no convierte los puntos
correlacionados de una misma galaxia en experimentos independientes.

## Evidencia adversa preservada

Los ocho perfiles negativos sostenidos pertenecen a cuatro galaxias: IC4202
(2), NGC0891 (2), NGC4217 (3) y UGC09037 (1), todos en radios internos de la
selección. Además, NGC3949, NGC4051, NGC5005 y UGC11557 no presentan ningún
radio positivo sostenido: sus 33 radios combinados son ambiguos. En total hay
123 discrepancias nominales negativas antes de propagar nuisances, de las
cuales solo ocho conservan signo negativo al 95%.

Estos casos no se eliminan ni se reinterpretan como señal. Delimitan regiones
donde pueden dominar cierre bariónico, geometría, dinámica no circular,
resolución o sistemáticas no incluidas, y constituyen objetivos prioritarios
para una auditoría posterior de identificabilidad.

## Qué es el inobservable derivado

En cada radio se conserva la distribución posterior de:

- aceleración efectiva firmada
  `g_I = (V_obs^2 - V_bar^2) / R`;
- masa encerrada esférico-equivalente
  `M_I = (V_obs^2 - V_bar^2) R / G`.

La mediana puntual de `g_I` tiene mediana muestral
`3.637881300389013e-11 m s^-2`; la mediana puntual de `M_I` tiene mediana
muestral `1.5111954040417904e10` masas solares. Estas dos cifras resumen una
colección heterogénea de radios y galaxias: no son constantes universales ni
estimadores poblacionales.

La autoridad exacta es
`DERIVED_EFFECTIVE_INOBSERVABLE_CONDITIONAL_NOT_ONTOLOGIZED`. Se obtuvo un
objeto inferencial que los modelos físicos deberán explicar; no se obtuvo su
identidad material.

## Significado científico y epistemológico

El avance respecto de v0.9 es categorial. v0.9 produjo un nulo detectorial GPS
válido pero periférico a la misión. v0.10 deriva una preimagen restringida de
la shadow cinemático-bariónica y propaga distancia, inclinación, errores de
velocidad y razones masa-luz. Por tanto, ya existe algo que comparar entre
arquitecturas, sin inventar un latente arbitrario.

El resultado es compatible con la necesidad conocida de una contribución
dinámica adicional en gran parte de las curvas de rotación, pero no adjudica
entre Lambda-CDM, MOND, modificaciones gravitatorias, sistemáticas bariónicas
o la conjetura morfotopológica de hiperestados plasmáticos. Tampoco establece
partículas, densidad tridimensional, mecanismo gravitatorio, fase,
multifractalidad, topología ni genealogía: esos componentes permanecen
`NOT_ESTIMABLE`.

## Limitaciones que gobiernan el siguiente salto

1. Los radios comparten draws de distancia, inclinación y masa-luz por galaxia;
   los 2,700 estados puntuales no son 2,700 evidencias independientes.
2. La masa derivada es esférico-equivalente y depende de dinámica circular y
   mapeo centrípeto newtoniano.
3. El coste de transformación publicado mantiene los nuisances restantes
   fijos; no es todavía un coste factométrico total.
4. No se modelaron barras, warps, presión, asimetrías, covarianzas publicadas no
   disponibles ni incertidumbre de forma tridimensional.
5. El resultado usa una sola familia de shadow. La identificación arquitectónica
   requiere al menos otra proyección independiente, por ejemplo lensing.

## Consecuencia y próximo paso crítico

La condición mínima exigida por la misión está cumplida: ya hay inobservables
derivados de shadows de observables. El siguiente salto no consiste en buscar
otra anomalía instrumental aislada ni en declarar una sustancia. Consiste en
construir una inferencia multi-shadow que una cinemática radial, geometría de
lensing y contexto bariónico con covarianza jerárquica, y después evaluar qué
arquitecturas reproducen simultáneamente esos inobservables, especialmente sus
transiciones radiales, ambigüedades y casos adversos.

## Custodia y deuda técnica

Los crudos SPARC se verificaron por tamaño y hashes, se usaron en scratch
efímero y se eliminaron antes de terminar el job. El dataset declara CC-BY-4.0;
el software DarkPipe permanece bajo GNU GPL versión 3 o posterior,
`GPL-3.0-or-later`, sin cláusula `only`.

GitHub emitió una advertencia porque `actions/checkout@v4`,
`actions/setup-python@v5` y `actions/upload-artifact@v4` aún declaran Node 20 y
el runner los forzó a Node 24. No afectó el resultado terminal, pero exige una
actualización futura de acciones; se conserva como deuda técnica explícita.
