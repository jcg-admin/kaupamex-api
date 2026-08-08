"""``account.bank.statement.line`` — lo que ``account_payment`` le cuelga
(≙ ``_inherit``). **0 de 1 símbolo portado.**

Adaptación de ``odoo19c: account_payment/models/account_bank_statement_line.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 15 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

No portado (declarado, no improvisado)
=========================================

- **``_get_partial_amounts``** — bloquea la conciliación parcial de un
  apunte bancario cuando el pago viene de un proveedor o es
  ISO20022/SEPA (``re.match(r"^iso20022.*|^sepa_ct$",
  payment.payment_method_code)`` o ``payment.payment_transaction_id``).
  Dos bloqueos, ninguno construible aquí:

  1. **El método base no existe.** ``api: account/models/
     account_bank_statement_line.py`` (medido: ``grep -n
     "_get_partial_amounts"`` → 0 hits) no declara
     ``_get_partial_amounts`` — no hay ``super()`` que envolver ni
     comportamiento de conciliación parcial que interceptar.
  2. **El campo que se lee no existe.** ``payment_method_code`` es
     ``related='payment_method_line_id.code'`` en la referencia;
     ``account.AccountPayment`` (``api:
     account/models/account_payment.py``, 9 campos, medido) no declara
     ``payment_method_line`` — mismo hueco que documentan
     ``models/account_payment.py`` y ``models/payment_provider.py`` para
     el resto del addon. ``payment_transaction_id`` **sí** se porta (ver
     ``models/account_payment.py``, propiedad ``payment_transaction``),
     pero no basta solo: la condición original es un ``or`` entre AMBAS
     señales, y la primera falta.

  Condición de cierre: cuando ``account.payment`` tenga
  ``payment_method_line`` (ver la condición de cierre ya declarada en
  ``models/account_payment.py``), este archivo puede portarse completo con
  la mitad que hoy falta.
"""
