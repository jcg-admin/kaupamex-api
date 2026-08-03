"""Helper transversal de jerarquías — anti-ciclo de ancestros.

Adaptación de proyecto (NO es un modelo de Odoo): ``_reject_hierarchy_cycle``
implementa la invariante "un nodo no puede ser su propio ancestro" sobre una
``Many2one`` reflexiva. Vivía en ``platform/models.py`` (DIS-04), donde lo
usaban ``Subsidiary`` y ``Department``. Al re-hogar ``Department`` al addon
``hr`` (``hr.department``), el helper quedaría usado por dos addons distintos;
se extrae aquí —a ``base``, dependencia común de ambos— para no duplicarlo
(D-4 de ``analisis-porte-familia-hr``).
"""
from django.core.exceptions import ValidationError


def _reject_hierarchy_cycle(node, fk_name, error_code):
    """Rechaza que ``node`` sea su propio ancestro por ``fk_name`` (DIS-04).

    Recorre la cadena de padres; si vuelve a ``node`` (o a sí mismo), lanza
    ``ValidationError`` con ``error_code`` en inglés (canon ``codigo_error``).
    Nodos aún sin pk (creación) no pueden cerrar un ciclo salvo auto-padre.
    """
    parent = getattr(node, fk_name, None)
    if parent is None:
        return
    if parent.pk is not None and parent.pk == node.pk:
        raise ValidationError({fk_name: error_code})
    seen = set()
    while parent is not None:
        if parent.pk == node.pk:
            raise ValidationError({fk_name: error_code})
        if parent.pk in seen:
            break
        seen.add(parent.pk)
        parent = getattr(parent, fk_name, None)
