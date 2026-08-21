/**
 * Panel de revisión: el gate humano (regla de oro 4, ADR 0003 y 0017).
 *
 * Es la única pantalla que **escribe**, y la única con sesión. También es la única en la que
 * una persona decide algo: todo lo demás del sistema es determinista o está a la espera.
 *
 * Tres decisiones de esta pantalla, y ninguna es estética:
 *
 * 1. **La evidencia va antes que el veredicto, en el orden de lectura.** Es la misma cautela
 *    que el fichero del subagente `jurista-lgtbi` llama anclaje: si quien revisa lee
 *    «retroceso» antes que el artículo, ya no lo juzga, lo confirma — y el gate se vacía por
 *    dentro sin que nadie lo desactive. Por eso la insignia de clasificación va a la derecha,
 *    en tamaño pequeño y precedida siempre de «propuesta», y los fragmentos del texto
 *    archivado ocupan el centro de la tarjeta.
 * 2. **Cada fragmento lleva sus offsets y la huella del documento.** No es metadato de
 *    relleno: es lo que convierte la revisión en verificación en vez de confianza (7.5). Con
 *    el `sha256` y el enlace a la fuente oficial, quien revisa puede contrastar el recorte
 *    contra el BOE sin ejecutar nuestro código, que es exactamente lo que el proyecto le pide
 *    al resto del mundo.
 * 3. **Aprobar dice lo que hace antes de hacerlo.** Emitir una alerta es la acción con
 *    consecuencias del sistema entero, así que el botón no dice «Aceptar» sino qué provoca.
 *
 * Lo que esta pantalla NO enseña: lo que dijo el modelo. La API tampoco lo publica (ver
 * `schemas/revision.py`). Se dice que el extractor pasó por la norma y cuántos punteros dejó;
 * su prosa no se pone al lado de la evidencia porque acabaría leyéndose como conclusión del
 * sistema (reglas de oro 3 y 10).
 */

import { useCallback, useState } from "react";
import {
  ApiError,
  abrirSesionPanel,
  cerrarSesionPanel,
  comprobarSesionPanel,
  listarColaRevision,
  resolverRevision,
  type InformeApoyoApi,
  type ItemRevisionApi,
} from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { CambiosPrecepto } from "../components/CambiosPrecepto/CambiosPrecepto";
import { formatearSelloTiempo } from "../lib/formato";

/** Etiqueta y color de cada clasificación del backend (los cuatro de la sección 5). */
const CLASIFICACION: Record<
  ItemRevisionApi["clasificacion"],
  { label: string; glyph: string; clases: string }
> = {
  avance: { label: "Avance", glyph: "▲", clases: "text-adv border-adv bg-adv-bg" },
  retroceso: { label: "Retroceso", glyph: "▼", clases: "text-reg border-reg bg-reg-bg" },
  neutro: { label: "Neutro", glyph: "●", clases: "text-neu border-neu bg-neu-bg" },
  // `indeterminado` es el umbral de recall alto de 7.6: el catálogo ha visto algo y no sabe de
  // qué signo. Se pinta en el color de aviso y NO en el de retroceso: son cosas distintas y
  // teñirlo de rojo sería emitir el veredicto que la regla se abstuvo de emitir.
  indeterminado: { label: "Sin signo", glyph: "?", clases: "text-alr border-alr bg-alr-bg" },
};

function Login({ onEntrar }: { onEntrar: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await abrirSesionPanel(password);
      setPassword("");
      onEntrar();
    } catch (fallo) {
      // Ni el mensaje ni el campo distinguen "contraseña incorrecta" de "no hay contraseña
      // configurada": el backend tampoco lo hace, y aquí se respeta.
      setError(
        fallo instanceof ApiError && fallo.status === 429
          ? "Demasiados intentos. Espera unos segundos."
          : "No se ha podido abrir la sesión de revisión.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto max-w-[520px] px-7 py-16">
      <h1 className="font-serif text-2xl font-bold text-ink">Panel de revisión</h1>
      <p className="mt-3 text-sm leading-relaxed text-ink-2">
        Ninguna alerta de Faro Cuir se publica sin que una persona la apruebe. Esta pantalla es
        ese paso, y no hay forma de saltárselo.
      </p>

      <form onSubmit={enviar} className="mt-8 rounded border border-line bg-surface p-6">
        <label htmlFor="panel-password" className="block text-sm font-medium text-ink">
          Contraseña de revisión
        </label>
        <input
          id="panel-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-2 w-full rounded border border-line-2 bg-bg px-3 py-2 text-sm text-ink"
        />
        {error && (
          <p role="alert" className="mt-3 text-sm text-reg">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={enviando || password === ""}
          className="mt-4 w-full rounded border border-ink bg-ink px-4 py-2 text-sm font-semibold text-bg disabled:opacity-40"
        >
          {enviando ? "Comprobando…" : "Entrar"}
        </button>
        <p className="mt-4 text-xs leading-relaxed text-ink-3">
          No hay cuentas de usuario y no se guarda quién revisa. Para auditar el gate basta con
          saber que se resolvió, cuándo y con qué nota (CLAUDE.md 6.4).
        </p>
      </form>
    </main>
  );
}

const SEMAFORO: Record<
  InformeApoyoApi["semaforo"],
  { etiqueta: string; glifo: string; clases: string }
> = {
  // Colores de **prioridad de lectura**, no de la paleta avance/retroceso. Es deliberado: el
  // semáforo dice «yo publicaría esto», no «esto recorta un derecho», y dos de los tres primeros
  // informes en rojo eran avances. Usar `reg` aquí haría que el color afirmara lo que el informe
  // no afirma.
  alerta: { etiqueta: "Yo lo publicaría", glifo: "●", clases: "border-alr bg-alr-soft text-alr" },
  mirar: { etiqueta: "Míralo con calma", glifo: "◐", clases: "border-line-2 bg-inset text-ink-2" },
  descartar: { etiqueta: "Yo lo descartaría", glifo: "○", clases: "border-line-2 text-ink-3" },
};

/**
 * El dosier de apoyo, si alguien lo ha preparado. ADR 0025.
 *
 * **Va debajo de la evidencia y del diff, nunca encima, y eso no es maquetación.** Si quien
 * revisa lee «yo publicaría esto» antes que el artículo, deja de juzgar y pasa a confirmar: el
 * gate humano se vacía por dentro sin que nadie lo desactive (CLAUDE.md 13.4). El orden de la
 * pantalla es el único sitio donde ese riesgo se puede administrar.
 *
 * Por lo mismo, `refutacion` se pinta con el mismo peso visual que la recomendación y nunca
 * plegada: es lo que le da a quien revisa con qué llevarle la contraria en treinta segundos.
 */
function InformeDeApoyo({ informe }: { informe: InformeApoyoApi }) {
  const meta = SEMAFORO[informe.semaforo];
  return (
    <section className="mt-5 rounded border border-dashed border-line-2 bg-inset p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${meta.clases}`}
        >
          <span aria-hidden="true">{meta.glifo}</span>
          {meta.etiqueta}
        </span>
        {/* La etiqueta que separa esto de una alerta aprobada. No se esconde ni se abrevia. */}
        <span className="font-mono text-[10.5px] text-ink-3">
          informe de apoyo · lo preparó {informe.generado_por} · no lo ha revisado nadie
        </span>
      </div>

      <p className="mt-2.5 text-sm leading-relaxed text-ink">{informe.resumen}</p>

      {informe.a_quien_afecta && (
        <p className="mt-2 text-sm leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">A quién afecta: </span>
          {informe.a_quien_afecta}
        </p>
      )}

      {informe.citas.length > 0 && (
        <ul className="mt-3 list-none space-y-2 p-0">
          {informe.citas.map((cita, indice) => (
            <li key={indice} className="border-l-2 border-line-2 pl-2.5">
              <p className="m-0 text-[13px] leading-relaxed text-ink-2">«{cita.texto}»</p>
              {(cita.apartado || cita.version) && (
                <p className="m-0 mt-0.5 font-mono text-[10.5px] text-ink-3">
                  {[cita.apartado, cita.version && `redacción ${cita.version}`]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Lo que hace publicable un hallazgo sin revisión humana: que alguien con nombre ya lo
          dijera. Vacío significa que ninguna organización de referencia lo ha señalado, y eso
          también es información. */}
      {informe.corroboraciones.length > 0 && (
        <div className="mt-3">
          <h5 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
            Quién más lo ha dicho
          </h5>
          <ul className="mt-1 list-none space-y-1 p-0 text-[13px] leading-relaxed text-ink-2">
            {informe.corroboraciones.map((fuente, indice) => (
              <li key={indice}>
                <span className="font-semibold text-ink">{fuente.organizacion}</span>
                {fuente.que_dice && `: ${fuente.que_dice}`}{" "}
                {fuente.url && (
                  <a
                    href={fuente.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-link underline"
                  >
                    fuente ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
        <p className="m-0 text-[13px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">Recomendación: </span>
          {informe.recomendacion}
        </p>
        {/* Mismo peso visual que la recomendación, y jamás plegado. Ver la cabecera. */}
        <p className="m-0 rounded border border-line-2 bg-surface p-2 text-[13px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">Qué le refutaría: </span>
          {informe.refutacion}
        </p>
      </div>
    </section>
  );
}

function Evidencia({ item }: { item: ItemRevisionApi }) {
  if (item.spans.length === 0) {
    return (
      <p className="mt-4 rounded border border-line-2 bg-inset p-3 text-sm text-ink-2">
        Este veredicto no trae fragmentos de evidencia. Es un caso para mirar con más cuidado, no
        con menos: sin spans no se puede contrastar contra el texto archivado.
      </p>
    );
  }

  return (
    <div className="mt-4">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-3">
        Evidencia · recortada del texto archivado, no de lo que dijo el modelo
      </h4>
      <ul className="mt-2 space-y-2">
        {item.spans.map((span) => (
          <li
            key={`${span.inicio}-${span.fin}`}
            className="rounded border border-line-2 bg-inset p-3"
          >
            <p className="font-mono text-[13px] leading-relaxed text-ink">«{span.fragmento}»</p>
            <p className="mt-1.5 font-mono text-[10.5px] text-ink-3">
              caracteres {span.inicio.toLocaleString("es-ES")}–{span.fin.toLocaleString("es-ES")}
              {item.version_texto_plano && ` · derivación del texto ${item.version_texto_plano}`}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface TarjetaProps {
  item: ItemRevisionApi;
  onResuelto: () => void;
}

function Tarjeta({ item, onResuelto }: TarjetaProps) {
  const [nota, setNota] = useState("");
  // El signo que fija quien revisa. Vacío = no lo toca, que es lo normal: la mayoría de las veces
  // la regla ya lo afirmó y aquí solo se aprueba o se descarta.
  const [signo, setSigno] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<"aprobar" | "descartar" | null>(null);
  const clasificacion = CLASIFICACION[item.clasificacion];

  async function resolver(accion: "aprobar" | "descartar") {
    setEnviando(accion);
    setError(null);
    try {
      await resolverRevision(
        item.id,
        accion,
        nota,
        // Solo al aprobar: descartar es decir «esto no se publica», y un signo sobre algo que no
        // se publica no significa nada.
        accion === "aprobar" && signo !== "" ? (signo as "avance") : null,
      );
      onResuelto();
    } catch (fallo) {
      setError(
        fallo instanceof ApiError && fallo.status === 409
          ? "Alguien ya resolvió este ítem. Recarga la cola."
          : fallo instanceof ApiError && fallo.status === 401
            ? "La sesión ha caducado. Vuelve a entrar."
            : "No se ha podido registrar la decisión.",
      );
      setEnviando(null);
    }
  }

  return (
    <article className="rounded border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[11px] text-ink-3">
            {item.norma.identificador_oficial}
            {item.norma.organo_emisor && ` · ${item.norma.organo_emisor}`}
          </p>
          <h3 className="mt-1 font-serif text-lg font-bold leading-snug text-ink">
            {item.norma.titulo}
          </h3>
        </div>
        <div className="text-right">
          <span className="block text-[10px] uppercase tracking-wide text-ink-3">
            Propuesta del catálogo
          </span>
          <span
            className={`mt-1 inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs font-semibold ${clasificacion.clases}`}
          >
            <span aria-hidden="true">{clasificacion.glyph}</span>
            {clasificacion.label}
          </span>
        </div>
      </div>

      <Evidencia item={item} />

      {/* Lo que se va a publicar si esto se aprueba. Estaba solo en la alerta, o sea DESPUÉS de
          la decisión: quien revisaba aprobaba sin ver el antes y el después. Lo señaló la
          auditoría del 2026-08-16 y es la mitad que faltaba del gate. */}
      {item.cambios.length > 0 && (
        <section className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-3">
            Redacción anterior y nueva · {item.cambios.length} precepto
            {item.cambios.length > 1 ? "s" : ""} archivados
          </h4>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-3">
            Sale del texto consolidado del BOE, no del boletín de aquel día. Es lo que verá quien
            reciba la alerta si la apruebas.
          </p>
          <CambiosPrecepto cambios={item.cambios} />
        </section>
      )}

      <dl className="mt-4 grid gap-x-6 gap-y-2 text-xs text-ink-2 sm:grid-cols-2">
        <div>
          <dt className="inline font-semibold text-ink">Regla: </dt>
          <dd className="inline font-mono">
            {item.regla_aplicada ?? "—"}
            {item.version_reglas && ` (catálogo ${item.version_reglas})`}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold text-ink">Norma vigilada que toca: </dt>
          <dd className="inline font-mono">
            {item.normas_vigiladas.length > 0 ? item.normas_vigiladas.join(", ") : "ninguna"}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold text-ink">Severidad declarada: </dt>
          {/* Sin calibrar, y dicho donde se pinta: ordena la cola, no es un dato medido. */}
          <dd className="inline">{item.severidad} de 5 · sin calibrar</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-ink">Extractor: </dt>
          <dd className="inline">
            {item.tiene_extraccion
              ? `pasó por esta norma (${item.punteros_corroborados} punteros corroborados, ${item.punteros_sin_corroborar} sin corroborar)`
              : "no pasó — este veredicto lo sostiene el archivo, no el modelo"}
          </dd>
        </div>
      </dl>

      <div className="mt-4 rounded border border-line-2 bg-inset p-3">
        <p className="text-xs font-semibold text-ink">Comprueba antes de decidir</p>
        {item.texto_archivado ? (
          <p className="mt-1 break-all font-mono text-[10.5px] leading-relaxed text-ink-2">
            sha256 {item.texto_archivado.sha256}
            <br />
            archivado el {formatearSelloTiempo(item.texto_archivado.sello_tiempo)} desde{" "}
            <a
              href={item.texto_archivado.url_original}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              la fuente oficial
            </a>
          </p>
        ) : (
          <p className="mt-1 text-[11px] text-ink-3">
            No consta texto archivado para esta norma: los fragmentos no se pueden contrastar.
          </p>
        )}
      </div>

      <fieldset className="mt-4 rounded border border-line-2 bg-inset p-3">
        <legend className="px-1 text-xs font-medium text-ink">
          Signo de la alerta (opcional)
        </legend>
        <p className="text-xs leading-relaxed text-ink-2">
          La regla dice{" "}
          <strong className="font-semibold text-ink">{item.clasificacion}</strong>. Si se abstuvo
          —derogar una ley es lo que hace tanto quien la desmonta como quien la sustituye por otra
          mejor— y al leer el texto lo tienes claro, fíjalo aquí.{" "}
          <strong className="font-semibold text-ink">No sobrescribe lo que dijo la regla</strong>:
          se publica aparte, atribuido a la revisión humana.
        </p>
        <div className="mt-2 flex flex-wrap gap-3">
          {[
            { valor: "", etiqueta: "No cambiarlo" },
            { valor: "avance", etiqueta: "Avance" },
            { valor: "retroceso", etiqueta: "Retroceso" },
            { valor: "neutro", etiqueta: "Neutro" },
          ].map((opcion) => (
            <label key={opcion.valor} className="flex items-center gap-1.5 text-xs text-ink">
              <input
                type="radio"
                name={`signo-${item.id}`}
                value={opcion.valor}
                checked={signo === opcion.valor}
                onChange={() => setSigno(opcion.valor)}
              />
              {opcion.etiqueta}
            </label>
          ))}
        </div>
      </fieldset>

      {/* ADR 0025: DESPUÉS de la evidencia y del diff, y antes de decidir. Es el último
          material de lectura, no el primero — ver la cabecera de `InformeDeApoyo`. */}
      {item.informe && <InformeDeApoyo informe={item.informe} />}

      <label htmlFor={`nota-${item.id}`} className="mt-4 block text-xs font-medium text-ink">
        Nota de revisión (opcional, se guarda con la decisión)
      </label>
      <textarea
        id={`nota-${item.id}`}
        value={nota}
        onChange={(e) => setNota(e.target.value)}
        rows={2}
        maxLength={2000}
        className="mt-1 w-full rounded border border-line-2 bg-bg px-3 py-2 text-sm text-ink"
      />

      {error && (
        <p role="alert" className="mt-2 text-sm text-reg">
          {error}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={enviando !== null}
          onClick={() => resolver("aprobar")}
          className="rounded border border-ink bg-ink px-4 py-2 text-sm font-semibold text-bg disabled:opacity-40"
        >
          {enviando === "aprobar" ? "Emitiendo…" : "Aprobar y emitir la alerta"}
        </button>
        <button
          type="button"
          disabled={enviando !== null}
          onClick={() => resolver("descartar")}
          className="rounded border border-line-2 bg-surface px-4 py-2 text-sm font-medium text-ink-2 hover:border-ink-3 hover:text-ink disabled:opacity-40"
        >
          {enviando === "descartar" ? "Descartando…" : "Descartar (no se emite nada)"}
        </button>
      </div>
      <p className="mt-2 text-[11px] text-ink-3">
        Descartar no borra la detección ni su evidencia: se conservan con la decisión. Ninguna de
        las dos acciones se puede deshacer desde aquí.
      </p>
    </article>
  );
}

export function RevisionPage() {
  // `recarga` es el disparador explícito de las dos peticiones: al resolver un ítem hay que
  // volver a pedir la cola, porque el ítem resuelto ya no pertenece a ella.
  const [recarga, setRecarga] = useState(0);
  const sesion = useRecurso((signal) => comprobarSesionPanel(signal), [recarga]);
  const refrescar = useCallback(() => setRecarga((n) => n + 1), []);

  if (sesion.fase === "cargando") {
    return <main className="mx-auto max-w-[900px] px-7 py-16 text-ink-2">Comprobando sesión…</main>;
  }
  if (sesion.fase === "error") {
    return (
      <main className="mx-auto max-w-[900px] px-7 py-16 text-ink-2">
        {describirError(sesion.error)}
      </main>
    );
  }
  if (!sesion.datos) return <Login onEntrar={refrescar} />;

  return <Cola onRecargar={refrescar} clave={recarga} />;
}

function Cola({ onRecargar, clave }: { onRecargar: () => void; clave: number }) {
  const estado = useRecurso((signal) => listarColaRevision("pendiente", signal), [clave]);

  return (
    <main className="mx-auto max-w-[900px] px-7 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-bold text-ink">Cola de revisión</h1>
          <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-ink-2">
            El sistema propone; aquí decide una persona. Lo que se apruebe se publica como alerta
            de Faro Cuir con su evidencia; lo que se descarte se queda archivado con la decisión.
          </p>
        </div>
        <button
          type="button"
          onClick={async () => {
            await cerrarSesionPanel();
            onRecargar();
          }}
          className="rounded border border-line-2 bg-surface px-3 py-1.5 text-xs text-ink-2 hover:border-ink-3 hover:text-ink"
        >
          Cerrar sesión
        </button>
      </div>

      {estado.fase === "cargando" && <p className="mt-10 text-ink-2">Cargando la cola…</p>}
      {estado.fase === "error" && (
        <p className="mt-10 text-ink-2">{describirError(estado.error)}</p>
      )}

      {estado.fase === "listo" && estado.datos.length === 0 && (
        <p className="mt-10 rounded border border-line bg-surface p-6 text-sm text-ink-2">
          No queda nada pendiente de revisar. Eso significa que el gate está al día, no que no
          haya normas en el sistema: el catálogo de reglas solo produce veredicto sobre lo que
          reconoce, y lo que no reconoce no llega hasta aquí.
        </p>
      )}

      {estado.fase === "listo" && estado.datos.length > 0 && (
        <>
          <p className="mt-6 font-mono text-xs text-ink-3">
            {estado.datos.length} pendiente{estado.datos.length === 1 ? "" : "s"} · ordenadas por
            severidad declarada
          </p>
          <div className="mt-3 space-y-5">
            {estado.datos.map((item) => (
              <Tarjeta key={item.id} item={item} onResuelto={onRecargar} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
