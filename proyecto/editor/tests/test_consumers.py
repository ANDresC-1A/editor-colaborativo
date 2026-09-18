import json

from django.test import TestCase
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from editor.consumers import DocumentoConsumer, usuarios_conectados_por_documento
from editor.models import Documento, PermisoDocumento


class DocumentoConsumerTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        self.doc = Documento.objects.create(titulo='Doc', contenido='inicial', propietario=self.alice)
        usuarios_conectados_por_documento.clear()

    async def _conectar(self, user, doc_id=None):
        doc_id = doc_id or self.doc.id
        communicator = WebsocketCommunicator(DocumentoConsumer.as_asgi(), f'/ws/documento/{doc_id}/')
        communicator.scope['url_route'] = {'kwargs': {'doc_id': str(doc_id)}}
        communicator.scope['user'] = user
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_conexion_rechazada_sin_autenticacion(self):
        from django.contrib.auth.models import AnonymousUser
        communicator, connected = await self._conectar(AnonymousUser())
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_conexion_rechazada_sin_permiso(self):
        charlie = await database_sync_to_async(User.objects.create_user)('charlie', 'c@example.com', 'clave123')
        communicator, connected = await self._conectar(charlie)
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_propietario_se_conecta_y_recibe_contenido_inicial(self):
        communicator, connected = await self._conectar(self.alice)
        self.assertTrue(connected)
        respuesta = await communicator.receive_json_from()
        self.assertEqual(respuesta['tipo'], 'inicial')
        self.assertEqual(respuesta['contenido'], 'inicial')
        await communicator.disconnect()

    async def test_editor_puede_editar_y_se_guarda(self):
        await database_sync_to_async(PermisoDocumento.objects.create)(
            documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice
        )
        communicator, connected = await self._conectar(self.bob)
        self.assertTrue(connected)
        await communicator.receive_json_from()  # mensaje inicial

        await communicator.send_json_to({'tipo': 'update', 'contenido': 'nuevo contenido'})
        respuesta = await communicator.receive_json_from()
        self.assertEqual(respuesta['tipo'], 'guardado')

        doc = await database_sync_to_async(Documento.objects.get)(id=self.doc.id)
        self.assertEqual(doc.contenido, 'nuevo contenido')
        self.assertEqual(doc.ultimo_editor_id, self.bob.id)

        await communicator.disconnect()

    async def test_lector_no_puede_editar(self):
        await database_sync_to_async(PermisoDocumento.objects.create)(
            documento=self.doc, usuario=self.bob, puede_editar=False, compartido_por=self.alice
        )
        communicator, connected = await self._conectar(self.bob)
        self.assertTrue(connected)
        await communicator.receive_json_from()  # mensaje inicial

        await communicator.send_json_to({'tipo': 'update', 'contenido': 'intento no autorizado'})
        respuesta = await communicator.receive_json_from()
        self.assertEqual(respuesta['tipo'], 'error')

        doc = await database_sync_to_async(Documento.objects.get)(id=self.doc.id)
        self.assertEqual(doc.contenido, 'inicial')

        await communicator.disconnect()

    async def test_documento_inexistente_no_permite_conectar(self):
        communicator, connected = await self._conectar(self.alice, doc_id=99999)
        self.assertFalse(connected)
        await communicator.disconnect()
