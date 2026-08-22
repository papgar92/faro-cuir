export function Footer() {
  return (
    <footer className="mt-10 border-t border-line bg-surface">
      <div className="mx-auto flex max-w-[1360px] flex-wrap items-center gap-6 px-7 py-5 text-xs text-ink-3">
        <span>Faro Cuir · proyecto de utilidad pública, sin ánimo de lucro</span>
        <span>Código abierto (AGPL-3.0)</span>
        {/* Enlaces reales. Antes eran `#repo`, `#metodologia` y `#datos`: anclas que no llevaban a
            ningún sitio. En un proyecto cuya tesis entera es «no te fíes, compruébalo», un enlace
            muerto no es una tarea pendiente de maquetación, es un agujero en el argumento. */}
        <a href="https://github.com/papgar92/faro-cuir" rel="noreferrer">
          Repositorio
        </a>
        <a href="https://github.com/papgar92/faro-cuir/tree/main/docs/adr" rel="noreferrer">
          Metodología de clasificación (ADRs)
        </a>
        {/*
          El feed es el único enlace de esta fila que lleva a algo que existe de verdad; los
          otros siguen siendo anclas muertas del diseño. Va aquí porque un canal de difusión que
          nadie encuentra no es un canal, y este es **el canal por defecto** del proyecto
          (ADR 0010): suscribirse con un lector no le dice a nadie quién eres.
        */}
        <a href="/api/alertas.xml" type="application/atom+xml">
          Feed de alertas (Atom)
        </a>
        <a href="/api/alertas">Datos abiertos (API)</a>
        <span className="ml-auto flex items-center gap-2">
          Geometría IGN · CC BY 4.0
          <span className="flex h-1 w-7 overflow-hidden rounded-sm" aria-hidden="true">
            <span className="flex-1 bg-[#5ec8e8]" />
            <span className="flex-1 bg-[#e9a5be]" />
            <span className="flex-1 bg-[#f2efe9]" />
            <span className="flex-1 bg-[#e9a5be]" />
            <span className="flex-1 bg-[#5ec8e8]" />
          </span>
        </span>
      </div>
    </footer>
  );
}
