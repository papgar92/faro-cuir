import { useCallback, useRef, useState } from "react";
import { MAPA_VIEWBOX } from "./ccaa-paths";

export interface Vista {
  x: number;
  y: number;
  ancho: number;
  alto: number;
}

const COMPLETA: Vista = { x: 0, y: 0, ancho: MAPA_VIEWBOX.ancho, alto: MAPA_VIEWBOX.alto };

/** Tope de ampliación. A ×12 una provincia pequeña llena la pantalla; más allá solo
 *  se ven los vértices de la simplificación, que no es detalle sino ruido. */
const ZOOM_MAX = 12;
const PASO = 1.6;

function encajar(vista: Vista): Vista {
  // El ancho manda: la relación de aspecto se conserva siempre, así que basta con
  // limitar uno y derivar el otro.
  const ancho = Math.min(Math.max(vista.ancho, COMPLETA.ancho / ZOOM_MAX), COMPLETA.ancho);
  const alto = (ancho * COMPLETA.alto) / COMPLETA.ancho;
  return {
    ancho,
    alto,
    // Sin este recorte se puede arrastrar el mapa fuera del lienzo y quedarse
    // mirando un rectángulo vacío sin saber cómo volver.
    x: Math.min(Math.max(vista.x, 0), COMPLETA.ancho - ancho),
    y: Math.min(Math.max(vista.y, 0), COMPLETA.alto - alto),
  };
}

/**
 * Zoom y desplazamiento sobre el `viewBox` del SVG.
 *
 * Sobre el `viewBox` y no con `transform: scale()` porque así el trazo se puede
 * mantener a grosor constante con `vector-effect` y, sobre todo, porque las áreas
 * sensibles al ratón y al foco siguen siendo los propios `<path>`: un `scale` de
 * CSS agranda también el objetivo de click, pero deja la geometría de foco donde
 * estaba en navegadores que no recalculan.
 *
 * **No se captura la rueda del ratón** a propósito. Un mapa embebido en una página
 * que se desplaza y que se traga el scroll es una trampa conocida de usabilidad;
 * aquí se amplía con los botones, con doble clic, arrastrando o con el teclado.
 */
export function useZoomMapa() {
  const [vista, setVista] = useState<Vista>(COMPLETA);
  const arrastre = useRef<{ id: number; x: number; y: number } | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  // Un arrastre que termina encima de una comunidad dispara igualmente su `click`.
  // Sin esta marca, desplazar el mapa selecciona la comunidad donde sueltas.
  const huboArrastre = useRef(false);

  const factor = COMPLETA.ancho / vista.ancho;

  /** Amplía o reduce manteniendo quieto el punto (fx, fy) en coordenadas del lienzo. */
  const ampliar = useCallback((paso: number, fx?: number, fy?: number) => {
    setVista((actual) => {
      const cx = fx ?? actual.x + actual.ancho / 2;
      const cy = fy ?? actual.y + actual.alto / 2;
      const ancho = actual.ancho / paso;
      const alto = (ancho * COMPLETA.alto) / COMPLETA.ancho;
      // Proporción del punto dentro de la vista actual, que debe conservarse.
      const px = (cx - actual.x) / actual.ancho;
      const py = (cy - actual.y) / actual.alto;
      return encajar({ x: cx - px * ancho, y: cy - py * alto, ancho, alto });
    });
  }, []);

  const acercar = useCallback(() => ampliar(PASO), [ampliar]);
  const alejar = useCallback(() => ampliar(1 / PASO), [ampliar]);
  const verTodo = useCallback(() => setVista(COMPLETA), []);

  const desplazar = useCallback((dx: number, dy: number) => {
    setVista((actual) => encajar({ ...actual, x: actual.x + dx, y: actual.y + dy }));
  }, []);

  /** Convierte coordenadas de pantalla a coordenadas del lienzo del SVG. */
  const aLienzo = useCallback(
    (svg: SVGSVGElement, clientX: number, clientY: number) => {
      const caja = svg.getBoundingClientRect();
      return {
        x: vista.x + ((clientX - caja.left) / caja.width) * vista.ancho,
        y: vista.y + ((clientY - caja.top) / caja.height) * vista.alto,
      };
    },
    [vista],
  );

  const onPointerDown = useCallback((event: React.PointerEvent<SVGSVGElement>) => {
    // Solo botón principal, y nunca sobre un elemento que ya tiene su propia
    // interacción de teclado: arrastrar no puede robarle el click a una comunidad.
    if (event.button !== 0) return;
    huboArrastre.current = false;
    arrastre.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
  }, []);

  /** True si el último gesto fue un arrastre. Lo consume el `click` y se rearma. */
  const consumirArrastre = useCallback(() => {
    const valor = huboArrastre.current;
    huboArrastre.current = false;
    return valor;
  }, []);

  const onPointerMove = useCallback(
    (event: React.PointerEvent<SVGSVGElement>) => {
      const inicio = arrastre.current;
      if (!inicio || inicio.id !== event.pointerId) return;
      const caja = event.currentTarget.getBoundingClientRect();
      const dx = ((event.clientX - inicio.x) / caja.width) * vista.ancho;
      const dy = ((event.clientY - inicio.y) / caja.height) * vista.alto;
      if (!arrastrando && Math.hypot(event.clientX - inicio.x, event.clientY - inicio.y) < 4) {
        // Umbral: por debajo de 4 px es un click con pulso, no un arrastre.
        return;
      }
      if (!arrastrando) {
        setArrastrando(true);
        huboArrastre.current = true;
        event.currentTarget.setPointerCapture(event.pointerId);
      }
      arrastre.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
      desplazar(-dx, -dy);
    },
    [arrastrando, desplazar, vista.alto, vista.ancho],
  );

  const onPointerUp = useCallback((event: React.PointerEvent<SVGSVGElement>) => {
    if (arrastre.current?.id === event.pointerId) {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      arrastre.current = null;
      setArrastrando(false);
    }
  }, []);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<SVGSVGElement>) => {
      const salto = vista.ancho / 6;
      const acciones: Record<string, () => void> = {
        "+": acercar,
        "=": acercar,
        "-": alejar,
        _: alejar,
        "0": verTodo,
        ArrowLeft: () => desplazar(-salto, 0),
        ArrowRight: () => desplazar(salto, 0),
        ArrowUp: () => desplazar(0, -salto),
        ArrowDown: () => desplazar(0, salto),
      };
      const accion = acciones[event.key];
      if (!accion) return;
      // Las flechas sobre un `path` enfocado no navegan entre comunidades (no es un
      // grupo de radio), así que aquí no se roba ningún comportamiento nativo.
      event.preventDefault();
      accion();
    },
    [acercar, alejar, desplazar, verTodo, vista.ancho],
  );

  return {
    vista,
    factor,
    arrastrando,
    puedeAcercar: factor < ZOOM_MAX - 0.01,
    puedeAlejar: factor > 1.01,
    acercar,
    alejar,
    verTodo,
    ampliar,
    aLienzo,
    consumirArrastre,
    manejadores: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp, onKeyDown },
  };
}
