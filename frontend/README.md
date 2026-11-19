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
