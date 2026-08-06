# Modelo de amenaza — Faro Cuir

> Documento vivo (`CLAUDE.md` sección 9). Cada control citado apunta al código que lo
> implementa; lo que no está implementado se marca como **no mitigado**, no se omite. Un
> modelo de amenaza que solo enumera lo que ya está resuelto no sirve para nada.

## 1. Qué hace especial a este sistema

Faro Cuir no es una aplicación web genérica a la que le tocan los mismos riesgos que a
cualquier otra. Tiene tres rasgos que mueven las prioridades:

1. **Ingiere contenido de 18 fuentes externas que no controlamos.** Es la superficie de
   ataque principal y no se puede reducir: consumir esas fuentes *es* el producto.
2. **Sus usuarios son un colectivo perseguido.** La sola condición de estar suscrito a
   alertas sobre derechos trans revela afinidad al colectivo LGTBI+ (art. 9 RGPD). Una fuga
   de suscriptores no es un incidente de privacidad corriente: es una lista de objetivos.
3. **Su valor es la credibilidad.** El producto afirma "el día X esta norma decía esto". Un
   atacante que consiga que el sistema publique un diff falso o una clasificación no derivada
   del texto no roba nada — destruye el proyecto entero, que es un daño mayor.

De ahí que la integridad pese más que la confidencialidad del contenido (los boletines son
públicos por definición) y que la manipulación del veredicto se trate como amenaza de primer
orden y no como un bug funcional.

## 2. Activos

| Activo | Por qué importa | Impacto si cae |
|---|---|---|
| Archivo de documentos (`sha256` + sello) | Es la prueba de qué se publicó | Alto — se pierde la razón de ser |
| Neutralidad del pipeline | El sistema no debe emitir juicio propio | Alto — reputacional irreversible |
| Datos de suscriptores | Categoría especial, art. 9 RGPD | **Crítico** — riesgo físico para personas |
| Disponibilidad de la ingesta | Un día perdido es un día sin vigilancia | Medio — recuperable reingiriendo |
| Credenciales (DB, pepper, API del LLM) | Acceso a todo lo anterior | Alto |

## 3. Actores de abuso

- **A1 — Fuente comprometida o maliciosa.** Quien controle un boletín (o el DNS/TLS hacia
  él) puede servirnos XML adversarial o URLs elegidas. Es el actor más probable y contra el
  que está construido casi todo `security/`.
- **A2 — Curioso oportunista contra la API pública.** Sin autenticación, cualquiera puede
  raspar o abusar. Bajo impacto salvo por disponibilidad.
- **A3 — Actor hostil al colectivo.** El que de verdad importa. Su objetivo no es el dinero:
  quiere **la lista de suscriptores** para acoso, o desacreditar el proyecto haciéndole
  publicar algo falso. Un actor así acepta esfuerzo alto por un premio no económico, que es
  exactamente el perfil que las defensas "suficientes para la mayoría" no cubren.
- **A4 — Insider con acceso al panel de revisión.** El gate humano es obligatorio (ADR 0003)
  y por tanto es también un punto único donde una persona puede aprobar algo indebido.
- **A5 — Administración que desindexa.** No es un atacante informático, es el actor contra
  el que existe el proyecto: la retirada silenciosa de un documento del boletín. El archivo
  sellado es la respuesta técnica (ADR 0005).

## 4. STRIDE por componente

### 4.1 Ingesta (worker)

| Amenaza | Escenario | Control | Estado |
|---|---|---|---|
| **S**poofing | Suplantar un boletín vía DNS y servir contenido falso | Solo HTTPS y puerto 443, verificación de certificado sin relajar, petición clavada a la IP validada con `Host` y `sni_hostname` (`security/url_guard.py`, ADR 0006) | Mitigado |
| **T**ampering | XML manipulado que altere lo archivado | `sha256` del cuerpo crudo antes de parsear; el fichero se nombra por su propio hash (`security/hashing.py`) | Mitigado |
| **T**ampering | XXE / entidades externas para leer ficheros del contenedor | `forbid_dtd=True` en `security/xml_safe.py`, con test de payload XXE | Mitigado |
| **R**epudiation | "Eso nunca se publicó así" | `sha256` + `sello_tiempo` por documento | Parcial — el sello lo pone nuestro ingestor, no una TSA; sin RFC 3161 es afirmación nuestra (ADR 0005) |
| **I**nfo disclosure | SSRF: usar el worker como proxy a la red interna | Allowlist de dominios, rechazo de toda IP no global (`is_global`), redirecciones revalidadas salto a salto, sin credenciales en URL | Mitigado |
| **D**oS | Bomba XML / respuesta gigante | Límites propios de profundidad y nº de nodos durante el parseo; tope de bytes al leer el cuerpo; timeouts | Mitigado |
| **D**oS | Path traversal al escribir el archivo | Nombre derivado del `sha256`, nunca del título; allowlist de extensiones | Mitigado |
| **E**levation | Ejecución vía el parser | Sin DTD, sin resolución de red, sin `eval` de contenido | Mitigado |

**No mitigado, consciente:** si una fuente oficial publica de verdad un documento alterado,
lo archivamos fielmente. El sistema garantiza *fidelidad a lo publicado*, no veracidad del
contenido. Es la propiedad correcta: un archivo que "corrige" lo publicado no sirve de
archivo.

### 4.2 API pública (lectura, sin autenticación)

| Amenaza | Escenario | Control | Estado |
|---|---|---|---|
| **T**ampering | Escritura por una ruta olvidada | La API **solo** tiene GET; hay un test que falla si aparece cualquier otro método | Mitigado |
| **I**nfo disclosure | Filtrar rutas internas del servidor | `ruta_almacen` no se expone; esquemas de salida escritos a mano, no derivados del modelo, para que publicar un campo nuevo sea un acto explícito | Mitigado |
| **I**nfo disclosure | Respuesta JSON interpretada como HTML por el navegador | `X-Content-Type-Options: nosniff` + CSP `default-src 'none'` (`security/headers.py`) | Mitigado |
| **I**nfo disclosure | Fuga de origen de navegación | `Referrer-Policy: no-referrer` — el referer revela por sí solo que alguien venía de aquí | Mitigado |
| **D**oS | `?limite=1000000` contra la base de datos | Tope duro de paginación en el servidor, no negociable por el cliente | Mitigado |
| **D**oS | Raspado agresivo | 60 peticiones/min por IP, ventana deslizante (`security/rate_limit.py`) | Parcial — por proceso; con varias réplicas se multiplica. No sustituye a un WAF |
| **S**poofing | Falsear la IP para saltarse el límite | No se lee `X-Forwarded-For`: la escribe el cliente | Mitigado |

**No mitigado, consciente:** no hay protección contra DDoS distribuido. Requiere
infraestructura delante (CDN/WAF) y queda fuera del alcance de un proyecto de 6 semanas.

### 4.3 Pipeline de clasificación

| Amenaza | Escenario | Control | Estado |
|---|---|---|---|
| **T**ampering | Inyección de prompt desde el texto del boletín para que el LLM diga lo que quiera el atacante | El LLM **no clasifica**: solo extrae hechos, y su salida se valida contra un esquema Pydantic; si no valida se descarta, no se "interpreta" (ADR 0002) | Diseñado — el extractor aún no está implementado |
| **T**ampering | Persistir el veredicto del LLM como si fuera la clasificación | `deteccion.origen` **no tiene el valor `llm`**: la CHECK de PostgreSQL hace que ese veredicto no sea representable en el esquema (ADR 0004) | Mitigado en el esquema |
| **T**ampering | Reescribir el histórico de un artículo | Trigger de PostgreSQL que rechaza UPDATE y DELETE sobre `version_norma` | Mitigado y verificado |
| **I**nfo disclosure | Enviar datos de suscriptores al proveedor del LLM | Los suscriptores nunca entran en el LLM ni en logs (6.4); el input del LLM es texto público de boletines | Diseñado |
| **E**levation | Una norma relevante se pierde en silencio | Prefiltro sesgado a recall, sin lista negra, con el término y la versión del vocabulario persistidos y **publicados en la API** (ADR 0007) | Parcial — el recall real no está medido; solo lo medirá el gold set |

**El riesgo más serio de esta sección no es un atacante: es el prefiltro.** Es la única etapa
que puede descartar una norma sin dejar rastro visible para nadie. Por eso la decisión se
persiste con su justificación y se expone en la API: para que el descarte sea auditable
desde fuera y no haya que fiarse de nosotros.

### 4.4 Datos de suscriptores

| Amenaza | Escenario | Control | Estado |
|---|---|---|---|
| **I**nfo disclosure | Volcado de la tabla → lista de personas del colectivo | Email guardado solo como **HMAC con pepper de entorno**, nunca en claro | Mitigado |
| **I**nfo disclosure | Reversión del hash con un diccionario de direcciones | Pepper fuera de la base de datos (variable de entorno); `hash_email` **falla cerrado** si no está, en vez de guardar un hash sin sal | Mitigado |
| **S**poofing | Dar de baja a otra persona adivinando su token | Token de baja aleatorio y opaco, no derivado del email | Mitigado |
| **I**nfo disclosure | Correlación por comportamiento | Sin perfilado, sin analítica, sin cookies de terceros | Mitigado por diseño |
| **R**epudiation | No poder demostrar el consentimiento | — | **No mitigado** — pendiente del flujo de alta (EIPD) |

**No mitigado, consciente:** el envío de una alerta requiere el email en claro en ese
momento. Ese es el punto débil estructural del modelo y no se puede eliminar del todo, solo
acotar (cifrado en reposo, mínimo tiempo de exposición). Se desarrolla en `docs/eipd.md`.

### 4.5 Panel de revisión y webhooks

Ambos **sin implementar**. Se listan porque las amenazas ya se conocen y condicionan el
diseño:

| Amenaza | Control previsto |
|---|---|
| Aprobación indebida por un insider (A4) | Registro de quién aprueba cada detección, inmutable |
| Fuerza bruta contra el panel | Autenticación con límite de intentos; el panel no es público |
| Webhook de salida suplantado | Firma HMAC-SHA256 del payload + timestamp + nonce anti-replay |
| Replay de un webhook de entrada | Verificación de firma y ventana temporal antes de procesar |

### 4.6 Cadena de suministro e infraestructura

| Amenaza | Control | Estado |
|---|---|---|
| Secreto commiteado | `gitleaks` en CI | Mitigado |
| Dependencia maliciosa | Dependencias fijadas; `defusedxml` obligatorio para XML; `pip-audit` en CI rompe el job ante un CVE conocido, transitivas incluidas | Mitigado |
| Configuración con secretos en el repo | Todo por entorno, `.env` en `.gitignore` | Mitigado |

## 5. Resumen honesto de lo que falta

Ordenado por riesgo, no por facilidad:

1. **Recall del prefiltro sin medir.** Hoy no se puede afirmar cuántas normas relevantes se
   pierden. Solo lo resuelve el gold set.
2. **Consentimiento y ciclo de vida de los suscriptores.** Sin flujo de alta/baja
   implementado no hay EIPD cerrable.
3. **Sello de tiempo sin tercero de confianza.** Hasta RFC 3161, la fecha del archivo es
   afirmación nuestra (ADR 0005).
4. **Panel de revisión y webhooks sin implementar**, con sus amenazas ya identificadas.
5. **Sin protección ante DDoS**, fuera de alcance por diseño.
