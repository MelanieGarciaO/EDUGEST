import { useEffect, useState } from 'react'

/** Devuelve el valor con retraso, para no consultar la API en cada tecla. */
export function useDebouncedValue(value, delay = 350) {
    const [debounced, setDebounced] = useState(value)
    useEffect(() => {
        const id = setTimeout(() => setDebounced(value), delay)
        return () => clearTimeout(id)
    }, [value, delay])
    return debounced
}
