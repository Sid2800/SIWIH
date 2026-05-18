from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode


class NoSessionRefreshOnPollingMiddleware:
    """
    Middleware que detecta requests de polling (header X-Polling-Request: true)
    y evita que esos requests reinicien el timer de expiración de sesión.

    Combinado con SESSION_SAVE_EVERY_REQUEST=True:
    - Requests normales (clicks, navegación, submits) → SÍ renuevan la sesión
    - Requests con header X-Polling-Request: true → NO renuevan la sesión

    Esto permite tener auto-refresh de tablas y notificaciones sin afectar
    el timeout de 30 minutos de inactividad real del usuario.

    IMPORTANTE: Debe ir ANTES de SessionMiddleware en la lista de MIDDLEWARE,
    o más bien, debe ejecutarse DESPUÉS de que la vista haga su trabajo
    para revertir cualquier modificación de sesión.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        es_polling = request.headers.get('X-Polling-Request', '').lower() == 'true'

        response = self.get_response(request)

        # Si fue un polling y la sesión está marcada como modificada,
        # forzamos a que NO se guarde (no se renueva la expiración)
        if es_polling and hasattr(request, 'session'):
            # Marcar accessed=False evita que SESSION_SAVE_EVERY_REQUEST la persista
            try:
                request.session.modified = False
                # Truco: marcar accessed para que Django no la considere "tocada"
                request.session.accessed = False
            except Exception:
                pass

        return response


class LoginRequiredMiddleware:
      def __init__(self, get_response):
            self.get_response = get_response

      def __call__(self, request):
            if not request.user.is_authenticated:
                  url_name = getattr(request.resolver_match, 'url_name', None)
                  
                  # Permitir login y logout sin redirección
                  if url_name in ['login', 'logout']:
                        return self.get_response(request)
                  
                  login_url = reverse('login')
                  home_url = reverse('home')
                  
                  # Evitar bucle infinito si ya está en login
                  if request.get_full_path().startswith(login_url):
                        return self.get_response(request)
                  
                  # Obtener la ruta original
                  next_path = request.get_full_path()
                  
                  # SOLUCIÓN: Filtrar rutas que NO queremos como next
                  # Si la ruta es logout, vacía, o es una ruta de autenticación, redirigir a home
                  rutas_no_permitidas = [
                        reverse('logout'),  # Ruta de logout
                        '/',                # Ruta raíz
                        login_url,          # Ruta de login
                  ]
                  
                  # Verificar si la URL actual es una ruta no permitida
                  if (url_name == 'logout' or 
                        not next_path or 
                        next_path in rutas_no_permitidas or
                        next_path.startswith(reverse('logout'))):
                        next_path = home_url
                  
                  # Redirigir al login con next
                  next_param = urlencode({'next': next_path})
                  return redirect(f"{login_url}?{next_param}")
      
            return self.get_response(request)