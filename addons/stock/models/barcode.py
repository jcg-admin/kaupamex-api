r"""``barcode.rule`` — los cuatro tipos de código de ``stock``: NO PORTADO.

Adaptación de Odoo ``stock/models/barcode.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 20 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03). El archivo entero de la referencia:

.. code-block:: python

    class BarcodeRule(models.Model):
        _inherit = 'barcode.rule'

        type = fields.Selection(selection_add=[
            ('weight', 'Weighted Product'),
            ('location', 'Location'),
            ('lot', 'Lot'),
            ('package', 'Package')
        ], ondelete={
            'weight': 'set default',
            'location': 'set default',
            'lot': 'set default',
            'package': 'set default',
        })

Un solo símbolo, y no declara nada nuevo: **amplía el vocabulario** del campo
``type`` de un modelo que vive en otro addon. Dice que, además de los tipos que
``barcodes`` conoce, un código escaneado puede designar un peso variable, una
ubicación, un lote o un paquete — las cuatro entidades que ``stock`` aporta al
almacén.

Por qué NO se porta — medido, no supuesto
==========================================

``barcode.rule`` es el modelo del addon **``barcodes``**, que no existe en este
árbol:

.. code-block:: text

    ls -d addons/barcodes            → No such file or directory
    grep -rln "barcode.rule\|BarcodeRule" addons/ src/ --include=*.py → 0

[PROVEN, medido en el pase que escribe este archivo.]

No es una divergencia de mecanismo: ``selection_add`` tiene equivalente aquí
—ampliar los ``choices`` de un campo existente— y el addon ``base`` ya construye
mecanismos comparables. Lo que falta es el **destino**: sin ``barcode.rule`` no
hay campo ``type`` cuyo vocabulario ampliar, y fabricar el modelo entero desde
``stock`` sería portar ``barcodes`` con otro nombre — el defecto de sitio que
:ref:`h-api-578` registra.

Este archivo existe, en vez de no existir, por el precedente que fija
``addons/account_check_printing/models/res_config_settings.py``: **un porte
bloqueado se declara donde la referencia lo declara**, con su medición y su
sucesor. Un archivo ausente no se distingue de un archivo olvidado.

Qué se pierde mientras tanto, exactamente
==========================================

Nada del dato de ``stock``: los cuatro tipos son etiquetas de **enrutado de
escaneo**, no columnas. Un lote sigue teniendo su ``ref``, una ubicación su
``barcode`` (``stock_location.py``), un paquete el suyo. Lo ausente es la
**tabla de reglas** que decide, ante una cadena escaneada, a cuál de las cuatro
entidades apunta.

Sucesor
========

Portar el addon ``barcodes`` — no está en el alcance de la tarea **#330**
(``stock`` completo), que cubre los 25 archivos de ``stock``. Registrado como
tarea **#386**; este archivo se completa en cuanto ``barcode.rule`` exista.
"""
