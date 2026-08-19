"""``account_peppol`` — enviar y recibir documentos por la red Peppol.

Adaptación de Odoo ``account_peppol`` (``odoo19c: addons/account_peppol/``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: el cliente del **proxy Peppol de Odoo S.A.** Peppol es la red europea
de facturación electrónica: una empresa se da de alta como participante, y a
partir de ahí envía y recibe facturas en formato BIS Billing 3.0 contra
cualquier otro participante. Este addon no habla el protocolo AS4 directamente
— habla con el proxy, que sí.

Layout — contra el de la referencia
=====================================

La referencia trae ``models/``, ``wizard/``, ``tools/``, ``controllers/``,
``exceptions.py``, ``data/``, ``demo/``, ``security/``, ``views/``,
``static/`` e ``i18n/``. Aquí:

- ``exceptions.py`` — **portado entero**: el catálogo de códigos de error del
  proxy (36 estándar + 43 ebMS) y sus cuatro funciones de despacho.
- ``tools/peppol_iap_connector.py`` — **portado entero**: las dos llamadas
  públicas al proxy (``can_connect``, ``create_connection``).
- ``tools/demo_utils.py`` — documentación: el arnés de demo depende de tres
  binarios de la referencia y del identificador externo de un cron.
- ``models/`` — 5 de 10 archivos instalan; los otros 5 son documentación con
  su desenlace medido. Ver ``models/__init__.py``.
- ``wizard/`` y ``controllers/`` — documentación; ver sus ``__init__.py``.
- ``data/`` (3 XML: crons, plantillas de correo, datos de contacto),
  ``demo/``, ``security/``, ``views/`` (5 XML), ``static/`` e ``i18n/`` —
  **no se portan**: capa de datos y cliente web de Odoo (criterio ya
  establecido en el árbol). Cada símbolo que dependía de uno de esos archivos
  lo declara en su docstring.

La arista con ``account_edi_ubl_cii`` — declarada, no resuelta
===============================================================

**Medido en la referencia**: ``peppol_eas``, ``peppol_endpoint``,
``invoice_edi_format`` y ``EAS_MAPPING`` los declara **``account_edi_ubl_cii``**
(``odoo19c: account_edi_ubl_cii/models/res_partner.py:43,51`` y
``.../account_edi_common.py:52``), no este addon. Ese addon **se está portando
en otro pase, en paralelo**, así que aquí **no se importa ni se declara en
``depends``**; cada símbolo que lo necesita queda marcado *BLOQUEADO por
``account_edi_ubl_cii``* y el orquestador reconcilia la arista al consolidar.

La consecuencia práctica, dicha sin adornos: con esta arista abierta el addon
**recibe y administra** (estado del participante, alta/baja, webhooks, crons,
verificación de contactos) pero **no envía** — la generación del UBL vive del
otro lado.

``post_init_hook`` — declarado y no portado
==============================================

``_account_peppol_post_init`` (``odoo19c: addons/account_peppol/__init__.py:9-14``)
hace dos cosas al instalar: sembrar el ``ir.default`` de
``peppol_verification_state`` por empresa, y poner el modo en ``demo`` si la
base está neutralizada. No se porta: ``IrDefault`` existe
(``src/addons/base/models/ir_default.py:145``) pero **sin un ``set()`` de
clase** (medido, 0 hits de ``def set(``), y ``database.is_neutralized`` no
tiene contraparte. Django tampoco tiene ``post_init_hook``: el precedente del
árbol es expresarlo como migración de datos
(``account_check_printing/migrations/0002_seed_check_payment_method.py``), y
las migraciones no son de este pase.

Dependencias externas — medidas contra ``uv.lock``
====================================================

+------------------+----------+------------------------------------------------+
| Paquete          | En lock  | Consecuencia                                   |
+==================+==========+================================================+
| ``requests``     | **sí**   | se usa (proxy y SMP)                           |
+------------------+----------+------------------------------------------------+
| ``lxml``         | **sí**   | se usa (dependencia directa, pyproject:52)     |
+------------------+----------+------------------------------------------------+
| ``phonenumbers`` | **no**   | ``_check_phonenumbers_import`` levanta, que es |
|                  |          | lo que la propia fuente especifica para ese    |
|                  |          | caso                                           |
+------------------+----------+------------------------------------------------+
| ``python-stdnum``| **no**   | ``PEPPOL_ENDPOINT_RULES`` queda vacío; sin     |
|                  |          | regla el endpoint se acepta, igual que la      |
|                  |          | fuente hace con un EAS sin regla               |
+------------------+----------+------------------------------------------------+

Este archivo NO importa ``models`` — el patrón local (``addons/utm``,
``addons/project_account``) deja el ``__init__.py`` raíz sin imports; las
extensiones corren en ``AccountPeppolConfig.ready()``.
"""
