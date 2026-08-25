# Cierre intermedio v0.8 — discovery de época AION independiente

La posición del proyecto mejora en independencia observacional, pero empeora en
sensibilidad instrumental respecto de v0.6. Por primera vez se procesó una época
AION distinta —RID34056, diciembre de 2024— bajo un prerregistro público previo.
El stage accedió sólo al 40 % cronológico de desarrollo: 2.588 filas LLN y 2.638
HLN superaron los cortes de calidad fijados; el holdout de excitación permanece
sin leer. Sobre 2.007 frecuencias entre 0,11198 y 74,98704 mHz se congelaron ocho
máximos, liderados por 69,76146 mHz con estadístico 5,32512. Son candidatos de
desarrollo, no significativos ni físicos.

El hallazgo metodológico adverso es la potencia. Con ruido auténtico RID34056,
la calibración tangente fija no recuperó ninguna de las inyecciones ensayadas en
0,3 o 1 mHz, ni siquiera a 1,2 rad; en 3 mHz sólo alcanzó 12,5 % a 1,2 rad, y el
máximo fue 43,75 % en 10 mHz a 1,2 rad. Por tanto, un futuro nulo en holdout no
podrá interpretarse como exclusión fuerte: la época 2024 es una prueba exigente
de falsos candidatos y transportabilidad del detector, pero de potencia baja y
heterogénea. La consecuencia inmediata es congelar sin retuning los ocho
candidatos y abrir el 60 % restante sólo después de que este freeze tenga commit
público y CI verde.

| Magnitud | Resultado congelado |
|---|---:|
| Grid de desarrollo | 2.007 frecuencias |
| Banda efectiva | 0,11198–74,98704 mHz |
| Candidatos | 8 |
| Mejor máximo | 69,76146 mHz; T=5,32512 |
| Potencia máxima ensayada | 0,4375 |
| Holdout de excitación accedido | no |
| Teoría física | `NOT_ESTIMABLE` |

