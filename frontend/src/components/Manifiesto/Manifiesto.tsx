/**
 * Texto reivindicativo de portada. Primer punto del backlog de CLAUDE.md sección 12,
 * pedido explícitamente como contenido y no como maquetación.
 *
 * El encargo tiene una tensión que merece la pena resolver aquí y no esquivar: el
 * proyecto **es** reivindicativo —existe porque hay derechos que se están recortando—
 * y a la vez el sistema **no emite juicios** (reglas de oro 2 y 3). Se resuelve
 * separando las dos cosas de forma explícita: la reivindicación está en por qué
 * existe la herramienta; la neutralidad, en lo que la herramienta afirma. Por eso el
 * bloque "Lo que no hace" tiene el mismo peso visual que el resto, en vez de ir en
 * letra pequeña al pie: renunciar a opinar es parte del argumento, no una advertencia
 * legal.
 *
 * Ninguna cifra en este texto. No hay ni un dato del pipeline todavía, y un titular
 * con un número inventado es exactamente lo que el aviso de datos de demostración
 * intenta evitar.
 */
export function Manifiesto() {
  return (
    <section
      aria-labelledby="manifiesto-titulo"
      className="mb-7 overflow-hidden rounded border border-line bg-surface"
    >
      <div className="grid grid-cols-1 gap-x-9 gap-y-6 px-7 py-7 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
            Observatorio de derechos LGTBI+ · vigilancia normativa
          </p>
          <h1
            id="manifiesto-titulo"
            className="mt-2.5 max-w-[22ch] font-serif text-[2.1rem] font-bold leading-[1.14] tracking-tight text-ink"
          >
            Un derecho no se pierde el día que sale en los periódicos.
          </h1>
          <p className="mt-4 max-w-[58ch] text-[15px] leading-relaxed text-ink-2">
            Se pierde meses antes, en una instrucción de dos páginas publicada un martes de agosto
            en el boletín de una comunidad autónoma. No la firma nadie con nombre conocido y no
            lleva titular. Cambia una palabra —un <em>podrá</em> donde decía <em>deberá</em>, un
            informe que antes no hacía falta— y desde esa página hay personas que dejan de tener lo
            que tenían.
          </p>
          <p className="mt-3.5 max-w-[58ch] text-[15px] leading-relaxed text-ink-2">
            <strong className="font-semibold text-ink">Faro Cuir</strong> lee cada día los boletines
            oficiales de las comunidades autónomas y el BOE buscando exactamente esos cambios, con
            atención especial a los que afectan a las personas trans. Archiva cada documento con su
            huella digital y su fecha, para que lo que se publicó no dependa de que siga colgado en
            la web de quien lo publicó.
          </p>
        </div>

        <div className="flex flex-col gap-4 lg:border-l lg:border-line lg:pl-9">
          <div>
            <h2 className="font-serif text-base font-bold text-ink">Lo que hace</h2>
            <p className="mt-1.5 max-w-[46ch] text-sm leading-relaxed text-ink-2">
              Enseña la diferencia entre lo que decía un artículo y lo que dice ahora, con enlace a
              la fuente oficial para que cualquiera lo compruebe por su cuenta. Ese es todo el valor
              que pretende tener: que no haya que fiarse de nosotros.
            </p>
          </div>
          <div>
            <h2 className="font-serif text-base font-bold text-ink">Lo que no hace</h2>
            <p className="mt-1.5 max-w-[46ch] text-sm leading-relaxed text-ink-2">
              No opina. La clasificación entre avance y retroceso se deriva del propio texto con
              reglas escritas y auditables, nunca del criterio de un modelo de lenguaje. Y ninguna
              alerta se publica sin que una persona la haya revisado antes.
            </p>
          </div>
          <div>
            <h2 className="font-serif text-base font-bold text-ink">Para quién</h2>
            <p className="mt-1.5 max-w-[46ch] text-sm leading-relaxed text-ink-2">
              Para quien necesita enterarse a tiempo: personas trans y sus familias, asociaciones,
              servicios jurídicos, periodistas. Es gratuito, no lleva publicidad y no hace falta
              dejar ningún dato personal para consultarlo.
            </p>
          </div>
        </div>
      </div>

      <p className="border-t border-line bg-inset px-7 py-3 font-serif text-[15px] italic text-ink-2">
        Vigilar lo que se publica no es desconfianza: es la forma más barata de que un derecho no se
        pierda en silencio.
      </p>
    </section>
  );
}
