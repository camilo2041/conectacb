import { useEffect, useState } from 'react';

// Carga datos de la API al montar. `data` es null mientras carga (y en el HTML pre-renderado).
export function useApi(load) {
  const [state, setState] = useState({ data: null, error: null });
  useEffect(() => {
    let alive = true;
    load()
      .then(data => alive && setState({ data, error: null }))
      .catch(error => alive && setState({ data: null, error }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}

// Viaje de ejemplo para las secciones ilustrativas: siempre el mismo, calculado por la API
// para las 7:00 a. m. de un lunes (a esa hora todas las líneas operan).
export const SAMPLE_TRIP = { texto: 'de Quiba a Portal Tunal', hora: '07:00', dia: 'L', label: 'Quiba → Portal Tunal, saliendo a las 7:00 a. m.' };
