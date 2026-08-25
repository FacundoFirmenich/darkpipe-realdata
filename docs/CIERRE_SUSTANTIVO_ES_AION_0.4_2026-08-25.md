# Cierre sustantivo — DarkPipe 0.4.0 / AION

Fecha: 2026-08-25

## Objetivo gobernante

Dar el siguiente salto desde la caracterización ambiental NOAA–USGS de DarkPipe 0.3 hacia una validación real de nivel instrumental, usando datos auténticos de interferometría atómica diferencial, con estadístico congelado antes del cálculo, custodia pública y sin descargar localmente el archivo bruto AION de 1,196 GB.

## Qué se logró realmente

Se seleccionó el depósito primario AION asociado a Baynham et al., Nature 654, 622–628 (2026), DOI `10.1038/s41586-026-10617-1`, y Zenodo DOI `10.5281/zenodo.19592552`. Del ZIP upstream de 134.533.837 bytes se extrajeron por streaming 27 miembros que totalizan 19.018.652 bytes: controles LLN/HLN, siete registros de inyección, barridos de máxima verosimilitud, frecuencias verdaderas precomputadas, derivados de incertidumbre, código/notebooks de referencia y licencias. No se guardó el ZIP y no se descargó el archivo bruto de 1.195.587.720 bytes.

Los 27 archivos fueron leídos completamente, hasheados y parseados. El inventario congelado tiene SHA-256 `d2382637d12b99252a3ede1c6109791d98277c04d0757c32e2b593c0847234bd`. El preregistro `DP-AION-0.4-20260825` quedó en git como commit `f2da008` antes de calcular E1/E2.

DarkPipe 0.4 incorpora módulo original GPL-3.0-or-later, comando `darkpipe aion-validate`, script directo, Colab, figura, recibo JSON/Markdown, manifiesto y cinco tests nuevos. La suite completa terminó 10/10 PASS en Python 3.14.

## Resultado científico-técnico

La decisión terminal es `PASS_BOUNDED`.

Gate 0 pasó 27/27 archivos y todos los contratos de esquema/mapeo. E1 recuperó las siete modulaciones intencionalmente inyectadas —0,1; 0,3; 1; 3; 10; 30 y 100 mHz nominales— dentro de una celda de Fourier. Los errores normalizados `|f_hat-f_true|T` fueron 0,00881; 0,03568; 0,04545; 0,01689; 0,00927; 0,02591 y 0,04229; el umbral preregistrado era 1.

E2 estimó una diferencia HLN−LLN de 14,2767 µrad con incertidumbre combinada 19,2830 µrad e intervalo normal bilateral 95% [−23,5180, 52,0714] µrad. El intervalo incluye cero, por lo que no se resuelve un exceso de ruido diferencial debido a la fase láser añadida dentro de esta representación upstream. LLN dio 260,281 ± 13,286 µrad y HLN 274,558 ± 13,976 µrad; las referencias SQL publicadas escaladas son 258,540 ± 9,510 µrad y 258,517 ± 9,509 µrad, respectivamente.

Esto valida que DarkPipe puede custodiar y adjudicar controles de un sensor cuántico diferencial real y reproducir la localización de señales de control en presencia de fase común aleatorizada. No reproduce independientemente desde HDF5 toda la máxima verosimilitud de AION: usa sus CSV/NPY/NPZ derivados publicados y aplica un endpoint DarkPipe independiente y preregistrado sobre ellos.

## Significado metodológico y epistemológico

El salto es real pero acotado. DarkPipe deja de ser sólo una tubería ambiental y pasa a tener un carril instrumental auténtico con control negativo/estabilidad y siete controles positivos. La congelación previa impide escoger frecuencias, cambiar tolerancias o retirar casos tras ver el resultado.

Un `PASS_BOUNDED` no es una detección. Demuestra corrección de custodia, correspondencia y recuperación dentro de este depósito. No demuestra equivalencia HLN/LLN, ausencia de todos los sistemáticos, sensibilidad de AION-10/AION-km, ni validez de un modelo de materia oscura u ondas gravitacionales.

Quedan obligatoriamente `NOT_ESTIMABLE`: tasa de falsa alarma de búsqueda ciega; significación global de nueva física; transferencia a baselines largos; y reproducción completa del likelihood desde los HDF5 brutos.

## Evidencia adversa preservada

- El primer inventario reportó 24 archivos y siete CSV no parseables. La causa conjunta fue doble: tres nombres superaban el límite de ruta de Windows y los CSV AION comienzan con comentarios `#`. Se corrigió con rutas extendidas y `comment="#"`; el inventario final fue 27/27 sin alterar bytes.
- Cuatro series de inyección contienen en total cinco pasos temporales no monótonos. Se contaron y reportaron; no se borraron, interpolaron ni reordenaron. E1 usa sólo `min(timestamp)` y `max(timestamp)` según preregistro.
- La primera suite terminó 9/10: una aserción buscaba literalmente “GPL version 3 or later”, aunque la licencia correcta dice “version 3 ... or any later version” y SPDX `GPL-3.0-or-later`. Se reparó únicamente el test; la licencia y los endpoints no cambiaron.
- La inspección visual nativa de la figura falló por el helper ACL de Windows. El PNG fue verificado programáticamente: 2520×756 RGBA, finito, no vacío, SHA-256 `5E4DD131331E8738F1C40648CBB52950521E62434DCAED9861260EC377C46B91`.
- Zenodo declara `CC-BY-4.0` para el depósito y el bundle incluye MIT para software. DarkPipe no relicensea esos bytes; el código original sigue bajo GPL-3.0-or-later, sin `only`.

## Estado y próximo gate

Verde: autenticidad del depósito, custodia 27/27, preregistro previo, E1 7/7, E2 consistente con cero, reproducción local, suite 10/10, Colab/script y techo de afirmación explícito.

La publicación se realizó mediante el PR público `#3` (`https://github.com/FacundoFirmenich/darkpipe-realdata/pull/3`). Los checks GitHub Actions de los eventos push y pull request terminaron PASS: `https://github.com/FacundoFirmenich/darkpipe-realdata/actions/runs/32821026078` y `https://github.com/FacundoFirmenich/darkpipe-realdata/actions/runs/32821060255`.

Pendiente: búsqueda ciega, distribución nula con trials, cobertura desde HDF5, transferencia instrumental y réplica independiente.

La siguiente acción científica crítica es un null/injection challenge ciego o held-out con ensemble nulo completo y corrección de múltiples pruebas, seguido por réplica en otro intervalo o instrumento. Añadir más APIs sin ese gate no aumenta autoridad científica.
