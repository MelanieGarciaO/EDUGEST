import { Link } from 'react-router-dom'

import { useLegalInfo } from '../../lib/legal'
import LegalLayout, { Contacto, Lista } from './LegalLayout'

export default function Terminos() {
    const { institucion, correo } = useLegalInfo()
    const inst = <b>{institucion}</b>
    const privacidad = (
        <Link to="/privacidad" className="font-bold text-brand-700 hover:underline">política de privacidad</Link>
    )

    const secciones = [
        {
            id: 'objeto',
            titulo: 'Qué es EduGest',
            contenido: (
                <p>
                    EduGest es la plataforma que {inst} pone a disposición de su personal y de los representantes
                    legales de sus estudiantes para publicar actividades académicas, registrar calificaciones,
                    consultar el desempeño y dar seguimiento a los planes de refuerzo. Al usar EduGest aceptas
                    estos términos y la {privacidad}.
                </p>
            ),
        },
        {
            id: 'cuentas',
            titulo: 'Cuentas de usuario',
            contenido: (
                <Lista>
                    <li>Las cuentas las crea únicamente la administración de la institución; no existe registro abierto.</li>
                    <li>La cuenta es personal e intransferible. No compartas tu contraseña con nadie, incluidos los estudiantes.</li>
                    <li>En tu primer ingreso debes reemplazar la contraseña temporal por una propia.</li>
                    <li>Eres responsable de lo que se haga con tu cuenta. Si sospechas que alguien más la usa, avisa de inmediato a la institución.</li>
                    <li>Cierra sesión al usar equipos compartidos o públicos.</li>
                </Lista>
            ),
        },
        {
            id: 'roles',
            titulo: 'Responsabilidades según tu rol',
            contenido: (
                <Lista>
                    <li>
                        <b>Docente:</b> publicar actividades claras y oportunas, registrar calificaciones correctas y
                        corregirlas cuando corresponda, y revisar y aprobar los planes de refuerzo antes de
                        publicarlos.
                    </li>
                    <li>
                        <b>Representante:</b> consultar la información de su representado, acompañar el cumplimiento
                        de las actividades y marcar como cumplidas solo las actividades de refuerzo realmente
                        realizadas.
                    </li>
                    <li>
                        <b>Administración:</b> mantener actualizadas las cuentas, paralelos, estudiantes y
                        asignaciones, y desactivar oportunamente las cuentas que ya no deban tener acceso.
                    </li>
                </Lista>
            ),
        },
        {
            id: 'uso',
            titulo: 'Uso adecuado',
            contenido: (
                <>
                    <p>Al usar EduGest te comprometes a no:</p>
                    <Lista>
                        <li>Acceder o intentar acceder a información que no te corresponde, ni a cuentas de otras personas.</li>
                        <li>Copiar, publicar o difundir —por ejemplo, en redes sociales o grupos de mensajería— calificaciones, dificultades o planes de refuerzo de cualquier estudiante.</li>
                        <li>Registrar contenido falso, ofensivo, discriminatorio o ajeno a la gestión académica.</li>
                        <li>Interferir con el funcionamiento del sistema, probar sus vulnerabilidades o automatizar accesos sin autorización.</li>
                    </Lista>
                </>
            ),
        },
        {
            id: 'herramientas',
            titulo: 'Herramientas automáticas',
            contenido: (
                <p>
                    Las sugerencias que genera EduGest —fecha y materiales extraídos del texto de una tarea,
                    dificultades detectadas y actividades de refuerzo propuestas— son un apoyo para el docente.
                    La decisión final siempre es del docente y de la institución, que deben revisarlas antes de
                    publicarlas.
                </p>
            ),
        },
        {
            id: 'contenido',
            titulo: 'Contenido y propiedad',
            contenido: (
                <p>
                    Las actividades y los recursos del banco de refuerzo pertenecen a sus autores o a la
                    institución y solo pueden usarse con fines educativos dentro de la institución. La información
                    académica de cada estudiante pertenece a él y a su familia, y la institución la custodia
                    conforme a la {privacidad}.
                </p>
            ),
        },
        {
            id: 'disponibilidad',
            titulo: 'Disponibilidad del servicio',
            contenido: (
                <p>
                    La institución procura que EduGest esté disponible de forma continua, pero puede haber
                    interrupciones por mantenimiento, actualizaciones o fallas técnicas. Cuando ocurra, EduGest lo
                    indicará en pantalla y se reconectará automáticamente al volver el servicio. Las fechas de
                    entrega y los procesos académicos se rigen por lo que disponga la institución, también durante
                    esas interrupciones.
                </p>
            ),
        },
        {
            id: 'suspension',
            titulo: 'Suspensión de cuentas',
            contenido: (
                <p>
                    La institución puede desactivar una cuenta cuando termine la relación con el usuario (por
                    ejemplo, cuando el estudiante deja la institución) o cuando se incumplan estos términos.
                    Desactivar una cuenta no elimina el historial académico que la institución debe conservar.
                </p>
            ),
        },
        {
            id: 'responsabilidad',
            titulo: 'Limitación de responsabilidad',
            contenido: (
                <p>
                    EduGest es una herramienta de apoyo a la gestión académica y no reemplaza los registros
                    oficiales que la institución lleva según la normativa educativa. En caso de diferencia entre
                    EduGest y un registro oficial, prevalece el registro oficial; repórtala a la institución para
                    su corrección.
                </p>
            ),
        },
        {
            id: 'cambios',
            titulo: 'Cambios en los términos',
            contenido: (
                <p>
                    La institución puede actualizar estos términos. Cada versión indica su fecha de vigencia y, si
                    hay cambios, se te pedirá aceptarlos la próxima vez que inicies sesión.
                </p>
            ),
        },
        {
            id: 'ley',
            titulo: 'Ley aplicable y contacto',
            contenido: (
                <p>
                    Estos términos se rigen por las leyes de la República del Ecuador. Para consultas o reclamos
                    sobre el uso de EduGest escribe a <Contacto correo={correo} />.
                </p>
            ),
        },
    ]

    return (
        <LegalLayout
            titulo="Términos de uso"
            resumen={
                <>
                    En pocas palabras: tu cuenta es personal, ves solo la información que te corresponde, no
                    compartas datos de los estudiantes fuera de EduGest y las sugerencias automáticas siempre las
                    revisa el docente.
                </>
            }
            secciones={secciones}
            otro={{ to: '/privacidad', label: 'Política de privacidad' }}
        />
    )
}
