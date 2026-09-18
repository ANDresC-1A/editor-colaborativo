from django.contrib import admin
from .models import Documento, PermisoDocumento

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'propietario', 'creado', 'actualizado')
    search_fields = ('titulo', 'contenido', 'propietario__username')
    list_filter = ('propietario', 'creado')
    readonly_fields = ('creado', 'actualizado')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(propietario=request.user)

@admin.register(PermisoDocumento)
class PermisoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('documento', 'usuario', 'puede_editar', 'compartido_por', 'fecha_compartido')
    search_fields = ('documento__titulo', 'usuario__username')
    list_filter = ('puede_editar', 'fecha_compartido')
    readonly_fields = ('fecha_compartido',)