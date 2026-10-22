import { Children, useEffect, useId, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, Eye, EyeOff, GraduationCap, Loader2, X } from 'lucide-react'

import { initials } from '../lib/roles'

export function cx(...parts) {
    return parts.filter(Boolean).join(' ')
}

export function Logo({ light = false, className }) {
    return (
        <span className={cx('inline-flex items-center gap-2.5', className)}>
            <span
                className={cx(
                    'grid size-9 place-items-center rounded-xl',
                    light ? 'bg-white text-navy-800' : 'bg-navy-800 text-white',
                )}
            >
                <GraduationCap className="size-5" aria-hidden="true" />
            </span>
            <span className={cx('text-xl font-extrabold tracking-tight', light ? 'text-white' : 'text-navy-800')}>
                EduGest
            </span>
        </span>
    )
}

export function Spinner({ className }) {
    return <Loader2 className={cx('size-5 animate-spin', className)} aria-hidden="true" />
}

export function FullScreenSpinner({ label = 'Cargando' }) {
    return (
        <div className="grid min-h-screen place-items-center bg-brand-50" role="status">
            <div className="flex items-center gap-3 text-navy-800">
                <Spinner className="size-6" />
                <span className="font-semibold">{label}…</span>
            </div>
        </div>
    )
}

const BUTTON_VARIANTS = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-200',
    secondary: 'bg-white text-navy-800 border border-line hover:bg-brand-50',
    ok: 'bg-ok-600 text-white hover:bg-ok-600/90 disabled:bg-ok-600/50',
    danger: 'bg-danger-600 text-white hover:bg-danger-600/90 disabled:bg-danger-600/50',
    ghost: 'text-brand-700 hover:bg-brand-100',
}

/**
 * Envuelve los textos sueltos en <span>. Así React nunca usa un nodo de texto como
 * referencia para insertBefore (p. ej. al mostrar el spinner de carga). Si el traductor
 * del navegador o una extensión reemplaza ese texto, la app ya no se rompe.
 */
function wrapText(children) {
    return Children.map(children, (child) =>
        typeof child === 'string' || typeof child === 'number' ? <span>{child}</span> : child,
    )
}

export function Button({ variant = 'primary', loading = false, className, children, disabled, ...rest }) {
    return (
        <button
            type="button"
            disabled={disabled || loading}
            className={cx(
                'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-[15px] font-bold',
                'transition-colors disabled:cursor-not-allowed',
                BUTTON_VARIANTS[variant],
                className,
            )}
            {...rest}
        >
            {loading ? <Spinner className="size-4" /> : null}
            {wrapText(children)}
        </button>
    )
}

export function Field({ label, error, hint, className, ...input }) {
    const id = useId()
    const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink-700">
                {label}
            </label>
            <input
                id={id}
                aria-invalid={error ? 'true' : undefined}
                aria-describedby={describedBy}
                className={cx(
                    'block min-h-11 w-full rounded-xl border bg-white px-3.5 text-[15px] text-ink-900',
                    'placeholder:text-ink-300',
                    error ? 'border-danger-600' : 'border-line hover:border-ink-300',
                )}
                {...input}
            />
            {error ? (
                <p id={`${id}-err`} className="mt-1.5 text-sm font-medium text-danger-600">
                    {error}
                </p>
            ) : hint ? (
                <p id={`${id}-hint`} className="mt-1.5 text-sm text-ink-500">
                    {hint}
                </p>
            ) : null}
        </div>
    )
}

export function PasswordField({ label, error, hint, className, ...input }) {
    const id = useId()
    const [visible, setVisible] = useState(false)
    const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink-700">
                {label}
            </label>
            <div className="relative">
                <input
                    id={id}
                    type={visible ? 'text' : 'password'}
                    aria-invalid={error ? 'true' : undefined}
                    aria-describedby={describedBy}
                    className={cx(
                        'block min-h-11 w-full rounded-xl border bg-white py-0 pr-12 pl-3.5 text-[15px] text-ink-900',
                        error ? 'border-danger-600' : 'border-line hover:border-ink-300',
                    )}
                    {...input}
                />
                <button
                    type="button"
                    onClick={() => setVisible((v) => !v)}
                    aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                    aria-pressed={visible}
                    className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-xl text-ink-500 hover:text-navy-800"
                >
                    {visible ? <EyeOff className="size-5" aria-hidden="true" /> : <Eye className="size-5" aria-hidden="true" />}
                </button>
            </div>
            {error ? (
                <p id={`${id}-err`} className="mt-1.5 text-sm font-medium text-danger-600">
                    {error}
                </p>
            ) : hint ? (
                <p id={`${id}-hint`} className="mt-1.5 text-sm text-ink-500">
                    {hint}
                </p>
            ) : null}
        </div>
    )
}

const ALERT_STYLES = {
    error: { box: 'bg-danger-50 text-danger-600', Icon: AlertCircle, role: 'alert' },
    ok: { box: 'bg-ok-50 text-ok-600', Icon: CheckCircle2, role: 'status' },
    warn: { box: 'bg-warn-50 text-warn-600', Icon: AlertCircle, role: 'status' },
}

export function Alert({ tone = 'error', children, className }) {
    const { box, Icon, role } = ALERT_STYLES[tone]
    return (
        <div role={role} className={cx('flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm font-semibold', box, className)}>
            <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>{children}</div>
        </div>
    )
}

export function Card({ as: Tag = 'section', className, children, ...rest }) {
    return (
        <Tag className={cx('rounded-2xl border border-line bg-white p-5 sm:p-6', className)} {...rest}>
            {children}
        </Tag>
    )
}

export function PageHeader({ title, subtitle, children }) {
    return (
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
                <h1 className="text-2xl font-extrabold tracking-tight text-navy-800 sm:text-3xl">{title}</h1>
                {subtitle && <p className="mt-1 max-w-prose text-ink-500">{subtitle}</p>}
            </div>
            {children}
        </header>
    )
}

export function EmptyState({ icon: Icon, title, children }) {
    return (
        <div className="rounded-2xl border border-dashed border-brand-200 bg-white/60 px-6 py-10 text-center">
            {Icon && <Icon className="mx-auto mb-3 size-8 text-brand-500" aria-hidden="true" />}
            <p className="font-bold text-navy-800">{title}</p>
            {children && <p className="mx-auto mt-1 max-w-md text-sm text-ink-500">{children}</p>}
        </div>
    )
}

export function Avatar({ user, className }) {
    return (
        <span
            aria-hidden="true"
            className={cx(
                'grid size-10 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-extrabold text-navy-800',
                className,
            )}
        >
            {initials(user)}
        </span>
    )
}

export function Chip({ children, tone = 'brand' }) {
    const tones = {
        brand: 'bg-brand-100 text-brand-700',
        ok: 'bg-ok-50 text-ok-600',
        warn: 'bg-warn-50 text-warn-600',
        danger: 'bg-danger-50 text-danger-600',
    }
    return <span className={cx('inline-block rounded-full px-2.5 py-1 text-xs font-bold', tones[tone])}>{children}</span>
}

export function SelectField({ label, error, hint, className, children, ...select }) {
    const id = useId()
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink-700">
                {label}
            </label>
            <select
                id={id}
                aria-invalid={error ? 'true' : undefined}
                className={cx(
                    'block min-h-11 w-full rounded-xl border bg-white px-3 text-[15px] text-ink-900 disabled:bg-brand-50 disabled:text-ink-500',
                    error ? 'border-danger-600' : 'border-line hover:border-ink-300',
                )}
                {...select}
            >
                {children}
            </select>
            {error ? (
                <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p>
            ) : hint ? (
                <p className="mt-1.5 text-sm text-ink-500">{hint}</p>
            ) : null}
        </div>
    )
}

/** Ventana modal basada en <dialog>: el navegador gestiona el foco y la tecla Escape. */
export function Modal({ open, onClose, title, children, footer, size = 'md' }) {
    const ref = useRef(null)

    useEffect(() => {
        const dialog = ref.current
        if (!dialog) return
        if (open && !dialog.open) dialog.showModal()
        if (!open && dialog.open) dialog.close()
    }, [open])

    return (
        <dialog
            ref={ref}
            onClose={onClose}
            onClick={(e) => e.target === ref.current && onClose()}
            aria-label={title}
            className={cx(
                'm-auto w-[calc(100%-2rem)] rounded-2xl bg-white p-0 text-ink-900 shadow-xl backdrop:bg-navy-900/60',
                size === 'lg' ? 'max-w-xl' : 'max-w-md',
            )}
        >
            {open && (
                <div className="p-5 sm:p-6">
                    <div className="mb-4 flex items-start justify-between gap-4">
                        <h2 className="text-xl font-extrabold tracking-tight text-navy-800">{title}</h2>
                        <button
                            type="button"
                            onClick={onClose}
                            aria-label="Cerrar"
                            className="-mt-1 -mr-2 grid size-10 place-items-center rounded-xl text-ink-500 hover:bg-brand-50"
                        >
                            <X className="size-5" aria-hidden="true" />
                        </button>
                    </div>
                    {children}
                    {footer && <div className="mt-6 flex flex-wrap justify-end gap-3">{footer}</div>}
                </div>
            )}
        </dialog>
    )
}

export function ConfirmDialog({ open, title, children, confirmLabel, tone = 'danger', loading, error, onConfirm, onClose }) {
    return (
        <Modal
            open={open}
            onClose={onClose}
            title={title}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={loading}>
                        Cancelar
                    </Button>
                    <Button variant={tone} onClick={onConfirm} loading={loading}>
                        {confirmLabel}
                    </Button>
                </>
            }
        >
            {error ? <Alert className="mb-3">{error}</Alert> : null}
            <div className="text-ink-700">{wrapText(children)}</div>
        </Modal>
    )
}

export function Pagination({ page, count, pageSize, onPage }) {
    const pages = Math.max(1, Math.ceil(count / pageSize))
    if (pages <= 1) return null
    return (
        <nav aria-label="Paginación" className="mt-4 flex items-center justify-between gap-3 text-sm">
            <p className="text-ink-500">
                Página {page} de {pages} · {count} en total
            </p>
            <div className="flex gap-2">
                <Button variant="secondary" className="min-h-10 px-4" disabled={page <= 1} onClick={() => onPage(page - 1)}>
                    Anterior
                </Button>
                <Button variant="secondary" className="min-h-10 px-4" disabled={page >= pages} onClick={() => onPage(page + 1)}>
                    Siguiente
                </Button>
            </div>
        </nav>
    )
}

/** Pestañas accesibles. `tabs` = [{ id, label }]; el contenido lo pinta quien la usa. */
export function Tabs({ tabs, value, onChange, label }) {
    return (
        <div role="tablist" aria-label={label} className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
            {tabs.map((t) => {
                const active = t.id === value
                return (
                    <button
                        key={t.id}
                        type="button"
                        role="tab"
                        id={`tab-${t.id}`}
                        aria-selected={active}
                        aria-controls={`panel-${t.id}`}
                        onClick={() => onChange(t.id)}
                        className={cx(
                            '-mb-px min-h-11 shrink-0 border-b-[3px] px-4 text-[15px] font-bold transition-colors',
                            active ? 'border-brand-600 text-navy-800' : 'border-transparent text-ink-500 hover:text-navy-800',
                        )}
                    >
                        {t.label}
                    </button>
                )
            })}
        </div>
    )
}

export function TextAreaField({ label, error, hint, className, ...textarea }) {
    const id = useId()
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink-700">
                {label}
            </label>
            <textarea
                id={id}
                aria-invalid={error ? 'true' : undefined}
                className={cx(
                    'block min-h-28 w-full rounded-xl border bg-white px-3.5 py-2.5 text-[15px] text-ink-900',
                    error ? 'border-danger-600' : 'border-line hover:border-ink-300',
                )}
                {...textarea}
            />
            {error ? (
                <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p>
            ) : hint ? (
                <p className="mt-1.5 text-sm text-ink-500">{hint}</p>
            ) : null}
        </div>
    )
}

export function CheckboxField({ label, hint, className, ...input }) {
    const id = useId()
    return (
        <div className={cx('flex items-start gap-3 rounded-xl border border-line bg-white px-4 py-3', className)}>
            <input id={id} type="checkbox" className="mt-0.5 size-5 shrink-0 accent-brand-700" {...input} />
            <div>
                <label htmlFor={id} className="block font-bold text-ink-900">{label}</label>
                {hint && <p className="mt-0.5 text-sm text-ink-500">{hint}</p>}
            </div>
        </div>
    )
}