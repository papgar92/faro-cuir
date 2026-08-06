# Política de seguridad

> Documento vivo: se actualiza junto con el código, no como trámite final. Ver `CLAUDE.md`
> sección 9.

Este proyecto ingiere contenido (XML, PDF, HTML) de 18 fuentes externas no controladas por
nosotros. Esa es la superficie de ataque principal. El detalle del modelo de amenaza vive en
[`THREAT-MODEL.md`](./THREAT-MODEL.md); este documento resume la postura y el proceso.

## Alcance

- Parseo de contenido no confiable (XXE, bombas XML, PDFs).
- SSRF en el worker de ingesta.
- Path traversal al nombrar ficheros descargados.
- Datos de suscriptores (categoría especial, art. 9 RGPD).
- Integridad del archivo (sellado de tiempo + sha256).
- Webhooks de entrada/salida (firma HMAC).
- Inyección de prompt sobre el LLM extractor.

El detalle técnico de cada punto está en `CLAUDE.md` sección 6; el estado real de cada
control, más abajo.

## Reporte de vulnerabilidades

TODO(verificar): definir canal de contacto cuando el proyecto tenga despliegue público. Por
ahora es un proyecto académico sin instancia expuesta.

## Estado de los controles

Tres estados y nada más: **Implementado** (hay código y test), **Parcial** (funciona pero con
una limitación conocida que se nombra) y **Pendiente**. No se marca como implementado nada
que no se pueda enseñar funcionando.

| Control | Estado | Dónde |
|---|---|---|
| `defusedxml` para parseo XML (XXE, bombas de entidades) | Implementado | `security/xml_safe.py` |
| Límites propios de profundidad y nº de nodos | Implementado | `security/xml_safe.py` |
| Puerta única de salida HTTP / anti-SSRF | Implementado | `security/url_guard.py`, ADR 0006 |
| Nombrado de ficheros por `sha256` (path traversal) | Implementado | `security/hashing.py` |
| Archivo íntegro: `sha256` + sello de tiempo | **Parcial** — el sello lo pone nuestro ingestor; sin RFC 3161 no es verificable por terceros | ADR 0005 |
| HMAC con pepper del email de suscriptores | Implementado — falla cerrado sin pepper | `security/hashing.py` |
| Token de baja opaco | Implementado | `models/suscriptor.py` |
| Veredicto del LLM no representable en el esquema | Implementado | CHECK de `deteccion.origen`, ADR 0004 |
| Histórico inmutable | Implementado — trigger que rechaza UPDATE/DELETE | `version_norma` |
| API pública de solo lectura | Implementado — test que falla si aparece un método distinto de GET | `api/documentos.py` |
| Tope duro de paginación | Implementado | `api/documentos.py` |
| Rate limiting API pública | **Parcial** — por proceso, se reinicia con él, no sustituye a un WAF | `security/rate_limit.py` |
| Cabeceras de seguridad (CSP, HSTS, nosniff, ...) | Implementado | `security/headers.py` |
| Prefiltro auditable (decisión persistida y publicada) | Implementado — recall **sin medir** hasta el gold set | ADR 0007 |
| `gitleaks` en CI | Implementado | `.github/workflows/ci.yml` |
| Validación Pydantic de la salida del LLM | Pendiente — el extractor no existe todavía | ADR 0002 |
| Firma HMAC de webhooks | Pendiente | — |
| Autenticación del panel de revisión | Pendiente | ADR 0003 |
| Escaneo de vulnerabilidades en dependencias | Implementado — `pip-audit` en CI, rompe el job si hay CVE | `.github/workflows/ci.yml` |

El detalle de cada amenaza, con los escenarios concretos y lo que **no** está mitigado, está
en [`THREAT-MODEL.md`](./THREAT-MODEL.md).
