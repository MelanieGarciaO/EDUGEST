/** Une clases de Tailwind ignorando las vacías: cx('a', cond && 'b') -> 'a b'. */
export function cx(...parts) {
    return parts.filter(Boolean).join(' ')
}