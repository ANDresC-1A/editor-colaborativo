"""
Script para crear usuarios y documentos de prueba.

Uso:
    python manage.py shell < setup_usuarios_prueba.py
o bien:
    python setup_usuarios_prueba.py   (requiere DJANGO_SETTINGS_MODULE configurado)

Crea:
    - 3 usuarios: alice / bob / charlie (contraseña: clave123)
    - Un documento propiedad de alice, compartido con bob (editor) y charlie (lector)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')
django.setup()

from django.contrib.auth.models import User
from editor.models import Documento, PermisoDocumento

USUARIOS_PRUEBA = [
    ('alice', 'alice@example.com', 'clave123'),
    ('bob', 'bob@example.com', 'clave123'),
    ('charlie', 'charlie@example.com', 'clave123'),
]

usuarios = {}
for username, email, password in USUARIOS_PRUEBA:
    usuario, creado = User.objects.get_or_create(username=username, defaults={'email': email})
    if creado:
        usuario.set_password(password)
        usuario.save()
        print(f"✓ Usuario creado: {username} / {password}")
    else:
        print(f"· Usuario ya existía: {username}")
    usuarios[username] = usuario

alice, bob, charlie = usuarios['alice'], usuarios['bob'], usuarios['charlie']

documento, creado = Documento.objects.get_or_create(
    titulo='Proyecto colaborativo',
    propietario=alice,
    defaults={'contenido': 'Este es un documento de ejemplo para probar la edición colaborativa.'}
)
if creado:
    print(f"✓ Documento creado: {documento.titulo} (propietario: alice)")
else:
    print(f"· Documento ya existía: {documento.titulo}")

PermisoDocumento.objects.get_or_create(
    documento=documento, usuario=bob,
    defaults={'puede_editar': True, 'compartido_por': alice}
)
print("✓ Compartido con bob (Editor)")

PermisoDocumento.objects.get_or_create(
    documento=documento, usuario=charlie,
    defaults={'puede_editar': False, 'compartido_por': alice}
)
print("✓ Compartido con charlie (Solo lectura)")

print("\nListo. Usuarios de prueba: alice, bob, charlie — contraseña: clave123")
