from django.test import TestCase
from django.contrib.auth.models import User
from editor.models import Documento, PermisoDocumento, VersionDocumento


class DocumentoModelTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        self.charlie = User.objects.create_user('charlie', 'charlie@example.com', 'clave123')
        self.doc = Documento.objects.create(titulo='Doc de prueba', contenido='hola', propietario=self.alice)

    def test_propietario_puede_ver_y_editar(self):
        self.assertTrue(self.doc.puede_ver(self.alice))
        self.assertTrue(self.doc.puede_editar(self.alice))
        self.assertEqual(self.doc.rol_de(self.alice), 'Propietario')

    def test_usuario_sin_permiso_no_puede_ver_ni_editar(self):
        self.assertFalse(self.doc.puede_ver(self.bob))
        self.assertFalse(self.doc.puede_editar(self.bob))
        self.assertIsNone(self.doc.rol_de(self.bob))

    def test_permiso_editor(self):
        PermisoDocumento.objects.create(
            documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice
        )
        self.assertTrue(self.doc.puede_ver(self.bob))
        self.assertTrue(self.doc.puede_editar(self.bob))
        self.assertEqual(self.doc.rol_de(self.bob), 'Editor')

    def test_permiso_lector(self):
        PermisoDocumento.objects.create(
            documento=self.doc, usuario=self.charlie, puede_editar=False, compartido_por=self.alice
        )
        self.assertTrue(self.doc.puede_ver(self.charlie))
        self.assertFalse(self.doc.puede_editar(self.charlie))
        self.assertEqual(self.doc.rol_de(self.charlie), 'Lector')

    def test_solo_propietario_puede_restaurar(self):
        PermisoDocumento.objects.create(
            documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice
        )
        self.assertTrue(self.doc.puede_restaurar(self.alice))
        self.assertFalse(self.doc.puede_restaurar(self.bob))

    def test_version_documento_se_puede_crear(self):
        version = VersionDocumento.objects.create(
            documento=self.doc, contenido='versión anterior', usuario=self.alice
        )
        self.assertEqual(self.doc.versiones.count(), 1)
        self.assertEqual(version.documento, self.doc)
