import { Link } from 'react-router-dom'

import { useLegalInfo } from '../../lib/legal'
import LegalLayout, { Contacto, Lista } from './LegalLayout'

export default function Privacidad() {
    const { institucion, ciudad, correo, plazo } = useLegalInfo()
    const inst = <b>{institucion}</b>

    const secciones = [
        {
            id: 'responsable',
            titulo: 'Quién es responsable de tus datos',
            contenido: (
                <>
                    <p>
                        El responsable del tratamiento de los datos personales registrados en EduGest es {inst}
                        {ciudad && `, con domicilio en ${ciudad}, Ecuador`}. EduGest es la herramienta que la
                        institución utiliza para gestionar actividades académicas, calificaciones y planes de
                        refuerzo; la institución decide qué datos se registran y para qué se usan.
                    </p>
                    <p>
                        Para cualquier consulta sobre tus datos puedes escribir a <Contacto correo={correo} />.
                    </p>
                </>
            ),
        },
        {
            id: 'datos',
            titulo: 'Qué datos tratamos',
            contenido: (
                <>
                    <p>Solo se registran los datos necesarios para la gestión académica:</p>
                    <Lista>
                        <li>
                            <b>Personal docente y administrativo:</b> nombres, apellidos, correo electrónico
                            institucional, rol y asignaturas o paralelos asignados.
                        </li>
                        <li>
                            <b>Representantes legales:</b> nombres, apellidos, correo electrónico y el vínculo con
                            el estudiante que representan.
                        </li>
                        <li>
                            <b>Estudiantes:</b> nombres, apellidos, grado y paralelo; las actividades asignadas, sus
                            calificaciones, el promedio y nivel de logro por tema, las dificultades de aprendizaje
                            detectadas y los planes de refuerzo con su avance y evaluación.
                        </li>
                        <li>
                            <b>Datos técnicos de uso:</b> fecha del último acceso, aceptación de estos términos y el
                            historial de cambios de calificaciones (quién la cambió, cuándo y de cuánto a cuánto).
                        </li>
                    </Lista>
                    <p>
                        EduGest <b>no</b> solicita cédula, dirección, teléfono, fotografías, datos de salud,
                        ubicación ni ningún otro dato que no sea necesario para estas finalidades.
                    </p>
                </>
            ),
        },
        {
            id: 'finalidades',
            titulo: 'Para qué usamos los datos',
            contenido: (
                <>
                    <Lista>
                        <li>Publicar actividades y tareas para cada paralelo.</li>
                        <li>Registrar calificaciones y calcular el desempeño por asignatura y tema.</li>
                        <li>Detectar dificultades de aprendizaje y elaborar, aprobar y dar seguimiento a planes de refuerzo académico.</li>
                        <li>Informar al representante sobre las actividades, notas y refuerzos de su representado.</li>
                        <li>Administrar las cuentas de usuario y mantener la seguridad del sistema.</li>
                    </Lista>
                    <p>
                        Los datos <b>no</b> se usan con fines publicitarios o comerciales, no se venden y no se
                        utilizan para crear perfiles ajenos a la gestión académica.
                    </p>
                </>
            ),
        },
        {
            id: 'base-legal',
            titulo: 'Con qué base legal',
            contenido: (
                <p>
                    El tratamiento se realiza para cumplir la función educativa de la institución y las
                    obligaciones que le impone la normativa educativa ecuatoriana (evaluación, seguimiento y
                    refuerzo académico), de acuerdo con la Ley Orgánica de Protección de Datos Personales (LOPDP)
                    y su Reglamento. Cuando la normativa lo exige, la institución solicita además el
                    consentimiento del representante legal del estudiante.
                </p>
            ),
        },
        {
            id: 'menores',
            titulo: 'Datos de niñas, niños y adolescentes',
            contenido: (
                <>
                    <p>
                        La mayoría de los estudiantes son menores de edad, por lo que sus datos reciben una
                        protección reforzada y se tratan siempre atendiendo a su interés superior:
                    </p>
                    <Lista>
                        <li>Los estudiantes no tienen cuenta propia; quien accede a su información es su representante legal.</li>
                        <li>Cada representante ve únicamente la información de sus propios representados.</li>
                        <li>Cada docente ve solo a los estudiantes de los paralelos y asignaturas que tiene asignados.</li>
                        <li>Las dificultades y los planes de refuerzo nunca se muestran a otros representantes ni a otros estudiantes.</li>
                    </Lista>
                </>
            ),
        },
        {
            id: 'automatizado',
            titulo: 'Procesos automáticos y revisión humana',
            contenido: (
                <>
                    <p>EduGest automatiza algunas tareas para ahorrar tiempo al docente:</p>
                    <Lista>
                        <li>
                            Lee el texto de una tarea para sugerir fecha, materiales y tema. Este análisis se hace
                            en el propio servidor de EduGest, sin enviar el texto a servicios externos.
                        </li>
                        <li>Detecta una dificultad cuando el promedio de un tema es menor a 7,00.</li>
                        <li>Propone actividades de refuerzo tomadas del banco de recursos.</li>
                    </Lista>
                    <p>
                        Ninguna de estas sugerencias produce efectos por sí sola: el docente revisa y publica cada
                        actividad, registra cada nota y <b>aprueba</b> cada plan antes de que el representante lo
                        vea. Si no estás de acuerdo con un resultado, puedes pedir su revisión al docente o a la
                        institución.
                    </p>
                </>
            ),
        },
        {
            id: 'acceso',
            titulo: 'Quién puede ver los datos',
            contenido: (
                <>
                    <Lista>
                        <li><b>Administración de la institución:</b> gestiona cuentas, paralelos, estudiantes y asignaciones.</li>
                        <li><b>Docentes:</b> solo sus paralelos y asignaturas.</li>
                        <li><b>Representantes:</b> solo sus representados.</li>
                    </Lista>
                    <p>
                        Los datos no se comunican a terceros, salvo al proveedor que aloja el sistema (que actúa
                        como encargado del tratamiento y solo puede usarlos para prestar ese servicio) o cuando
                        una autoridad competente lo requiera conforme a la ley.
                    </p>
                </>
            ),
        },
        {
            id: 'conservacion',
            titulo: 'Cuánto tiempo se conservan',
            contenido: (
                <p>
                    Los datos se conservan mientras el estudiante forme parte de la institución y, después,
                    durante {plazo}. Cumplido ese plazo, se eliminan o se anonimizan. Las cuentas que dejan de
                    usarse se desactivan en lugar de borrarse de inmediato, para conservar el historial académico
                    que la institución está obligada a mantener.
                </p>
            ),
        },
        {
            id: 'seguridad',
            titulo: 'Cómo protegemos la información',
            contenido: (
                <Lista>
                    <li>Las contraseñas se guardan cifradas (Argon2); nadie, ni siquiera la administración, puede verlas.</li>
                    <li>Cada cuenta inicia con una contraseña temporal que el usuario debe cambiar en su primer ingreso.</li>
                    <li>La sesión se cierra al cerrar la pestaña del navegador y el acceso se renueva con credenciales de corta duración.</li>
                    <li>Los permisos se controlan en el servidor según el rol de cada usuario.</li>
                    <li>Los intentos repetidos de inicio de sesión se limitan para evitar accesos indebidos.</li>
                    <li>Los cambios de calificaciones quedan registrados para garantizar su trazabilidad.</li>
                </Lista>
            ),
        },
        {
            id: 'almacenamiento',
            titulo: 'Cookies y almacenamiento en tu navegador',
            contenido: (
                <p>
                    EduGest <b>no usa cookies</b> de publicidad, analítica ni seguimiento. Para mantener tu sesión
                    abierta guarda temporalmente una credencial en el almacenamiento de la pestaña del navegador,
                    que se borra al cerrarla o al cerrar sesión.
                </p>
            ),
        },
        {
            id: 'derechos',
            titulo: 'Tus derechos',
            contenido: (
                <>
                    <p>
                        Como titular de tus datos —o como representante legal del estudiante— puedes ejercer los
                        derechos que reconoce la LOPDP:
                    </p>
                    <Lista>
                        <li><b>Acceso:</b> saber qué datos se tienen y cómo se usan.</li>
                        <li><b>Rectificación y actualización:</b> corregir datos inexactos o incompletos.</li>
                        <li><b>Eliminación:</b> pedir que se borren cuando ya no sean necesarios, salvo obligación legal de conservarlos.</li>
                        <li><b>Oposición y suspensión del tratamiento</b> en los casos previstos por la ley.</li>
                        <li><b>Portabilidad:</b> recibir tus datos en un formato de uso común.</li>
                        <li><b>No ser objeto de decisiones basadas solo en procesos automatizados</b> (ver la sección 6).</li>
                    </Lista>
                    <p>
                        Para ejercerlos escribe a <Contacto correo={correo} /> indicando tu nombre, el derecho que
                        quieres ejercer y, si eres representante, el nombre del estudiante. La institución
                        responderá en los plazos que establece la LOPDP. Si consideras que tus derechos no fueron
                        atendidos, puedes presentar un reclamo ante la Superintendencia de Protección de Datos
                        Personales.
                    </p>
                </>
            ),
        },
        {
            id: 'cambios',
            titulo: 'Cambios en esta política',
            contenido: (
                <p>
                    Si esta política cambia, se publicará una nueva versión con su fecha de vigencia y se te
                    pedirá aceptarla la próxima vez que inicies sesión. También puedes consultar los{' '}
                    <Link to="/terminos" className="font-bold text-brand-700 hover:underline">términos de uso</Link>.
                </p>
            ),
        },
    ]

    return (
        <LegalLayout
            titulo="Política de privacidad"
            resumen={
                <>
                    En pocas palabras: {institucion} usa EduGest para gestionar actividades, notas y refuerzos
                    académicos. Solo se registran los datos necesarios para ese fin, cada persona ve únicamente lo
                    que le corresponde, los datos de los estudiantes reciben protección reforzada y nunca se usan
                    con fines comerciales.
                </>
            }
            secciones={secciones}
            otro={{ to: '/terminos', label: 'Términos de uso' }}
        />
    )
}
