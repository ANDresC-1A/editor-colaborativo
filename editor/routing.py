from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/documento/(?P<doc_id>\w+)/$', consumers.DocumentoConsumer.as_asgi()),
]