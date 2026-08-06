# 0003 — Gate humano obligatorio antes de emitir cualquier alerta

## Contexto

Faro Cuir puede emitir alertas públicas diciendo que una comunidad autónoma ha recortado un
derecho. Los costes de equivocarse no son simétricos:

- **Falso positivo publicado:** una acusación pública incorrecta contra una administración.
  Daña a las personas a las que el proyecto quiere proteger, porque quema la credibilidad de la
  herramienta justo cuando haga falta que la crean. Y es munición para quien quiera desacreditar
  el trabajo entero: basta un error para hablar de "alarmismo".
- **Retraso de unas horas por revisión:** el cambio normativo sigue ahí. Casi ningún caso de
  este dominio se decide en una tarde.

El sistema procesa 18 fuentes a diario con un pipeline que incluye un LLM y un clasificador por
reglas. Ambos se equivocarán.

## Decisión

**Ninguna detección se convierte en alerta sin que una persona la apruebe.** Sin excepción, sin
modo "auto-publicar lo de confianza alta", sin umbral por encima del cual se salte el paso.

Está en el modelo de datos, no solo en el código: una `deteccion` va a `cola_revision`, y solo
desde el estado `aprobada` puede nacer una fila en `alerta`. Que exista una fila en `alerta`
significa, por construcción, que alguien la aprobó.

El clasificador usa **dos umbrales** (sección 7): uno de precisión alta y otro de recall alto.
La diferencia entre ambos no es "esto se publica solo y esto se revisa" — todo se revisa. Es la
prioridad con la que aparece en la cola y el orden en que un humano lo mira.

### Qué no se guarda del revisor

`cola_revision` registra el estado, cuándo se resolvió y una nota libre. **No registra quién
revisó.** Para auditar que el gate funciona basta saber que se resolvió y cuándo; almacenar qué
persona revisó qué alerta sobre derechos LGTBI+ crearía un dato personal sensible que el
proyecto no necesita (sección 6.4). Si algún día hicieran falta varios revisores con
responsabilidades distintas, se revisita aquí.

## Alternativas consideradas

- **Auto-publicar por encima de un umbral de confianza.** Descartado, y es la alternativa que
  más veces se va a proponer. El problema es que el umbral se calibra sobre el gold set, es
  decir sobre normativa pasada, y el caso que más importa detectar es precisamente el que no se
  parece a nada anterior. Un umbral que funciona bien en agregado no protege del error concreto
  y ruidoso, que es el único que hace daño aquí.
- **Publicar automáticamente y corregir después.** Descartado. Una retractación nunca llega a
  la misma gente que la afirmación original.
- **Gate humano solo para `retroceso`.** Descartado: un "avance" mal detectado también es una
  afirmación falsa sobre lo que hizo una administración, y desmiente al sistema igual.
- **Cola con caducidad: si nadie revisa en N horas, se publica.** Descartado. Convierte el gate
  en un retardo, no en un control — y falla exactamente cuando el equipo está saturado, que es
  cuando peor se revisa.

## Consecuencias

- El sistema **no es tiempo real**, y no debe venderse como tal. Es vigilancia diaria con
  revisión. El pitch ("el Rainbow Map pero en tiempo real") describe la frecuencia de la
  *ingesta*, no la de la publicación; conviene no confundirlo al comunicarlo.
- El proyecto necesita al menos una persona revisora sostenida en el tiempo. Es una dependencia
  organizativa real, no técnica, y hay que decirla al hablar con asociaciones: sin alguien que
  revise, el sistema no emite.
- El panel de revisión pasa a ser parte crítica del producto, no un accesorio de administración.
  Si revisar es incómodo, la cola se atasca y el sistema deja de servir.
- La cola es el sitio natural donde medir la calidad real del pipeline: la proporción de
  detecciones descartadas por un humano es la métrica honesta de precisión, mucho mejor que
  cualquier número que se calcule contra el gold set.
