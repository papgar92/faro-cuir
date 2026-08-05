/**
 * Datos mock que simulan lo que devolvería la API real. Todo en un único archivo
 * a propósito, para poder enseñar la interfaz llena en la demo mientras el
 * backend no está cableado. Transcritos del handoff de diseño
 * (frontend/_design-export/Centinela.dc.html), no inventados de cero.
 *
 * Los metadatos de glifo/etiqueta/color (que sí son tokens de diseño reutilizables,
 * no datos de API) viven aparte en src/lib/classification.ts.
 */

import type { ClasificacionAlerta, EstadoMapa } from "../lib/classification";

export interface RegionSummary {
  code: string;
  name: string;
  state: EstadoMapa;
  alerts: number;
  sources: string;
  title?: string;
  date?: string;
  rango?: string;
  ambito?: string;
}

export const REGIONS: Record<string, RegionSummary> = {
  AN: {
    code: "AN",
    name: "Andalucía",
    state: "retroceso",
    alerts: 3,
    sources: "BOJA · Parlamento",
    title:
      "La instrucción sobre acompañamiento en centros educativos pasa a requerir informe de la inspección previa.",
    date: "28 jul 2026",
    rango: "Instrucción",
    ambito: "Educativo",
  },
  AR: {
    code: "AR",
    name: "Aragón",
    state: "retroceso",
    alerts: 2,
    sources: "BOA · Cortes",
    title: "Se deroga el capítulo III de la ley de identidad y expresión de género.",
    date: "11 jun 2026",
    rango: "Ley",
    ambito: "General",
  },
  AS: {
    code: "AS",
    name: "Asturias",
    state: "estable",
    alerts: 0,
    sources: "BOPA · Junta General",
  },
  IB: {
    code: "IB",
    name: "Illes Balears",
    state: "alerta",
    alerts: 4,
    sources: "BOIB · Parlament",
    title:
      "El acceso de menores al acompañamiento de identidad de género pasa a exigir autorización de ambos tutores e informe psicológico.",
    date: "30 jul 2026",
    rango: "Orden",
    ambito: "Sanitario",
  },
  CB: {
    code: "CB",
    name: "Cantabria",
    state: "estable",
    alerts: 1,
    sources: "BOC · Parlamento",
    title: "Se prorroga sin cambios el protocolo de atención sanitaria específica.",
    date: "19 may 2026",
    rango: "Resolución",
    ambito: "Sanitario",
  },
  CL: {
    code: "CL",
    name: "Castilla y León",
    state: "retroceso",
    alerts: 2,
    sources: "BOCYL · Cortes",
    title: "Se suprime la formación obligatoria del profesorado en diversidad afectivo-sexual.",
    date: "2 jul 2026",
    rango: "Decreto",
    ambito: "Educativo",
  },
  CM: {
    code: "CM",
    name: "Castilla-La Mancha",
    state: "avance",
    alerts: 1,
    sources: "DOCM · Cortes",
    title:
      "Se amplía la cartera de servicios de atención sanitaria a personas trans a las cinco provincias.",
    date: "24 jun 2026",
    rango: "Orden",
    ambito: "Sanitario",
  },
  CT: {
    code: "CT",
    name: "Catalunya",
    state: "avance",
    alerts: 1,
    sources: "DOGC · Parlament",
    title: "El cambio de nombre sentido en la documentación académica pasa a ser automático.",
    date: "21 jul 2026",
    rango: "Decreto",
    ambito: "Documental",
  },
  VC: {
    code: "VC",
    name: "C. Valenciana",
    state: "retroceso",
    alerts: 3,
    sources: "DOGV · Corts",
    title: "Se elimina la obligación de recoger la identidad sentida en los registros escolares.",
    date: "17 jul 2026",
    rango: "Orden",
    ambito: "Educativo",
  },
  EX: {
    code: "EX",
    name: "Extremadura",
    state: "avance",
    alerts: 0,
    sources: "DOE · Asamblea",
    title: "Se crea la unidad de referencia autonómica de atención integral.",
    date: "3 abr 2026",
    rango: "Decreto",
    ambito: "Sanitario",
  },
  GA: {
    code: "GA",
    name: "Galicia",
    state: "estable",
    alerts: 1,
    sources: "DOG · Parlamento",
    title: "Se actualiza sin cambios sustantivos el protocolo laboral antidiscriminación.",
    date: "9 jun 2026",
    rango: "Instrucción",
    ambito: "Laboral",
  },
  MD: {
    code: "MD",
    name: "Madrid",
    state: "alerta",
    alerts: 5,
    sources: "BOCM · Asamblea",
    title: "Se modifica el régimen sancionador por discriminación: se rebajan los importes máximos.",
    date: "1 ago 2026",
    rango: "Ley",
    ambito: "General",
  },
  MC: {
    code: "MC",
    name: "Murcia",
    state: "retroceso",
    alerts: 2,
    sources: "BORM · Asamblea",
    title: "Se retira la mención a la identidad de género del plan de convivencia escolar.",
    date: "14 jul 2026",
    rango: "Orden",
    ambito: "Educativo",
  },
  NC: {
    code: "NC",
    name: "Navarra",
    state: "avance",
    alerts: 0,
    sources: "BON · Parlamento",
    title: "Se reconoce la filiación no biológica sin requisito de matrimonio previo.",
    date: "28 may 2026",
    rango: "Ley foral",
    ambito: "Documental",
  },
  PV: {
    code: "PV",
    name: "Euskadi",
    state: "avance",
    alerts: 1,
    sources: "BOPV · Parlamento",
    title:
      "Se incorpora la identidad de género como causa expresa en el protocolo de acoso laboral.",
    date: "23 jul 2026",
    rango: "Decreto",
    ambito: "Laboral",
  },
  RI: {
    code: "RI",
    name: "La Rioja",
    state: "estable",
    alerts: 0,
    sources: "BOR · Parlamento",
  },
  CN: {
    code: "CN",
    name: "Canarias",
    state: "avance",
    alerts: 2,
    sources: "BOC · Parlamento",
    title: "Se garantiza la atención sanitaria específica en las islas no capitalinas.",
    date: "26 jul 2026",
    rango: "Ley",
    ambito: "Sanitario",
  },
};

export interface AlertaFeedItem {
  id: string;
  com: string;
  ambito: string;
  tipo: ClasificacionAlerta;
  title: string;
  date: string;
  rango: string;
  ref: string;
}

export const FEED: AlertaFeedItem[] = [
  {
    id: "bocm-182-2026",
    com: "Madrid",
    ambito: "General",
    tipo: "retroceso",
    title: "Se rebajan los importes máximos de las sanciones por discriminación por identidad de género.",
    date: "1 ago 2026",
    rango: "Ley",
    ref: "BOCM 182/2026",
  },
  {
    id: "boib-112-2026",
    com: "Illes Balears",
    ambito: "Sanitario",
    tipo: "retroceso",
    title:
      "El acceso de menores al servicio de acompañamiento pasa a exigir autorización de ambos tutores e informe psicológico previo.",
    date: "30 jul 2026",
    rango: "Orden",
    ref: "BOIB 112/2026",
  },
  {
    id: "boja-143-2026",
    com: "Andalucía",
    ambito: "Educativo",
    tipo: "retroceso",
    title: "La instrucción sobre acompañamiento en centros educativos pasa a requerir informe previo de la inspección.",
    date: "28 jul 2026",
    rango: "Instrucción",
    ref: "BOJA 143/2026",
  },
  {
    id: "boc-89-2026",
    com: "Canarias",
    ambito: "Sanitario",
    tipo: "avance",
    title: "Se garantiza la atención sanitaria específica para personas trans en las islas no capitalinas.",
    date: "26 jul 2026",
    rango: "Ley",
    ref: "BOC 89/2026",
  },
  {
    id: "bopv-138-2026",
    com: "Euskadi",
    ambito: "Laboral",
    tipo: "avance",
    title:
      "La identidad de género se incorpora como causa expresa en el protocolo de acoso laboral de la administración.",
    date: "23 jul 2026",
    rango: "Decreto",
    ref: "BOPV 138/2026",
  },
  {
    id: "dogc-9312-2026",
    com: "Catalunya",
    ambito: "Documental",
    tipo: "avance",
    title: "El cambio de nombre sentido en la documentación académica pasa a tramitarse de forma automática.",
    date: "21 jul 2026",
    rango: "Decreto",
    ref: "DOGC 9312/2026",
  },
  {
    id: "boe-171-2026",
    com: "Estado (BOE)",
    ambito: "Documental",
    tipo: "neutro",
    title: "Se corrige un error material en la disposición transitoria segunda del reglamento de registro civil.",
    date: "18 jul 2026",
    rango: "Corrección de errores",
    ref: "BOE 171/2026",
  },
  {
    id: "dogv-9841-2026",
    com: "C. Valenciana",
    ambito: "Educativo",
    tipo: "retroceso",
    title: "Se elimina la obligación de recoger la identidad sentida del alumnado en los registros escolares.",
    date: "17 jul 2026",
    rango: "Orden",
    ref: "DOGV 9841/2026",
  },
  {
    id: "borm-159-2026",
    com: "Murcia",
    ambito: "Educativo",
    tipo: "retroceso",
    title: "Se retira la mención a la identidad de género del plan autonómico de convivencia escolar.",
    date: "14 jul 2026",
    rango: "Orden",
    ref: "BORM 159/2026",
  },
  {
    id: "bocyl-124-2026",
    com: "Castilla y León",
    ambito: "Educativo",
    tipo: "retroceso",
    title: "Se suprime el carácter obligatorio de la formación del profesorado en diversidad afectivo-sexual.",
    date: "2 jul 2026",
    rango: "Decreto",
    ref: "BOCYL 124/2026",
  },
  {
    id: "bor-74-2026",
    com: "La Rioja",
    ambito: "General",
    tipo: "neutro",
    title: "Se publica la composición del consejo asesor de diversidad sin cambios en sus competencias.",
    date: "27 jun 2026",
    rango: "Resolución",
    ref: "BOR 74/2026",
  },
];

export type DiffSegmentTipo = "same" | "del" | "ins";

export interface DiffSegment {
  text: string;
  tipo: DiffSegmentTipo;
}

export interface FichaDetail {
  id: string;
  ref: string;
  clasificacion: ClasificacionAlerta;
  comunidad: string;
  ambito: string;
  titulo: string;
  resumen: string;
  diff: {
    articulo: string;
    antes: { label: string; fuente: string; segmentos: DiffSegment[] };
    despues: { label: string; fuente: string; segmentos: DiffSegment[] };
    stats: {
      fragmentosModificados: number;
      palabrasAnadidas: number;
      palabrasEliminadas: number;
      nota: string;
    };
  };
  metadatos: {
    tituloOficial: string;
    organoEmisor: string;
    rango: string;
    rangoDetalle: string;
    publicacion: string;
    entradaVigor: string;
    fuenteLabel: string;
    fuenteNota: string;
  };
  integridad: {
    hashSha256: string;
    selloTiempo: string;
    autoridadTsa: string;
    captura: string;
    ultimaComprobacion: string;
  };
  historial: Array<{
    fecha: string;
    norma: string;
    clasificacion: ClasificacionAlerta | "original";
  }>;
}

/**
 * Única ficha detallada del mock (Illes Balears / BOIB 112/2026), tal como estaba
 * en el diseño — allí tampoco era data-driven desde el feed. Cuando se cablee la
 * API real, cada item de FEED podrá resolver a su propia FichaDetail por `id`.
 */
export const fichaDetail: FichaDetail = {
  id: "boib-112-2026",
  ref: "BOIB 112/2026",
  clasificacion: "retroceso",
  comunidad: "Illes Balears",
  ambito: "Sanitario",
  titulo:
    "El acceso de menores al servicio de acompañamiento a la identidad de género pasa a exigir autorización de ambos tutores e informe psicológico previo",
  resumen:
    "La Orden 112/2026 modifica el artículo 7.2 de la Orden 45/2023. Se añaden dos requisitos previos de acceso y se limita la duración del acompañamiento, antes indefinida hasta la mayoría de edad.",
  diff: {
    articulo: "artículo 7.2",
    antes: {
      label: "Antes",
      fuente: "Orden 45/2023 · 14 mar 2023",
      segmentos: [
        {
          text: "Las personas menores de dieciséis años podrán acceder al servicio de acompañamiento a la identidad de género ",
          tipo: "same",
        },
        { text: "con el consentimiento de una de las personas", tipo: "del" },
        { text: " que ejerzan la tutela legal. El acompañamiento se prestará de forma continuada ", tipo: "same" },
        { text: "hasta la mayoría de edad", tipo: "del" },
        { text: ".", tipo: "same" },
      ],
    },
    despues: {
      label: "Después",
      fuente: "Orden 112/2026 · 30 jul 2026",
      segmentos: [
        {
          text: "Las personas menores de dieciséis años podrán acceder al servicio de acompañamiento a la identidad de género ",
          tipo: "same",
        },
        { text: "previa autorización expresa de ambas personas", tipo: "ins" },
        { text: " que ejerzan la tutela legal ", tipo: "same" },
        { text: "y previo informe psicológico favorable", tipo: "ins" },
        { text: ". El acompañamiento se prestará ", tipo: "same" },
        { text: "durante un máximo de doce meses, prorrogable mediante resolución motivada", tipo: "ins" },
        { text: ".", tipo: "same" },
      ],
    },
    stats: {
      fragmentosModificados: 3,
      palabrasAnadidas: 27,
      palabrasEliminadas: 11,
      nota: "alineación automática, revisada por una persona",
    },
  },
  metadatos: {
    tituloOficial:
      "Orden 112/2026, de 30 de julio, por la que se modifica la Orden 45/2023 reguladora del servicio de acompañamiento a la identidad de género",
    organoEmisor: "Conselleria de Salut · Govern de les Illes Balears",
    rango: "Orden",
    rangoDetalle: "desarrollo reglamentario",
    publicacion: "30 jul 2026 · BOIB núm. 98 · pág. 41.207",
    entradaVigor: "1 sep 2026",
    fuenteLabel: "Texto íntegro en el BOIB (PDF)",
    fuenteNota: "copia archivada por Centinela",
  },
  integridad: {
    hashSha256: "9f2c41e8b7d05a6c3e19fb84a7c2d0516be93f7ac48d21b0e6f5c9a3d7481e2b",
    selloTiempo: "2026-07-30 06:12:04Z",
    autoridadTsa: "freetsa.org (RFC 3161)",
    captura: "boib.caib.es · 06:11:58Z",
    ultimaComprobacion: "hoy 07:40",
  },
  historial: [
    { fecha: "30 jul 2026", norma: "Orden 112/2026", clasificacion: "retroceso" },
    { fecha: "14 mar 2023", norma: "Orden 45/2023", clasificacion: "avance" },
    { fecha: "2 feb 2019", norma: "Ley 8/2019", clasificacion: "original" },
  ],
};
