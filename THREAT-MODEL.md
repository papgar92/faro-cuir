# Modelo de amenaza — Faro Cuir

> Pendiente de desarrollo completo. Este documento se irá llenando a medida que se implemente
> cada componente; no es un trámite de cierre, se mantiene vivo (`CLAUDE.md` sección 9).

## Activos a proteger

- Integridad del archivo de documentos ingeridos (sha256 + sello de tiempo).
- Disponibilidad e integridad de la infraestructura de ingesta (backend, worker, DB).
- Confidencialidad de los datos de suscriptores (categoría especial, art. 9 RGPD).
- Neutralidad e integridad del pipeline de clasificación (que nadie pueda hacer que el
  sistema publique un juicio no derivado del diff).

## Actores de abuso considerados (TODO — desarrollar)

- TODO(verificar): fuente maliciosa o comprometida que sirve XML/PDF adversarial.
- TODO(verificar): actor que intenta usar el worker como proxy SSRF.
- TODO(verificar): actor que intenta correlacionar suscriptores con afinidad LGTBI+.
- TODO(verificar): actor que intenta inyectar instrucciones vía el contenido de un boletín
  para manipular al LLM extractor.

## STRIDE (TODO — tabla completa por componente)

| Componente | Spoofing | Tampering | Repudiation | Info disclosure | DoS | Elevation |
|---|---|---|---|---|---|---|
| Ingesta (worker) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| API pública | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Panel de revisión | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Webhooks | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |

Se desarrollará en una sesión dedicada, en paralelo a la implementación de `security/`
(`CLAUDE.md` sección 6).
