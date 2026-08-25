# DarkPipe 0.9 — cuaderno de fuentes primarias

Fecha de cierre de búsqueda: 2026-08-25.

## Pregunta

¿Qué sensor independiente, abierto y temporalmente compatible permite ampliar la
jurisdicción de DarkPipe después del nulo AION v0.8, sin reutilizar AION como
nuevo holdout ni ascender una anomalía instrumental a materia oscura?

## Fuentes verificadas

1. JPL, productos GNSS GipsyX:
   <https://gipsyx.jpl.nasa.gov/index.php?page=data>
2. JPL, descripción de productos finales:
   <https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/>
3. JPL, formato TDP:
   <https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/TimeDependentParameter.html>
4. JPL, formato POS/GOA:
   <https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/PosGoaFormat.html>
5. IGS, productos precisos GNSS:
   <https://www.igs.org/products/>
6. IGS, RINEX Clock 3.04:
   <https://files.igs.org/pub/data/format/rinex_clock304.txt>
7. Panelli, Roberts y Derevianko, matched filtering en redes cuánticas:
   <https://arxiv.org/abs/1908.03320>
8. Roberts et al., búsqueda con relojes GPS:
   <https://arxiv.org/abs/1704.06844>
9. GNOME, búsqueda con magnetómetros ópticos:
   <https://www.nature.com/articles/s41567-021-01393-y>
10. INTERMAGNET HAPI:
    <https://imag-data.bgs.ac.uk/GIN_V1/hapi>
11. NASA/SPDF data-use policy:
    <https://hdrl.gsfc.nasa.gov/data_use_policy.html>

## Hechos que gobiernan la selección

- JPL publica estimaciones finales nativas de órbitas y sesgos de reloj. Los
  productos Final/Rapid abarcan 30 h y el reloj de alta tasa tiene cadencia de
  30 s.
- TDP es ASCII ordenado: tiempo, valor nominal, valor, sigma y nombre. El reloj
  está en metros y el tiempo es GPS continuo desde J2000GPS.
- POS/GOA aporta XYZ terrestres en km y puede incluir velocidad y sigmas.
- IGS ofrece relojes finales combinados a 30 s, pero la combinación añade otra
  transformación al producto de un centro de análisis.
- La literatura de relojes GPS establece que la referencia común induce
  covarianza entre nodos; no debe borrarse de forma ad hoc.
- GNOME es físicamente atractivo para frentes propagantes, pero datos y código
  completos del estudio se obtienen por solicitud razonable.
- INTERMAGNET y OMNI son buenos veto/contexto ambiental, no un sensor cuántico
  diferencial del mismo tipo.
- Los productos JPL son para investigación y educación; el crudo no se
  redistribuye en este repositorio.

## Correcciones surgidas durante la investigación

1. El origen temporal preliminar a mediodía UTC era incorrecto. Se sustituyó por
   J2000GPS = 2000-01-01 11:59:47 UTC con cinco leap seconds posteriores hasta
   2024. El epoch 787309200 corresponde a 2024-12-12 20:59:42 UTC.
2. Tres bloques diarios durante 14 días no justificaban 42 réplicas diarias.
   Se sustituyeron por 42 días anteriores y un máximo por día.
3. IGS combinado se descartó como carril principal. JPL Final nativo reduce una
   capa de combinación, aunque sigue siendo una estimación procesada.
4. La especie histórica de reloj activa por satélite no se puede reconstruir con
   autoridad suficiente. No se producirán límites de acoplamiento físico.
5. El smoke estructural abrió en memoria el 12 de diciembre sin calcular el
   estadístico. Ese día se excluyó del nulo; el fondo quedó del 31 de octubre
   al 11 de diciembre.

## Frontera de evidencia

Este cuaderno sustenta selección de sensor y operador. No contiene datos del
objetivo ni resultados. La conjetura de hiperestados plasmáticos
morfotopológicos carece todavía de un operador hacia sesgos de reloj; permanece
NOT_ESTIMABLE.
