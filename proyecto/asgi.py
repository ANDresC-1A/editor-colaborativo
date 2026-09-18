import os
from django.core.asgi import get_asgi_application

# Importante: Django debe configurarse ANTES de importar channels
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')
django_asgi_app = get_asgi_application()

# Ahora sí, importar channels
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from editor.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})