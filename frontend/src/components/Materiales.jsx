import { useId, useState } from 'react'
import { Plus, X } from 'lucide-react'

import { Button, Chip } from './ui'

const MAX = 20

/** Muestra los materiales como etiquetas. */
export function MaterialesChips({ items }) {
    if (!items?.length) return null
    return (
        <ul className="flex flex-wrap gap-2" aria-label="Materiales">
            {items.map((m) => (
                <li key={m}>
                    <Chip>{m}</Chip>
                </li>
            ))}
        </ul>
    )
}

/** Lista editable de materiales: se escribe uno y se agrega con Enter o con el botón. */
export function MaterialesInput({ value, onChange, error }) {
    const id = useId()
    const [text, setText] = useState('')

    function add() {
        const item = text.trim().replace(/\s+/g, ' ')
        if (!item) return
        if (value.length < MAX && !value.some((v) => v.toLowerCase() === item.toLowerCase())) onChange([...value, item])
        setText('')
    }

    return (
        <div>
            <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink-700">
                Materiales
            </label>
            <div className="flex gap-2">
                <input
                    id={id}
                    value={text}
                    maxLength={100}
                    placeholder="Ej.: Regla"
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault()
                            add()
                        }
                    }}
                    className="block min-h-11 w-full rounded-xl border border-line bg-white px-3.5 text-[15px] placeholder:text-ink-300 hover:border-ink-300"
                />
                <Button variant="secondary" onClick={add} disabled={!text.trim() || value.length >= MAX} className="shrink-0">
                    <Plus className="size-4" aria-hidden="true" />
                    Agregar
                </Button>
            </div>
            {value.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2">
                    {value.map((m) => (
                        <li key={m} className="inline-flex items-center gap-1 rounded-full bg-brand-100 py-1 pr-1 pl-3 text-sm font-bold text-brand-700">
                            {m}
                            <button
                                type="button"
                                onClick={() => onChange(value.filter((v) => v !== m))}
                                aria-label={`Quitar ${m}`}
                                className="grid size-6 place-items-center rounded-full hover:bg-brand-200"
                            >
                                <X className="size-3.5" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            {error ? (
                <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p>
            ) : (
                <p className="mt-1.5 text-sm text-ink-500">Opcional. Lo que el estudiante debe llevar o usar.</p>
            )}
        </div>
    )
}
