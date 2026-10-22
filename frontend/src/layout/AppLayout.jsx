import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { BarChart3, ClipboardList, GraduationCap, Home, LifeBuoy, Library, ListTree, LogOut, Menu, School, TriangleAlert, UserRound, Users, X } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import ErrorBoundary from '../components/ErrorBoundary'
import { Avatar, Logo, cx } from '../components/ui'
import { ROLE_LABELS, homeFor } from '../lib/roles'

const ADMIN_NAV = [
    { to: '/admin/usuarios', label: 'Usuarios', icon: Users },
    { to: '/admin/academico', label: 'Estructura académica', icon: School },
    { to: '/admin/estudiantes', label: 'Estudiantes', icon: GraduationCap },
    { to: '/admin/asignaciones', label: 'Asignaciones', icon: ClipboardList },
    { to: '/admin/temas', label: 'Temas', icon: ListTree },
    { to: '/admin/recursos', label: 'Banco de recursos', icon: Library },
]

const DOCENTE_NAV = [
    { to: '/docente/actividades', label: 'Actividades', icon: ClipboardList },
    { to: '/docente/recursos', label: 'Banco de recursos', icon: Library },
    { to: '/docente/desempeno', label: 'Desempeño', icon: BarChart3 },
    { to: '/docente/dificultades', label: 'Dificultades', icon: TriangleAlert },
    { to: '/docente/planes', label: 'Planes de refuerzo', icon: LifeBuoy },
]

const REPRESENTANTE_NAV = [
    { to: '/representante/actividades', label: 'Actividades', icon: ClipboardList },
    { to: '/representante/desempeno', label: 'Desempeño', icon: BarChart3 },
    { to: '/representante/dificultades', label: 'Dificultades', icon: TriangleAlert },
    { to: '/representante/planes', label: 'Planes de refuerzo', icon: LifeBuoy },
]

function navFor(user) {
    // Las demás secciones se agregan a medida que se construyen sus módulos.
    return [
        { to: homeFor(user.role), label: 'Inicio', icon: Home, end: true },
        ...(user.role === 'ADMINISTRADOR' ? ADMIN_NAV : []),
        ...(user.role === 'DOCENTE' ? DOCENTE_NAV : []),
        ...(user.role === 'REPRESENTANTE' ? REPRESENTANTE_NAV : []),
        { to: '/perfil', label: 'Perfil', icon: UserRound },
    ]
}

function SidebarContent({ onNavigate }) {
    const { user, logout } = useAuth()
    const [leaving, setLeaving] = useState(false)

    return (
        <div className="flex h-full flex-col">
            <div className="bg-navy-800 px-5 py-5">
                <Logo light />
            </div>
            <nav aria-label="Principal" className="flex-1 space-y-1 p-3">
                {navFor(user).map(({ to, label, icon: Icon, end }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={end}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                            cx(
                                'flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-[15px] font-bold transition-colors',
                                isActive ? 'bg-brand-100 text-navy-800' : 'text-ink-700 hover:bg-brand-50',
                            )
                        }
                    >
                        <Icon className="size-5" aria-hidden="true" />
                        {label}
                    </NavLink>
                ))}
            </nav>
            <div className="border-t border-line p-3">
                <div className="flex items-center gap-3 px-2 py-2">
                    <Avatar user={user} />
                    <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-ink-900">
                            {user.first_name} {user.last_name}
                        </p>
                        <p className="text-xs text-ink-500">{ROLE_LABELS[user.role]}</p>
                    </div>
                </div>
                <button
                    type="button"
                    disabled={leaving}
                    onClick={() => {
                        setLeaving(true)
                        logout()
                    }}
                    className="mt-1 flex min-h-11 w-full items-center gap-3 rounded-xl px-3.5 text-[15px] font-bold text-danger-600 hover:bg-danger-50 disabled:opacity-60"
                >
                    <LogOut className="size-5" aria-hidden="true" />
                    Cerrar sesión
                </button>
                <p className="mt-2 px-3.5 text-xs text-ink-500">
                    <Link to="/privacidad" onClick={onNavigate} className="hover:text-brand-700 hover:underline">Privacidad</Link>
                    {' · '}
                    <Link to="/terminos" onClick={onNavigate} className="hover:text-brand-700 hover:underline">Términos</Link>
                </p>
            </div>
        </div>
    )
}

export default function AppLayout({ children }) {
    const [open, setOpen] = useState(false)

    useEffect(() => {
        if (!open) return undefined
        const onKey = (e) => e.key === 'Escape' && setOpen(false)
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [open])

    return (
        <div className="min-h-screen lg:grid lg:grid-cols-[17rem_1fr]">
            <a
                href="#contenido"
                className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold"
            >
                Saltar al contenido
            </a>

            <aside className="sticky top-0 hidden h-screen border-r border-line bg-white lg:block">
                <SidebarContent />
            </aside>

            <div className="sticky top-0 z-30 flex items-center justify-between bg-navy-800 px-4 py-3 lg:hidden">
                <Logo light />
                <button
                    type="button"
                    onClick={() => setOpen(true)}
                    aria-label="Abrir menú"
                    aria-expanded={open}
                    className="grid size-11 place-items-center rounded-xl text-white hover:bg-navy-700"
                >
                    <Menu className="size-6" aria-hidden="true" />
                </button>
            </div>

            {open && (
                <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menú">
                    <button
                        type="button"
                        aria-label="Cerrar menú"
                        className="absolute inset-0 bg-navy-900/60"
                        onClick={() => setOpen(false)}
                    />
                    <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white shadow-xl">
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            aria-label="Cerrar menú"
                            className="absolute top-3 right-3 grid size-10 place-items-center rounded-xl text-white hover:bg-navy-700"
                        >
                            <X className="size-5" aria-hidden="true" />
                        </button>
                        <SidebarContent onNavigate={() => setOpen(false)} />
                    </div>
                </div>
            )}

            <main id="contenido" className="min-w-0 px-4 py-6 sm:px-8 sm:py-8">
                <div className="mx-auto max-w-5xl">
                    <PantallaSegura>{children ?? <Outlet />}</PantallaSegura>
                </div>
            </main>
        </div>
    )
}

/** Si una pantalla falla al dibujarse, el menú sigue disponible; se reinicia al cambiar de ruta. */
function PantallaSegura({ children }) {
    const { pathname } = useLocation()
    return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
}
