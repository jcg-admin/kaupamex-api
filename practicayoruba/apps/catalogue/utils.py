"""Upload path callables for catalogue media fields. UC-CAT-06, UC-CAT-09."""
import os


def category_upload_path(instance, filename):
    """Organizes category images by PK: categories/<pk>/<ext>."""
    _, ext = os.path.splitext(filename)
    pk = instance.pk if instance.pk else 'new'
    return f'categories/{pk}{ext.lower()}'


def product_image_upload_path(instance, filename):
    """Organizes product images by product PK: products/<product_pk>/<pk><ext>."""
    _, ext = os.path.splitext(filename)
    product_pk = instance.product_id if instance.product_id else 'new'
    img_pk = instance.pk if instance.pk else 'tmp'
    return f'products/{product_pk}/{img_pk}{ext.lower()}'
