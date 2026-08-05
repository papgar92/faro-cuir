# 0005 — Archivo íntegro con sellado de tiempo

## Contexto

El problema que justifica Faro Cuir no es solo que un derecho se recorte, sino que se recorte
**sin dejar rastro público**: una instrucción de rango bajo que se publica, produce efectos, y
más tarde desaparece del sitio donde estaba o se sustituye por otra versión sin que quede
registro accesible de qué decía antes. Contra eso, una herramienta que solo enlace a la fuente
oficial no sirve: si la fuente cambia, el enlace pasa a apuntar a otra cosa y nuestra alerta
queda sin respaldo, indistinguible de un error nuestro.

`CLAUDE.md` sección 6.5 fija el requisito: de cada documento ingerido, sha256 del contenido
más un sello de tiempo. Este ADR documenta cómo se ha implementado y, sobre todo, **qué
demuestra exactamente y qué no**, que es lo que se puede defender ante un tribunal.

## Decisión

### Se archiva el byte exacto, sin normalizar

`documento.sha256` es el sha256 de lo que envió el servidor, tal cual. No se normalizan
espacios, ni encoding, ni orden de atributos, ni se reserializa el XML antes de hashear.

Es tentador normalizar —haría los hashes estables frente a cambios cosméticos— y es
exactamente lo que no se debe hacer: en cuanto se normaliza, el hash deja de probar *qué se
publicó* y pasa a probar *qué entendimos nosotros*. Lo segundo no vale como archivo.

### El nombre del fichero se deriva del hash

El contenido se guarda en `<almacen>/ab/cd/<sha256>.xml`. Esto resuelve dos cosas a la vez:
el path traversal de la sección 6.3 (ningún valor de la fuente toca el sistema de ficheros) y
la verificabilidad (`sha256sum` sobre el fichero debe devolver su propio nombre; si no
coincide, el archivo está corrupto y se nota de inmediato).

La escritura es atómica —temporal más `os.replace`— para que un proceso muerto a mitad no
deje un fichero truncado cuyo nombre promete un hash que su contenido ya no cumple.

### El sello de tiempo es, de momento, nuestro reloj

`documento.sello_tiempo` es la hora UTC en la que nuestro sistema ingirió el documento.

**Esto hay que decirlo con precisión: no es prueba frente a terceros.** Demuestra la
integridad del contenido desde que lo archivamos (el hash), pero la fecha es una afirmación
nuestra, y quien no confíe en nosotros no tiene por qué aceptarla. Lo que sí garantiza es lo
que hace falta para el uso principal: que nuestra propia alerta esté respaldada por el
contenido exacto que la originó, y que cualquiera pueda comprobar que ese contenido no se ha
tocado después.

La evolución natural —y barata— es un sello RFC 3161 contra una TSA pública, que convierte la
fecha en algo verificable por terceros sin confiar en nosotros. Queda documentada como el
siguiente paso, no implementada: el campo `sello_tiempo` ya existe y añadir el token de la TSA
no cambia el modelo, solo añade una columna.

## Alternativas consideradas

- **Guardar solo la URL oficial y no archivar contenido.** Descartado: es precisamente el
  fallo que el proyecto existe para cubrir. Si la fuente cambia o desindexa, no queda nada.
- **Normalizar el contenido antes de hashear** (canonicalización XML, por ejemplo). Descartado
  por lo dicho arriba: el hash dejaría de probar lo publicado. Si en algún momento hiciera
  falta comparar versiones ignorando cambios cosméticos, eso es trabajo del *diff* de la
  sección 7, sobre el contenido ya archivado, y nunca sustituye al hash del original.
- **Sello RFC 3161 contra una TSA pública desde el primer día.** Aplazado, no descartado. Es
  la mejora de mayor valor por menor coste de las pendientes, pero añade una dependencia
  externa en el camino crítico de la ingesta (si la TSA no responde, ¿se ingiere igual?, ¿se
  reintenta?) y esa decisión merece resolverse cuando el pipeline esté completo, no antes.
- **Anclaje en blockchain.** Descartado. Resuelve el mismo problema que una TSA con muchísima
  más complejidad operativa y sin ventaja real para este caso de uso.
- **Archivar solo los documentos que el prefiltro marca como relevantes.** Descartado: un
  archivo que solo guarda lo que nos interesó no puede demostrar qué *más* se publicó ese día.
  Por eso `descartado` es un estado normal del pipeline y no un motivo para no archivar.

## Consecuencias

- El almacén crece con todo lo publicado, no solo con lo relevante. Es el coste deliberado de
  que el archivo sirva como prueba. Un sumario diario del BOE ronda los 200 KB.
- `documento.ruta_almacen` se guarda **relativa**: la raíz del almacén es configuración de
  despliegue (`ALMACEN_ROOT`) y meterla en la fila ataría los datos a una máquina concreta.
- Como el nombre depende del contenido, la deduplicación sale gratis: dos ingestas del mismo
  contenido escriben el mismo fichero y la segunda ni siquiera lo reescribe.
- Cualquier afirmación pública sobre lo que decía una norma debe poder respaldarse con el
  fichero archivado correspondiente. Esto es una restricción permanente sobre el diseño de las
  alertas, no solo una nota de implementación.
