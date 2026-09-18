from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from editor.models import Documento, PermisoDocumento, VersionDocumento


class UsuariosTests(TestCase):
    def test_registro_exitoso(self):
        resp = self.client.post(reverse('register'), {
            'username': 'nuevo', 'email': 'nuevo@example.com',
            'password': 'clave123', 'password2': 'clave123',
        })
        self.assertRedirects(resp, reverse('dashboard'))
        self.assertTrue(User.objects.filter(username='nuevo').exists())

    def test_registro_contrasenas_no_coinciden(self):
        resp = self.client.post(reverse('register'), {
            'username': 'nuevo', 'email': 'nuevo@example.com',
            'password': 'clave123', 'password2': 'otra456',
        })
        self.assertFalse(User.objects.filter(username='nuevo').exists())
        self.assertEqual(resp.status_code, 200)

    def test_registro_usuario_vacio(self):
        resp = self.client.post(reverse('register'), {
            'username': '', 'email': 'nuevo@example.com',
            'password': 'clave123', 'password2': 'clave123',
        })
        self.assertEqual(User.objects.count(), 0)

    def test_registro_usuario_existente(self):
        User.objects.create_user('alice', 'alice@example.com', 'clave123')
        resp = self.client.post(reverse('register'), {
            'username': 'alice', 'email': 'otro@example.com',
            'password': 'clave123', 'password2': 'clave123',
        })
        self.assertEqual(User.objects.filter(username='alice').count(), 1)

    def test_login_exitoso(self):
        User.objects.create_user('alice', 'alice@example.com', 'clave123')
        resp = self.client.post(reverse('login'), {'username': 'alice', 'password': 'clave123'})
        self.assertRedirects(resp, reverse('dashboard'))

    def test_login_usuario_inexistente(self):
        resp = self.client.post(reverse('login'), {'username': 'nadie', 'password': 'clave123'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_login_password_incorrecta(self):
        User.objects.create_user('alice', 'alice@example.com', 'clave123')
        resp = self.client.post(reverse('login'), {'username': 'alice', 'password': 'incorrecta'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_logout(self):
        user = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.client.force_login(user)
        resp = self.client.get(reverse('logout'))
        self.assertRedirects(resp, reverse('login'))


class DocumentosTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        self.client.force_login(self.alice)

    def test_crear_documento(self):
        resp = self.client.post(reverse('crear_documento'), {'titulo': 'Mi doc', 'contenido': 'hola'})
        doc = Documento.objects.get(titulo='Mi doc')
        self.assertRedirects(resp, reverse('documento', args=[doc.id]))
        self.assertEqual(doc.propietario, self.alice)

    def test_crear_documento_titulo_vacio_usa_default(self):
        self.client.post(reverse('crear_documento'), {'titulo': '   ', 'contenido': ''})
        self.assertTrue(Documento.objects.filter(titulo='Documento sin título').exists())

    def test_ver_documento_propio(self):
        doc = Documento.objects.create(titulo='D', contenido='x', propietario=self.alice)
        resp = self.client.get(reverse('documento', args=[doc.id]))
        self.assertEqual(resp.status_code, 200)

    def test_ver_documento_sin_permiso(self):
        doc = Documento.objects.create(titulo='D', contenido='x', propietario=self.bob)
        resp = self.client.get(reverse('documento', args=[doc.id]))
        self.assertRedirects(resp, reverse('dashboard'))

    def test_ver_documento_inexistente(self):
        resp = self.client.get(reverse('documento', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_eliminar_documento_propietario(self):
        doc = Documento.objects.create(titulo='D', contenido='x', propietario=self.alice)
        resp = self.client.post(reverse('eliminar_documento', args=[doc.id]))
        self.assertRedirects(resp, reverse('dashboard'))
        self.assertFalse(Documento.objects.filter(id=doc.id).exists())

    def test_eliminar_documento_no_propietario(self):
        doc = Documento.objects.create(titulo='D', contenido='x', propietario=self.bob)
        resp = self.client.post(reverse('eliminar_documento', args=[doc.id]))
        self.assertTrue(Documento.objects.filter(id=doc.id).exists())


class PermisosTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        self.charlie = User.objects.create_user('charlie', 'charlie@example.com', 'clave123')
        self.doc = Documento.objects.create(titulo='Doc', contenido='x', propietario=self.alice)

    def test_propietario_comparte_documento(self):
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('compartir_documento', args=[self.doc.id]), {
            'username': 'bob', 'puede_editar': 'on',
        })
        self.assertRedirects(resp, reverse('documento', args=[self.doc.id]))
        permiso = PermisoDocumento.objects.get(documento=self.doc, usuario=self.bob)
        self.assertTrue(permiso.puede_editar)

    def test_no_propietario_no_puede_compartir(self):
        PermisoDocumento.objects.create(documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice)
        self.client.force_login(self.bob)
        resp = self.client.post(reverse('compartir_documento', args=[self.doc.id]), {
            'username': 'charlie', 'puede_editar': 'on',
        })
        self.assertFalse(PermisoDocumento.objects.filter(usuario=self.charlie).exists())

    def test_compartir_usuario_inexistente(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('compartir_documento', args=[self.doc.id]), {
            'username': 'nadie', 'puede_editar': 'on',
        })
        self.assertEqual(PermisoDocumento.objects.filter(documento=self.doc).count(), 0)

    def test_cambiar_permiso_existente(self):
        permiso = PermisoDocumento.objects.create(documento=self.doc, usuario=self.bob, puede_editar=False, compartido_por=self.alice)
        self.client.force_login(self.alice)
        self.client.post(reverse('compartir_documento', args=[self.doc.id]), {
            'username': 'bob', 'puede_editar': 'on',
        })
        permiso.refresh_from_db()
        self.assertTrue(permiso.puede_editar)

    def test_revocar_permiso(self):
        permiso = PermisoDocumento.objects.create(documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice)
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('eliminar_permiso', args=[self.doc.id, permiso.id]))
        self.assertRedirects(resp, reverse('documento', args=[self.doc.id]))
        self.assertFalse(PermisoDocumento.objects.filter(id=permiso.id).exists())

    def test_editor_no_puede_revocar_permisos(self):
        PermisoDocumento.objects.create(documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice)
        permiso_charlie = PermisoDocumento.objects.create(documento=self.doc, usuario=self.charlie, puede_editar=False, compartido_por=self.alice)
        self.client.force_login(self.bob)
        self.client.post(reverse('eliminar_permiso', args=[self.doc.id, permiso_charlie.id]))
        self.assertTrue(PermisoDocumento.objects.filter(id=permiso_charlie.id).exists())


class HistorialTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        self.doc = Documento.objects.create(titulo='Doc', contenido='original', propietario=self.alice)
        self.version = VersionDocumento.objects.create(documento=self.doc, contenido='versión vieja', usuario=self.alice)

    def test_ver_historial(self):
        self.client.force_login(self.alice)
        resp = self.client.get(reverse('historial_documento', args=[self.doc.id]))
        self.assertEqual(resp.status_code, 200)

    def test_restaurar_version_propietario(self):
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('restaurar_version', args=[self.doc.id, self.version.id]))
        self.assertRedirects(resp, reverse('documento', args=[self.doc.id]))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.contenido, 'versión vieja')

    def test_restaurar_version_no_propietario_falla(self):
        PermisoDocumento.objects.create(documento=self.doc, usuario=self.bob, puede_editar=True, compartido_por=self.alice)
        self.client.force_login(self.bob)
        resp = self.client.post(reverse('restaurar_version', args=[self.doc.id, self.version.id]))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.contenido, 'original')


class BusquedaTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'clave123')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'clave123')
        Documento.objects.create(titulo='Informe anual', contenido='', propietario=self.alice)
        Documento.objects.create(titulo='Notas personales', contenido='', propietario=self.alice)
        self.doc_bob = Documento.objects.create(titulo='Proyecto secreto', contenido='', propietario=self.bob)

    def test_busqueda_por_titulo(self):
        self.client.force_login(self.alice)
        resp = self.client.get(reverse('dashboard'), {'q': 'informe'})
        self.assertContains(resp, 'Informe anual')
        self.assertNotContains(resp, 'Notas personales')

    def test_busqueda_respeta_permisos(self):
        self.client.force_login(self.alice)
        resp = self.client.get(reverse('dashboard'), {'q': 'secreto'})
        self.assertNotContains(resp, 'Proyecto secreto')
