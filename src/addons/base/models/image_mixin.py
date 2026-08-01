"""Modelo abstracto ``image.mixin`` — imagen con sus cuatro derivadas.

Adaptación fiel de Odoo ``odoo/addons/base/models/image_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

**Qué hace la referencia.** Declara ``image_1920`` y cuatro campos
``related="image_1920"`` con ``store=True`` y un ``max_width``/``max_height``
decreciente: 1024, 512, 256, 128. El ORM de Odoo resuelve el redimensionado
dentro del tipo ``fields.Image``, así que el modelo no escribe código.

**Qué cambia aquí, y por qué.** Django no tiene un tipo de campo que
redimensione, así que el redimensionado se hace explícito en ``save()`` con
Pillow (ya declarado en ``pyproject.toml``). Los tamaños, los nombres de los
campos y la relación derivada→original son los de la referencia; sólo cambia
**quién** ejecuta el resize.

Segunda divergencia declarada: la referencia guarda las imágenes en **base64**
dentro de la columna (``fields.Image`` es un ``Binary`` con adjunto). Aquí son
``ImageField``, es decir archivos en el storage con la ruta en la columna. Es
la convención del árbol —el resto de modelos con imagen ya la usa— y evita
cargar un blob de 1920px en cada consulta.
"""
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image

# Los cuatro derivados y su lado mayor, verbatim de la referencia.
_DERIVED_SIZES = {
    'image_1024': 1024,
    'image_512': 512,
    'image_256': 256,
    'image_128': 128,
}


def _resize(source, box):
    """Reduce ``source`` para que quepa en un cuadrado de ``box`` px.

    Preserva la proporción, como ``max_width``/``max_height`` de la referencia:
    los dos límites son iguales, así que el resultado cabe en el cuadrado sin
    recortar. No amplía: una imagen menor que ``box`` se devuelve intacta.
    """
    source.open()
    img = Image.open(source)
    img.thumbnail((box, box), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format=img.format or 'PNG')
    return ContentFile(buf.getvalue())


class ImageMixin(models.Model):
    """Imagen original más sus cuatro reducciones (``image.mixin``).

    Las cuatro derivadas se **almacenan** —igual que el ``store=True`` de la
    referencia— porque recalcularlas por petición es caro y el consumidor
    (SPA) pide la que le cabe en pantalla.
    """

    image_1920 = models.ImageField(
        upload_to='images/original/', null=True, blank=True,
        verbose_name='Imagen',
        help_text='Odoo image_1920. Original; las derivadas salen de aquí.',
    )
    image_1024 = models.ImageField(
        upload_to='images/1024/', null=True, blank=True, editable=False,
        verbose_name='Imagen 1024',
    )
    image_512 = models.ImageField(
        upload_to='images/512/', null=True, blank=True, editable=False,
        verbose_name='Imagen 512',
    )
    image_256 = models.ImageField(
        upload_to='images/256/', null=True, blank=True, editable=False,
        verbose_name='Imagen 256',
    )
    image_128 = models.ImageField(
        upload_to='images/128/', null=True, blank=True, editable=False,
        verbose_name='Imagen 128',
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Regenera las derivadas cuando cambia el original.

        En la referencia esto no existe: el ``related`` + ``store`` del ORM lo
        resuelve. Aquí es explícito, y sólo corre si hay original — un registro
        sin imagen deja las cinco columnas vacías, como allá.
        """
        super().save(*args, **kwargs)
        if not self.image_1920:
            return
        changed = False
        for field, box in _DERIVED_SIZES.items():
            if getattr(self, field):
                continue
            name = self.image_1920.name.rsplit('/', 1)[-1]
            getattr(self, field).save(name, _resize(self.image_1920, box), save=False)
            changed = True
        if changed:
            super().save(update_fields=list(_DERIVED_SIZES))

    def _clear_derived_images(self):
        """Vacía las derivadas para forzar su regeneración en el próximo save."""
        for field in _DERIVED_SIZES:
            setattr(self, field, None)
