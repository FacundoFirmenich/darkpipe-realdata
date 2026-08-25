# DarkPipe 0.9 - calibracion GPS

Decision: **CALIBRATION_GREEN_TARGET_MAY_OPEN**.

La calibracion uso exclusivamente 42 bloques autenticos anteriores a la
ventana objetivo, con 22 relojes GPS seleccionados por cobertura. El
maximo familiar de cada bloque incluye ambos tramos, todos los centros, ambos
signos y las 256 velocidades prospectivas.

En la amplitud de calibracion mas alta (8.0
sigmas robustas), la recuperacion conjunta deteccion-localizacion fue
120/128; limite inferior Wilson 95%:
0.8815. La ventana objetivo no fue abierta.

Esto no calibra materia oscura ni la conjetura plasmatica. Calibra solamente
la capacidad del operador congelado para recuperar el impulso estandarizado
declarado sobre fondo GPS autentico.
