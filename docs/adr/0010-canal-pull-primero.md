# ADR 0010 — Canal pull primero: se difunde por feed, no por lista de suscriptores

- **Fecha**: 2026-08-14
- **Estado**: aceptado
- **Contexto de tarea**: primer canal de difusión, escrito en cuanto hubo algo que difundir (la
  primera alerta aprobada por el gate humano, ADR 0017).
- **Número**: el 0010 estaba **reservado desde la revisión del 2026-08-07**, cuando la decisión
  se tomó en CLAUDE.md 6.4 y quedó sin ADR. Esto lo cierra. El 0013 (trazabilidad por offsets)
  sigue reservado y sin escribir; el siguiente libre es el **0018**.

## Contexto

El diseño original daba por hecho el canal habitual: la gente se suscribe con su correo, hay una
tabla `suscriptor`, y el sistema envía. Esa tabla existe en el modelo desde S1, con el email
guardado solo como HMAC con pepper y un token de baja aleatorio (6.4).

El problema no es cómo se guarda: es **que exista**. Estar suscrito a alertas sobre derechos
trans revela afinidad al colectivo, y eso es dato de categoría especial del artículo 9 del RGPD.
Una lista así es, a la vez:

- un objetivo que merece la pena atacar, en un proyecto sobre un colectivo que sufre ataques;
- una obligación de cumplimiento larga (consentimiento, doble opt-in, baja, conservación,
  derechos de acceso y supresión, y una EIPD que gira alrededor de ella);
- y algo que hay que custodiar durante toda la vida del proyecto, incluida la parte en la que a
  nadie le paguen por mantenerlo.

Y para el caso de uso principal —que una asociación o una persona se entere de un cambio
normativo— **no hace falta**.

## Decisión

**El canal principal de difusión es *pull*: la web pública y un feed Atom
(`GET /api/alertas.xml`). Quien quiera enterarse se suscribe con su lector, y el sistema no sabe
quién es.** El correo y los webhooks quedan como vías secundarias y opcionales, con doble opt-in
y todo lo de 6.4, para cuando alguien los pida.

Consecuencias que esto tiene y que son parte de la decisión, no efectos colaterales:

- **La tabla `suscriptor` no se elimina, pero deja de ser el camino por defecto.** El feed no
  tiene suscriptores que enumerar.
- **No hay feed personalizado ni token por suscriptor.** Un feed con una URL única por persona
  es una lista de suscriptores con otro nombre, y encima una que viaja en la barra de
  direcciones. Hay un test que comprueba que un parámetro extra no cambia la respuesta y que no
  existe ninguna ruta con token.
- **No se registra quién descarga el feed.** El limitador de peticiones ya funcionaba con la
  ventana en memoria y sin persistir IPs, y el 2026-08-14 se apagó además el log de acceso de
  uvicorn, que las escribía en cada petición contradiciendo la 6.4 desde S0.
- **Solo sale lo aprobado.** El feed comparte la consulta con `GET /api/alertas`
  (`services/alertas.py`) y esa consulta parte de la tabla `alerta`, que solo escribe el gate
  humano. Un canal de difusión nuevo que reutilice eso hereda el control; uno que escriba su
  propia consulta sobre `deteccion`, no. Por eso lo compartido es lo obvio de usar.
- **La huella del archivo viaja dentro de cada entrada.** El `sha256`, el sello y la URL de la
  fuente oficial van en el cuerpo del feed y no solo en la web: quien lo recibe en su lector
  tiene que poder contrastarlo sin volver a nuestra página. Un aviso que hay que creerse porque
  lo manda quien lo manda es exactamente lo que este proyecto no quiere ser (6.5).

## Alternativas consideradas

**Lista de correo como canal principal.** Es lo que espera la gente y llega mejor. Se descarta
como *principal* por lo de arriba, no por dificultad técnica: crea el dato sensible que el resto
del diseño se dedica a no crear. Sigue disponible como vía secundaria para quien la pida
explícitamente, y entonces el consentimiento es real porque es una elección de esa persona, no
la única puerta que hay.

**Un servicio externo de newsletters.** Coste, cuenta de terceros y —lo importante— le entrega a
un proveedor la lista completa de personas interesadas en derechos trans. Contra la 6.4 en el
peor sitio posible.

**RSS 2.0 en vez de Atom.** Los dos los leen todos los lectores. Atom está mejor especificado en
lo que aquí importa: identificadores de entrada obligatorios y estables (RFC 4151), fechas ISO
sin ambigüedad y contenido con tipo declarado. Con RSS habría habido que decidir a mano qué es
el `guid` y cómo se escapa el contenido.

**Enlazar cada entrada a una página propia de la alerta.** No existe todavía: el frontend no
tiene rutas por alerta. El enlace va a la **fuente oficial**, que además es mejor — lo que se
quiere es que quien lo lea lo contraste en el BOE. Cuando haya URL por alerta, se añade como
enlace secundario sin cambiar el `id` de la entrada (ver abajo).

**Usar la URL de la web como `id` de entrada.** Es lo habitual y aquí habría sido un error: el
proyecto no tiene dominio público todavía, así que el día que lo tenga **todos los lectores
marcarían el feed entero como no leído**. Se usa una `tag:` URI, que es un identificador y no
una dirección, y por tanto sobrevive a cualquier cambio de hosting.

## Consecuencias

**Buenas**

- Desaparece medio capítulo de cumplimiento: sin lista no hay consentimiento que recoger, ni
  baja que gestionar, ni brecha posible. `docs/eipd.md` se puede articular sobre un tratamiento
  por defecto que **no recoge datos personales**.
- El canal es trivial de operar y de auditar: es una consulta y un XML, sin cola de envío, sin
  rebotes, sin reputación de remitente, sin coste.
- Cualquiera puede reutilizarlo (una asociación puede pasarlo por su propio automatismo) sin
  pedirnos permiso ni una clave.

**Malas, y asumidas**

- **Llega a menos gente.** Un feed exige que la persona sepa lo que es y tenga un lector, y eso
  es minoritario fuera de perfiles técnicos. Es el precio consciente de no tener la lista, y la
  mitigación no es técnica: que las asociaciones, que sí tienen sus propios canales, reenvíen a
  su gente.
- **No se puede medir el alcance**, porque medirlo sería registrar quién descarga. Un proyecto
  que quisiera enseñar «N suscriptores» tendría que romper la decisión entera para conseguir la
  cifra.
- **No hay forma de avisar de algo urgente a quien no mire su lector.** Es aceptable: esto
  vigila boletines oficiales, cuyo ritmo es diario, no de minutos.
- El feed tiene un tope de 50 entradas, así que **no es un archivo histórico**. Para eso está la
  API y el archivo de documentos con sus huellas.

## Verificación

11 tests propios, 421 en total, y comprobado contra la base de datos real: el feed sale como
`application/atom+xml`, valida como Atom al parsearlo con `defusedxml`, y la única entrada es la
alerta aprobada —la reforma madrileña— con **sus doce fragmentos de evidencia, sus offsets, el
sha256 del texto archivado y el enlace al BOE**. Un feed sin alertas responde 200 con cero
entradas y no un error: un día en que nada pasa el gate es un día normal, no una avería.
