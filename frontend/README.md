# EduGest — Frontend

Interfaz web de EduGest, hecha con **React + Vite**, React Router, TanStack Query y Tailwind CSS.

La documentación completa del proyecto (funcionalidades, arquitectura, instalación y pruebas) está
en el [README principal](../README.md).

## Inicio rápido

```bash
npm install
cp .env.example .env     # VITE_API_URL=http://localhost:8000/api
npm run dev              # http://localhost:5173
```

| Script | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con recarga en caliente |
| `npm run lint` | Revisa el código con ESLint |
| `npm run build` | Genera la versión de producción en `dist/` |
| `npm run preview` | Sirve localmente la versión de producción |

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente HTTP (JWT y renovación de token) |
| `src/components/` | Componentes reutilizables (modales, tarjetas, semáforo, vista del plan) |
| `src/layout/` | Estructura general: menú lateral y encabezado por rol |
| `src/lib/` | Consultas a la API con TanStack Query y utilidades (formato de notas, fechas, roles, clases CSS) |
| `src/pages/` | Pantallas por rol: `admin/`, `docente/`, `representante/` y `legal/` |

## Despliegue en Vercel

Publicado en **https://edugest-kappa.vercel.app**. Vercel despliega automáticamente cada cambio en
`main`.

| Campo en Vercel | Valor |
|---|---|
| Framework Preset | Vite |
| Root Directory | `frontend` |
| Build Command / Output | `npm run build` / `dist` |
| Variable de entorno | `VITE_API_URL=https://edugest-api-444v.onrender.com/api` |

- `vercel.json` redirige todas las rutas a `index.html`, para que React Router funcione al recargar
  una página interna (por ejemplo, `/docente/actividades`).
- `VITE_API_URL` se incluye en el build: si cambia, hay que hacer **Redeploy**. Debe ser la URL
  completa, con `https://` y sin `/` al final.
- Las variables con prefijo `VITE_` son visibles en el navegador: nunca pongas claves con ese prefijo.

El backend, sus variables y las tareas programadas están en la sección
[Despliegue del README principal](../README.md#despliegue).