import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import './index.css'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import { esErrorDeSistema } from './api/system'
import ErrorBoundary from './components/ErrorBoundary'
import SystemStatusOverlay from './components/SystemStatusOverlay'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Si el sistema está caído o en mantenimiento no tiene sentido reintentar: la pantalla
      // de estado se encarga de volver a consultar cuando el servicio regrese.
      retry: (fallos, error) => !esErrorDeSistema(error) && fallos < 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary variant="full">
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
        <SystemStatusOverlay />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
