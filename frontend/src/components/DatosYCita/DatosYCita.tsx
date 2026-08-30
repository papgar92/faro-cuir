/**
 * De dónde bajarse los datos y cómo citarlos.
 *
 * ## Por qué esto no es un adorno
 *
 * La tesis entera de este proyecto es «no te fíes, compruébalo». Cada alerta viaja con la cita
 * literal, los offsets, la huella `sha256` y el sello de tiempo **para que un tercero pueda
 * rehacer el trabajo sin nosotros**. Pero hasta ahora la única salida de datos que la interfaz
 * mencionaba era un párrafo sobre Atom, y las anclas del pie no llevaban a ningún sitio: se
 * pedía confianza en la misma pantalla en la que se predicaba lo contrario.
 *
 * Las organizaciones que hacen esto bien —Our World in Data, Civio, ILGA-Europe— ponen la
 * descarga y la cita **en la propia vista**, no en una página de créditos. Eso es lo que se copia
 * aquí; lo que NO se copia son sus descargables «listos para redes» (PNG, JPG), porque una imagen
 * se comparte descontextualizada y sin la huella, que es justo lo que hace verificable a esto.
 *
 * ## La cadena de cita lleva la huella a propósito
 *
 * Citar «Faro Cuir, alerta 12» no sirve de nada dentro de cinco años si nadie puede comprobar
 * qué decía. Con el `sha256` del documento archivado, quien lea la cita puede pedir ese fichero y
 * verificar que es el mismo — aunque la administración lo haya retirado de su web, que es
 * literalmente el daño que este proyecto existe para documentar (6.5).
 */

interface DatosYCitaProps {
  /** Endpoint JSON de esta vista. */
  json: string;
  /** Feed Atom, si esta vista lo tiene. Las alertas sí; los hallazgos todavía no. */
  atom?: string;
  /** Un ejemplo real de esta vista para la cadena de cita. Sin él, no se enseña ejemplo. */
  ejemplo?: {
    identificador: string;
    sha256: string | null;
    fecha: string;
  };
}

export function DatosYCita({ json, atom, ejemplo }: DatosYCitaProps) {
  const anio = new Date().getFullYear();

  return (
    <section className="mt-8 max-w-[900px] rounded border border-line-2 bg-inset p-4">
      <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
        Datos y verificación
      </h2>

      <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-xs">
        <dt className="text-ink-3">JSON</dt>
        <dd className="m-0">
          <a href={json} className="text-link hover:text-ink">
            {json}
          </a>
        </dd>
        {atom && (
          <>
            <dt className="text-ink-3">Atom</dt>
            <dd className="m-0">
              <a href={atom} type="application/atom+xml" className="text-link hover:text-ink">
                {atom}
              </a>
            </dd>
          </>
        )}
      </dl>

      {ejemplo && (
        <>
          <h3 className="mt-3.5 text-xs font-semibold uppercase tracking-wide text-ink-2">
            Cómo citar
          </h3>
          {/* En monoespaciada y seleccionable: está para copiarla, no para leerla. */}
          <p className="mt-1.5 rounded border border-line-2 bg-surface p-2.5 font-mono text-[11px] leading-relaxed text-ink">
            Faro Cuir ({anio}). {ejemplo.identificador}, archivado el {ejemplo.fecha}
            {ejemplo.sha256 && <> · sha256 {ejemplo.sha256.slice(0, 16)}…</>}. Consultado el{" "}
            DD-MM-AAAA.
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-3">
            La huella va en la cita a propósito: es lo que permite comprobar dentro de años que el
            documento citado es el mismo, aunque para entonces ya no esté colgado en la web de
            quien lo publicó.
          </p>
        </>
      )}
    </section>
  );
}
