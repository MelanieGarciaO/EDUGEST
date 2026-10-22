import { useQuery } from '@tanstack/react-query'

import { api, fetchAll } from '../api/client'

export const useParalelos = () =>
  useQuery({ queryKey: ['paralelos'], queryFn: () => fetchAll('/academic/paralelos/', { is_active: 'true' }) })

export const useAsignaciones = () =>
  useQuery({ queryKey: ['asignaciones'], queryFn: () => fetchAll('/academic/asignaciones/', { is_active: 'true' }) })

export const useEstudiantes = () =>
  useQuery({ queryKey: ['estudiantes'], queryFn: () => fetchAll('/academic/estudiantes/', { is_active: 'true' }) })

/** Solo el total de un listado paginado (para los resúmenes del administrador). */
export const useCount = (key, url, params) =>
  useQuery({
    queryKey: ['count', key, params],
    queryFn: async () => (await api.get(url, { params: { ...params, page: 1 } })).data.count,
  })

export const useAsignaturasActivas = () =>
  useQuery({
    queryKey: ['asignaturas', 'activas'],
    queryFn: () => fetchAll('/academic/asignaturas/', { is_active: 'true' }),
  })

/** Usuarios activos de un rol, para llenar listas de selección (solo administrador). */
export const useUsuariosActivos = (role) =>
  useQuery({
    queryKey: ['users', 'activos', role],
    queryFn: () => fetchAll('/security/users/', { role, is_active: 'true' }),
  })

export const useGrados = () => useQuery({ queryKey: ['grados'], queryFn: () => fetchAll('/academic/grados/') })

/** Todos los temas y subtemas activos (para elegir el tema de un recurso). */
export const useTemasActivos = () =>
  useQuery({ queryKey: ['temas', 'activos'], queryFn: () => fetchAll('/academic/temas/', { is_active: 'true' }) })

/** Actividades (paginadas). `params`: page, paralelo, asignatura, estudiante, vigencia, search. */
export const useActividades = (params) =>
  useQuery({
    queryKey: ['actividades', params],
    queryFn: async () => (await api.get('/activities/actividades/', { params })).data,
    placeholderData: (prev) => prev,
  })

/** Una actividad por id (para conocer su asignatura y paralelo). */
export const useActividad = (id) =>
  useQuery({ queryKey: ['actividad', id], queryFn: async () => (await api.get(`/activities/actividades/${id}/`)).data })

/** Estudiantes del paralelo de una actividad con su nota (o sin calificar). */
export const useNotasActividad = (id) =>
  useQuery({
    queryKey: ['notas-actividad', id],
    queryFn: async () => (await api.get(`/grades/actividades/${id}/calificaciones/`)).data,
  })

/** Desempeño de un estudiante por asignatura y tema. */
export const useDesempeno = (estudianteId) =>
  useQuery({
    queryKey: ['desempeno', estudianteId],
    enabled: !!estudianteId,
    queryFn: async () => (await api.get(`/grades/desempeno/estudiantes/${estudianteId}/`)).data,
  })

/** Dificultades (paginadas). `params`: page, estado, nivel, estudiante, asignatura, paralelo, tema. */
export const useDificultades = (params) =>
  useQuery({
    queryKey: ['dificultades', params],
    queryFn: async () => (await api.get('/grades/dificultades/', { params })).data,
    placeholderData: (prev) => prev,
  })

/** Planes de refuerzo (paginados). `params`: page, estado, estudiante, asignatura, paralelo. */
export const usePlanes = (params) =>
  useQuery({
    queryKey: ['planes', params],
    queryFn: async () => (await api.get('/reinforcement/planes/', { params })).data,
    placeholderData: (prev) => prev,
  })

export const usePlan = (id) =>
  useQuery({ queryKey: ['plan', id], queryFn: async () => (await api.get(`/reinforcement/planes/${id}/`)).data })
