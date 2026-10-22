import { Route, Routes } from 'react-router-dom'

import { PublicOnly, RequireAccessStep, RequireAuth, RequireRole, RootRedirect } from './auth/guards'
import AppLayout from './layout/AppLayout'
import { ROLES } from './lib/roles'
import AdminHome from './pages/AdminHome'
import AceptarTerminos from './pages/AceptarTerminos'
import ChangePassword from './pages/ChangePassword'
import DocenteHome from './pages/DocenteHome'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Profile from './pages/Profile'
import RepresentanteHome from './pages/RepresentanteHome'
import Users from './pages/admin/Users'
import Academico from './pages/admin/Academico'
import Asignaciones from './pages/admin/Asignaciones'
import Estudiantes from './pages/admin/Estudiantes'
import Temas from './pages/admin/Temas'
import Recursos from './pages/Recursos'
import DocenteActividades from './pages/docente/Actividades'
import NuevaActividad from './pages/docente/NuevaActividad'
import RepresentanteActividades from './pages/representante/Actividades'
import Calificar from './pages/docente/Calificar'
import Desempeno from './pages/Desempeno'
import Dificultades from './pages/Dificultades'
import PlanDetalle from './pages/docente/PlanDetalle'
import DocentePlanes from './pages/docente/Planes'
import RepresentantePlanDetalle from './pages/representante/PlanDetalle'
import RepresentantePlanes from './pages/representante/Planes'
import Privacidad from './pages/legal/Privacidad'
import Terminos from './pages/legal/Terminos'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnly />}>
        <Route path="/login" element={<Login />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route path="/" element={<RootRedirect />} />
        <Route element={<AppLayout />}>
          <Route element={<RequireRole roles={[ROLES.ADMINISTRADOR]} />}>
            <Route path="/admin" element={<AdminHome />} />
            <Route path="/admin/usuarios" element={<Users />} />
            <Route path="/admin/academico" element={<Academico />} />
            <Route path="/admin/estudiantes" element={<Estudiantes />} />
            <Route path="/admin/asignaciones" element={<Asignaciones />} />
            <Route path="/admin/temas" element={<Temas />} />
            <Route path="/admin/recursos" element={<Recursos />} />
          </Route>
          <Route element={<RequireRole roles={[ROLES.DOCENTE]} />}>
            <Route path="/docente" element={<DocenteHome />} />
            <Route path="/docente/recursos" element={<Recursos />} />
            <Route path="/docente/actividades" element={<DocenteActividades />} />
            <Route path="/docente/actividades/nueva" element={<NuevaActividad />} />
            <Route path="/docente/actividades/:id/calificar" element={<Calificar />} />
            <Route path="/docente/desempeno" element={<Desempeno />} />
            <Route path="/docente/dificultades" element={<Dificultades />} />
            <Route path="/docente/planes" element={<DocentePlanes />} />
            <Route path="/docente/planes/:id" element={<PlanDetalle />} />
          </Route>
          <Route element={<RequireRole roles={[ROLES.REPRESENTANTE]} />}>
            <Route path="/representante" element={<RepresentanteHome />} />
            <Route path="/representante/actividades" element={<RepresentanteActividades />} />
            <Route path="/representante/desempeno" element={<Desempeno />} />
            <Route path="/representante/dificultades" element={<Dificultades />} />
            <Route path="/representante/planes" element={<RepresentantePlanes />} />
            <Route path="/representante/planes/:id" element={<RepresentantePlanDetalle />} />
          </Route>
          <Route path="/perfil" element={<Profile />} />
        </Route>
      </Route>

      {/* Pasos del primer acceso: solo existen mientras están pendientes.
          El cambio de contraseña voluntario se hace desde Perfil. */}
      <Route element={<RequireAccessStep path="/cambiar-clave" />}>
        <Route path="/cambiar-clave" element={<ChangePassword />} />
      </Route>
      <Route element={<RequireAccessStep path="/aceptar-terminos" />}>
        <Route path="/aceptar-terminos" element={<AceptarTerminos />} />
      </Route>

      {/* Páginas legales: públicas, se pueden leer con o sin sesión. */}
      <Route path="/privacidad" element={<Privacidad />} />
      <Route path="/terminos" element={<Terminos />} />

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
