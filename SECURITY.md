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

El detalle técnico de cada punto está en `CLAUDE.md` sección 6, y se irá reflejando aquí a
medida que se implemente cada control (`TODO(verificar)` mientras no exista código).

## Reporte de vulnerabilidades

TODO(verificar): definir canal de contacto cuando el proyecto tenga despliegue público. Por
ahora es un proyecto académico sin instancia expuesta.

## Estado de los controles

| Control | Estado |
|---|---|
| `defusedxml` para parseo XML | Pendiente |
| `url_guard.py` (SSRF) | Pendiente |
| Nombrado de ficheros por `sha256` | Pendiente |
| Hash+sal de email de suscriptores | Pendiente |
| Sellado de tiempo del archivo íntegro | Pendiente |
| Firma HMAC de webhooks | Pendiente |
| Validación Pydantic de salida del LLM | Pendiente |
| `gitleaks` en CI | Pendiente (S0, esta sesión) |
| Rate limiting API pública | Pendiente |
| Cabeceras de seguridad (CSP, HSTS, ...) | Pendiente |
