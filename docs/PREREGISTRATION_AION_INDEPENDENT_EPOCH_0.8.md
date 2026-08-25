# DarkPipe 0.8: prerregistro de época AION independiente

ID: DP-AION-INDEPENDENT-0.8-20260825

Estado: protocolo ejecutable congelable después de un inventario ciego y antes
de leer valores de excitación del desarrollo o del holdout RID34056. El commit
Git que contenga este documento, el módulo, el runner y los tests será la
autoridad del prerregistro.

## Objetivo y techo de afirmación

La campaña pregunta si un máximo de frecuencia descubierto en el 40 % inicial
de la época histórica AION RID34056 se confirma en el 60 % cronológico restante
con control familiar del error. RID34056 se adquirió el 13 de diciembre de 2024,
casi un año antes y con otro commit experimental que la familia 2025 usada por
v0.6-v0.7. Es una época de adquisición independiente, pero pertenece a la misma
familia instrumental AION: no es validación en un segundo instrumento.

Un resultado terminal puede respaldar, como máximo, la validación del detector
y un candidato de sensor limitado a esta época. No es una detección física de
materia oscura, ondas gravitacionales ni del sistema morfotopológico de
hiperestados plásmicos conjeturado.

## Fuente, versión y jurisdicción

- Registro histórico Zenodo v1: 15166670; RID34056.
- Archivo: `000034056-DifferentialClockInterferometryWithNoiseFrag.h5`.
- Bytes: 564.439.752.
- MD5: `e7053ad0a8401c4198b4729feec8441c`.
- SHA-256 observado por el inventario cloud:
  `daa120265407b82fd35f60035c806beb81c52103ab80f1c06db2aa08c98be981`.
- Inventario ciego: run 32879655060, 63 datasets, cero valores endpoint leídos,
  bruto eliminado y no subido.
- El registro v1 fue sucedido por v2 dentro del mismo concept record. Se usa
  como época histórica diferenciada, no como versión canónica sustitutiva de v2.
- Zenodo no declara licencia de reutilización legible por máquina:
  `NO_MACHINE_READABLE_REUSE_LICENSE_DECLARED`. DarkPipe descarga para
  análisis reproducible, no redistribuye el HDF5 ni publica filas derivadas.
- El código DarkPipe conserva GNU GPL versión 3 o posterior,
  SPDX `GPL-3.0-or-later`, nunca `GPL-3.0-only`.

## Canales congelados

Las 22.839 filas tienen fase aplicada, condición de ruido, timestamp UTC,
fracciones de excitación forward/backward, números atómicos forward/backward,
frecuencia del contador Rigol y cuatro contadores de relock. No se leen imágenes
ni perfiles de cámara.

`axis_1=0` define LLN y `axis_1=2` define HLN. La fase en turns se transforma
exactamente como `phi=2*pi*axis_0`.

## Cronología y separación de acceso

Para cada condición se realiza orden estable por timestamp y
`floor(0.40*n)` define desarrollo; el resto es holdout. El stage discovery
puede leer para todas las filas sólo fase, condición y timestamp, necesarios
para fijar la cronología. Lee excitación, número atómico y monitores únicamente
en los índices de desarrollo. El stage confirm vuelve a descargar la misma
fuente verificada y sólo entonces lee el holdout.

## Calidad congelada

En desarrollo, para cada condición y monitor se calcula la moda exacta, con
desempate por el menor valor. Si ninguna moda abarca al menos el 50 % de valores
finitos, la campaña se abstiene. En ambos segmentos se conservan sólo filas con:

1. fase finita en [0,1] turns y timestamp finito;
2. ambas excitaciones finitas en [0,1];
3. ambos números atómicos finitos y positivos;
4. cada monitor igual a la moda fijada en desarrollo;
5. primer timestamp en caso de duplicación estable.

No se inventan umbrales de número atómico. Deben quedar al menos 1.000 filas por
condición y segmento o el resultado es `ABSTAIN_INTEGRITY`.

## Operador observacional y nuisance

Para cada condición y brazo se ajusta en desarrollo la base

`[1,u,cos(phi),sin(phi),u*cos(phi),u*sin(phi)]`,

donde `u` es el tiempo reescalado a [-1,1] sobre toda la condición. La escala
es 1,4826 veces el MAD residual, con desviación estándar sólo como fallback.

Una perturbación diferencial de fase usa la derivada de la franja con signo
+1/2 en forward y -1/2 en backward. A cada frecuencia se perfilan coseno y seno
junto con nuisance y se usa la forma cuadrática exacta de dos cuadraturas. Este
es un operador instrumental local; no es aún un mapa de acoplamiento físico de
la conjetura.

## Banda y candidatos de desarrollo

- Piso: 0,1 mHz.
- Techo: el mínimo entre 75 mHz y 0,90 veces el menor Nyquist nominal calculado
  desde la mediana de cadencia LLN/HLN.
- Muestreo irregular: Nyquist es diagnóstico conservador, no idealización.
- Paso: una celda Rayleigh, 1/T del desarrollo conjunto.
- Elegibilidad: máximo local finito, izquierda no mayor y derecha menor.
- Ranking: estadístico descendente y luego frecuencia ascendente.
- Separación mínima: dos celdas Rayleigh.
- Familia máxima: ocho; sin umbral de significación en desarrollo.

El JSON y la figura de candidatos deben quedar en un commit público antes de
calcular cualquier endpoint de excitación del holdout.

## Potencia declarada

Después de seleccionar los candidatos —sin posibilidad de revisarlos— se mide
una calibración fija sobre ruido auténtico de desarrollo. Las frecuencias son
0,1; 0,3; 1; 3; 10; 30 y 100 mHz, restringidas a la banda adaptativa. Las
amplitudes 0,3; 0,6 y 1,2 rad provienen de la familia de inyecciones upstream.
Se usan 16 fases equiespaciadas y la misma perturbación tangente declarada.

La potencia es `FIXED_FAMILY_TANGENT_INJECTION_POWER`: no es potencia de la
búsqueda continua, no es sensibilidad a un acoplamiento físico y no convierte
inyecciones sintéticas en observaciones.

## Confirmación y multiplicidad

Sólo se evalúan en holdout las frecuencias congeladas. Se generan exactamente
4.095 rotaciones circulares no nulas por condición con seed 2026082508;
forward/backward comparten rotación, LLN/HLN son independientes y cada réplica
aporta el máximo sobre toda la familia. Para estadístico T:

`p_FWER=(1 + count(null_max >= T))/4096`.

Un candidato confirma si `p_FWER<=0.05`. No se cambian familia, banda, nuisance,
seed ni umbral después del commit de candidatos.

## Decisiones terminales

- `NO_INDEPENDENT_HOLDOUT_CANDIDATE`: ninguno confirma.
- `INDEPENDENT_EPOCH_SENSOR_CANDIDATE`: al menos uno confirma.
- `ABSTAIN_INTEGRITY`: falla fuente, esquema, calidad, cronología o custodia.

Con sólo dos épocas, incluso dos resultados nulos no estiman una tasa de falsos
positivos. Permanecen `NOT_ESTIMABLE`: causalidad, exclusión física,
transferencia a otro instrumento, materia oscura, ondas gravitacionales,
conjetura morfotopológica y potencia física de la búsqueda continua.
