# Borradores del gold set

Lo que produce `scripts/preparar_gold_set.py`: candidatos **elegidos pero sin etiquetar**.

Un borrador trae solo **hechos** —identificador, fecha, título, órgano, el `sha256` del cuerpo
archivado, cuántos caracteres hay que leer y dónde leerlos— y le faltan a propósito los tres
campos de juicio: `prefiltro_esperado`, `ejes_esperados` y `notas`.

## Cómo se etiqueta uno

1. Abrir el documento por `_leer_en` y **leerlo entero**. La etiqueta se pone sobre el texto
   íntegro, nunca sobre el título (CLAUDE.md 7.1).
2. Añadir los tres campos. La guía de cada valor está en `esquema.py`, y la regla que más
   importa es: **ante la duda, `sospecha`**. `sospecha` cuesta un puesto en la cola; `descartada`
   cuesta perder la norma.
3. Borrar los campos que empiezan por guion bajo y mover el fichero a `casos/`.

El esquema **rechaza** el fichero mientras falte cualquiera de los tres, así que un borrador no
puede colarse en el gold set sin que alguien lo haya mirado.

## Por qué el borrador no dice qué opina el sistema

Ni los términos que encontró el prefiltro, ni su estado, ni qué ejes disparó. Es la misma
disciplina anti-anclaje que el fichero de `jurista-lgtbi` impone a sus informes: **si quien
etiqueta lee primero el veredicto, deja de juzgar y pasa a confirmar**, y entonces el gold set
mide si el sistema se parece a sí mismo en vez de si acierta.

Por lo mismo, **el modelo que escribe el pipeline no etiqueta**. Un corpus etiquetado por él no
mide nada.

## No se versionan

Los `.json` de esta carpeta están en `.gitignore`: son andamiaje, no producto. Y son
**regenerables** —la semilla de `preparar_gold_set.py` es fija y está escrita—, así que perder
un borrador sin etiquetar no cuesta nada. Lo que se versiona es lo etiquetado, en `casos/`.
