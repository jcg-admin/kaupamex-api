"""
Tests — Returns endpoints (UC-RET-01..06): retirado, la superficie REST no existe.

Probaba ``/api/v2/returns/`` (comprador) y ``/api/v2/admin/returns/``
(cola admin: aprobar/rechazar/pedir info/recepción/reembolso). La familia
``returns`` se disolvió en ``stock`` (``ReturnRequest``/``ReturnItem``/
``ReturnHistoryEntry``/``ReturnEvidence`` viven en
``src/addons/stock/models/return_request.py``), pero **sólo los modelos**
viajaron — el addon ``stock`` no tiene ``views.py``/``serializers.py``/
``urls.py`` en absoluto (verificado: ``find src/addons/stock -iname views.py
-o -iname urls.py`` → vacío). No hay ninguna ruta ``/return-requests/`` ni
``/returns/`` registrada en ningún ``urls.py`` del árbol.

La cobertura de modelo (estado, soft-delete, historial) sigue viva en
``test_soft_delete_returnrequest.py``. Este módulo se reescribe cuando el RMA
tenga su capa REST — es una decisión estructural pendiente, no un bug de
reconexión de imports.
"""
