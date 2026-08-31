# DarkPipe v0.17 — resultado global de orientación y reparación del estimador

Fecha de corte: 2026-08-31

## Resultado sustantivo

El proyecto queda materialmente mejor posicionado. El barrido KiDS auténtico completo, ejecutado en ocho particiones sobre 21 262 011 fuentes, 106 843 lentes y 3 017 858 899 pares aceptados, retuvo la base lineal exacta de orientación y permitió adjudicar cuatro convenciones sin releer ni rotar adaptativamente los datos. La fusión cubre de forma continua todas las filas y conserva un hash de contenido propio: `5d5f8c3a11cbe99b5192f015fd43f6c8f3ac29152f51d11ef743baf868bd4cfc`.

La única convención que supera la puerta preregistrada es la transformación de signo `e2` documentada para el marco RA/Dec de KiDS, manteniendo el ángulo desde el este. En la deproyección objeto a objeto reduce la discrepancia mediana absoluta frente a Mistele et al. (2024) desde 1,0365400070 hasta 0,0494255413 dex, una mejora de 0,9871144657 dex. Conserva 15 de 15 bins positivos y el máximo residuo cruzado diagonal es 1,75594 sigma. El diagnóstico SIS previo a deproyección converge de forma independiente: 0,0436427705 dex y 15 de 15 bins positivos.

Esto localiza el defecto principal en la convención geométrica del estimador anterior. No estaba en la fusión, las particiones, la deproyección exacta ni el signo obtenido mediante un ajuste posterior. La corrección se aplica ahora directamente durante la acumulación:

`e_t = -(e1 cos(2 phi) - e2 sin(2 phi))`

`e_x = e1 sin(2 phi) + e2 cos(2 phi)`

El código sigue pudiendo retener las cuatro componentes básicas para auditoría y una prueba verifica que la salida predeterminada corregida coincide exactamente con la reconstrucción preregistrada.

## Límite adverso que permanece

La mejora no equivale a reproducción completa. Sólo 10 de las 15 estimaciones centrales deproject-first y 12 de las 15 SIS caen dentro de la envolvente total 1 sigma publicada; por la puerta fijada de antemano, `reproduction_gate=false`. El resultado es una reparación metodológica fuerte, no una detección de materia oscura, una validación de una arquitectura plásmica ni una adjudicación entre Lambda-CDM, MOND u otros marcos.

La pequeña discrepancia residual puede contener control aleatorio incompleto, covarianza subestimada, diferencias de selección, calibración de Sigma crítica, masa bariónica o identidad exacta de la muestra. Esas posibilidades permanecen abiertas y no deben elegirse retrospectivamente para forzar un resultado favorable.

## Incidencia técnica reparada

El primer intento del analizador posterior al merge falló al pedir la clave histórica `effective_count`; la API vigente devuelve `effective_lenses`. La causa quedó corregida mediante un adaptador explícito y pruebas de contrato. No se repitió el escaneo remoto: el artefacto científico era válido y la falla estaba limitada al reporte local.

## Consecuencia y próxima acción crítica

La corrección de `e2` queda promovida a convención predeterminada experimental de v0.17, sin reescribir los artefactos adversos históricos. La siguiente acción es estimar el control aleatorio 50x auténtico con la misma convención y covarianza espacial suficiente, restarlo antes de la deproyección y volver a aplicar la puerta de reproducción. Como el algoritmo piloto global resultaría computacionalmente prohibitivo, la campaña siguiente debe explotar la localidad por tesela: generar el random congelado por cada una de las 1006 teselas oficiales, leer únicamente los intervalos de fuentes vecinos y reducir inmediatamente a estadísticos aditivos. Sólo después de esa corrección señal menos control será lícito derivar inobservables o discutir el marco físico propuesto.
