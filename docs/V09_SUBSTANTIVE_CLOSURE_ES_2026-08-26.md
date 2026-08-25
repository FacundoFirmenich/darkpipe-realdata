# Cierre sustantivo DarkPipe 0.9

## Resultado y cambio real

DarkPipe queda mejor posicionado que en v0.8 porque ya no depende solo de la
familia instrumental AION: v0.9 ejecuta una prueba prospectiva sobre una red
independiente de 22 relojes GPS de los productos Final de JPL. El unico acceso
al objetivo, autorizado despues de superar el umbral de potencia
prerregistrado, produjo `NO_GPS_NETWORK_TRANSIENT_CANDIDATE`. El maximo del
objetivo fue 7.6678744897237845 y su p exacto por rango, corregido internamente
sobre dos segmentos, todos los centros, ambos signos y 256 plantillas de
velocidad, fue 0.3023255813953488 frente a 42 maximos diarios autenticos.

En plata: la excursion ganadora no fue rara bajo el fondo medido. Doce de los
42 maximos nulos fueron al menos tan grandes como el objetivo, por lo que el
resultado no constituye una candidata debil sino un nulo detectorial claro
dentro del operador congelado. El objetivo no se relanzo, no se reajusto el
banco de plantillas y no se reciclo la ventana tras conocer el resultado.

## Que fue realmente validado

La calibracion previa selecciono 22 nodos con cobertura suficiente y construyo
un combinador coherente usando diferencias de reloj a 30 segundos,
normalizacion robusta y covarianza Ledoit-Wolf. La prueba de potencia declarada
inyecto exclusivamente frentes sinteticos de calibracion sobre fondos reales:
a amplitud 8 sigma recupero y localizo 120 de 128 ensayos, con limite inferior
Wilson del 95% igual a 0.8815120889557413, superando el umbral 0.80 que permitia
abrir el objetivo. A 4 sigma, sin embargo, el exito conjunto fue solo 38 de 128
(limite inferior 0.2245816608356667). Esta evidencia adversa se conserva: el
nulo es fuerte frente a perfiles grandes compatibles con el operador, pero no
autoriza una exclusion general de transitorios mas debiles.

## Limite cientifico y epistemologico

La jurisdiccion de v0.9 es exclusivamente una candidata o no-candidata de
transitorio coherente en la red GPS, la ventana UTC y el banco de velocidades
congelados. No hay una prediccion cuantitativa de acoplamiento que traduzca la
conjetura arquitectonica a una forma de onda GPS y tampoco se dispone de la
especie historica de cada reloj. Por ello siguen `NOT_ESTIMABLE`: materia
oscura, el sistema morfotopologico hiperdimensional de hiperestados plasmicos,
el mecanismo gravitatorio, cualquier limite de acoplamiento o exclusion fisica
y una confirmacion cruzada de AION. La genealogia AION solo fijo la ventana;
ningun valor, frecuencia ni candidata AION entro en el estadistico GPS.

El resultado no debilita por si solo la conjetura fisica: discrimina una
realizacion detectorial concreta y evita confundir arquitectura conceptual con
prediccion contrastable. El siguiente salto cientificamente decisivo no es
repetir esta ventana ni multiplicar sensores sin modelo, sino derivar un
operador directo que conecte clases de hiperestados y sus respuestas de borde
con observables instrumentales, perfiles temporales y escalas de acoplamiento.
Solo entonces una campana multisensor podra estimar parametros fisicos en vez
de limitarse a buscar coincidencias morfologicas.

## Trazabilidad y custodia

- Campana: `DP-GPS-NETWORK-TRANSIENT-0.9-20260825`.
- Calibracion terminal: `CALIBRATION_GREEN_TARGET_MAY_OPEN`.
- Ejecucion de calibracion: https://github.com/FacundoFirmenich/darkpipe-realdata/actions/runs/32902385323
- Unica ejecucion objetivo: https://github.com/FacundoFirmenich/darkpipe-realdata/actions/runs/32903445755
- Resultado compacto: `evidence/gps_network_v09/target_result.json`.
- Los cuatro productos fuente conservan URL, tamano comprimido y SHA-256; los
  datos crudos no se redistribuyen ni se conservan en disco local.

DarkPipe se distribuye bajo GNU GPL version 3 o posterior,
`GPL-3.0-or-later`, nunca `GPL-3.0-only`.
