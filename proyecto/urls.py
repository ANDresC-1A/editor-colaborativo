from django.contrib import admin
from django.urls import path
from editor import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Autenticación
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard y documentos
    path('dashboard/', views.dashboard, name='dashboard'),
    path('documento/nuevo/', views.crear_documento, name='crear_documento'),
    path('documento/<int:doc_id>/', views.documento, name='documento'),
    path('documento/<int:doc_id>/compartir/', views.compartir_documento, name='compartir_documento'),
    path('documento/<int:doc_id>/permiso/<int:permiso_id>/eliminar/', views.eliminar_permiso, name='eliminar_permiso'),
    path('documento/<int:doc_id>/eliminar/', views.eliminar_documento, name='eliminar_documento'),

    # Historial de versiones
    path('documento/<int:doc_id>/historial/', views.historial_documento, name='historial_documento'),
    path('documento/<int:doc_id>/version/<int:version_id>/', views.ver_version, name='ver_version'),
    path('documento/<int:doc_id>/version/<int:version_id>/restaurar/', views.restaurar_version, name='restaurar_version'),
]