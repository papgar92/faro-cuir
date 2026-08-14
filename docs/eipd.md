# Evaluación de Impacto en Protección de Datos (EIPD)

- **Versión**: 1.0 — 2026-08-14
- **Sistema**: Faro Cuir, vigilancia de cambios normativos que afectan a los derechos del
  colectivo LGTBI+ (ver `README.md` y `CLAUDE.md` sección 1).
- **Estado del sistema**: no desplegado públicamente. Se ejecuta en la máquina de desarrollo
  contra el BOE. **Hoy no hay ninguna persona interesada real**, y esta evaluación se escribe
  antes de que la haya, que es cuando sirve de algo.

> **Aviso de alcance, y va primero a propósito.** Esto es el análisis de protección de datos de
> un proyecto de máster, hecho por quien lo desarrolla. **No es un dictamen jurídico y no lo
> sustituye.** Las conclusiones sobre bases de legitimación están razonadas, no validadas por
> nadie con habilitación para hacerlo, y antes de un despliegue público con personas reales
> haría falta esa revisión. Se dice aquí porque la regla de oro 8 del proyecto prohíbe presentar
> como verificado lo que no lo está, y una EIPD que se presente a sí misma con más autoridad de
> la que tiene es peor que no tenerla.

---

## 1. Conclusión, por delante

**La decisión de diseño más importante de esta evaluación es que el tratamiento de riesgo alto
que la motivaba ya no ocurre.**

El diseño original preveía una lista de personas suscritas a alertas sobre derechos trans. Estar
en esa lista **revela por sí solo afinidad al colectivo LGTBI+**, que es dato de categoría
especial (art. 9 RGPD): orientación sexual, y en la práctica también identidad de género. Un
fichero así, en un proyecto sobre un colectivo que sufre ataques dirigidos, es un objetivo.

El **ADR 0010** cambió el canal por defecto a *pull*: web pública y feed Atom
(`GET /api/alertas.xml`). Quien quiera enterarse se suscribe con su lector y **el sistema no
sabe quién es**. No hay lista, no hay fichero, no hay consentimiento que recoger ni baja que
gestionar, y no hay brecha posible de datos que no existen.

Eso es protección de datos desde el diseño y por defecto (art. 25 RGPD) en su forma más
literal: el riesgo no se mitiga, se elimina quitando el tratamiento.

**Lo que queda y esta evaluación sí tiene que analizar** es lo que no desaparece:

1. El **archivo íntegro de boletines oficiales**, que contiene datos personales de terceros
   publicados por la propia administración (sección 3.1). Es el tratamiento con más volumen y el
   que menos se suele mirar, porque «son documentos públicos».
2. La **autenticación del panel de revisión** (sección 3.4).
3. Los **restos del canal push**: la tabla `suscriptor`, hoy sin uso (sección 3.5).

Riesgo residual estimado: **bajo**, con las salvedades de la sección 7.

---

## 2. Por qué se hace esta evaluación

El artículo 35 del RGPD la exige cuando un tratamiento puede entrañar un riesgo alto para los
derechos y libertades de las personas. Aquí concurrían dos de los criterios habituales:

- **Datos de categoría especial** (art. 9): la afinidad al colectivo LGTBI+ deducible de una
  suscripción.
- **Colectivo vulnerable**: personas trans y LGTBI+ en un contexto en el que el propio proyecto
  documenta que se están recortando derechos.

Que la decisión de la sección 1 elimine el tratamiento no hace innecesaria la evaluación: la
hace **corta y con una conclusión que se puede defender**. Además el sistema sigue tratando
datos personales por otras vías, y esas son las que se analizan.

---

## 3. Descripción sistemática de los tratamientos

### 3.1 Archivo íntegro de boletines oficiales

**Qué se trata.** El sistema descarga y archiva el contenido exacto de los sumarios del BOE y del
texto íntegro de cada norma del día (ADR 0011 y 0015), con su `sha256` y un sello de tiempo (ADR
0005). Hoy, 3 sumarios y 652 cuerpos.

**Los boletines contienen datos personales de terceros**, y conviene decirlo con ejemplos en vez
de en abstracto: nombramientos y ceses con nombre y apellidos, listas de admitidos y excluidos de
oposiciones con documento de identidad parcialmente enmascarado, resoluciones sancionadoras,
notificaciones por comparecencia, concesiones de nacionalidad, indultos. No los buscamos: vienen
dentro de lo que se archiva, porque **archivar el documento entero y sin modificar es justamente
la garantía** que el proyecto ofrece (6.5) — un archivo recortado no prueba nada.

**Fines.** Detectar cambios normativos que afecten a derechos del colectivo, y poder demostrar
qué decía un boletín el día que se publicó, frente a desindexaciones o reescrituras sin registro
público. Es el fin declarado del proyecto y no hay ningún otro; en particular **no se busca ni se
indexa por persona**, y no existe ninguna consulta del sistema que responda «qué dice el archivo
sobre fulano».

**Base de legitimación (razonada, no dictaminada).** Interés público (art. 6.1.e) e interés
legítimo (art. 6.1.f) en la vigilancia de la actividad normativa, sobre datos que la propia
administración ha publicado oficialmente y con carácter obligatorio. Para el archivo en sí, el
art. 89.1 contempla el tratamiento con fines de archivo en interés público, y el art. 17.3.d
limita el derecho de supresión cuando el tratamiento es necesario para esos fines.

**La tensión real, escrita y no escondida.** El proyecto existe porque un archivo inmutable
detecta lo que una administración borra en silencio. Esa inmutabilidad choca de frente con el
derecho de supresión de un tercero que aparezca nombrado en un boletín. No se resuelve diciendo
«son datos públicos»: que un dato sea público no lo convierte en libremente tratable para
cualquier fin. Se gestiona así:

- **El contenido archivado no se publica.** La API expone el `sha256`, el sello y la URL
  original — la *huella*, no el texto. `ruta_almacen` no se expone nunca. Quien quiera el
  contenido lo descarga de la fuente oficial, que es quien decide si sigue estando.
- **No se indexa por nombre.** No hay búsqueda de personas, ni entidad de tipo «persona» en el
  modelo de dominio, ni el LLM extrae nombres: el esquema de extracción no tiene campo para
  ellos (`schemas/extraccion.py`).
- **Lo único del cuerpo que llega a publicarse son los fragmentos de evidencia** de una alerta, y
  pasan antes por una persona (sección 3.3).
- Una solicitud de supresión sobre el archivo se atendería **caso a caso**, valorando el fin de
  archivo frente al derecho concreto. Hoy no hay procedimiento escrito porque no hay despliegue
  público; **es el primer hueco a cerrar antes de que lo haya** (sección 8).

### 3.2 Extracción con modelo de lenguaje

Se ejecuta contra **Ollama en local** (ADR 0008): ni el texto de los boletines ni nada del
sistema sale a un servicio de terceros. **No hay transferencias internacionales de datos** ni
encargados del tratamiento externos, y no es un efecto colateral de la decisión de coste 0 € —
es una de sus consecuencias buenas.

El modelo extrae hechos estructurados sobre el articulado (qué norma, qué artículos, qué cambia)
y su salida se valida contra un esquema Pydantic con `extra="forbid"`. **No emite juicios** (ADR
0002) y **su salida no acciona nada** (6.10). Los suscriptores nunca entran en el modelo ni en
los logs, y el esquema no tiene ningún campo donde aterrizaría un nombre de persona.

### 3.3 Detecciones, alertas y su publicación

Una alerta publica el título oficial de la norma, la clasificación derivada de reglas y los
**fragmentos literales del texto archivado** sobre los que se aplicó la regla, con sus offsets.

Los fragmentos son citas del articulado —«se suprime el artículo 7»—, no del cuerpo de una
resolución nominativa, porque las reglas del catálogo buscan construcciones normativas. Aun así
**nada garantiza por sí solo que un fragmento no pueda contener un nombre**, y por eso importa
que entre el clasificador y la publicación esté el **gate humano obligatorio** (regla de oro 4,
ADR 0003 y 0017): una persona lee la evidencia exacta que se va a publicar antes de que se
publique. Ese control existía por neutralidad editorial; **funciona igual como control de
protección de datos**, y conviene tenerlo escrito aquí para que nadie lo suprima creyendo que
solo servía para lo primero.

### 3.4 Autenticación del panel de revisión

Es el único tratamiento de datos personales que el sistema **crea** por sí mismo, y se diseñó
para que sea el mínimo posible (ADR 0017):

- **No hay tabla de usuarios.** Una credencial compartida, cuyo hash scrypt vive en el entorno.
- **No se guarda quién revisa.** `cola_revision` tiene fecha, estado y nota; no tiene autor. Para
  auditar el gate basta con saber que se resolvió y cuándo. Registrar qué persona aprueba qué
  alerta sobre derechos trans crearía exactamente el dato sensible que el resto del diseño evita.
- **Las sesiones viven en memoria**, indexadas por el `sha256` del token, con caducidad y tope.
  No hay tabla de sesiones y un reinicio las cierra todas.
- **La cadencia de intentos no mira la IP** (ver 3.6), y el log de accesos fallidos es un
  **contador agregado**, sin dirección ni identificador.

**Consecuencia asumida:** con credencial compartida el rastro dice «se aprobó», no «lo aprobó
Fulana». Es el intercambio correcto con una sola persona revisora; con dos, habría que rehacerlo
y **volver a pasar por aquí**, porque entonces sí habría datos de personal identificable.

### 3.5 Suscriptores (tabla existente, sin uso)

`suscriptor` sigue en el modelo desde S1 y **no la usa ningún flujo**. Si algún día se activa el
canal por correo como vía secundaria, ya está diseñada con: email como **HMAC-SHA256 con pepper
de entorno** (nunca en claro, nunca con el pepper en la base de datos), token de baja **aleatorio
y opaco** —no derivado del email, para que ni conocer una dirección permita dar de baja a alguien
ni ver un token permita deducir la dirección—, y sin perfilado ni analítica.

Activarla exigiría doble opt-in, procedimiento de baja y **revisar esta evaluación**, porque
reintroduce el tratamiento de categoría especial que la sección 1 dice que hoy no ocurre.

### 3.6 Registros de actividad (logs)

- **No se registran las IPs de quien consulta la web ni el feed.** El limitador de peticiones
  funciona con una ventana en memoria sin persistir direcciones, y el **2026-08-14 se apagó
  además el log de acceso de uvicorn**, que las escribía en cada petición contradiciendo la
  política desde S0. Fue un hallazgo de esta misma sesión y se corrigió en el momento.
- Los logs de la aplicación registran **qué normas se procesaron y qué se aprobó o descartó**,
  con identificadores de fila. Nunca quién leyó qué, nunca la nota de revisión, nunca la salida
  del modelo (6.10), nunca una contraseña ni un token.

---

## 4. Necesidad y proporcionalidad

| Principio (art. 5 RGPD) | Cómo se cumple |
|---|---|
| Limitación de la finalidad | El único fin es detectar y publicar cambios normativos. No hay analítica, ni perfilado, ni segunda finalidad. |
| Minimización | No se recogen datos de quien lee. No se crea tabla de usuarios. No se registran IPs. El único dato que el sistema genera es un hash de contraseña en el entorno. |
| Exactitud | El archivo guarda el byte exacto publicado; su `sha256` permite comprobarlo. Las clasificaciones llevan la regla y la evidencia que las sostiene, y **ninguna se publica sin revisión humana**. |
| Limitación del plazo | El archivo de boletines es **permanente a propósito** (fin de archivo, sección 3.1). Las sesiones del panel caducan en una hora. No hay ningún otro dato personal con plazo que fijar, porque no hay ningún otro dato personal. |
| Integridad y confidencialidad | Sección 5. |
| Responsabilidad proactiva | ADRs versionados con la decisión y sus alternativas, modelo de amenazas vivo (`THREAT-MODEL.md`), y esta evaluación. |

**Proporcionalidad del archivo.** Es la parte que más justificación necesita, porque es la que
más datos toca. El razonamiento es que **no existe una alternativa menos intrusiva que cumpla el
fin**: guardar solo un resumen, o solo los artículos que interesan, destruiría la garantía —un
archivo recortado por nosotros no puede demostrar qué publicó la administración. Lo que sí se
puede minimizar, y se minimiza, es **qué se publica** de lo archivado: la huella, no el texto.

---

## 5. Medidas de seguridad (art. 32)

Las de detalle están en `SECURITY.md` y `THREAT-MODEL.md`; aquí las que protegen datos
personales:

| Riesgo | Medida | Dónde |
|---|---|---|
| Acceso no autorizado a la emisión de alertas | Sesión con cookie `HttpOnly`+`Secure`+`SameSite=Strict`, cabecera anti-CSRF y método POST: tres controles que fallan por motivos distintos | `security/panel.py`, `api/revision.py` |
| Fuerza bruta contra el panel | scrypt (derivación lenta, sal por credencial) + cadencia global de intentos fallidos, **que no puede dejar fuera a quien sabe la contraseña** | `security/panel.py` |
| Fuga del archivo por ruta manipulada | Nombre de fichero derivado del `sha256`, nunca de un valor de la fuente; lista blanca de extensiones | `security/hashing.py` |
| El sistema usado como proxy a la red interna | Puerta única de salida HTTP con allowlist, rechazo de IPs no globales y pin a la IP validada | `security/url_guard.py` (ADR 0006) |
| Ejecución de contenido hostil de una fuente | Puerta única de parseo XML sin DTD ni entidades, con límites de profundidad y nodos | `security/xml_safe.py` |
| Publicación de datos personales dentro de una evidencia | Gate humano obligatorio antes de emitir, sin flag que lo salte | `services/revision.py` (ADR 0003) |
| Reidentificación de quien consulta | No se persisten IPs en ningún punto; log de acceso del servidor apagado | `security/rate_limit.py`, `docker-compose.yml` |
| Filtración de datos a un tercero | Sin proveedores externos: el LLM corre en local y no hay transferencias | ADR 0008 |

---

## 6. Derechos de las personas interesadas

- **Quien lee la web o el feed** no es una persona interesada, porque no se trata ningún dato
  suyo. No hay nada que ejercer y esa es la idea.
- **Quien aparece nombrado en un boletín archivado**: derechos de acceso, rectificación,
  oposición y supresión, con la limitación del art. 17.3.d por el fin de archivo. La
  rectificación de un dato del boletín corresponde al organismo que lo publicó, no a nosotros;
  lo que sí está en nuestra mano es no publicar ni indexar ese contenido, que es lo que ya se
  hace. **Falta un canal escrito para recibir esas solicitudes** (sección 8).
- **Quien revisa**: no se guarda ningún dato suyo.

---

## 7. Riesgo residual

**Bajo, con tres salvedades escritas:**

1. **El archivo sigue conteniendo datos personales de terceros**, y su inmutabilidad está en
   tensión permanente con el derecho de supresión. Se mitiga no publicándolo ni indexándolo, pero
   la tensión no desaparece: es inherente al fin del proyecto y hay que poder defenderla, no
   negarla.
2. **La credencial compartida del panel** funciona hoy porque hay una sola persona revisora.
   Añadir la segunda cambia el análisis.
3. **Nada de esto está desplegado.** Un despliegue público añade el tratamiento del proveedor de
   alojamiento y sus propios registros de acceso — que es justo donde reaparecerían las IPs que
   el sistema se cuida de no guardar. **Elegir alojamiento es, por tanto, una decisión de
   protección de datos**, no solo de coste, y hay que tratarla como tal cuando llegue.

**Consulta previa a la autoridad de control** (art. 36): no procede a juicio de esta evaluación,
porque no queda riesgo alto sin mitigar. Con la lista de suscriptores activa, la valoración
sería otra.

**Delegado de protección de datos**: no se aprecia obligación de designarlo con el diseño actual,
en el que no hay tratamiento a gran escala de categorías especiales — precisamente porque ese
tratamiento se eliminó.

---

## 8. Plan de acción

Lo que falta, en orden, y ninguno es código:

1. **Canal escrito para ejercer derechos** (una dirección de contacto y qué se hace con cada
   tipo de solicitud), antes de cualquier despliegue público.
2. **Aviso de privacidad** en la web, corto y de verdad: qué se trata, qué no, y que consultar
   no deja rastro. Hoy la interfaz lo insinúa junto al enlace del feed; merece página propia.
3. **Revisión jurídica externa** de las bases de legitimación de la sección 3.1 antes de un
   despliegue con personas reales.
4. **Revisar esta evaluación** si ocurre cualquiera de estas tres cosas: se activa el canal por
   correo, revisa el panel más de una persona, o se despliega en un proveedor de alojamiento.

---

## 9. Referencias internas

- `CLAUDE.md` 6.4 — minimización y canal pull. `CLAUDE.md` 6.5 — archivo con sellado de tiempo.
- ADR 0003 (gate humano), 0005 (archivo con sello), 0006 (salida HTTP), 0008 (LLM local),
  0010 (canal pull primero), 0017 (autenticación del panel).
- `THREAT-MODEL.md` — STRIDE por componente. `SECURITY.md` — estado de los controles.
