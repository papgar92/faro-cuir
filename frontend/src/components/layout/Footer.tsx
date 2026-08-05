export function Footer() {
  return (
    <footer className="mt-10 border-t border-line bg-surface">
      <div className="mx-auto flex max-w-[1360px] flex-wrap items-center gap-6 px-7 py-5 text-xs text-ink-3">
        <span>Faro Cuir · proyecto de utilidad pública, sin ánimo de lucro</span>
        <span>Código abierto (AGPL-3.0)</span>
        <a href="#repo">Repositorio</a>
        <a href="#metodologia">Metodología de clasificación</a>
        <a href="#datos">Datos abiertos (API)</a>
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
