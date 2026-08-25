# Cierre sustantivo — DarkPipe AION blind holdout 0.6

Fecha: 2026-08-25
Campaña: `DP-AION-BLIND-0.6-20260825`
Decisión: **PASS_BOUNDED**

## Qué se ha conseguido realmente

DarkPipe ha atravesado el gate que v0.5 mantenía abierto en su forma más honesta y ejecutable con la evidencia local: una campaña prospectivamente congelada, con holdout, compromiso criptográfico, predicciones escritas antes del reveal y corrección familiar de siete trials.

El commit `dbd2da7` congeló código y regla antes de construir el desafío. El commit `3dd30b6` fijó los bytes sellados y las predicciones antes de abrir la semilla. El compromiso SHA-256 se verificó sin divergencia.

El caso nulo auténtico no produjo ninguna detección familiar; su máximo tuvo p global 0.3857421875. Las siete inyecciones de 0.60 rad fueron identificadas 7/7: cada target fue el pico, la única frecuencia detectada y obtuvo p global 0.000244140625. No hubo target perdido ni frecuencia espuria promovida.

## Significado científico y metodológico

El resultado demuestra que el detector fijo puede separar, en este replay, un control sin inyección de siete perturbaciones coherentes sobre ruido instrumental AION auténtico, manteniendo control de multiplicidad sobre la familia congelada. La diferencia frente a v0.4/v0.5 es temporal y epistemológica: la verdad de los casos no participó en la predicción y el resultado no podía ser ajustado después del reveal sin romper la traza Git y los hashes.

La inyección es científicamente legítima pero acotada: se añade en el espacio tangente de fase diferencial obtenido del modelo de fringe, con signos opuestos forward/backward. No reproduce de forma independiente la cadena completa ARTIQ/HDF5 ni el likelihood no lineal upstream.

## Dónde queda fuerte

- custodia exacta de controles y desafío;
- freeze verificable antes del holdout;
- mapa de casos ausente de las predicciones;
- corrección FWER sobre siete frecuencias;
- null holdout limpio bajo la regla;
- recuperación 7/7 sin detecciones secundarias;
- reproducción automatizada y claims tipados.

## Qué sigue débil o no validado

- sólo existe una realización nula holdout y las siete señales reutilizan el mismo fondo;
- la calibración circular supone estacionariedad/exchangeability aproximada;
- no hay banda continua ni look-elsewhere effect fuera de siete frecuencias;
- no hay curva de potencia/cobertura sobre múltiples amplitudes;
- no hay extracción independiente desde raw HDF5;
- no hay réplica externa, nueva época ni nuevo instrumento;
- no hay detección de materia oscura, ondas gravitacionales o plasma oculto.

Por ello permanecen `NOT_ESTIMABLE`: tasa de falsos positivos en repeticiones independientes, significancia de búsqueda continua, equivalencia con likelihood no lineal, transferencia a AION-10/AION-km y cualquier detección física.

## Consecuencia para el objetivo DarkPipe

DarkPipe ya no es sólo una tubería que ingiere datos reales y reproduce controles publicados. Posee una primera arquitectura de desafío científicamente gobernado: separa desarrollo, holdout, sellado, predicción, reveal y autoridad del claim. Eso habilita el siguiente programa serio: campañas raw-phase independientes y búsqueda continua, sin fingir que ya están resueltas.

## Próxima acción crítica

Ejecutar una campaña v0.7 con nuevos bloques instrumentales o raw HDF5 no reutilizados, prerregistrar una banda continua y un modelo de no-estacionariedad, y estimar simultáneamente falsa alarma, cobertura y potencia en una escalera de amplitudes. La réplica independiente, no otro refinamiento sobre el mismo fondo, es ahora el gate que más autoridad añadiría.
