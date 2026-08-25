# Deep research v0.9 — selección de sensor independiente

## Resultado sustantivo

El proyecto queda **mejor posicionado, pero todavía no más cerca de validar una
teoría de materia oscura**. La mejora es jurisdiccional: DarkPipe pasa de una
sola familia instrumental AION a una búsqueda prospectiva en una red
independiente de relojes atómicos GPS. Se eligieron los productos finales
nativos de JPL porque combinan acceso para investigación, 30 s de cadencia,
posiciones orbitales y literatura específica sobre frentes propagantes.

La selección no convierte reloj GPS en detector de materia oscura. JPL publica
estimaciones procesadas, los sesgos comparten una referencia y no se conoce con
autoridad la especie de reloj activa en 2024. v0.9 solo podrá adjudicar un
candidato de coherencia transitoria de red dentro de un operador congelado.

## Comparación ordenativa

Escala 0–3 por eje. El score decide el carril experimental; no mide verdad
física.

| Fuente | Apertura | Independencia | Frente propagante | Sincronización | Reproducibilidad | Total / 15 | Decisión |
|---|---:|---:|---:|---:|---:|---:|---|
| JPL Final GPS clocks + POS | 3 | 3 | 3 | 3 | 3 | 15 | carril v0.9 |
| GNOME | 1 | 3 | 3 | 3 | 1 | 11 | reserva mediante solicitud |
| NASA OMNI | 3 | 3 | 1 | 2 | 3 | 12 | veto/contexto solar |
| INTERMAGNET | 3 | 3 | 1 | 2 | 2 | 11 | veto geomagnético |
| IGS Final combinado | 3 | 3 | 3 | 3 | 3 | 15 | no principal: combinación adicional |

El empate JPL–IGS se resuelve por menor distancia al producto de un centro de
análisis: JPL nativo evita una combinación multianálisis adicional. Esto no
demuestra que JPL preserve todo transitorio; solo reduce una transformación
evitable.

## Base física y estadística

JPL documenta clocks Final de alta tasa a 30 s, TDP en metros y POS/GOA con XYZ
terrestres en km. El matched filtering para redes cuánticas representa un frente
mediante retardos dependientes de posición y velocidad. GNOME barre 53.7–770
km/s sobre direcciones 4π; v0.9 adopta ese dominio cinemático, pero no reclama
su 97.5 % de cobertura porque utiliza otro banco y geometría. La recuperación
efectiva se estima con inyecciones declaradas sobre fondo auténtico.

La referencia común no se elimina con una mediana de red. Se estima una
covarianza Ledoit–Wolf en fondo anterior y se utiliza
\(C^{-1}\mathbf 1/\sqrt{\mathbf 1^T C^{-1}\mathbf 1}\). La correlación común
forma parte del ruido en vez de desaparecer después de mirar el objetivo.

## Falsabilidad

- Ventana, 42 días de fondo, banco, transformaciones, umbral y decisiones quedan
  congelados antes de descargar el objetivo.
- Cada máximo diario incluye partes, tiempos, signos y velocidades.
- El objetivo solo puede abrirse si, a ocho sigmas robustas, el límite inferior
  Wilson 95 % de recuperación conjunta detección–localización es al menos 0.80.
- Fallo de integridad o potencia produce abstención, no un nulo.
- Un candidato no asciende a materia oscura.

## Relación con la conjetura morfotopológica

La conjetura puede modularse como una arquitectura semiabierta de grados de
libertad plasmáticos anidados cuya respuesta de borde efectiva se manifestaría
gravitacionalmente y se organizaría mediante una morfosintaxis dinámica,
jerárquica y semántica. Es una heurística para construir modelos, no todavía una
teoría predictiva: faltan acción, variables, simetrías, contornos y mapa
observacional.

v0.9 no prueba ese marco. A lo sumo produce evidencia detector-level compatible
con una clase amplia de frentes correlacionados. Para conectar niveles hace
falta un operador explícito desde hiperestado plasmático hacia sesgo de reloj,
con predicciones diferenciales frente a referencia común, órbita y modelos
estándar. Hasta entonces teoría, gravedad, materia oscura y acoplamientos son
NOT_ESTIMABLE.

## Fuentes primarias

- [JPL Orbit and Clock Data Products](https://gipsyx.jpl.nasa.gov/index.php?page=data)
- [JPL GNSS Product Overview](https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/)
- [JPL TDP](https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/TimeDependentParameter.html)
- [JPL POS/GOA](https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/PosGoaFormat.html)
- [IGS precise products](https://www.igs.org/products/)
- [Matched filtering in quantum-sensor networks](https://arxiv.org/abs/1908.03320)
- [GPS clock domain-wall search](https://arxiv.org/abs/1704.06844)
- [GNOME domain-wall search](https://www.nature.com/articles/s41567-021-01393-y)
