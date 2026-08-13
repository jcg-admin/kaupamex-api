"""``controllers/`` de ``account_payment`` — **0 de 10 rutas portadas**.

La referencia trae dos archivos (``odoo19c: account_payment/controllers/
payment.py`` — 5 métodos, 153 líneas; ``odoo19c: account_payment/
controllers/portal.py`` — 5 métodos, 168 líneas). Los diez son rutas del
cliente **portal/website** de Odoo:

======================================  ==================================================
Símbolo de la referencia                 Por qué no tiene contraparte DRF
======================================  ==================================================
``PaymentPortal.invoice_transaction``    Ruta ``type='jsonrpc'`` autenticada por
                                          ``access_token`` de sesión anónima portal —
                                          este stack autentica con JWT de sesión
                                          (``HasCapability``), no hay concepto de token
                                          de acceso por documento.
``PaymentPortal.overdue_invoices_transaction``  Idem + agrupa facturas vencidas por
                                          ``get_next_batch_payment_communication()``,
                                          método de ``res.company`` no portado.
``PaymentPortal._process_transaction``   Helper interno de las dos anteriores.
``PaymentPortal.payment_pay`` (override) Renderiza el formulario de pago QWeb
                                          (``odoo.addons.payment``'s base route)
                                          — sin cliente web aquí.
``PaymentPortal._get_extra_payment_form_values``  Idem, valores para ese render.
``PortalAccount._invoice_get_page_view_values``   Render de la página portal de
                                          una factura (QWeb, ``request.render``).
``PortalAccount.portal_my_overdue_invoices``      Idem.
``PortalAccount._overdue_invoices_get_page_view_values``  Idem.
``PortalAccount._get_common_page_view_values``    Arma el contexto de render:
                                          ``payment.provider._get_compatible_
                                          providers``/``payment.method._get_
                                          compatible_payment_methods``/``payment.
                                          token._get_available_tokens`` — ninguno
                                          de los tres existe en este stack
                                          (``PaymentGateway``/``SavedCard`` no
                                          declaran ese álgebra de compatibilidad).
``PortalAccount.portal_my_invoice_detail`` (override)  Render portal.
======================================  ==================================================

Y el único flujo con valor de negocio real detrás de estas diez rutas
—"crear la transacción de pago de una factura"— está bloqueado río arriba:
``payment.Payment.sale_order`` es ``NOT NULL PROTECT`` (``api:
payment/models/payment.py:61-63``, H-API-97), así que
``_create_payment_transaction`` no es construible sin una orden de venta
(ver ``models/account_payment.py``, sección "No portado"). Aunque se
tradujera la superficie HTTP a DRF, no habría a qué método de negocio
llamar.

Condición de cierre: cuando exista (a) autenticación de sesión + capacidad
para "pagar una factura propia" equivalente a lo que ``payment/controllers/
portal.py`` ya construyó para órdenes de venta (``initiate_payment``/
``payment_status``/``payment_history``, ``api:
payment/controllers/portal.py``), Y (b) ``payment.Payment.sale_order`` deje
de ser obligatorio (decisión de producto), este paquete puede tener su
primera ruta real: un análogo de ``/invoice/transaction/<id>`` sobre
``POST /api/v2/payments/invoices/<id>/initiate/``.
"""
