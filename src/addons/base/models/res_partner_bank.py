"""``res.partner.bank`` — la cuenta bancaria de un contacto (Odoo ``base``).

Adaptación de Odoo ``odoo/addons/base/models/res_bank.py`` (clase
``ResPartnerBank``, odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso
de licencia preservados (DEC-KX-03).

Vive en ``base`` porque es donde la referencia lo declara, junto a ``res.bank``
(la institución, ya portada en ``res_bank.py``). La distinción que ya anticipaba
el docstring de aquél: el **banco** es la institución con su BIC; la **cuenta**
es el número que un contacto tiene en ella.

``account`` lo **extiende** con 11 campos más (diario asociado, avisos de IBAN y
de transferencia de dinero, rangos de proveedor/cliente del contacto, asientos
relacionados, detección de duplicados). Esa extensión es alcance de la Ola B —
medido: de los 19 campos que ``odoo19c: account/models/res_partner_bank.py``
declara, **11 son nuevos y 8 son re-declaraciones** de los que están aquí (el
idioma ``_name`` + ``_inherit`` de sí mismo de Odoo 19 obliga a re-listarlos).

Divergencias declaradas (DEC-KX-03)
====================================

1. **``company`` no se porta.** La referencia lo deriva:
   ``company_id = related='partner_id.company_id'`` (odoo19c: res_bank.py:101).
   Nuestro ``ResPartner`` **no tiene esa FK** — verificado: declara
   ``is_company`` (booleano: empresa vs persona) y ``company_name`` (Char), que
   son otra cosa. Fabricar aquí una FK directa a ``ResCompany`` daría un campo
   que puede divergir de la empresa del contacto, que es exactamente el drift
   que la referencia evita derivándolo. Se omite y se declara: **DESCONOCIDO
   con condición de cierre** — entra cuando ``res.partner`` porte su superficie
   multi-empresa. Registrado como la tarea #139.

2. **``acc_type`` se porta como columna, no como ``compute``.** En la
   referencia es un ``Selection`` calculado por ``retrieve_acc_type()``, un
   método pensado para que un addon lo sobreescriba: ``base`` devuelve siempre
   ``'bank'`` y ``base_iban`` lo cambia a ``'iban'`` cuando el número valida
   como IBAN (odoo19c: res_bank.py:135-139). ``base_iban`` es la **Ola 0 · T-06**
   y todavía no está portado, así que el punto de extensión se preserva como
   método de clase ``retrieve_acc_type()`` —sobreescribible igual que en la
   referencia— y el campo se rellena en ``save()``.

3. **``bank_name``/``bank_bic``/``country_code`` no se portan como columna.**
   Son ``related=`` de la referencia — proyecciones de un join, no dato propio.
   Se navegan por la FK (``cuenta.bank.name``, ``cuenta.partner.country.code``).
   Mismo criterio que los ``related`` de ``account.report.external.value``.

4. **``color`` no se porta.** Es ``compute`` sin ``store`` (odoo19c:
   res_bank.py:104): un índice de paleta para el cliente web de Odoo, que este
   producto no tiene.
"""
import fields
import models
from tools.translate import _


def sanitize_account_number(acc_number):
    """Deja sólo alfanuméricos y en mayúsculas — fiel a la referencia.

    ``odoo19c: odoo/addons/base/models/res_bank.py`` la define a nivel de
    módulo y la usa en el ``compute`` de ``sanitized_acc_number`` y en el
    ``search`` de ``acc_number``. Es lo que permite que ``ES91 2100 0418 45``
    y ``es9121000418-45`` se reconozcan como la misma cuenta.
    """
    if not acc_number:
        return ''
    return ''.join(ch for ch in acc_number if ch.isalnum()).upper()


def _supported_account_types():
    """Vocabulario de ``acc_type`` — ≙ el ``selection=lambda`` de la referencia.

    ``odoo19c: res_bank.py:89`` declara el campo como
    ``Selection(selection=lambda x: x.env['res.partner.bank']
    .get_supported_account_types())``. Django acepta un invocable en
    ``choices`` (``django.utils.choices.CallableChoiceIterator``), así que la
    forma se conserva: la lista se resuelve en cada validación, no al importar
    el módulo — que es lo que permite a ``base_iban`` añadir ``iban`` desde su
    ``ready()``, después de que esta clase ya existe.

    Se declara a nivel de módulo porque una referencia a ``ResPartnerBank``
    dentro del cuerpo de la propia clase no resuelve; aquí el nombre se busca
    al invocar, no al definir.
    """
    return ResPartnerBank.get_supported_account_types()


class ResPartnerBank(models.Model):
    """``res.partner.bank`` — cuenta bancaria de un contacto."""

    acc_number = fields.Char(
        max_length=64,
        help_text='Número de cuenta tal como lo escribió el usuario (Odoo '
                  'acc_number, requerido).',
    )
    sanitized_acc_number = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        help_text='``acc_number`` sin separadores y en mayúsculas. Es la '
                  'columna que hace única la cuenta y por la que se busca — '
                  'sin ella, el mismo IBAN escrito con y sin espacios serían '
                  'dos cuentas distintas (Odoo sanitized_acc_number).',
    )
    acc_type = fields.Selection(
        max_length=16, default='bank', choices=_supported_account_types,
        help_text='Tipo inferido del número: ``bank`` en el núcleo, ``iban`` '
                  'cuando base_iban lo valide (Odoo acc_type; ver '
                  'divergencia 2).',
    )
    clearing_number = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número de compensación, donde el país lo usa (Odoo '
                  'clearing_number).',
    )
    acc_holder_name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Titular de la cuenta, cuando difiere del nombre del '
                  'contacto (Odoo acc_holder_name).',
    )
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.CASCADE,
        related_name='bank_accounts',
        help_text='Contacto titular de la cuenta (Odoo partner_id, requerido, '
                  'ondelete cascade).',
    )
    bank = fields.Many2one(
        'base.ResBank', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accounts',
        help_text='Institución donde está la cuenta (Odoo bank_id).',
    )
    currency = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_accounts',
        help_text='Divisa de la cuenta (Odoo currency_id).',
    )
    allow_out_payment = fields.Boolean(
        default=False,
        help_text='La cuenta puede usarse para pagos salientes. Default False '
                  'a propósito, fiel a la referencia: habilitar una cuenta '
                  'para enviar dinero es un acto deliberado (Odoo '
                  'allow_out_payment).',
    )
    sequence = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Cuenta vigente; desactivar la archiva sin borrarla (Odoo '
                  'active).',
    )
    note = fields.Text(
        blank=True, default='', help_text='Notas libres (Odoo note).',
    )

    class Meta:
        db_table = 'res_partner_bank'
        ordering = ['sequence', 'id']
        constraints = [
            # odoo19c: res_bank.py:106-109 — _unique_number. Va sobre el
            # numero SANEADO, no sobre acc_number: es lo que impide registrar
            # dos veces la misma cuenta escrita distinto.
            models.UniqueConstraint(
                fields=['sanitized_acc_number', 'partner'],
                name='unique_partner_bank_account',
            ),
        ]

    @classmethod
    def get_supported_account_types(cls):
        """Vocabulario público de ``acc_type`` — ≙ ``odoo19c: res_bank.py:81``.

        La referencia separa el método público del que los addons
        sobreescriben; se conserva la separación para que un addon extienda
        ``_get_supported_account_types`` sin tocar el punto de consumo.
        """
        return cls._get_supported_account_types()

    @classmethod
    def _get_supported_account_types(cls):
        """Los tipos que el núcleo reconoce — ≙ ``odoo19c: res_bank.py:85``.

        Punto de extensión acumulativo: ``base_iban`` le añade ``iban`` con
        ``chain_method(..., combine=extend_list)``.
        """
        return [('bank', _('Normal'))]

    @classmethod
    def retrieve_acc_type(cls, acc_number):
        """Tipo de cuenta inferido del número.

        Punto de extensión, igual que en la referencia (``odoo19c:
        res_bank.py:135-139``, con su comentario *"To be overridden by
        subclasses in order to support other account_types"*): el núcleo
        devuelve siempre ``bank``, y ``base_iban`` (Ola 0 · T-06) lo cambia a
        ``iban`` cuando el número valida.
        """
        return 'bank'

    def save(self, *args, **kwargs):
        """Deriva las dos columnas que la referencia calcula sobre el número.

        Son ``compute`` con ``store=True`` en la referencia y dependen sólo de
        ``acc_number`` — un campo de la propia fila. Por eso sí se recalculan
        en ``save()``, a diferencia de los ``compute`` que cruzan a otra fila
        (criterio de ``account_reconcile_model.py``, divergencia 4).
        """
        self.sanitized_acc_number = sanitize_account_number(self.acc_number)
        self.acc_type = self.retrieve_acc_type(self.acc_number)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.acc_number or ''
