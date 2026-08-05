import { CLASIFICACION_ALERTA_META, type ClasificacionAlerta } from "../../lib/classification";

interface AlertFiltersProps {
  comunidades: string[];
  ambitos: string[];
  comunidad: string;
  ambito: string;
  tipo: string;
  onComunidadChange: (value: string) => void;
  onAmbitoChange: (value: string) => void;
  onTipoChange: (value: string) => void;
  onClear: () => void;
}

const selectClasses = "min-w-[150px] rounded border border-line-2 bg-surface px-2.5 py-2 text-sm text-ink";
const labelClasses = "flex flex-col gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-3";

const TIPOS = Object.keys(CLASIFICACION_ALERTA_META) as ClasificacionAlerta[];

/** Filtros del feed de Alertas: comunidad, ámbito y tipo de cambio. */
export function AlertFilters({
  comunidades,
  ambitos,
  comunidad,
  ambito,
  tipo,
  onComunidadChange,
  onAmbitoChange,
  onTipoChange,
  onClear,
}: AlertFiltersProps) {
  return (
    <div className="mt-5 flex flex-wrap items-end gap-3.5 rounded border border-line bg-surface p-3.5">
      <label className={labelClasses}>
        Comunidad
        <select
          className={`${selectClasses} min-w-[190px] normal-case tracking-normal`}
          value={comunidad}
          onChange={(event) => onComunidadChange(event.target.value)}
        >
          <option value="todas">Todas las comunidades</option>
          {comunidades.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      <label className={labelClasses}>
        Ámbito
        <select
          className={`${selectClasses} normal-case tracking-normal`}
          value={ambito}
          onChange={(event) => onAmbitoChange(event.target.value)}
        >
          <option value="todos">Todos los ámbitos</option>
          {ambitos.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </label>

      <label className={labelClasses}>
        Tipo de cambio
        <select
          className={`${selectClasses} normal-case tracking-normal`}
          value={tipo}
          onChange={(event) => onTipoChange(event.target.value)}
        >
          <option value="todos">Todos</option>
          {TIPOS.map((key) => (
            <option key={key} value={key}>
              {CLASIFICACION_ALERTA_META[key].glyph} {CLASIFICACION_ALERTA_META[key].label}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={onClear}
        className="ml-auto whitespace-nowrap rounded border border-line-2 px-3.5 py-2 text-sm text-ink-2 hover:border-ink-3 hover:text-ink"
      >
        Limpiar filtros
      </button>
    </div>
  );
}
