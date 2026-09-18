import json
import logging
from datetime import timedelta

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import Documento

logger = logging.getLogger(__name__)

# Intervalo mínimo entre versiones guardadas en el historial para el mismo
# documento. Evita crear una fila de VersionDocumento en cada pulsación;
# el contenido en vivo (doc.contenido) se sigue guardando siempre.
INTERVALO_MIN_VERSION = timedelta(seconds=20)

# Registro en memoria de usuarios conectados por documento.
# NOTA: esto vive en memoria del proceso (coherente con CHANNEL_LAYERS
# InMemoryChannelLayer, sin Redis). Si se despliega con varios workers/procesos,
# esta lista dejaría de ser exacta entre procesos; para ese caso habría que
# migrar a channels-redis y guardar la presencia allí también.
usuarios_conectados_por_documento = {}


class DocumentoConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------
    # Ciclo de vida de la conexión
    # ------------------------------------------------------------------

    async def connect(self):
        self.doc_id = self.scope['url_route']['kwargs']['doc_id']
        self.room_group_name = f'documento_{self.doc_id}'

        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            logger.warning(f"❌ Intento de conexión sin autenticación al documento {self.doc_id}")
            await self.close()
            return

        puede_ver = await self.verificar_permisos_visualizacion()
        if not puede_ver:
            logger.warning(f"❌ Usuario {user.username} sin permisos para ver documento {self.doc_id}")
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Registrar presencia
        usuarios_conectados_por_documento.setdefault(self.room_group_name, set()).add(user.username)

        # Enviar estado inicial (contenido + quién está conectado ya)
        contenido = await self.get_documento_contenido()
        ultimo_editor, ultima_fecha = await self.get_ultimo_editor()
        await self.send(text_data=json.dumps({
            'tipo': 'inicial',
            'contenido': contenido,
            'usuarios_conectados': sorted(usuarios_conectados_por_documento[self.room_group_name]),
            'ultimo_editor': ultimo_editor,
            'ultima_modificacion': ultima_fecha,
        }))

        # Avisar a los demás que este usuario se conectó
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'documento_evento',
            'tipo': 'usuario_conectado',
            'usuario': user.username,
        })

        logger.info(f"✅ Usuario {user.username} conectado al documento {self.doc_id}")

    async def disconnect(self, close_code):
        user = self.scope.get('user')
        username = user.username if user and user.is_authenticated else None

        if username and self.room_group_name in usuarios_conectados_por_documento:
            usuarios_conectados_por_documento[self.room_group_name].discard(username)
            if not usuarios_conectados_por_documento[self.room_group_name]:
                del usuarios_conectados_por_documento[self.room_group_name]

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if username:
            await self.channel_layer.group_send(self.room_group_name, {
                'type': 'documento_evento',
                'tipo': 'usuario_desconectado',
                'usuario': username,
            })

        logger.info(f"❌ Usuario {username or 'Anónimo'} desconectado del documento {self.doc_id}")

    # ------------------------------------------------------------------
    # Mensajes entrantes
    # ------------------------------------------------------------------

    async def receive(self, text_data):
        try:
            user = self.scope.get('user')
            if not user or not user.is_authenticated:
                logger.warning(f"⚠️ Intento de edición sin autenticación en documento {self.doc_id}")
                return

            data = json.loads(text_data)
            tipo = data.get('tipo', 'update')

            if tipo == 'update':
                await self._manejar_update(user, data)
            elif tipo == 'editando':
                await self._manejar_editando(user, data)
            else:
                logger.debug(f"Mensaje de tipo desconocido recibido: {tipo}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error al decodificar JSON: {e}")
        except Exception as e:
            logger.error(f"❌ Error en receive: {e}", exc_info=True)

    async def _manejar_update(self, user, data):
        """Autoguardado: el cliente envía el contenido completo con debounce propio."""
        contenido = data.get('contenido', '')

        puede_editar = await self.verificar_permisos_edicion()
        if not puede_editar:
            logger.warning(f"⚠️ Usuario {user.username} sin permisos de edición en documento {self.doc_id}")
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'mensaje': 'No tienes permisos para editar este documento'
            }))
            return

        logger.info(f"📝 Usuario {user.username} guardando contenido en documento {self.doc_id}...")
        guardado, fecha = await self.save_documento_contenido(contenido, user)

        if not guardado:
            logger.warning("⚠️ No se pudo guardar el contenido")
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'mensaje': 'No se pudo guardar el documento'
            }))
            return

        logger.info(f"✅ Contenido guardado exitosamente ({len(contenido)} caracteres)")

        # Confirmar guardado al autor
        await self.send(text_data=json.dumps({
            'tipo': 'guardado',
            'fecha': fecha,
        }))

        # Propagar el nuevo contenido a todos (incluido el propio autor, para
        # mantener consistencia si hay varias pestañas abiertas)
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'documento_evento',
            'tipo': 'update',
            'contenido': contenido,
            'usuario': user.username,
            'fecha': fecha,
        })

    async def _manejar_editando(self, user, data):
        """Indicador de 'X está escribiendo...'. escribiendo=True/False."""
        escribiendo = bool(data.get('escribiendo', True))
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'documento_evento',
            'tipo': 'usuario_editando',
            'usuario': user.username,
            'escribiendo': escribiendo,
        })

    # ------------------------------------------------------------------
    # Reenvío de eventos de grupo -> WebSocket del cliente
    # ------------------------------------------------------------------

    async def documento_evento(self, event):
        """Handler genérico: reenvía cualquier evento de grupo tal cual al cliente,
        excepto el campo interno 'type' que usa Channels para el ruteo."""
        payload = {k: v for k, v in event.items() if k != 'type'}
        await self.send(text_data=json.dumps(payload))

    # ------------------------------------------------------------------
    # Acceso a base de datos
    # ------------------------------------------------------------------

    @database_sync_to_async
    def get_documento_contenido(self):
        try:
            doc = Documento.objects.get(id=self.doc_id)
            return doc.contenido
        except Documento.DoesNotExist:
            logger.warning(f"⚠️ Documento {self.doc_id} no existe")
            return ""
        except Exception as e:
            logger.error(f"❌ Error al cargar documento: {e}", exc_info=True)
            return ""

    @database_sync_to_async
    def get_ultimo_editor(self):
        try:
            doc = Documento.objects.get(id=self.doc_id)
            username = doc.ultimo_editor.username if doc.ultimo_editor else None
            return username, doc.actualizado.isoformat()
        except Documento.DoesNotExist:
            return None, None

    @database_sync_to_async
    def save_documento_contenido(self, contenido, user):
        """Guarda el contenido del documento y, si corresponde, una versión en el historial."""
        from .models import VersionDocumento
        try:
            doc = Documento.objects.get(id=self.doc_id)

            contenido_cambio = doc.contenido != contenido

            doc.contenido = contenido
            doc.ultimo_editor = user
            doc.save()

            if contenido_cambio:
                ultima_version = doc.versiones.first()
                crear_version = (
                    ultima_version is None or
                    (timezone.now() - ultima_version.fecha) > INTERVALO_MIN_VERSION
                )
                if crear_version:
                    VersionDocumento.objects.create(
                        documento=doc,
                        contenido=contenido,
                        usuario=user,
                    )

            logger.info(f"💾 Documento {self.doc_id} guardado: {len(contenido)} caracteres")
            return True, doc.actualizado.isoformat()
        except Documento.DoesNotExist:
            logger.warning(f"⚠️ No se puede guardar: Documento {self.doc_id} no existe")
            return False, None
        except Exception as e:
            logger.error(f"❌ Error al guardar: {e}", exc_info=True)
            return False, None

    @database_sync_to_async
    def verificar_permisos_edicion(self):
        try:
            from .models import PermisoDocumento
            user = self.scope.get('user')

            if not user or not user.is_authenticated:
                return False

            doc = Documento.objects.get(id=self.doc_id)

            if doc.propietario == user:
                return True

            return PermisoDocumento.objects.filter(
                documento=doc, usuario=user, puede_editar=True
            ).exists()

        except Documento.DoesNotExist:
            logger.error(f"❌ Documento {self.doc_id} no existe")
            return False
        except Exception as e:
            logger.error(f"❌ Error verificando permisos de edición: {e}", exc_info=True)
            return False

    @database_sync_to_async
    def verificar_permisos_visualizacion(self):
        try:
            from .models import PermisoDocumento
            user = self.scope.get('user')

            if not user or not user.is_authenticated:
                return False

            doc = Documento.objects.get(id=self.doc_id)

            if doc.propietario == user:
                return True

            return PermisoDocumento.objects.filter(documento=doc, usuario=user).exists()

        except Documento.DoesNotExist:
            logger.error(f"❌ Documento {self.doc_id} no existe para verificar visualización")
            return False
        except Exception as e:
            logger.error(f"❌ Error verificando permisos de visualización: {e}", exc_info=True)
            return False
