import type { FichaDetail } from "../../api/mocks";
import { CLASIFICACION_ALERTA_META, COLOR_CLASSES } from "../../lib/classification";

interface ArticleHistoryProps {
  articulo: string;
  historial: FichaDetail["historial"];
}

/** Historial de versiones del artículo afectado. */
export function ArticleHistory({ articulo, historial }: ArticleHistoryProps) {
  return (
    <section className="rounded border border-line bg-surface p-4">
      <h2 className="text-[13.5px] font-semibold text-ink">Historial del {articulo}</h2>
      <ol className="m-0 mt-3 flex list-none flex-col p-0">
        {historial.map((item, index) => {
          const isLast = index === historial.length - 1;
          const meta = item.clasificacion === "original" ? null : CLASIFICACION_ALERTA_META[item.clasificacion];

          return (
            <li
              key={`${item.fecha}-${item.norma}`}
              className={`ml-1 flex gap-2.5 border-l pl-3.5 ${
                isLast ? "border-transparent" : "border-line pb-3.5"
              }`}
            >
              <div>
                <div className="font-mono text-xs text-ink-3">{item.fecha}</div>
                <div className="mt-0.5 text-sm text-ink">
                  {item.norma}{" "}
                  {meta ? (
                    <span className={`font-semibold ${COLOR_CLASSES[meta.color].text}`}>
                      {meta.glyph} {meta.label.toLowerCase()}
                    </span>
                  ) : (
                    <span className="font-semibold text-ink-3">● texto original</span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
