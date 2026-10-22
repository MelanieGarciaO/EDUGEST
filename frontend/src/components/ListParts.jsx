/** Piezas visuales compartidas por las listas del área de administración. */

export function IconButton({ label, onClick, children, tone }) {
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={label}
            title={label}
            className={
                'grid size-10 place-items-center rounded-xl hover:bg-brand-50 ' +
                (tone === 'danger' ? 'text-danger-600 hover:bg-danger-50' : 'text-ink-700')
            }
        >
            {children}
        </button>
    )
}

export function ListBox({ children }) {
    return <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-white">{children}</ul>
}

export function Row({ title, detail, chips, children }) {
    return (
        <li className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
            <div className="min-w-0 flex-1 basis-56">
                <p className="font-bold text-ink-900">{title}</p>
                {detail && <p className="text-sm text-ink-500">{detail}</p>}
            </div>
            {chips}
            <div className="ml-auto flex">{children}</div>
        </li>
    )
}
