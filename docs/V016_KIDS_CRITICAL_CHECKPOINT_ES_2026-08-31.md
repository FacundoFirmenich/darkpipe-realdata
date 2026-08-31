# DarkPipe v0.16 — cierre sustantivo del salto KiDS real-data

## Resultado en plata

El proyecto queda **materialmente mejor posicionado**, pero no queda todavía
autorizado a afirmar que ha detectado la naturaleza de la materia oscura ni un
hiperestado plásmico. El salto real consiste en que ya no dependemos de una
descripción abstracta del dataset: los 17,7 GB del catálogo fuente están
custodiados remotamente por rangos; el software decodifica las tablas FITS
reales sin llenar el disco local; las tablas de lentes se alinearon objeto por
objeto; y ya existe un inobservable derivado real, `eta=log10(gobs/gbar)`,
calculado desde los 15 bins publicados de la RAR de lente débil.

El resultado adverso inicial se conserva: la primera reconstrucción físicamente
concurrente dejó 153.879 lentes, no 106.843. No se maquilló ni se ajustó el radio
para acertar. Sobre ese fallo, el sucesor recuperó de la tabla oficial ESO TAP
los `MAG_GAAP_u/r` nativos de los 1.239.422 objetos KiDS-bright y ejecutó la
geometría cartesiana de distancia angular compatible con la implementación
histórica. El cierre es exacto: **106.843 lentes, delta cero, 100% de filas
emparejadas y ninguna magnitud reconstruida como fallback**. Esto convierte un
fallo localizado en un gate verde reproducible; no convierte la selección en
una medición de lente débil ni en evidencia de plasma.

## Resultado científico que sí existe

Sobre la tabla publicada, el inobservable efectivo `eta` crece de 0,76 a 2,17
dex: el cociente `gobs/gbar` va aproximadamente de 5,75 a 147,91. Los quince
bins presentan exceso efectivo positivo. La pendiente descriptiva ponderada
diagonalmente es 0,511, cercana al comportamiento de raíz cuadrada de la RAR a
baja aceleración. Frente a la forma de referencia con `a0=1,2e-10 m/s²`, la
mediana del residuo es 0,008 dex. Este acuerdo es observacionalmente relevante,
pero no discrimina por sí mismo entre ΛCDM con física bariónica, una realización
concreta de gravedad modificada u otra arquitectura física.

No se calcula un p-valor global: la tabla pública no contiene la covarianza
cruzada de los quince bins y los errores de deproyección crecen mucho en la cola
de menor aceleración. Convertir los errores diagonales en una falsa evidencia
global sería metodológicamente incorrecto. Tampoco se transforma `eta` en
densidad de plasma, partícula oscura o topología: hoy es un inobservable
efectivo condicionado, no una ontología.

## Custodia y disco

El catálogo SOM-gold está dividido en 185 intervalos lógicos contiguos que
cubren exactamente 17.712.469.440 bytes. Cada intervalo tiene SHA-256 de la
fuente y vínculo al objeto de Drive. Hay 187 objetos físicos porque dos rangos
fueron subidos dos veces; ambos duplicados se conservan como evidencia adversa.
Drive no expone un hash de contenido mediante el conector activo, por lo cual el
cierre utiliza una raíz criptográfica de la partición y declara expresamente que
no se calculó un SHA-256 lineal de todo el archivo. El archivo completo nunca se
materializó en los discos locales.

El barrido científico completo del catálogo terminó sobre las 21.262.011
filas, no sobre una muestra. Los cortes publicados dejan 19.109.925 fuentes
con forma y peso finitos y positivos. Los conteos por bin fotométrico son
1.727.608, 3.442.980, 5.624.220, 4.006.695 y 4.308.422. Las medias elípticas
ponderadas globales son `e1=6,8481e-5` y `e2=5,4026e-4`: son diagnósticos de
aditividad residual, no una detección gravitatoria. Además, se descargaron las
cinco distribuciones `n(z)` SOM oficiales y se construyó la tabla real de
`Sigma_crit` efectiva integrando la incertidumbre fotométrica de la lente y
renormalizando cada `n(z)` por detrás de ella, como exige la ecuación 10 del
artículo. El rango obtenido es 3,047e15–9,010e15 Msun/Mpc².

## Estado de los gates

- Custodia byte-a-byte por partición: **verde**.
- Decodificación FITS remota y acotada en memoria: **verde**.
- Alineación objeto-a-objeto de lentes/LePhare: **verde**.
- Reproducción exacta de 106.843 lentes: **verde; delta cero con fotometría GAAP nativa**.
- Inobservable bin-level real `eta`: **verde con jurisdicción publicada**.
- Barrido integral y attrition de 21.262.011 fuentes: **verde**.
- `n(z)` oficial y `Sigma_crit` efectiva de la ecuación 10: **verde**.
- RAR objeto-a-objeto desde las fuentes: **pendiente; estimador calibrado**.
- Random subtraction, cross-shear y covarianza propios: **pendientes**.
- Predicción diferencial de la conjetura plásmica: **NOT_ESTIMABLE**.

## Validación y recibos compactos

El recibo final de selección tiene SHA-256
`10a3d596ddfb882069b3a24c3fbe40be8b6e22f42e2140b0fd22f47a3e79050a`.
El vector exacto de 106.843 índices seleccionados tiene SHA-256
`eaa41bda4a09a3f418129ed6b812f6922afedc7a2e1c38061a0bd1aa23c91fc0`.
La suite histórica completa pasó 94 pruebas usando un directorio temporal dentro
del workspace; la prueba nueva de cierre del recibo también pasó. Un
primer intento registró 13 errores exclusivamente porque el sandbox negó acceso
al directorio temporal global de pytest; no fueron fallos científicos ni de
código y se resolvieron sin cambiar la implementación.

## Próximo salto crítico

La siguiente acción ya no es resolver la muestra de lentes ni barrer las fuentes:
ambos gates están cerrados. Es ejecutar el acumulador lente-fuente sobre el
catálogo completo, generar randoms reproducibles sobre el footprint y sus
máscaras, restar su señal, abrir el cross-shear y estimar la covarianza por
regiones de cielo. Solo después se debe unir un shadow sensible a plasma —SZ,
rayos X o rotación de Faraday— bajo predicciones firmadas antes de mirar el
resultado. Así, un resultado favorable o adverso podrá cambiar realmente la
posición de la conjetura, en vez de limitarse a reinterpretar una discrepancia
gravitatoria ya conocida.
