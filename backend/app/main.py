"""Punto de entrada de la app FastAPI."""

import logging

from fastapi import FastAPI

from app.api.alertas import router as alertas_router
from app.api.cobertura import router as cobertura_router
from app.api.documentos import router as documentos_router
from app.api.feed import router as feed_router
from app.api.hallazgos import router as hallazgos_router
from app.api.health import router as health_router
from app.api.revision import router as revision_router
from app.config import get_settings
from app.security.headers import SecurityHeadersMiddleware
from app.security.rate_limit import RateLimitMiddleware

# Sin esto, **los logs de la aplicación no salían**. uvicorn solo configura sus propios
# loggers; los nuestros propagan al raíz, que sin handler deja pasar únicamente WARNING y
# superiores por el `lastResort` de la biblioteca. El worker sí llamaba a `basicConfig` y la API
# no, así que el rastro del gate humano —«aprobada la revisión N, alerta emitida» (ADR 0003 y
# 0017)— se escribía en un logger que nadie escuchaba. Se descubrió al verificar el panel en el
# navegador: la fila estaba en la base de datos y no había ni una línea en el log.
logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Faro Cuir")

# El orden no es indiferente. En Starlette el **último** `add_middleware` queda por fuera,
# así que las cabeceras se registran las últimas para envolverlo todo: el limitador sigue
# rechazando antes de que la petición toque la ruta o la base de datos, y su respuesta 429
# sale igualmente por el middleware de cabeceras. Al revés, un 429 viajaría sin ellas — y una
# respuesta de error es tan susceptible de acabar interpretada por un navegador como las
# demás. Hay un test que fija este orden.
#
# No se activa CORS a propósito (CLAUDE.md): el proxy de Vite resuelve el desarrollo y en
# producción frontend y API van tras el mismo origen.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health_router)
app.include_router(documentos_router)
app.include_router(cobertura_router)
# Lo aprobado por el gate humano, y solo eso. Público y de solo lectura: es lo que el proyecto
# afirma en su nombre, así que va con su evidencia para que se pueda comprobar.
app.include_router(alertas_router)
# El canal de difusión por defecto (6.4, ADR 0010): un feed Atom que no sabe quién lo lee. Va
# después de las alertas porque es el mismo dato con otra piel — y comparte la consulta, que es
# donde vive el control de que solo salga lo aprobado.
app.include_router(feed_router)
# Los hallazgos históricos (ADR 0025, decisiones 3 y 4): cambios que el archivo prueba y que
# **nadie ha revisado**, publicables solo porque una organización con nombre ya los documentó.
# Router aparte del de alertas a propósito: son dos superficies que afirman cosas distintas, y
# fundirlas en una ruta con un parámetro dejaría la diferencia en manos de una etiqueta.
app.include_router(hallazgos_router)
# El panel de revisión (gate humano, regla de oro 4): la única parte de la API que escribe y la
# única con autenticación. Va detrás de los mismos dos middlewares que todo lo demás — el
# limitador de peticiones también cuenta los intentos de login, además de la cadencia propia
# del panel.
app.include_router(revision_router)
