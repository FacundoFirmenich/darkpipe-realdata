# DarkPipe: siguiente gate KiDS, 2026-10-30

## Resultado y consecuencia para la misión

El proyecto queda mejor posicionado metodológicamente: dispone de un cálculo
emparejado de la covarianza de señal menos control y de un auditor ejecutable
de las entradas congeladas. El gate científico sigue abierto. No hay una
nueva RAR corregida ni un control aleatorio 50x terminado.

La recuperación de contexto local encontró que las campañas AION 0.6-0.8 y
GPS 0.9 ya estaban cerradas. El avance vigente es KiDS 0.17, en otra línea del
mismo repositorio. Se preservaron sin modificaciones las dos superficies
locales preexistentes, sus archivos no versionados y los artefactos históricos.
No se incorporó la actividad de tarifas energéticas encontrada en remoto.

## Hallazgo estadístico y cambio realizado

El jackknife por centros aleatorios preparado en septiembre cuantifica una
covarianza del control R. No produce por sí solo la covarianza de D=S-R:

`C_D = C_S + C_R - C_SR - C_SR.T`.

Como señal y control reutilizan fuentes, asumir independencia requiere una
justificación que esta campaña no aporta. El nuevo módulo
`kids_paired_covariance.py` recibe sumas suficientes por regiones espaciales
emparejadas, elimina la misma región de ambas poblaciones y calcula la
covarianza conjunta de cuatro canales. Mantiene radios/canales no estimables
como NaN y no invierte automáticamente matrices singulares.

Esta corrección es algebraica y metodológica. No hace existir las sumas por
región que faltan: el mapa espacial de exclusiones, la política de eliminación
de fuentes, los replicados de señal y el control 50x completo todavía deben
construirse y sellarse antes de abrir la RAR final. La fórmula delete-one
requiere una región de tamaño comparable o una justificación apropiada; las
1006 teselas originales no son automáticamente un diseño de covarianza válido.

## Verificación observada

- 17/17 pruebas focales: PASS en 3,02 s, Python 3.14.
- Comprobación analítica de cancelación de un modo común y de la identidad
  completa de covarianzas; rechazo de regiones permutadas y datos no finitos.
- Prueba adversa de manipulación de un byte congelado: abstención correcta.
- Entradas auténticas: cuatro hashes PASS; índice con cobertura exacta de
  21.262.011 filas, 988 pointings y conservación de 45.038.900 randoms.
- Gate ejecutado: `BLOCKED_EXECUTION_AND_PAIRED_COVARIANCE`.

Los primeros intentos con temporales de pytest fallaron antes de dos fixtures:
acceso denegado al temporal global y luego inexistencia del padre del temporal
de workspace. Se usó un temporal nuevo de ruta corta y la suite terminó. No se
cambió ningún dato, umbral o aserción para obtener el PASS.

El primer CI Ubuntu detectó un contrato de bytes mal definido en este nuevo
auditor: había tomado el hash CRLF del checkout Windows, aunque Git conserva
explícitamente LF para ese JSON. Se corrigió admitiendo sólo los dos hashes
exactos conocidos y verificando su transformación; cualquier otro byte sigue
produciendo abstención. No se mutaron las entradas históricas.

El CI general detectó además dos comparaciones históricas AION con diferencias
numéricas de unos 1e-12 en los errores normalizados, con decisiones 7/7
intactas. Se probó declarar `float_precision="high"`; el cambio no reparó el
fallo en Linux y fue retirado. La causa exacta de la diferencia entre entornos
sigue pendiente; no se afirma que sea sólo una versión concreta de pandas.
Las aserciones, el código histórico y los recibos científicos permanecen
intactos. Los runs adversos `41133174270`, `41133174272`, `41133243313`,
`41133991790` y `41133997722` se conservan como fallidos. El gate focal sí
terminó PASS, run `41133991749`, 17/17 pruebas. No se declara CI global verde.

Una ampliación local dio 33 pases y un fallo de manifiesto durante una
escritura concurrente del índice Git por el propio agente. Esta carrera de
validación se preserva como adversa; no cambia ningún resultado observacional.

## Frontera científica

La corrección geométrica histórica permanece: discrepancia mediana 0,04943 dex,
15 bins positivos pero sólo 10/15 dentro de la envolvente publicada; por tanto
`reproduction_gate=false`. El piloto aleatorio de 10.060 posiciones no puede
sustituir el control congelado de 45.038.900. Las pruebas nuevas usan fixtures
analíticos declarados y no constituyen observaciones adicionales.

## Recurso y decisión necesarios

El FITS pesa 17.712.469.440 bytes y no se descargó durante este gate. La
proyección histórica del algoritmo anterior es 231-417 horas por partición
original, ocho particiones; no es una medición del nuevo algoritmo por tesela.
GitHub mantiene un máximo de seis horas por job alojado y 14 GB de SSD en sus
runners Linux estándar. Esta combinación no admite sin más el plan de una
copia completa y ocho jobs. Las llaves VPS históricas tienen jurisdicción
Jarvis y no se reutilizaron.

El siguiente paso concreto es admitir un nodo DarkPipe con al menos 40 GB de
scratch, ejecutar un benchmark limitado a 30 minutos y obtener un recibo de
tiempo/memoria/pares/bytes. El benchmark determina el presupuesto finito y la
partición de la campaña; no autoriza automáticamente el 50x completo. En
paralelo hay que sellar el mapa de regiones y producir la señal/control con
exclusiones coincidentes. Sólo después podrá ejecutarse la reproducción con
covarianza espacial, manteniendo aparte los sistemáticos no cubiertos.

Código y documentos nuevos: GPL-3.0-or-later, sin only. No se fusiona main ni
se compran recursos. El PR es una propuesta verificable del siguiente gate,
no una declaración de campaña científica completada.
