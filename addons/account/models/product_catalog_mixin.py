r"""``product.catalog.mixin`` colgado por ``account`` — gestión de secciones del catálogo.

Adaptación de ``addons/account/models/product_catalog_mixin.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Siete símbolos, los siete portados.

Clase Python, no ``AbstractModel`` — mismo criterio que el mixin base
========================================================================

La referencia declara ``models.AbstractModel`` con ``_inherit =
'product.catalog.mixin'`` y **ningún campo** — sólo comportamiento. El propio
``product/models/product_catalog_mixin.py`` de este árbol ya fija la regla en
su docstring: *"mixin sólo de comportamiento → clase"*. Se sigue aquí: estas
siete funciones se cuelgan directo sobre la clase ``ProductCatalogMixin`` ya
portada, sin ``Meta``/``abstract=True`` propios.

**No es una extensión cross-app diferida en ``ready()``.**
``ProductCatalogMixin`` NO es un modelo Django (no hay resolución de FK por
string, no hay riesgo de ``AppRegistryNotReady``) — es una clase Python
importable en cualquier momento del import. Aun así se expone
``apply_account_extensions()`` con el mismo nombre que el resto del pase, por
uniformidad de wiring futuro (ver ``apply_account_extensions`` abajo).

Consumidor todavía sin cablear — medido antes de escribir
=============================================================

``odoo19c: account_move.py:74`` declara ``_inherit = [..., 'product.catalog
.mixin', 'account.document.import.mixin']``. Medido en este árbol
(``grep -n "ProductCatalogMixin\|AccountDocumentImportMixin"
addons/account/models/account_move.py`` → 0 hits): ``AccountMove`` **no**
incluye ninguno de los dos mixins todavía. Este archivo y
``account_document_import_mixin.py`` (mismo pase) quedan disponibles y
correctos, pero inertes hasta que ``AccountMove`` los declare como bases —
fuera del alcance de este porte (``account_move.py`` no está en la lista de
archivos a escribir). Sucesor: cablear ambos mixins en ``AccountMove``.

Odoo recordset → Django queryset, símbolo a símbolo
======================================================

``self[child_field].sorted('sequence')`` → ``getattr(self,
child_field).order_by('sequence')``; ``lines.filtered_domain([...])`` →
``.filter(...)``; ``line.get_parent_section_line()`` — la referencia lo
asume definido en el modelo de línea concreto (``sale.order.line``,
``account.move.line``…) y NO lo declara aquí tampoco: es un gancho que cada
modelo de línea con secciones debe aportar. Se documenta como precondición,
igual que hace el docstring de ``product/models/product_catalog_mixin.py``
con ``_get_product_catalog_lines_data``.
"""
from addons.product.models.product_catalog_mixin import ProductCatalogMixin


def _create_section(self, child_field, name, position, **kwargs):
    """≙ ``_create_section`` (``odoo19c: account/models/
    product_catalog_mixin.py:9-24``)."""
    parent_field = self._get_parent_field_on_child_model()
    if not parent_field:
        return {}

    lines = list(getattr(self, child_field).all().order_by('sequence'))
    line_manager = getattr(self, child_field)
    line_model = line_manager.model
    sequence = 10
    if lines:
        sequence = (
            lines[0].sequence - 1 if position == 'top'
            else lines[-1].sequence + 1
        )

    section = line_model.objects.create(**{
        parent_field: self.pk,
        'name': name,
        'display_type': 'line_section',
        'sequence': sequence,
        **self._get_default_create_section_values(),
    })

    return {'id': section.pk, 'sequence': section.sequence}


def _get_new_line_sequence(self, child_field, section_id):
    """≙ ``_get_new_line_sequence`` (``:26-46``)."""
    lines = list(getattr(self, child_field).all().order_by('sequence'))

    sequence = (lines[-1].sequence + 1) if lines else 10
    if section_id:
        section_found = False
        for line in lines:
            if line.display_type != 'line_section':
                continue
            if section_found:
                sequence = line.sequence
                break
            if line.pk == section_id:
                section_found = True
    else:
        section_lines = [l for l in lines if l.display_type == 'line_section']
        if section_lines:
            sequence = section_lines[0].sequence

    for line in [l for l in lines if l.sequence >= sequence]:
        line.sequence += 1
        line.save()

    return sequence


def _get_sections(self, child_field, **kwargs):
    """≙ ``_get_sections`` (``:48-71``)."""
    sections = {}
    no_section_count = 0
    lines = list(getattr(self, child_field).all().order_by('sequence'))
    for line in lines:
        if line.display_type == 'line_section':
            sections[line.pk] = {
                'id': line.pk,
                'name': line.name,
                'sequence': line.sequence,
                'line_count': 0,
            }
        elif self._is_line_valid_for_section_line_count(line):
            section_line = line.get_parent_section_line()
            sec_id = section_line.pk if section_line is not None else None
            if sec_id and sec_id in sections:
                sections[sec_id]['line_count'] += 1
            else:
                no_section_count += 1

    if no_section_count > 0 or not sections:
        sections[False] = {
            'id': False,
            'name': 'Sin sección',
            'sequence': (lines[0].sequence - 1) if lines else 0,
            'line_count': no_section_count,
        }

    return sorted(sections.values(), key=lambda x: x['sequence'])


def _get_default_create_section_values(self):
    """≙ ``_get_default_create_section_values`` (``:73-76``, terminal — sobreescribir)."""
    return {}


def _get_parent_field_on_child_model(self):
    """≙ ``_get_parent_field_on_child_model`` (``:78-81``, terminal — sobreescribir)."""
    return ''


def _is_line_valid_for_section_line_count(self, line):
    """≙ ``_is_line_valid_for_section_line_count`` (``:83-89``).

    ``product_type`` y ``quantity`` presuponen los campos de una línea de
    venta/compra (``sale.order.line``); ``account.move.line`` de este árbol
    no los declara todavía (medido: sólo ``quantity``, no ``product_type``,
    en ``account_move_line.py``). Se usa ``getattr`` con neutro fiel al
    sentido de cada comprobación: sin ``product_type`` no hay forma de saber
    si es un combo, así que no se descarta por eso (``!= 'combo'`` por
    defecto ``True``); sin ``quantity`` no hay línea que contar (``> 0``
    por defecto ``False``).
    """
    return (
        not line.display_type
        and getattr(line, 'product_type', None) != 'combo'
        and getattr(line, 'quantity', 0) > 0
    )


def _resequence_sections(self, sections, child_field, **kwargs):
    """≙ ``_resequence_sections`` (``:154-186``)."""
    lines = list(getattr(self, child_field).all().order_by('sequence'))
    move_section, target_section = sections

    move_block = [
        line for line in lines
        if line.pk == move_section['id']
        or getattr(line, 'parent_id', None) == move_section['id']
    ]
    target_block = [
        line for line in lines
        if line.pk == target_section['id']
        or getattr(line, 'parent_id', None) == target_section['id']
    ]

    remaining_lines = [line for line in lines if line not in move_block]
    insert_after = move_section['sequence'] < target_section['sequence']
    insert_index = len(remaining_lines)
    for idx, line in enumerate(remaining_lines):
        target_pk = (target_block[-1].pk if insert_after
                     else target_section['id'])
        if line.pk == target_pk:
            insert_index = idx + 1 if insert_after else idx
            break

    reordered_lines = (
        remaining_lines[:insert_index]
        + move_block
        + remaining_lines[insert_index:]
    )

    result_sections = {}
    for sequence, line in enumerate(reordered_lines, start=1):
        line.sequence = sequence
        line.save()
        if line.display_type == 'line_section':
            result_sections[line.pk] = sequence

    return result_sections


def apply_account_extensions():
    """Cuelga la gestión de secciones sobre ``ProductCatalogMixin`` — ≙ ``_inherit``.

    Setattr directo (no ``chain_method``): son símbolos nuevos que la clase
    base no declara, y ``ProductCatalogMixin`` no es un modelo Django con
    riesgo de timing de registro (ver el docstring del módulo).
    """
    for name, func in (
        ('_create_section', _create_section),
        ('_get_new_line_sequence', _get_new_line_sequence),
        ('_get_sections', _get_sections),
        ('_get_default_create_section_values', _get_default_create_section_values),
        ('_get_parent_field_on_child_model', _get_parent_field_on_child_model),
        ('_is_line_valid_for_section_line_count', _is_line_valid_for_section_line_count),
        ('_resequence_sections', _resequence_sections),
    ):
        if not hasattr(ProductCatalogMixin, name):
            setattr(ProductCatalogMixin, name, func)
