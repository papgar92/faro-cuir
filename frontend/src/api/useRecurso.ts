/**
 * Hook mínimo para leer un recurso de la API dentro de un componente.
 *
 * No se añade react-query ni SWR: las dos pantallas que leen de la API hacen una petición
 * cada una, sin caché compartida, sin reintentos y sin invalidación. Traer una librería de
 * estado de servidor para eso sería más superficie que valor. Si aparece caché compartida
 * entre pantallas, se revisa esta decisión.
 *
 * Lo que sí resuelve, porque hacerlo mal es un bug real: cancela la petición en curso cuando
 * el componente se desmonta o cambian las dependencias, y distingue una cancelación de un
 * error. Sin eso, cambiar de documento rápido deja que la respuesta lenta de la petición
 * anterior pise a la nueva.
 */

import { useEffect, useState } from "react";
import { ApiError } from "./client";

export type Estado<T> =
  | { fase: "cargando" }
  | { fase: "listo"; datos: T }
  | { fase: "error"; error: Error };

/**
 * `cargar` recibe la señal de cancelación y debe pasársela al cliente. `deps` funciona como
 * las de `useEffect`: cuando cambian, se cancela lo anterior y se vuelve a pedir.
 */
export function useRecurso<T>(
  cargar: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): Estado<T> {
  const [estado, setEstado] = useState<Estado<T>>({ fase: "cargando" });

  useEffect(() => {
    const control = new AbortController();
    setEstado({ fase: "cargando" });

    cargar(control.signal).then(
      (datos) => {
        if (!control.signal.aborted) setEstado({ fase: "listo", datos });
      },
      (error: unknown) => {
        // Una cancelación no es un fallo: el componente ya no quiere esta respuesta. Pintar
        // "error al cargar" aquí sería mentirle al usuario sobre el estado de la API.
        if (control.signal.aborted) return;
        setEstado({
          fase: "error",
          error: error instanceof Error ? error : new Error(String(error)),
        });
      },
    );

    return () => control.abort();
    // `cargar` se recrea en cada render (es una lambda en el cuerpo del componente), así que
    // no puede entrar en las dependencias: haría un bucle de peticiones. Quien llama declara
    // en `deps` de qué depende de verdad.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return estado;
}

/**
 * Texto para el usuario a partir del error. Separa "la API respondió que no" de "no se pudo
 * hablar con la API", que son problemas distintos y se arreglan de forma distinta.
 */
export function describirError(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "No existe ese recurso en la API.";
    return `La API respondió con un error ${error.status}.`;
  }
  return "No se ha podido contactar con la API. ¿Está levantado el backend?";
}
