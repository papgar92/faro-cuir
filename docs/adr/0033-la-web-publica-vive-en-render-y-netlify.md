# ADR 0033 — La web pública vive en Netlify y la API en Render

- **Fecha:** 2026-09-05
- **Estado:** aceptado (preparado; **el despliegue lo autoriza el humano**, sección 12)
- **Afecta a:** `render.yaml`, `netlify.toml`, `backend/Dockerfile`, `docker-compose.yml`,
  `docs/eipd.md`, `THREAT-MODEL.md`
- **Continúa:** ADR 0032 (la ingesta, la base y el archivo salieron del portátil)

## Contexto

El ADR 0032 sacó de la máquina de casa las tres piezas que tenían que correr desatendidas: la
ingesta a GitHub Actions, la base a Neon y el archivo a Backblaze B2. Quedaban fuera las dos que
tienen público: **el backend de FastAPI y la web**.

La sección 12 lo tenía escrito como acción externa pendiente —«investigar opciones para desplegar
una versión pública»— y con la entrega movida al 2026-10-01 ya cabe.

## La restricción que decidió la respuesta, y no era el precio

**Las sesiones del panel de revisión y su cadencia de intentos viven en memoria del proceso**
(`api/revision.py`; el `docker-compose.yml` lo lleva escrito desde hace tiempo: *«con varios, la
cadencia se multiplicaría y eso falla ABIERTO»*).

Eso **descarta de entrada todo lo serverless** —funciones de Vercel, Lambda, Cloudflare Workers,
Deno Deploy, Cloud Run—, que es justamente donde están hoy casi todos los planes gratuitos que no
duermen. No es un «casi vale»: es exactamente el fallo abierto que ese comentario documenta.

Conviene tenerlo consciente: **el coste de aquella decisión no es cero, y hoy se paga en un minuto
de arranque en frío.** La decisión sigue siendo correcta —un gate humano que falla abierto no es
un gate— pero es un compromiso medido, no un accidente del hosting.

## Decisión

| pieza | dónde | por qué esa |
|---|---|---|
| **API** | Render, plan Free, **Frankfurt** | Es la única que cumple las seis restricciones **sin tarjeta**. Sus docs dicen que los servicios Free **no admiten «scaling beyond a single instance»**: el proceso único está garantizado por documentación, no por suerte. Y sin método de pago **no puede haber cargo**: el modo de fallo es la suspensión |
| **Web** | Netlify, plan Free | El único que puede hacer **proxy de `/api` hacia el backend**, lo que conserva el **mismo origen** |

**Netlify y no Cloudflare Pages, y el motivo no es el ancho de banda.** Cloudflare Pages tiene
tráfico ilimitado y Netlify un tope de 100 GB, pero **Pages no puede hacer de proxy hacia un
origen externo**. Sin proxy, la web y la API quedan en dominios distintos y hay que activar CORS
en FastAPI — lo que `vite.config.ts` ya había descartado por escrito: *«obligaría a relajar en el
backend una política de origen cruzado para resolver un problema que solo existe en desarrollo»*.
Con nuestro tráfico, 100 GB sobran; relajar CORS no.

Tres decisiones dentro:

1. **La configuración va en el repositorio, no en el panel del proveedor.** `render.yaml` y
   `netlify.toml` se revisan en un PR y aparecen en un diff. Un ajuste que solo vive en la
   interfaz de un proveedor no lo audita nadie y nadie se entera cuando cambia. Los **secretos**
   no: van con `sync: false`, que es «esto lo rellena una persona».
2. **La imagen pública deja de llevar `ruff`, `mypy` y `pytest`.** El `Dockerfile` pasa a dos
   etapas: `base` es lo que se publica y `dev` —la que usa el compose— añade las herramientas del
   CI. El comentario que había decía *«una imagen de despliegue real las quitaría con una etapa
   aparte; ese día se añade»*. Es hoy.
3. **El `CMD` honra `$PORT`.** Render inyecta el puerto por entorno y no se puede elegir; con un
   8000 fijo el servicio arrancaría y su comprobación de salud fallaría sin que el log dijera nada
   útil. En local no hay `PORT` y se queda en 8000.

## Consecuencias, incluidas las incómodas

- **El servicio duerme a los 15 minutos sin tráfico y tarda ~1 minuto en despertar.** Para un
  observatorio que alguien abre una vez por semana es feo, no inhabilitante.
- **Las sesiones del panel mueren en cada suspensión.** Quien revise tendrá que autenticarse casi
  cada vez. No rompe el gate humano; lo hace incómodo.
- **La ventana de cadencia de intentos también se reinicia al despertar.** Es el mismo «falla
  abierto» en versión temporal: alguien puede esperar a que el servicio duerma para reintentar.
  **Va al THREAT-MODEL como riesgo residual**, no se ignora.
- **Hay una salida aritmética y no se toma a la ligera:** las 750 horas/mes del plan son más que
  un mes entero (744 en uno de 31 días), así que un ping cada ~14 minutos lo mantendría despierto
  dentro de cuota. Pero los pings de keep-alive están en **zona gris en los términos** de casi
  todas estas plataformas y no se han leído los de Render. Hasta que se lean, no se hace.
- **La afirmación sobre las IPs se afloja, y el humano decidió cómo** (2026-09-05). Con estas
  plataformas **no se puede afirmar «no se registran IPs», solo «nosotros no las registramos»**:
  Netlify y Render las procesan en su borde por necesidad técnica y ninguno lo desactiva desde un
  plan gratuito.

  **Lo que se afirma pasa a ser exactamente eso**, sin adornarlo: el sistema no las registra
  —uvicorn con `--no-access-log`, comprobado en el `Dockerfile` y en el compose— y lo que haga el
  proveedor no está en nuestra mano.

  **Y el encuadre importa más que el matiz:** esto que se despliega es **la muestra**. Si algún
  día una asociación LGTBI+ lo usara de verdad, lo alojaría en su propia infraestructura y ese
  control sería de su IT, no nuestro — que es además la respuesta correcta para un sistema cuyos
  usuarios son dato de categoría especial. Nosotros nos encargamos de la muestra, aun en
  producción. La EIPD lo dice así y nombra a los proveedores como encargados del tratamiento; no
  promete un control que no tiene, que es justo lo que la haría inútil.
- **Queda un defecto de privacidad que hay que arreglar ANTES de publicar**, y no es del hosting:
  `index.html` carga las tipografías desde **Google Fonts**, así que el navegador de cada
  visitante manda su IP a Google en cada carga. Eso contradice de frente la 6.4. Se arregla
  alojando las fuentes nosotros, y entonces la CSP puede sostener `default-src 'self'` sin
  excepciones. **Mientras no se haga, la CSP nombra a Google y eso se ve en el diff**, que es
  justamente el sitio donde tiene que verse.

## Alternativas descartadas

- **Vercel / Cloudflare Workers / Cloud Run para la API.** N instancias efímeras: rompen el panel.
- **Cloudflare Pages para la web.** Tráfico ilimitado, pero no proxea a un origen externo.
- **GitHub Pages.** **No permite cabeceras HTTP propias en absoluto** — ni HSTS ni
  `X-Content-Type-Options`, solo CSP por `<meta>`. La 6.8 las exige.
- **Fly.io** (sin plan gratuito desde octubre de 2024), **Railway** ($1/mes que no acumula),
  **Koyeb** (pide tarjeta y su página de precios ya no lista plan gratuito de cómputo tras la
  compra por Mistral AI), **Hugging Face Spaces** (cumple todo salvo la región: no hay Europa en
  el runtime gratuito), **Clever Cloud** (sin plan gratuito desde 2023).
- **El GitHub Student Pack** ($200 en DigitalOcean, always-on en Ámsterdam). Es la única vía a un
  servicio que no duerme dentro del EEE, pero exige verificación de estudiante, caduca a los 12
  meses y deja una VM que administrar. Contradice la 0 bis: «la que exija menos cosas que
  conseguir». Queda anotada por si el arranque en frío molesta de verdad.
