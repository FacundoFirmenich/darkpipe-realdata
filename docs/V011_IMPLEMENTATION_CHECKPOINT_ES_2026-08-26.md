# Cierre sustantivo intermedio DarkPipe v0.11

Fecha: 2026-08-26
Estado: implementación y preregistración completas; resultado oficial pendiente.

## Posición del proyecto

DarkPipe queda mejor posicionado que en v0.10 porque ya dispone de un segundo
canal observacional galáctico que no usa curvas de rotación: lente
gravitatoria débil de KiDS. El avance no consiste en volver a mostrar la misma
discrepancia con otro gráfico, sino en transportar la cadena
observables -> shadows -> inobservables derivados a una medición físicamente
distinta y a aceleraciones más bajas.

No se ha fusionado el PR 18 ni se ha aceptado todavía un resultado oficial
v0.11. GitHub Actions sufre una caída mayor confirmada por GitHub Status, de
modo que los eventos push y pull_request fueron recibidos pero no generaron
runs. Ese estado es CI_NOT_TRIGGERED, no PASS.

## Qué quedó construido y congelado

El commit 36d6751 congela antes del resultado:

- la selección primaria Mistele et al. 2024;
- una transcripción CC BY 4.0 de sus 15 bins de Table 1;
- el hash LF estable de la fuente y el hash de la superficie SPARC v0.10;
- el operador firmado g_I = g_obs - g_bar;
- eta = log10(g_obs/g_bar);
- una envolvente de sensibilidad con incertidumbre estadística, deproyección y
  el término estelar fijo de 0.1 dex;
- una cola sistemática explícita por debajo de 10^-14 m/s^2;
- un atlas SPARC/KiDS de igual peso por galaxia y sin likelihood conjunta;
- runner, workflow manual, tests, documentación, ledger de fuentes y Colab;
- GPL-3.0-or-later para el software, nunca GPL-3.0-only.

La suite completa alcanzó 60/60. Tras normalizar la fuente a LF y restaurarla
después de detectar un intento de normalización adverso, los cuatro tests
dirigidos volvieron a pasar y el hash real coincidió con el gate del runner.
La revisión del PR encontró además una indentación inválida en las celdas
Colab; fue corregida en 949317b y las cinco celdas ahora compilan como Python.

## Reproducción local post-freeze

Se ejecutó una reproducción local real, determinista y posterior al freeze,
exclusivamente para validar integración. Fue borrada después de inspeccionar
sus JSON y CSV y no se publica ni se relabela como run oficial.

Resultado candidato:

- 15 de 15 bins con discrepancia efectiva positiva bajo la envolvente
  condicional declarada;
- 11 bins en la jurisdicción primaria;
- 4 bins en LOW_ACCELERATION_TAIL_SYSTEMATICS_DOMINANT;
- 3 bins con al menos cinco galaxias SPARC en el intervalo comparable;
- 12 bins sin solapamiento SPARC suficiente y por tanto NOT_ESTIMABLE para
  comparación cruzada;
- diferencia absoluta mediana descriptiva en los tres bins comunes:
  0.025272 dex.

Los tres cruces descriptivos fueron:

| log10(g_bar) | galaxias SPARC | eta KiDS | eta SPARC mediana | diferencia dex |
|---:|---:|---:|---:|---:|
| -11.41 | 65 | 0.7600 | 0.7347 | 0.0253 |
| -11.65 | 30 | 0.8700 | 0.8052 | 0.0648 |
| -11.90 | 9 | 1.0200 | 0.9966 | 0.0234 |

Esto es compatible con continuidad descriptiva entre cinemática y lensing en
la franja común. No es confirmación estadística: las poblaciones no coinciden
objeto a objeto y no existe covarianza cruzada.

El último bin, log10(g_bar) = -14.86, conserva un límite inferior positivo de
aproximadamente 4.95e-15 m/s2, pero con una envolvente extremadamente amplia.
Su signo condicional no vence la incertidumbre estructural del tail y no
autoriza un claim más fuerte.

## Significado científico y epistemológico

El segundo shadow debilita la explicación trivial de que la discrepancia de
v0.10 sea sólo un artefacto exclusivo de la cinemática rotacional: una
medición lensing poblacional también muestra g_obs mayor que g_bar y prolonga
la morfología del exceso hacia aceleraciones inferiores.

Lo que no cambia es la no-identificabilidad ontológica. El resultado no decide
entre partículas de materia oscura, Lambda-CDM, MOND u otra dinámica; tampoco
establece el mecanismo de la gravedad ni valida la conjetura morfotopológica
de hiperestados plasmáticos. Es un nuevo inobservable efectivo condicionado,
no la identidad de aquello que lo produce.

## Límites y evidencia adversa conservada

- Sólo tres bins permiten comparación SPARC descriptiva bajo el mínimo fijado.
- Cuatro bins están dominados por sistemáticos de cola.
- Table 1 no publica la covarianza completa de sistemáticos bariónicos.
- KiDS es una población apilada y no una réplica de las mismas galaxias.
- La inspección visual local de la figura quedó bloqueada por un fallo de ACL
  del visor; JSON, CSV y generación PNG sí fueron comprobados.
- CLASH permanece diferido: ofrece perfiles y correlaciones excelentes, pero
  no el perfil bariónico radial público necesario para restar sin inventar.

## Bloqueo y siguiente acción crítica

Bloqueo real: caída mayor de GitHub Actions iniciada el 2026-08-26 a las
15:11 UTC. Estado oficial:
https://www.githubstatus.com/api/v2/incidents/unresolved.json

Cuando Actions vuelva:

1. reemitir el evento CI si GitHub no recupera los pushes pendientes;
2. exigir PASS terminal del PR 18;
3. obtener autorización explícita para fusionar PR 18 en main;
4. ejecutar una sola vez el workflow manual v0.11 desde el commit fusionado;
5. custodiar el artefacto compacto, añadir el cierre oficial y sólo entonces
   preparar tag, release v0.11.0 y respaldo privado en Drive.

No quedan crudos ni reproducciones temporales en disco local.
