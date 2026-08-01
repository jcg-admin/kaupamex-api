"""``ir.model`` extendido por ``bus`` — las definiciones de modelo para el cliente.

Adaptación de ``addons/bus/models/ir_model.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 36 líneas). ``_get_model_definitions``
devuelve, por cada modelo pedido, sus campos con tipo y relación, para que el
cliente web sepa interpretar los registros que le llegan por el bus.

**No se porta el contenido**, por dos razones medidas y distintas:

1. Es la contraparte del WebSocket que DEC-AF-06 descarta: el cliente pide
   estas definiciones al suscribirse.
2. **Este árbol ya publica ese contrato por otra vía.** El esquema de lo que
   el cliente recibe es **OpenAPI**, generado por ``drf-spectacular`` y
   servido en ``/api/schema/`` — con ``@extend_schema`` en 354 puntos, medido
   en el skill ``backend-drf-spectacular``. Duplicarlo aquí daría dos
   descripciones del mismo contrato, y la segunda envejecería sin que nadie lo
   notara.

Nótese que ``ir.model`` **sí** está portado, y completo, en
``addons/base/models/ir_model.py``: lo que no se porta es esta **extensión**
del addon ``bus``, no el modelo.
"""
