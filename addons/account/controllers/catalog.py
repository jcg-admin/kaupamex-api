"""``catalog`` — secciones del catálogo de productos sobre una orden.

Adaptación de Odoo ``addons/account/controllers/catalog.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

Bloqueado por el controller padre de ``product`` (y por los métodos de
sección de las órdenes)
========================================================================

La referencia hereda de
``odoo.addons.product.controllers.catalog.ProductCatalogController`` — y
``addons/product/`` en este árbol **no tiene** directorio ``controllers/``
(medido: ``ls addons/product/`` → ``models``, ``migrations``, …). La clase
se porta sin ese padre; cuando el controller de ``product`` aterrice, esta
clase recupera la herencia sin cambiar sus métodos.

Los tres métodos delegan en ``_get_sections`` / ``_create_section`` /
``_resequence_sections`` del modelo de la orden — métodos que hoy ningún
modelo del árbol declara (medido: ``grep -rn "_get_sections" addons/`` →
0 hits). La resolución del modelo por su nombre de referencia
(``request.env[res_model]``) sí tiene contraparte —
``orm.registry.model_by_name`` — y se usa verbatim, así que cada método
compila hoy, resuelve el modelo, y falla en voz alta (``AttributeError``)
hasta que las órdenes declaren sus secciones.

Cuatro símbolos de la referencia (1 clase + 3 defs) — los tres defs se
portan con esa delegación; el ``with_company(order.company_id)`` de la
referencia (contexto multi-empresa del ORM Odoo) no tiene contraparte — la
empresa ya viaja en la fila de la orden (FK simple), divergencia declarada.
El cableado de URLs (``type='jsonrpc'``, ``auth='user'``) es del
orquestador (``urls.py`` queda fuera de este pase por directiva).
"""
from orm.registry import model_by_name


class ProductCatalogAccountController:
    """≙ ``ProductCatalogAccountController`` — sin el padre de ``product``
    (bloqueado; ver el docstring del módulo)."""

    def product_catalog_get_sections(self, request, res_model, order_id,
                                      child_field, **kwargs):
        """Return the sections which are in given order to be shown in the product catalog.

        :param string res_model: The order model.
        :param int order_id: The order id.
        :param string child_field: The field name of the lines in the order model.
        :rtype: list
        :return: A list of dictionaries containing section information with following structure:
            [
                {
                    'id': int,
                    'name': string,
                    'sequence': int,
                    'line_count': int,
                },
            ]

        (Docstring verbatim de la referencia.)"""
        model = model_by_name(res_model)
        order = model.objects.get(pk=order_id)
        return order._get_sections(child_field, **kwargs)

    def product_catalog_create_section(self, request, res_model, order_id,
                                        child_field, name, position,
                                        **kwargs):
        """Create a new section on the given order.

        :param string res_model: The order model.
        :param int order_id: The order id.
        :param string child_field: The field name of the lines in the order model.
        :param string name: The name of the section to create.
        :param str position: The position of the section where it should be created, either 'top'
                             or 'bottom'.
        :return: A dictionary with newly created section's 'id' and 'sequence'.
        :rtype: dict

        (Docstring verbatim de la referencia.)"""
        model = model_by_name(res_model)
        order = model.objects.get(pk=order_id)
        return order._create_section(child_field, name, position, **kwargs)

    def product_catalog_resequence_sections(self, request, res_model,
                                             order_id, sections, child_field,
                                             **kwargs):
        """Reorder the sections of a given order.

        param string res_model: The order model.
        :param int order_id: The order id.
        :param list sections:  A list of section dictionaries with their sequence.
        :param string child_field: The field name of the lines in the order model.
        :return: A dictionary with new sequences of the sections.
        :rtype: dict

        (Docstring verbatim de la referencia.)"""
        model = model_by_name(res_model)
        order = model.objects.get(pk=order_id)
        return order._resequence_sections(sections, child_field, **kwargs)
