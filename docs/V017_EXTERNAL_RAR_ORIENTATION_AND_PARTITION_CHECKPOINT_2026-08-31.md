# DarkPipe v0.17 — cierre de reproducción RAR, orientación y particiones

Fecha de corte: 2026-08-31
Estado: **reproducción científica adversa; localización metodológica avanzada; corrección aún no validada**

## Resultado sustantivo

El proyecto está mejor posicionado metodológicamente que en el corte anterior, aunque el resultado de reproducción sea adverso. DarkPipe ya construyó su primera RAR de nivel objeto con el catálogo KiDS auténtico completo —106 843 lentes, 21 262 011 fuentes y 3 017 858 899 pares aceptados— y comprobó que la curva central obtenida no reproduce la tabla publicada por Mistele et al. (2024). La mediana de la diferencia absoluta es 0,7157904423 dex; ninguna de las 15 estimaciones centrales cae dentro de la envolvente total 1 sigma publicada y cuatro bins no tienen valor central positivo estimable. Frente al perfil KiDS de Brouwer et al. (2021), el cociente mediano DarkPipe/referencia es aproximadamente 0,14 y el residuo diagonal máximo es 4,994 sigma. Esto invalida esta realización como reproducción del observable publicado, pero no adjudica ningún modelo gravitatorio, cosmológico ni ontológico.

La prueba de localización más importante es adversa de una forma útil: al comparar el apilado SIS antes de la deproyección exacta, la discrepancia mediana aumenta a 1,0056592858 dex. Por tanto, el defecto no nace en la deproyección vectorizada recién implementada; permanece en la superficie anterior de pares, convención de elipticidad/orientación, normalización ESD o una interacción entre esas capas. El máximo z diagonal del perfil cruzado corregido es 1,466 y la corrección del control aleatorio piloto alcanza 1,309 sigma; ninguno de esos dos diagnósticos rescata la discrepancia tangencial de casi un orden de magnitud.

## Qué quedó descartado

Se recuperaron las ocho particiones originales del escaneo completo y se rehicieron tanto su auditoría individual como su fusión. Los cinco estadísticos acumulados coinciden bit a bit con el artefacto sellado, incluido el hash de contenido `59e39fccb35df42524a10f0766480ec746ad13f49e53a35764c0e5d7edd1e2d9`. Todas las particiones fallan individualmente, con discrepancias medianas entre 0,4070 y 0,8208 dex. No hay evidencia de corrupción de merge, cancelación accidental entre particiones ni anomalía restringida a una sola región espacial.

También se ejecutó un diagnóstico limitado de orientación sobre 100 000 filas auténticas distribuidas por el catálogo completo. Ninguna de las cuatro convenciones fijas reproducía el perfil publicado. La aparente mejora de la convención norte sin inversión de `e2` no es admisible como corrección: sólo conserva cuatro bins positivos y el piloto es demasiado ruidoso. Este resultado no selecciona una convención; justifica retener exactamente la base trigonométrica completa durante un nuevo escaneo global.

## Salto técnico implementado

El acumulador de pares puede ahora conservar, además de los estadísticos históricos, las cuatro componentes suficientes `e1*cos(2phi)`, `e1*sin(2phi)`, `e2*cos(2phi)` y `e2*sin(2phi)`. A partir de una única lectura completa del catálogo se reconstruyen exactamente cuatro convenciones preregistradas: ángulo desde el este o desde el norte, con `e2` de catálogo o con su signo invertido. La fusión mantiene esta superficie sin mutar el artefacto histórico y el analizador produce, para cada convención, el perfil SIS, la RAR de nivel objeto, el perfil cruzado y la decisión preregistrada.

Una convención sólo podrá considerarse candidata de reparación si reduce en al menos 0,30 dex la discrepancia mediana respecto de 0,7157904423 dex, conserva como mínimo 13 bins positivos y mantiene el perfil cruzado por debajo de 3 sigma diagonal. Cumplir esa puerta no constituirá todavía reproducción: obligará a ejecutar nuevamente el escaneo señal con la corrección explícita y, sólo después, el control aleatorio congelado 50x.

## Frontera de evidencia

Los datos son observacionales y auténticos, pero esta etapa sigue siendo una auditoría de reproducción de método. No hay detección de materia oscura, de un hiperestado plásmico ni de una morfosintaxis física. Tampoco hay estimación válida de covarianza campo a campo, control aleatorio 50x, réplica independiente o adjudicación entre Lambda-CDM, MOND u otras arquitecturas. Los resultados adversos se conservan sin reinterpretación retrospectiva.

## Próxima acción crítica

Ejecutar en GitHub Actions el escaneo KiDS completo de ocho particiones con la base de orientación retenida, fusionarlo de forma exacta y aplicar la puerta preregistrada. Ésta es la acción que puede separar una convención geométrica corregible de un defecto más profundo en la conversión ESD/normalización. El control aleatorio 50x permanece diferido hasta resolver esa capa anterior, evitando gastar aproximadamente 40 GB remotos en corregir con mayor precisión un estimador cuya reproducción central todavía falla.
