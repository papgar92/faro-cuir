import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Suscriptor(Base):
    """Destinatario de alertas. **Dato de categoría especial (art. 9 RGPD).**

    Estar suscrito a alertas sobre derechos trans revela afinidad al colectivo, que es
    exactamente lo que el artículo 9 protege. El modelo está construido alrededor de esa idea
    (CLAUDE.md 6.4), y lo más importante de esta tabla es **lo que no tiene**:

    - No hay nombre, ni apellidos, ni teléfono, ni idioma, ni zona horaria.
    - No hay dirección IP, ni user-agent, ni fecha de último acceso, ni contador de aperturas.
      Nada de analítica de comportamiento: si no se recoge, no se puede filtrar ni exigir por
      requerimiento.
    - No hay email en claro. Solo su hash con pepper (ver `security/hashing.py`), que permite
      comprobar "¿está esta dirección suscrita?" sin poder listar quién lo está.

    Un volcado completo de esta tabla no permite a quien lo obtenga saber a quién avisar ni a
    quién señalar. Ese es el criterio de diseño, y es comprobable leyendo las columnas.
    """

    __tablename__ = "suscriptor"

    id: Mapped[int] = mapped_column(primary_key=True)

    # HMAC-SHA256 del email con un pepper de entorno. Único: evita suscripciones duplicadas
    # sin necesidad de guardar la dirección. Con el pepper fuera de la base de datos, un
    # volcado de la tabla no basta para hacer fuerza bruta sobre el espacio de emails.
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Canal alternativo para las ONGs (Slack/Discord/n8n). Se firma con HMAC al enviar,
    # sección 6.6. Va en claro porque es una URL de servicio, no un dato personal.
    webhook_url: Mapped[str | None] = mapped_column(String(1000))

    # Lista de CCAA de interés. JSON en vez de ARRAY de Postgres para que el esquema se pueda
    # montar también en SQLite en los tests.
    ccaa_interes: Mapped[list[Any] | None] = mapped_column(JSON)

    # Token de baja opaco: aleatorio, nunca derivado del email ni predecible (6.4). Si se
    # derivara, quien conociera el email podría dar de baja a alguien; y peor, quien viera un
    # token podría deducir el email.
    token_baja_opaco: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Única marca temporal que se guarda, y solo para poder purgar suscripciones nunca
    # confirmadas. No hay `ultimo_acceso` ni equivalente a propósito.
    creado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
