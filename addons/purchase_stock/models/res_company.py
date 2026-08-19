"""``res.company`` — el plazo de confirmación de una orden de compra
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/res_company.py``
(``odoo19c: addons/purchase_stock/models/res_company.py``, 12 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
====================================

*Métrica:* entradas del cuerpo de ``class ResCompany`` contadas por AST sobre
la fuente. Son **2** con ``_inherit``; **1** sin él, que es el denominador que
aplica (``_inherit`` no es un símbolo a portar: aquí se expresa colgando de
``base.ResCompany``).
*Ciega a:* lo que la referencia declara para ``res.company`` en OTROS archivos
— ``stock`` y ``sale`` le cuelgan lo suyo y este conteo no los ve.

===============================================  =============================
Símbolo de la referencia                         Dónde queda en este puerto
===============================================  =============================
``ResCompany.days_to_purchase`` (``:10-12``)     campo homónimo, ``extend_model``
===============================================  =============================

``fields.Float`` de la referencia → ``fields.Float`` aquí (``FloatField``): el
valor es un número de días que admite fracción (``0.5`` = medio día), igual
que en la fuente. ``string='Days to Purchase'`` se traduce a ``help_text``
—este stack no expone etiquetas de vista XML— y el ``help`` de la fuente se
conserva verbatim dentro de él.
"""
from orm.model_classes import extend_model

import fields


def apply_purchase_stock_res_company_extensions():
    """Cuelga ``days_to_purchase`` sobre ``base.ResCompany`` — ≙ ``_inherit``.

    Par de Django (``'base', 'ResCompany'``) y no el nombre punteado: el
    modelo vive en ``src/addons/base/models/res_company.py`` y el orden de
    carga de los addons no garantiza que su fila del registro por nombre esté
    poblada cuando este módulo se importa (``H-API-577``).
    """
    extend_model(
        'base', 'ResCompany',
        campos={
            'days_to_purchase': fields.Float(
                default=0.0, null=True, blank=True,
                help_text='Días necesarios para confirmar una orden de '
                          'compra; define cuándo debería validarse '
                          '(Odoo days_to_purchase).',
            ),
        },
    )
