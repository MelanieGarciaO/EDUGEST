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

export function initials(user) {
  const first = user?.first_name?.trim()?.[0] ?? ''
  const last = user?.last_name?.trim()?.[0] ?? ''
  return (first + last).toUpperCase() || '?'
}
