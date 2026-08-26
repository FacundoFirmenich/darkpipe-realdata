# Prerregistro DarkPipe 0.10: observable -> shadow -> inobservable

Campaign ID: DP-OBS-SHADOW-INOBS-0.10-20260826

## Correcci¢n de objetivo

La misi¢n central no es buscar directamente una se¤al oscura en observables.
Primero deben derivarse inobservables a partir de las shadows de observables.
Una shadow no es un residuo desnudo: es la cara relacional-transformacional del
suceso observado, con evidencia, coste de transformaci¢n, escala, frontera y
genealog¡a. Esta primera campa¤a solo estima las componentes que el dataset
autoriza; las restantes conservan NOT_ESTIMABLE.

## Fuente congelada

- Registro: Zenodo 16284118, DOI 10.5281/zenodo.16284118.
- Licencia declarada por el registro: CC-BY-4.0.
- SPARC_Lelli2016c.mrt: 28,259 bytes; MD5
  6181df386bfc05868a3700c196e800da.
- MassModels_Lelli2016c.mrt: 269,518 bytes; MD5
  fe6188538c3f5504f70f486ff6b4d29c.
- Los crudos se descargan a scratch ef¡mero, se verifican y se borran en finally.

## Cara observable

Para cada radio se usan exclusivamente: radio, velocidad circular observada y
error citado, y contribuciones de gas, disco y bulbo del modelo de masa SPARC.
Las velocidades de disco y bulbo est n tabuladas para M/L=1; el gas conserva la
convenci¢n firmada de SPARC.

## Selecci¢n congelada

- calidad de galaxia Q <= 2;
- inclinaci¢n nominal >= 30 grados;
- radio, velocidad y error estrictamente positivos;
- error fraccional de velocidad <= 0.10;
- no se elimina ning£n punto por signo de la discrepancia.

## Shadow congelada

La shadow radial contiene:

1. discrepancia firmada delta V^2 = Vobs^2 - Vbar^2;
2. probabilidad posterior de signo positivo;
3. coste evidencial de signo en bits;
4. coste de transformaci¢n, en sigmas de velocidad citada, necesario para
   alcanzar cierre bari¢nico manteniendo fijos los dem s nuisances.

El cuarto componente es deliberadamente parcial. El coste factom‚trico total,
fase, multifractalidad, topolog¡a y genealog¡a permanecen NOT_ESTIMABLE.

## Nuisances y Monte Carlo

- 4,096 muestras; semilla 20260826010;
- distancia e inclinaci¢n: gaussianas citadas, truncadas a dominios f¡sicos;
- M/L de disco: mediana 0.5 y sigma 0.11 dex;
- M/L de bulbo: mediana 0.7 y sigma 0.11 dex;
- velocidad observada: error gaussiano citado;
- escalamiento por distancia e inclinaci¢n aplicado de forma com£n a todos los
  radios de cada galaxia;
- no se recortan discrepancias negativas.

## Inobservable derivado

Se deriva la distribuci¢n posterior de:

- aceleraci¢n efectiva firmada g_I = (Vobs^2 - Vbar^2) / R;
- masa encerrada esf‚rico-equivalente M_I = delta V^2 R / G.

Estos objetos son inobservables condicionados. No son una densidad
tridimensional, part¡culas, MOND, Lambda-CDM ni hiperestados plasm ticos.

## Gate terminal

- DERIVED_CONDITIONAL_INOBSERVABLE_PROFILES_AVAILABLE si las fuentes y hashes
  pasan, se conservan al menos 20 galaxias y 500 puntos, y todas las salidas son
  finitas.
- ABSTAIN_INTEGRITY_INSUFFICIENT_REAL_OBSERVATIONS en caso contrario.

No existe un gate de detecci¢n f¡sica en esta campa¤a. El resultado, adverso o
favorable, se publicar  sin retuning.
