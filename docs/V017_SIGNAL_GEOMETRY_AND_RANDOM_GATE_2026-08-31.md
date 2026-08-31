# DarkPipe v0.17 — cierre sustantivo de señal y apertura del control aleatorio

Fecha: 2026-08-31
Estado: `SIGNAL_SUFFICIENT_STATISTICS_COMPLETE__RANDOM_CONTROL_PENDING`

## Resultado observado

La lectura remota íntegra del catálogo KiDS DR4.1 SOM-gold terminó sobre sus
21.262.011 filas sin custodiar localmente el FITS de 17,7 GB. La reducción
compacta reúne 106.843 lentes, 19.109.925 fuentes que pasan los filtros,
4.550.915.122 pares candidatos y 3.017.858.899 pares aceptados en 27 bins
radiales. Los ocho intervalos son exactos, disjuntos y cubren
`[0, 21262011)`.

El payload fusionado local contiene estadísticas suficientes aditivas, no una
tabla de pares ni un resultado cosmológico. Su hash de contenido es
`59e39fccb35df42524a10f0766480ec746ad13f49e53a35764c0e5d7edd1e2d9`;
el payload de lentes es
`3c4a43f9516e438a9c35e098ddd3d37768180f9d84e08fb01d73924c899c2b0a`,
la tabla de Sigma crítica es
`02700c57c9affa47630881b4f2f23023fd632ca4cd0a42c82c89ee78b9bd3da1`
y el vector radial congelado es
`a12f1929640d79a9f50730f9907070c9a0a8febce0a9f13cc28b738d52853ee7`.

## Hallazgo adverso y resolución metodológica

El primer intento de fusión abortó antes de abrir las matrices de señal porque
la unión de `THELI_NAME` contenía 988 nombres y el preregistro exigía 1006. El
aborto fue correcto; lo incorrecto era identificar ambos cardinales como una
misma superficie. La comparación independiente con el manifiesto oficial de
descarga (`kids_dr4.0_cat_wget.sh`, 1006 entradas) mostró que:

- los 988 nombres `THELI_NAME` están contenidos en el footprint oficial;
- 1006 es el número de teselas oficiales de catálogo y la superficie correcta
  para sembrar coordenadas aleatorias;
- 988 es el número de nombres de pointing/reducción realmente presentes en la
  columna de señal y la superficie correcta para exigir completitud al escaneo;
- la tabla pública de observaciones contiene 1015 centros: las 1006 teselas del
  release y nueve entradas adicionales, que no deben incorporarse al azar.

No se relajó ningún gate: se tiparon dos jurisdicciones que antes estaban
confladas y ambas conservan cardinal exacto.

## Significado científico y límite

El proyecto está mejor posicionado porque ya posee una medición observacional
completa y reproducible de la señal de lente débil a nivel de objeto. Aún no
existe una adjudicación de RAR, materia oscura, plasma ni hiperestados: faltan
la sustracción aleatoria, la covarianza, los canales cruzados, los nulos y la
deproyección comparada. El estado correcto sigue siendo `scientific_result =
false`.

## Próxima acción crítica

El control aleatorio exige 45.038.900 coordenadas sobre las 1006 teselas y no
puede persistir matrices por lente de tamaño cercano a 50 GB. Se incorpora un
índice remoto exacto de intervalos contiguos por `THELI_NAME`, construido en
ocho trabajos efímeros sobre GitHub Actions. Ese índice permitirá seleccionar
solamente rangos fuente espacialmente pertinentes por lote de teselas,
reducirlos inmediatamente a sumas de apilado, covarianza y nulos, y descargar
al equipo local únicamente artefactos compactos.

La deproyección implementada es exacta únicamente respecto de la integral del
interpolante lineal firmado elegido. No convierte las hipótesis físicas, las
colas exteriores ni el modelo cosmológico en verdades observacionales.

## Resultado del índice y decisión de transporte

El run de GitHub Actions `33404790882` terminó con los ocho trabajos y la suite
completa en verde. El índice fusionado cubre las 21.262.011 filas, contiene los
988 nombres esperados y conserva el hash de sus 96.741 tramos contiguos:
`e76d1a0204bafdb0d08d647df9dbde50dd24f8b26b08f228ce7b593b6f496a8c`.
Cada uno de los ocho artefactos efímeros queda sellado por bytes, hash de
archivo, hash de tramos e intervalo de filas dentro del índice fusionado.

El resultado adverso útil es que todos los nombres `THELI_NAME` reaparecen en
múltiples tramos: la mediana es 99 tramos por nombre y el total es 96.741. Por
ello, consultar por tesela directamente no ahorra transporte suficiente. La
frontera medida sobre las 1006 teselas y el radio angular conservador da:

| Hueco coalescido máximo | Peticiones | Bytes remotos | Sobrecarga |
|---:|---:|---:|---:|
| 0 filas | 982.156 | 453,9 GB | 0,0 % |
| 128 filas | 700.634 | 462,7 GB | 1,9 % |
| 512 filas | 486.213 | 514,3 GB | 11,8 % |
| 2.048 filas | 328.619 | 637,9 GB | 28,8 % |

Una de las 1006 teselas oficiales, `KIDS_150.1_2.2`, no tiene ningún pointing
THELI a menos del radio central conservador de 3,21 grados; sus coordenadas
aleatorias no producirían pares en la superficie fuente observada y deben
quedar como contribuciones no estimables, no rellenarse ni eliminarse en
silencio.

Esta medición cambia la próxima acción: el control completo no debe ejecutarse
como mil consultas dispersas. La solución científicamente fiel es materializar
una sola copia temporal del FITS de 17,7 GB en almacenamiento remoto y leerla
localmente desde el nodo de cómputo, persistiendo solo reducciones aditivas. La
extrapolación del ritmo de pares observado en la señal sitúa el control 50x en
aproximadamente 1,92 billones de pares candidatos; es una proyección de carga,
no un conteo observado ni un resultado científico.

La llave VPS existente no autoriza esta campaña: su recibo limita la
jurisdicción a Jarvis y ese carril está pausado. GitHub Actions sigue siendo la
vía remota autorizada; un VPS sería solo un acelerador futuro tras ampliar
expresamente su jurisdicción a DarkPipe.
