# Preregistración DarkPipe GPS Network Transient 0.9

Estado: **PREREGISTERED — TARGET CLOSED**
Campaign ID: **DP-GPS-NETWORK-TRANSIENT-0.9-20260825**
Licencia del software: **GPL-3.0-or-later**
Fecha de congelado: 2026-08-25

## 1. Pregunta y unidad de decisión

Pregunta: ¿el operador de coherencia propagante congelado produce en la ventana
objetivo un máximo más extremo que el fondo diario anterior, con potencia
prospectivamente suficiente?

Unidad de decisión: la red GPS completa en una única ventana UTC. No se decide
por satélite ni por pico local.

## 2. Fuente primaria

- JPL Final GipsyX YYYY-MM-DD_hr.tdp.gz: sesgos de reloj a 30 s, valor y sigma
  en metros.
- JPL Final GipsyX YYYY-MM-DD.pos.gz: órbitas Earth-fixed XYZ en km.
- Los bytes crudos se descargan al runner efímero, se validan y se eliminan. El
  repositorio contiene solo recibos, parámetros y resultados compactos. No se
  redistribuyen productos JPL.

## 3. Ventana objetivo congelada

Origen genealógico: cobertura temporal de AION RID34056. No se usan valores
AION, candidatos AION ni el nulo v0.8 en el estadístico v0.9.

- Inicio: 2024-12-13T20:10:45.136597Z
- División: 2024-12-14T00:00:00Z
- Fin: 2024-12-14T03:37:16.434186Z

La división impide diferenciar relojes a través del cambio de producto diario.
Cada parte se procesa por separado y después se toma el máximo de ambas.

## 4. Fondo congelado

- 42 días: 2024-10-31 a 2024-12-11, inclusive.
- Un bloque por día.
- Inicio rotatorio: 00:15, 08:00 y 15:45 UTC.
- Cada bloque reproduce consecutivamente las dos duraciones del objetivo.
- Se excluyen 1200 s en cada extremo de cada parte.
- El máximo diario engloba ambas partes, centros, signos y velocidades.

La inferencia por rango requiere intercambiabilidad aproximada de máximos
diarios. Tendencia o cambio de régimen puede degradarla; no se afirma
independencia perfecta.

## 5. Tiempo y preprocesamiento

J2000GPS se implementa como 2000-01-01 11:59:47 UTC más tiempo GPS continuo,
con los leap seconds efectivos de 2006, 2009, 2012, 2015 y 2017.

Para el nodo \(i\), con sesgo JPL \(b_i(t)\):

\[
\Delta b_i(t)=b_i(t)-b_i(t-30\,\mathrm{s}).
\]

No se calcula diferencia si la cadencia no es contigua. Los nodos se seleccionan
solo con fondo: cobertura mínima 0.98 y mínimo 20 nodos. La selección no puede
cambiar al ver el objetivo.

\[
z_i(t)=\frac{\Delta b_i(t)-\operatorname{median}(\Delta b_i)}
{1.4826\,\operatorname{MAD}(\Delta b_i)}.
\]

Se ajusta \(C\) mediante Ledoit–Wolf sobre filas completas del fondo. La
referencia común no se resta ad hoc:

\[
w=\frac{C^{-1}\mathbf 1}
{\sqrt{\mathbf 1^T C^{-1}\mathbf 1}}.
\]

## 6. Banco cinemático y geometría

- 256 vectores Sobol scrambled.
- Seed 2026082509.
- Direcciones isotrópicas.
- Velocidad log-uniforme: 53.7–770 km/s.
- Posiciones Earth-fixed interpoladas al centro de cada parte y congeladas
  durante esa parte.

Para \(\mathbf r_i\), velocidad \(v\) y dirección \(\hat n\):

\[
\tau_i(v,\hat n)=
\frac{(\mathbf r_i-\bar{\mathbf r})\cdot\hat n}{v}.
\]

El banco no reclama la cobertura 97.5 % de GNOME. Su sensibilidad efectiva queda
medida por calibración.

## 7. Estadístico y multiplicidad

\[
S_{v,\hat n}(t)=\sum_i w_i z_i(t+\tau_i),
\qquad
T_B=\max_{\text{partes},t,v,\hat n}|S_{v,\hat n}(t)|.
\]

Con los 42 máximos diarios \(T_1,\ldots,T_{42}\):

\[
p_{\mathrm{rank}}=
\frac{1+\#\{j:T_j\ge T_{\mathrm{target}}\}}{43}.
\]

El test es bilateral y el máximo absorbe toda multiplicidad interna. Umbral:
\(p_{\mathrm{rank}}\le0.05\). Resolución mínima: \(1/43\).

## 8. Potencia antes de abrir objetivo

Las únicas señales sintéticas autorizadas son impulsos de calibración declarados
inyectados en \(z_i\) sobre fondo auténtico.

- Amplitudes: 1, 2, 4 y 8 sigmas robustas.
- 128 ensayos por amplitud.
- Velocidades y direcciones continuas, independientes del banco.
- Detección: p por rango ≤ 0.05.
- Localización temporal: error ≤ 120 s.
- Éxito conjunto: detección y localización.
- Gate: a 8 sigmas, límite inferior Wilson 95 % del éxito conjunto ≥ 0.80.

Si falla, la ventana permanece cerrada y la decisión es
**ABSTAIN_INSUFFICIENT_POWER_TARGET_MUST_REMAIN_CLOSED**.

## 9. Decisiones terminales

- GPS_NETWORK_TRANSIENT_CANDIDATE
- NO_GPS_NETWORK_TRANSIENT_CANDIDATE
- ABSTAIN_INTEGRITY_OR_POWER

El target se ejecuta una sola vez sobre el commit congelado y solo después de un
gate verde.

## 10. Techo de claim

Autorizado: candidato o no candidato de coherencia transitoria en la red GPS
dentro del operador, banco y ventana congelados.

No estimable:

- materia oscura;
- hiperestados plasmáticos;
- mecanismo gravitatorio;
- acoplamientos o límites de exclusión;
- confirmación cruzada de AION;
- respuesta por especie de reloj.

## 11. Riesgos preservados

- JPL entrega estimaciones procesadas, no telemetría cruda del oscilador.
- La referencia común puede dominar la covarianza.
- La especie histórica activa de reloj no tiene trazabilidad suficiente.
- La posición congelada al centro aproxima el movimiento orbital intraparte.
- Las inyecciones calibran impulsos de una muestra estandarizada, no todos los
  perfiles físicos.
- El p por rango depende de intercambiabilidad diaria aproximada.
