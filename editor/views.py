from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from .models import Documento, PermisoDocumento, VersionDocumento

def login_view(request):
    """Vista de login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        if not username or not password:
            messages.error(request, 'Debes ingresar usuario y contraseña')
            return render(request, 'editor/login.html', {'username': username})

        if not User.objects.filter(username=username).exists():
            messages.error(request, 'El usuario no existe')
            return render(request, 'editor/login.html', {'username': username})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Contraseña incorrecta')
            return render(request, 'editor/login.html', {'username': username})

    return render(request, 'editor/login.html')

def register_view(request):
    """Vista de registro"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''
        password2 = request.POST.get('password2') or ''

        contexto = {'username': username, 'email': email}

        # Validaciones (se comprueban en orden, mostrando un solo mensaje claro)
        if not username:
            messages.error(request, 'El nombre de usuario no puede estar vacío')
        elif not email:
            messages.error(request, 'El correo electrónico no puede estar vacío')
        elif not password or not password2:
            messages.error(request, 'Debes completar la contraseña y su confirmación')
        elif password != password2:
            messages.error(request, 'Las contraseñas no coinciden')
        elif len(password) < 6:
            messages.error(request, 'La contraseña debe tener al menos 6 caracteres')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
        else:
            # Crear usuario
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            messages.success(request, f'¡Cuenta creada exitosamente! Bienvenido {username}')
            return redirect('dashboard')

        return render(request, 'editor/register.html', contexto)

    return render(request, 'editor/register.html')

def logout_view(request):
    """Vista de logout"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('login')

@login_required
def dashboard(request):
    """Dashboard con documentos del usuario, con búsqueda opcional por título"""
    query = (request.GET.get('q') or '').strip()

    # Documentos propios
    documentos_propios = Documento.objects.filter(propietario=request.user)

    # Documentos compartidos conmigo
    documentos_compartidos = Documento.objects.filter(
        permisos__usuario=request.user
    ).distinct()

    if query:
        documentos_propios = documentos_propios.filter(titulo__icontains=query)
        documentos_compartidos = documentos_compartidos.filter(titulo__icontains=query)

    # Adjuntar el rol (Editor/Lector) a cada documento compartido para la plantilla
    documentos_compartidos = list(documentos_compartidos)
    for doc in documentos_compartidos:
        doc.rol = doc.rol_de(request.user)

    return render(request, 'editor/dashboard.html', {
        'documentos_propios': documentos_propios,
        'documentos_compartidos': documentos_compartidos,
        'query': query,
    })

@login_required
def crear_documento(request):
    """Crear nuevo documento"""
    if request.method == 'POST':
        titulo = (request.POST.get('titulo') or '').strip()
        contenido = request.POST.get('contenido', '')

        if not titulo:
            titulo = 'Documento sin título'

        documento = Documento.objects.create(
            titulo=titulo,
            contenido=contenido,
            propietario=request.user
        )
        messages.success(request, f'Documento "{titulo}" creado exitosamente')
        return redirect('documento', doc_id=documento.id)
    
    return render(request, 'editor/crear_documento.html')

@login_required
def documento(request, doc_id):
    """Vista del editor de documento"""
    doc = get_object_or_404(Documento, id=doc_id)
    
    # Verificar permisos
    if not doc.puede_ver(request.user):
        messages.error(request, 'No tienes permiso para ver este documento')
        return redirect('dashboard')
    
    # Verificar si puede editar
    puede_editar = doc.puede_editar(request.user)
    
    # Obtener usuarios con permisos
    permisos = PermisoDocumento.objects.filter(documento=doc).select_related('usuario')
    
    return render(request, 'editor/documento.html', {
        'documento': doc,
        'puede_editar': puede_editar,
        'es_propietario': doc.propietario == request.user,
        'permisos': permisos,
        'total_versiones': doc.versiones.count(),
    })

@login_required
def compartir_documento(request, doc_id):
    """Compartir documento con otro usuario"""
    doc = get_object_or_404(Documento, id=doc_id)
    
    # Solo el propietario puede compartir
    if doc.propietario != request.user:
        messages.error(request, 'Solo el propietario puede compartir este documento')
        return redirect('documento', doc_id=doc_id)
    
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        puede_editar = request.POST.get('puede_editar') == 'on'

        if not username:
            messages.error(request, 'Debes indicar un nombre de usuario')
            return redirect('documento', doc_id=doc_id)

        try:
            usuario = User.objects.get(username=username)
            
            # No compartir consigo mismo
            if usuario == request.user:
                messages.error(request, 'No puedes compartir el documento contigo mismo')
            else:
                # Crear o actualizar permiso
                permiso, created = PermisoDocumento.objects.get_or_create(
                    documento=doc,
                    usuario=usuario,
                    defaults={
                        'puede_editar': puede_editar,
                        'compartido_por': request.user
                    }
                )
                
                if not created:
                    permiso.puede_editar = puede_editar
                    permiso.save()
                    messages.success(request, f'Permisos actualizados para {username}')
                else:
                    messages.success(request, f'Documento compartido con {username}')
        
        except User.DoesNotExist:
            messages.error(request, f'El usuario "{username}" no existe')
        
        return redirect('documento', doc_id=doc_id)
    
    # GET: Listar todos los usuarios disponibles
    usuarios_disponibles = User.objects.exclude(id=request.user.id)
    
    return render(request, 'editor/compartir.html', {
        'documento': doc,
        'usuarios_disponibles': usuarios_disponibles,
    })

@login_required
def eliminar_permiso(request, doc_id, permiso_id):
    """Eliminar permiso de un usuario"""
    doc = get_object_or_404(Documento, id=doc_id)
    
    # Solo el propietario puede eliminar permisos
    if doc.propietario != request.user:
        messages.error(request, 'No tienes permiso para realizar esta acción')
        return redirect('documento', doc_id=doc_id)
    
    permiso = get_object_or_404(PermisoDocumento, id=permiso_id, documento=doc)
    username = permiso.usuario.username
    permiso.delete()
    
    messages.success(request, f'Permiso revocado para {username}')
    return redirect('documento', doc_id=doc_id)

@login_required
def eliminar_documento(request, doc_id):
    """Eliminar documento (solo propietario)"""
    doc = get_object_or_404(Documento, id=doc_id)
    
    if doc.propietario != request.user:
        messages.error(request, 'Solo el propietario puede eliminar este documento')
        return redirect('dashboard')
    
    if request.method == 'POST':
        titulo = doc.titulo
        doc.delete()
        messages.success(request, f'Documento "{titulo}" eliminado exitosamente')
        return redirect('dashboard')
    
    return render(request, 'editor/eliminar_documento.html', {'documento': doc})


@login_required
def historial_documento(request, doc_id):
    """Muestra el historial de versiones de un documento"""
    doc = get_object_or_404(Documento, id=doc_id)

    if not doc.puede_ver(request.user):
        messages.error(request, 'No tienes permiso para ver este documento')
        return redirect('dashboard')

    versiones = doc.versiones.select_related('usuario').all()

    return render(request, 'editor/historial.html', {
        'documento': doc,
        'versiones': versiones,
        'puede_restaurar': doc.puede_restaurar(request.user),
    })


@login_required
def ver_version(request, doc_id, version_id):
    """Muestra el contenido de una versión anterior sin restaurarla"""
    doc = get_object_or_404(Documento, id=doc_id)

    if not doc.puede_ver(request.user):
        messages.error(request, 'No tienes permiso para ver este documento')
        return redirect('dashboard')

    version = get_object_or_404(VersionDocumento, id=version_id, documento=doc)

    return render(request, 'editor/ver_version.html', {
        'documento': doc,
        'version': version,
    })


@login_required
def restaurar_version(request, doc_id, version_id):
    """Restaura el contenido de una versión anterior. Solo el propietario puede hacerlo."""
    doc = get_object_or_404(Documento, id=doc_id)

    if not doc.puede_restaurar(request.user):
        messages.error(request, 'Solo el propietario puede restaurar versiones')
        return redirect('documento', doc_id=doc_id)

    version = get_object_or_404(VersionDocumento, id=version_id, documento=doc)

    if request.method == 'POST':
        # Guardar el estado actual como una nueva versión antes de sobrescribir,
        # para no perder trabajo al restaurar
        VersionDocumento.objects.create(
            documento=doc,
            contenido=doc.contenido,
            usuario=request.user,
        )
        doc.contenido = version.contenido
        doc.ultimo_editor = request.user
        doc.save()
        messages.success(request, f'Documento restaurado a la versión del {version.fecha.strftime("%d/%m/%Y %H:%M")}')
        return redirect('documento', doc_id=doc_id)

    return render(request, 'editor/restaurar_version.html', {
        'documento': doc,
        'version': version,
    })