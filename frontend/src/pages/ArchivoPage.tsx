import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { DocumentoDetalleApi, EstadoPrefiltro, NormaApi } from "../api/client";
import { entraEnLaCola, listarDocumentos, obtenerDocumento } from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { BandaPrefiltro } from "../components/BandaPrefiltro/BandaPrefiltro";
import { FichaNorma } from "../components/FichaNorma/FichaNorma";
import { FilaNormaIndice } from "../components/FilaNormaIndice/FilaNormaIndice";
import { SelectorDocumento } from "../components/SelectorDocumento/SelectorDocumento";
import { acortarHash, formatearFecha, formatearSelloTiempo } from "../lib/formato";
import { escribirUrl, leerUrl } from "../lib/navigation";

/**
 * Archivo: el índice de lo ingerido y la ficha de la norma abierta, en una sola pantalla.
 *
 * ## Qué cambió el 2026-09-05 y por qué
 *
 * Antes eran dos pestañas —«Archivo» y «Ficha de norma»— y una lista plana cortada en 60. Los
 * tres problemas, medidos:
 *
 * 1. **La lista escondía justo lo que importa.** No se ordenaba nunca: salía en el orden de
 *    secciones del sumario oficial, y el corte era posicional. Sobre cuatro boletines del BOE,
 *    las normas que el prefiltro NO descartó caían en las posiciones 169/169, 130/130,
 *    207-210/210 y 112/112. **Cuatro de cuatro fuera de la pantalla.** El razonamiento que lo
 *    justificaba —«el tope obliga a usar el buscador, que es la forma real de encontrar algo»—
 *    se da la vuelta solo: para buscar hay que saber qué buscas, y esta es la pantalla de
 *    descubrimiento.
 * 2. **Las dos pestañas ya eran una sola pantalla y el código lo decía**: la Ficha volvía a
 *    pedir el mismo documento de 160 KB que el Archivo tenía en memoria, y «Ficha de norma» en
 *    el menú, pulsada en frío, solo ofrecía un botón para ir al Archivo.
 * 3. **Una norma no se podía enlazar.** Ahora la selección viaja en la URL (`?pantalla=archivo&
 *    doc=…&norma=…`), que para un archivo que se ofrece como verificable es media función.
 *
 * ## Lo que NO cambia, porque es lo que sostiene la 6.5
 *
 * Las bandas agrupan por `prefiltro_estado`, y eso **no es un juicio sobre las normas**: es
 * publicar la decisión que el sistema ya tomó y que 7.2 define como «qué entra en el LLM y en
 * qué orden». Todas las bandas pesan lo mismo, todas enseñan la huella de sus normas, y las
 * descartadas nacen plegadas **por volumen y no por peso** — siguen contadas, siguen a un clic
 * y siguen con su sha256 a la vista.
 */

/** Cuántos boletines trae cada página del selector. Es el tope duro del backend. */
const DOCUMENTOS_POR_PAGINA = 100;

/**
 * Tope por banda, no por lista.
 *
 * Aquí sí es honesto: una banda es un cajón que declara su contenido («207 descartadas») antes
 * de recortarlo, así que el recorte no puede esconder una categoría entera como hacía el corte
 * posicional de la lista plana.
 */
const NORMAS_POR_BANDA = 60;

/** Quita acentos y baja a minúsculas para que "fisicas" encuentre "Físicas". */
function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function Aviso({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-line-2 bg-surface p-6 text-center text-sm text-ink-2">
      {children}
    </div>
  );
}

function CabeceraDocumento({ documento }: { documento: DocumentoDetalleApi }) {
  return (
    <div className="mt-4 rounded border border-line bg-inset px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-mono text-sm font-semibold text-ink">
          {documento.identificador_oficial}
        </h2>
        <span className="text-xs text-ink-2">{formatearFecha(documento.fecha_publicacion)}</span>
        <span className="text-xs text-ink-3">
          {documento.normas.length} {documento.normas.length === 1 ? "norma" : "normas"}
        </span>
        <span className="ml-auto font-mono text-[11px] text-ink-3">
          estado: {documento.estado_pipeline}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-[11.5px] sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="text-ink-3">sha256</dt>
          <dd className="m-0 truncate font-mono text-ink-2" title={documento.sha256}>
            {acortarHash(documento.sha256)}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-ink-3">sello</dt>
          <dd className="m-0 font-mono text-ink-2">
            {formatearSelloTiempo(documento.sello_tiempo)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * Las bandas del índice, **en este orden y con este estado inicial**.
 *
 * `ilegible` va primero y se dibuja siempre, aunque sean cero, porque 7.2 lo dice con estas
 * palabras: «el embudo lo cuenta aparte y **no se omite aunque sea cero**». La pantalla anterior
 * lo pintaba bajo `ilegibles > 0`, así que en la práctica desaparecía casi siempre — hoy hay 4
 * ilegibles en 83.344 normas. Y es el peldaño que más importa ver, porque **no habla de la norma
 * sino de nosotros**: es cobertura que este archivo aparenta y no tiene.
 */
const BANDAS: Array<{
  clave: string;
  glifo: string;
  titulo: string;
  explicacion: string;
  abierta: boolean;
  incluye: (estado: EstadoPrefiltro) => boolean;
}> = [
  {
    clave: "ilegible",
    glifo: "⊘",
    titulo: "Sin poder leer",
    explicacion:
      "Su texto está archivado y el pipeline no puede parsearlo (ADR 0020). No hay vigilancia " +
      "sobre ellas. Se cuenta siempre, también cuando es cero.",
    abierta: true,
    incluye: (estado) => estado === "ilegible",
  },
  {
    clave: "cola",
    glifo: "◉",
    titulo: "Entran en la cola",
    explicacion:
      "El prefiltro no las descartó tras leer su texto íntegro, así que pasan al extractor y al " +
      "catálogo de reglas. Incluye las de indicio débil (sospecha).",
    abierta: true,
    incluye: entraEnLaCola,
  },
  {
    clave: "pendiente",
    glifo: "◌",
    titulo: "Sin evaluar todavía",
    explicacion:
      "Aún no tienen su texto íntegro archivado, o no se han evaluado. No es un descarte: " +
      "vuelven solas en la pasada siguiente.",
    abierta: true,
    incluye: (estado) => estado === "pendiente",
  },
  {
    clave: "descartada",
    glifo: "○",
    titulo: "Descartadas",
    explicacion:
      "Descartadas después de leer su texto completo, nunca por el título. Se pliegan por " +
      "volumen, no por peso: son archivo igual que las demás y conservan su huella.",
    abierta: false,
    incluye: (estado) => estado === "descartada",
  },
];

export function ArchivoPage() {
  const inicial = useState(() => leerUrl(window.location.search))[0];

  const [pagina, setPagina] = useState(0);
  const [documentoElegido, setDocumentoElegido] = useState<number | null>(inicial.doc ?? null);
  const [normaElegida, setNormaElegida] = useState<number | null>(inicial.norma ?? null);
  const [busqueda, setBusqueda] = useState("");

  const lista = useRecurso(
    (signal) =>
      listarDocumentos(
        { limite: DOCUMENTOS_POR_PAGINA, desplazamiento: pagina * DOCUMENTOS_POR_PAGINA },
        signal,
      ),
    [pagina],
  );

  // Sin elección explícita se abre el más reciente: la API ya los devuelve ordenados por fecha
  // descendente, y obligar a un clic previo para ver el boletín de hoy sería ruido.
  const documentoId =
    documentoElegido ?? (lista.fase === "listo" ? (lista.datos[0]?.id ?? null) : null);

  const detalle = useRecurso<DocumentoDetalleApi | null>(
    (signal) =>
      documentoId === null ? Promise.resolve(null) : obtenerDocumento(documentoId, signal),
    [documentoId],
  );

  const documento = detalle.fase === "listo" ? detalle.datos : null;
  const norma = documento?.normas.find((item) => item.id === normaElegida) ?? null;

  // La URL sigue a la selección, para que una norma se pueda enlazar. `replaceState` y no
  // `pushState` por lo mismo que el resto del módulo: elegir norma es navegar dentro de una
  // pantalla, no cambiar de pantalla, y llenar el historial dejaría «atrás» inservible.
  useEffect(() => {
    if (documentoId === null) return;
    const actual = leerUrl(window.location.search);
    escribirUrl({
      screen: "archivo",
      ccaa: actual.ccaa,
      doc: documentoId,
      norma: norma?.id,
    });
  }, [documentoId, norma?.id]);

  const coincidencias = useMemo(() => {
    if (!documento) return [];
    const aguja = normalizar(busqueda.trim());
    if (!aguja) return documento.normas;
    return documento.normas.filter(
      (item) =>
        normalizar(item.titulo).includes(aguja) ||
        normalizar(item.identificador_oficial).includes(aguja) ||
        normalizar(item.organo_emisor ?? "").includes(aguja),
    );
  }, [documento, busqueda]);

  // El embudo del prefiltro, agrupado por banda. Se calcula en el cliente porque la API ya
  // devuelve todas las normas del documento: pedir un recuento aparte sería una petición extra
  // para contar lo que ya tenemos delante. Es el mismo embudo de antes; lo que cambia es que
  // ahora **es la estructura de la pantalla** en vez de una línea de texto que lo describía.
  const porBanda = useMemo(() => {
    const mapa = new Map<string, NormaApi[]>();
    for (const banda of BANDAS) {
      mapa.set(
        banda.clave,
        coincidencias.filter((item) => banda.incluye(item.prefiltro_estado)),
      );
    }
    return mapa;
  }, [coincidencias]);

  const elegirDocumento = (id: number) => {
    setDocumentoElegido(id);
    // La norma abierta pertenece al documento anterior: mantenerla dejaría la ficha enseñando
    // una norma que ya no está en el índice de la izquierda.
    setNormaElegida(null);
    setBusqueda("");
  };

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="max-w-[900px]">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">
            Archivo de documentos ingeridos
          </h1>
          <span className="rounded border border-adv bg-adv-bg px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-adv">
            Datos reales
          </span>
        </div>
        <p className="mt-2 max-w-[70ch] text-sm text-ink-2">
          Todo lo que Faro Cuir ha descargado y archivado, tal cual salió de la fuente oficial. De
          cada documento se guarda su huella SHA-256 y el momento de la captura, para que
          cualquiera pueda comprobar que lo archivado es lo que se publicó. El índice está
          agrupado por lo que decidió el prefiltro, no por el orden del boletín.
        </p>
      </div>

      <div className="mt-5">
        {lista.fase === "cargando" && <Aviso>Cargando el archivo…</Aviso>}

        {lista.fase === "error" && (
          <Aviso>
            <p className="m-0 font-semibold text-ink">No se ha podido cargar el archivo</p>
            <p className="mt-1.5">{describirError(lista.error)}</p>
          </Aviso>
        )}

        {lista.fase === "listo" && lista.datos.length === 0 && (
          <Aviso>
            <p className="m-0 font-semibold text-ink">Todavía no hay nada ingerido</p>
            <p className="mt-1.5">
              Lanza el worker de ingesta para poblar el archivo:{" "}
              <code className="font-mono text-xs">
                python -m worker.run --fuente boe --fecha 2024-12-19
              </code>
            </p>
          </Aviso>
        )}

        {lista.fase === "listo" && lista.datos.length > 0 && (
          <SelectorDocumento
            documentos={lista.datos}
            documentoId={documentoId}
            pagina={pagina}
            hayPaginaSiguiente={lista.datos.length === DOCUMENTOS_POR_PAGINA}
            onElegir={elegirDocumento}
            onPagina={(siguiente) => {
              setPagina(siguiente);
              setDocumentoElegido(null);
              setNormaElegida(null);
            }}
          />
        )}

        {detalle.fase === "error" && (
          <div className="mt-4">
            <Aviso>
              <p className="m-0 font-semibold text-ink">No se ha podido cargar el documento</p>
              <p className="mt-1.5">{describirError(detalle.error)}</p>
            </Aviso>
          </div>
        )}

        {documento && (
          <>
            <CabeceraDocumento documento={documento} />

            <div className="mt-4 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              <section
                aria-label="Índice de normas"
                className="rounded border border-line bg-surface"
              >
                <div className="border-b border-line px-4 py-3">
                  <label htmlFor="buscar-norma" className="block text-xs text-ink-3">
                    Buscar por título, identificador u órgano emisor
                  </label>
                  <input
                    id="buscar-norma"
                    type="search"
                    value={busqueda}
                    onChange={(evento) => setBusqueda(evento.target.value)}
                    placeholder={`Buscar entre ${documento.normas.length} normas…`}
                    className="mt-1.5 w-full rounded border border-line-2 bg-inset px-3 py-2 text-sm text-ink placeholder:text-ink-3"
                  />
                  <p aria-live="polite" className="m-0 mt-2 font-mono text-[11px] text-ink-3">
                    {coincidencias.length}{" "}
                    {coincidencias.length === 1 ? "norma coincide" : "normas coinciden"} de{" "}
                    {documento.normas.length}
                  </p>
                </div>

                {coincidencias.length === 0 ? (
                  <p className="m-0 px-4 py-8 text-center text-sm text-ink-2">
                    Ninguna norma de este documento coincide con la búsqueda.
                  </p>
                ) : (
                  BANDAS.map((banda) => {
                    const normas = porBanda.get(banda.clave) ?? [];
                    return (
                      <BandaPrefiltro
                        key={banda.clave}
                        glifo={banda.glifo}
                        titulo={banda.titulo}
                        explicacion={banda.explicacion}
                        recuento={normas.length}
                        // Con una búsqueda activa se abren todas: si has escrito algo, no
                        // quieres que el resultado se quede escondido dentro de un cajón.
                        abierta={banda.abierta || busqueda.trim().length > 0}
                      >
                        {normas.slice(0, NORMAS_POR_BANDA).map((item) => (
                          <FilaNormaIndice
                            key={item.id}
                            norma={item}
                            seleccionada={item.id === norma?.id}
                            onAbrir={() => setNormaElegida(item.id)}
                          />
                        ))}
                        {normas.length > NORMAS_POR_BANDA && (
                          <li className="px-4 py-2.5 font-mono text-[11px] text-ink-3">
                            … y {normas.length - NORMAS_POR_BANDA} más. Usa el buscador para
                            llegar a ellas.
                          </li>
                        )}
                      </BandaPrefiltro>
                    );
                  })
                )}
              </section>

              <section aria-label="Ficha de la norma" className="min-w-0">
                {norma ? (
                  <FichaNorma documento={documento} norma={norma} />
                ) : (
                  <div className="rounded border border-dashed border-line-2 bg-surface p-8 text-center">
                    <p className="m-0 font-semibold text-ink">Elige una norma del índice</p>
                    <p className="mx-auto mt-2 max-w-[52ch] text-sm text-ink-2">
                      Aquí aparecerán sus metadatos, qué decidió el prefiltro y con qué términos,
                      y la cadena de verificación de su texto archivado.
                    </p>
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
