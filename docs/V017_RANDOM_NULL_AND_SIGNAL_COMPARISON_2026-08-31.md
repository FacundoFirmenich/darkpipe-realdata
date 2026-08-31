# DarkPipe v0.17 — nulo aleatorio real y comparación con la señal completa

Fecha: 2026-08-31
Estado: `REAL_STRATIFIED_RANDOM_PILOT_COMPLETE__SIGNAL_CONTAMINATION_OBSERVED__FINAL_50X_CONTROL_BLOCKED_BY_COMPUTE_AUTHORITY`

## Cierre sustantivo

DarkPipe está mejor posicionado que en el checkpoint anterior porque el control
aleatorio dejó de ser una especificación y pasó a ser una medición ejecutada de
extremo a extremo. Se procesaron 10.060 coordenadas aleatorias auténticas —diez
por cada una de las 1006 teselas oficiales KiDS— contra las 21.262.011 fuentes
SOM-gold. Los ocho intervalos remotos exactos produjeron 575.059.669 pares
candidatos y 433.841.322 pares aceptados. No se guardó una matriz de pares ni se
descargó el FITS de 17,7 GB al equipo local: las ocho reducciones compactas
sumaban 13,31 MB y quedaron selladas antes de eliminar la copia transitoria.

El hallazgo principal es adverso y científicamente decisivo. El canal
tangencial aleatorio no es compatible con cero en el mayor radio del piloto,
`R = 10,24094 Mpc/h70`: `DeltaSigma_random = -2,8076e11 +/- 9,2092e10
M_sun/Mpc^2`, equivalente a `-3,05` desviaciones estándar diagonales. Tras la
deproyección individual y antes del apilado, el mismo borde produce
`g_obs,random = -1,5591e-13 +/- 3,1197e-14 m/s^2`, equivalente a `-5,00`
desviaciones estándar diagonales. El máximo del canal cruzado es menor:
`1,86` en ESD y `1,60` en aceleración deproyectada.

Esta asimetría es compatible con la clase de sesgo aditivo de gran escala que
el control aleatorio está diseñado para revelar. No demuestra su causa, no es
una detección cosmológica y no autoriza una interpretación en materia oscura o
hiperestados plásmicos. Sí demuestra que la sustracción aleatoria es un término
material del estimador: omitirla permitiría que la geometría y selección del
survey se transformasen por deproyección en una aparente señal radial.

## Comparación con la señal real

La misma reducción deproject-first se aplicó a la señal completa de 106.843
lentes y 3.017.858.899 pares aceptados. La comparación exploratoria
`señal - piloto aleatorio` muestra que el término aleatorio es comparable o
mayor que la señal en varios radios. Por ejemplo, en el mayor bin:

| Superficie | Señal | Piloto aleatorio | Corregida por piloto |
|---|---:|---:|---:|
| `DeltaSigma [M_sun/Mpc^2]` | `-9,6291e10` | `-2,8076e11` | `1,8447e11` |
| `g_obs [m/s^2]` | `-5,3966e-14` | `-1,5591e-13` | `1,0195e-13` |

La corrección incluso cambia el signo en ese borde. En `R = 2,20645 Mpc/h70`,
la señal ESD apilada es `5,0024e9`, mientras que el control piloto es
`-2,6317e11 M_sun/Mpc^2`. Esta dominancia no significa que la corrección final
tendrá exactamente ese valor: el piloto contiene solo 10.060 posiciones, no
las 45.038.900 del control preregistrado, y su error domina en muchos bins.
Significa que la RAR no puede abrirse legítimamente usando solo la superficie
de señal.

La primera celda radial de la señal queda `NaN`: no alcanza los dos puntos
válidos mínimos que exige la integral lineal. Se conserva como no estimable;
no fue rellenada, extrapolada ni suprimida.

## Límites estadísticos

Las significancias anteriores utilizan errores analíticos diagonales. No
incluyen la covarianza radial completa, correlaciones por reutilización de
fuentes, varianza de campo a campo ni una corrección por múltiples bins. Por
ello son diagnósticos de localización, no p-valores globales ni adjudicaciones
de modelo. El control de 10 puntos por tesela es un subconjunto uniforme sin
reemplazo del catálogo aleatorio congelado con semilla `20260831017`; es una
simulación de control científicamente necesaria, no datos sintéticos usados
como sustituto de observaciones. Su jurisdicción permanece:

`ENGINEERING_AND_NULL_PILOT_NOT_50X_ADDITIVE_BIAS_ESTIMATE`.

El resultado histórico de los pares y el nulo no cambia al optimizar el
integrador. La deproyección exacta respecto del interpolante lineal firmado se
reformuló como operadores lineales por máscara radial. Ocho pruebas verifican
la equivalencia con la integral escalar y la propagación de varianza de Eq. 60.
La reducción completa de los 106.843 perfiles pasó a 76,10 segundos en local,
sin deproyectar el promedio ni cambiar la regla de cola.

## Frontera de cómputo observada

El run público `33408609373` finalizó correctamente. Cada una de las ocho
particiones del piloto tardó entre 186 y 335 segundos en el paso de asociación.
El cociente exacto entre el control final y el piloto es `4477,0278`. Una
extrapolación lineal del conteo observado sitúa el control 50x en
aproximadamente `2,5746e12` pares candidatos y `1,9423e12` aceptados. Bajo la
implementación actual, cada partición original requeriría entre 231 y 417 horas,
muy por encima del límite de seis horas de un job alojado por GitHub.

GitHub Actions sigue sirviendo para CI, índices y pilotos, pero ya no es una vía
válida para ejecutar el control final con ocho particiones. Aumentar la matriz a
unas 39–70 particiones por cada partición actual sería una fragmentación
operativa de cientos de jobs y no elimina la repetición de lectura. El runner
Linux público dispone además de 14 GB de SSD, menos que los 17,7 GB del FITS.

## Autoridad y próxima acción crítica

La próxima acción científicamente correcta es ejecutar el control congelado
50x en un nodo remoto con al menos 40 GB de scratch, una sola copia efímera del
FITS y reducción por lotes directamente a sumas compactas. El código no debe
persistir 45 millones de perfiles ni una matriz de pares. Al finalizar debe
producir el control tangencial, cruzado, deproject-first, covarianza por tesela
o jackknife, y después la única superficie admisible para derivar
inobservables: señal menos control con incertidumbre completa.

Existe capacidad técnica de acceso a un VPS, pero el recibo vigente la limita a
KCH Jarvis y ese carril está pausado. `capability != permission != authority !=
execution`: DarkPipe no reutilizó esa llave. El bloqueo real no es software ni
datos; es la falta de una jurisdicción remota expresamente autorizada para
DarkPipe v0.17. No se tocó `main` y el trabajo continúa solamente en el PR 24.

## Evidencia compacta

- Run remoto: <https://github.com/FacundoFirmenich/darkpipe-realdata/actions/runs/33408609373>
- Metodología deproject-first y control aleatorio: <https://arxiv.org/html/2310.15248>
- Especificaciones de runners: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>
- Límite de job: <https://docs.github.com/en/actions/reference/limits>
- `random_null_profiles.csv`: 27 bins y ambos canales.
- `signal_random_comparison.csv`: señal, piloto, corrección y errores diagonales.
- `partition_artifact_custody.json`: hashes e intervalos de las ocho particiones.

Todos los payloads compactos mantienen `scientific_result = false`. Este
checkpoint valida el instrumento computacional y localiza contaminación real;
no adjudica todavía la conjetura física gobernante.
