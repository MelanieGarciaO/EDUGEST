export const ROLES = {
  ADMINISTRADOR: 'ADMINISTRADOR',
  DOCENTE: 'DOCENTE',
  REPRESENTANTE: 'REPRESENTANTE',
}

export const ROLE_LABELS = {
  ADMINISTRADOR: 'Administrador',
  DOCENTE: 'Docente',
  REPRESENTANTE: 'Representante',
}

const HOME_PATHS = {
  ADMINISTRADOR: '/admin',
  DOCENTE: '/docente',
  REPRESENTANTE: '/representante',
}

export function homeFor(role) {
  return HOME_PATHS[role] ?? '/login'
}

/**
 * Única fuente de verdad del acceso. Siguiente pantalla según el estado del usuario:
 * 1) clave temporal        -> /cambiar-clave  (solo en este caso existe esa pantalla)
 * 2) términos pendientes   -> /aceptar-terminos
 * 3) en cualquier otro caso -> inicio de su rol (sin importar desde dónde venía)
 */
export function destinoTrasAcceso(user) {
  if (!user) return '/login'
  if (user.must_change_password) return '/cambiar-clave'
  if (user.debe_aceptar_terminos) return '/aceptar-terminos'
  return homeFor(user.role)
}

export function initials(user) {
  const first = user?.first_name?.trim()?.[0] ?? ''
  const last = user?.last_name?.trim()?.[0] ?? ''
  return (first + last).toUpperCase() || '?'
}
