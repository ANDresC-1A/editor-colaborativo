from django.db import models
from django.contrib.auth.models import User

class Documento(models.Model):
    titulo = models.CharField(max_length=100)
    contenido = models.TextField(blank=True)
    propietario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documentos_propios')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    ultimo_editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documentos_editados_ultimo',
        help_text='Último usuario que modificó el contenido del documento'
    )

    def __str__(self):
        return f"{self.titulo} ({self.propietario.username})"
    
    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ['-actualizado']
    
    def puede_editar(self, usuario):
        """Verifica si un usuario puede editar este documento"""
        # El propietario siempre puede editar
        if self.propietario == usuario:
            return True
        # Verificar si tiene permiso compartido de escritura
        return PermisoDocumento.objects.filter(
            documento=self,
            usuario=usuario,
            puede_editar=True
        ).exists()
    
    def puede_ver(self, usuario):
        """Verifica si un usuario puede ver este documento"""
        # El propietario siempre puede ver
        if self.propietario == usuario:
            return True
        # Verificar si tiene algún permiso compartido
        return PermisoDocumento.objects.filter(
            documento=self,
            usuario=usuario
        ).exists()

    def puede_restaurar(self, usuario):
        """Solo el propietario puede restaurar versiones anteriores"""
        return self.propietario == usuario

    def rol_de(self, usuario):
        """Devuelve 'Propietario', 'Editor', 'Lector' o None"""
        if self.propietario == usuario:
            return 'Propietario'
        permiso = PermisoDocumento.objects.filter(documento=self, usuario=usuario).first()
        if permiso is None:
            return None
        return 'Editor' if permiso.puede_editar else 'Lector'


class PermisoDocumento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='permisos')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documentos_compartidos')
    puede_editar = models.BooleanField(default=False)
    compartido_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permisos_otorgados')
    fecha_compartido = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Permiso de Documento"
        verbose_name_plural = "Permisos de Documentos"
        unique_together = ['documento', 'usuario']
        ordering = ['-fecha_compartido']
    
    def __str__(self):
        permiso = "Editar" if self.puede_editar else "Solo lectura"
        return f"{self.documento.titulo} → {self.usuario.username} ({permiso})"


class VersionDocumento(models.Model):
    """Copia histórica del contenido de un documento, para poder revisarlo o restaurarlo."""
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='versiones')
    contenido = models.TextField(blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='versiones_creadas',
        help_text='Usuario que guardó esta versión'
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Versión de Documento"
        verbose_name_plural = "Versiones de Documentos"
        ordering = ['-fecha']

    def __str__(self):
        autor = self.usuario.username if self.usuario else 'Desconocido'
        return f"{self.documento.titulo} — v.{self.pk} por {autor}"