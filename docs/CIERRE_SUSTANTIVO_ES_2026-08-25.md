# Cierre sustantivo — DarkPipe 0.3.0

Fecha: 2026-08-25

## Objetivo gobernante

Recuperar la línea DarkPipe/plasma oscuro desde la conversación nativa completa y los artefactos actuales, reconstruirla como software científico real-data-first, ejecutarla con fuentes oficiales actuales y desplegarla con custodia pública en GitHub y respaldo verificable en Google Drive, sin cargar los discos locales con corpus pesados.

## Qué se logró realmente

DarkPipe 0.3.0 es un paquete Python instalable, una CLI, un Colab ejecutable y un pipeline de evidencia. Descarga observaciones reales de NOAA SWPC y USGS Geomagnetism dentro de límites duros de bytes; soporta además HAPI mediante INTERMAGNET y NASA CDAWeb. Conserva URLs resueltas, tiempos de recuperación, tamaños y SHA-256; alinea canales medidos; proyecta Bz, campo total, velocidad y densidad del viento solar como nuisances; y calcula PSD de Welch, baseline Whittle, diagnósticos residuales, lags y coherencia.

La corrida viva terminal terminó con exit code 0 sobre 1.433 observaciones alineadas entre 2026-08-24 06:00 UTC y 2026-08-25 05:54 UTC. Adquirió 3.747.961 bytes y todo el recibo ocupa aproximadamente 4,38 MB. La prueba HAPI INTERMAGNET separada terminó con exit code 0 y 60 filas BOU. La suite offline terminó 5/5 PASS; la instalación editable 0.3.0 y el entrypoint Python quedaron verificados.

## Resultado científico y significado

Después de proyectar los cuatro foregrounds heliosféricos medidos, el residual de dF/dt geomagnético presenta asimetría -0,6726, curtosis excedente 5,3222, p de normalidad 7,26e-58 y fracción de cola robusta 0,03838. Para esta ventana, una clausura gaussiana simple es insuficiente. Esto justifica modelos robustos, de colas pesadas o de mezcla y controles explícitos de no estacionariedad.

No es evidencia de materia oscura, plasma oculto ni defectos topológicos. La correlación de mayor magnitud en el barrido es débil (r=-0,1359 a +8 min) y la coherencia máxima estimada es 0,4171 a 0,00078125 Hz. Sin corrección por búsqueda, replicación, función de transferencia y canal instrumental, ambas son descripciones condicionadas, no causalidad ni detección.

## Estado del proyecto

Verde:

- conversación nativa leída a EOF con cadena de 59 páginas, cursores y hashes;
- diez notebooks actuales inventariados y clasificados sin promover snapshots antiguos a canon;
- fuentes NOAA RTSW, USGS y HAPI INTERMAGNET verificadas en vivo;
- pipeline real-data-first, instalación, Colab, pruebas y custodia de hashes operativos;
- repositorio escaneado: cero coincidencias de patrones de credenciales;
- licencia vigente GNU GPL v3 o posterior (GPL-3.0-or-later), por decisión expresa del autor;
- huella local del repositorio/evidencia de unos 4,46 MB y ZIP comprimido inferior a 1 MB.

Rojo o pendiente:

- no existe todavía un canal real sincronizado de gradiometría/interferometría atómica con calibración y auxiliares;
- no están validadas sensibilidad, tasa de falsa alarma, alcance/exclusión, múltiples pruebas, estabilidad larga ni réplica multiestación;
- no existe aún un estadístico de detección físico preregistrado ni blind injection-recovery sobre datos instrumentales reales;
- NASA CDAWeb tiene adaptador genérico y contrato de capacidades verificado, pero no una campaña de dataset físico seleccionada.

## Evidencia adversa preservada

- Los dos endpoints NOAA heredados de v0.2 devolvieron 404 y fueron reemplazados por productos oficiales actuales.
- La primera ventana propagada produjo 0 targets finitos porque USGS había devuelto valores nulos más allá de su corte; el pipeline se abstuvo en vez de interpolar o rebajar el gate.
- La primera prueba HAPI falló porque INTERMAGNET separa parámetros en /info y datos en /data; se corrigió y repitió con 60/60 filas.
- Un mensaje histórico no gobernante quedó truncado por transporte y no fue reconstruido.
- Untitled33.ipynb contiene errores almacenados en dos celdas de ese snapshot; no se extrapola a ramas nuevas.
- En un paquete público histórico de OpenADS se encontró una credencial NASA ADS incrustada. No se copió, no se usó y no está en DarkPipe. Debe revocarse/rotarse y publicarse un sucesor saneado sin alterar los bytes históricos.

## Despliegue y custodia

- GitHub público: https://github.com/FacundoFirmenich/darkpipe-realdata
- Carpeta Drive: https://drive.google.com/drive/folders/1rlV2kCaBxX9l7AF2Q2OW8Q0vbKw0oaFM
- ZIP Drive: https://drive.google.com/file/d/1WnTHjgALF7Unxe5pvo8y28f_oRyOznPg/view?usp=drivesdk

No se desplegó un daemon ni un servicio residente en VPS porque DarkPipe 0.3.0 es una cadena científica batch/Colab; mantener un servidor encendido no agrega autoridad científica y sí agrega superficie operativa. La ejecución, publicación y custodia solicitadas sí quedan desplegadas.

## Próxima acción crítica

La siguiente decisión no es añadir más APIs. Es seleccionar un canal real de sensor/gradiometría con calibración, reloj, función de transferencia y auxiliares; luego preregistrar plantilla física, jerarquía de nuisances, cortes de calidad, inyecciones ciegas, banda de búsqueda, corrección de trials y holdout. Ese gate decide si DarkPipe evoluciona desde caracterización de foregrounds hacia un ensayo de detección defendible.
