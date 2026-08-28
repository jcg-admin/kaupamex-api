"""``res.bank`` — instituciones bancarias (Odoo ``base``).

Adaptación de ``odoo/addons/base/models/res_bank.py`` (Odoo Community, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03). El banco como
institución (con su BIC/SWIFT y dirección), distinto de la cuenta bancaria
(``res.partner.bank``, cuya validación IBAN vive en el addon ``base_iban``).

Cross-app: ``country`` → ``base.ResCountry``; ``state`` → ``base.ResCountryState``.

Ningún ``Char`` de aquí lleva tope
===================================

Los **6** ``fields.Char`` de ``odoo19c: odoo/addons/base/models/res_bank.py``
declarados en ``ResBank`` se escriben sin tamaño, así que la columna es un
``varchar`` sin límite. Los nuestros llevaban topes inventados —``name`` 128,
``bic`` 16, ``street`` 128, ``zip`` 24, ``email`` 254, ``phone`` 32— que la
fuente no impone.

Es el mismo defecto que :ref:`h-api-750` corrigió en ``ir_module.py``, en otro
archivo: el tope no se sube, se **retira**, porque este stack expresa
exactamente lo que la referencia tiene
(``supports_unlimited_charfield = True`` en el backend PostgreSQL de Django 6).

El de ``bic`` era el más peligroso de los seis: un BIC son 8 u 11 caracteres,
así que 16 parece holgado — hasta que alguien guarda uno con separadores o un
identificador local que no es BIC. El tope arbitrario no protege de nada; sólo
espera para truncar.

Qué NO se porta, con su medición
=================================

- **``country_code``** — ``related='country.code'``. Aquí el acceso a través de
  la FK (``bank.country.code``) da el mismo valor sin duplicar la columna, y un
  ``related`` almacenado es una copia que puede divergir del original. Se omite
  y se declara: el consumidor lee la FK.
- **``ResPartnerBank`` no vive en este archivo, y en la referencia sí.**
  ``odoo19c: odoo/addons/base/models/`` declara **un solo** archivo de banca
  —``res_bank.py``— con las **dos** clases dentro. Aquí la cuenta vive en
  ``res_partner_bank.py``, que en la referencia **existe pero en otros
  addons** (``account`` y ``hr``), donde aloja su *extensión*. Es el defecto de
  :ref:`h-api-578`: un archivo en una raíz espejada que la fuente no tiene, y
  aquí agravado porque el nombre ya significa otra cosa un addon más allá.

  BLOQUEADO por ``0021_alter_respartnerbank_acc_type`` — esa migración importa
  ``addons.base.models.res_partner_bank`` por ruta de módulo para resolver
  ``_supported_account_types``, así que mover la clase reescribe historia ya
  aplicada. Registrado como **#118**.
"""
import fields
import models

from addons.base.models.res_country import ResCountry, ResCountryState


class ResBank(models.Model):
    """``res.bank`` — banco (institución) con su BIC y dirección."""

    _name = 'res.bank'
    _description = 'Bank'
    _order = 'name, id'
    _rec_names_search = ['name', 'bic']

    name         = fields.Char(help_text='Nombre del banco (Odoo name).')
    bic          = fields.Char(
        blank=True, default='', db_index=True,
        help_text='Bank Identifier Code / SWIFT (Odoo bic). A veces se le '
                  'llama BIC o Swift.',
    )
    street       = fields.Char(blank=True, default='', help_text='Odoo street.')
    street2      = fields.Char(blank=True, default='', help_text='Odoo street2.')
    zip          = fields.Char(blank=True, default='', help_text='Odoo zip.')
    city         = fields.Char(blank=True, default='', help_text='Odoo city.')
    state        = fields.Many2one(
        ResCountryState, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='Estado/provincia (Odoo state).',
    )
    country      = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='País (Odoo country).',
    )
    email        = fields.Char(blank=True, default='', help_text='Odoo email.')
    phone        = fields.Char(blank=True, default='', help_text='Odoo phone.')
    active       = fields.Boolean(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'res_bank'
        # Derivado de _order.
        ordering = ['name', 'id']
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``odoo19c: res_bank.py:35-39``).

        El nombre del banco más su BIC, cuando lo tiene. Es lo que consume
        ``__str__``, que aquí es el equivalente del ``display_name`` de la
        fuente.
        """
        return (self.name or '') + (' - ' + self.bic if self.bic else '')

    @classmethod
    def _search_display_name(cls, operator, value):
        """≙ ``_search_display_name`` (``odoo19c: res_bank.py:41-48``).

        Buscar «BBVA» encuentra el banco por nombre; buscar «BBVAMX» lo
        encuentra por BIC. La fuente lo consigue con un dominio en ``|``, y la
        asimetría importa: el BIC se compara **por prefijo**
        (``=ilike value + '%'``) y el nombre **por contenido** (``ilike``).

        Un BIC es un código estructurado que se teclea desde el principio; un
        nombre no. Comparar el BIC por contenido devolvería bancos cuyo código
        contiene la cadena en medio, que no es lo que nadie busca.

        Devuelve un ``QuerySet``. Los dos operadores que la fuente atiende son
        ``ilike`` y ``not ilike``; cualquier otro delega —aquí, en el
        ``filter`` por nombre, que es lo que ``super()`` hace allá.
        """
        if not value:
            return cls.objects.all()
        matched = models.Q(bic__istartswith=value) | models.Q(name__icontains=value)
        if operator == 'not ilike':
            return cls.objects.exclude(matched)
        if operator == 'ilike':
            return cls.objects.filter(matched)
        return cls.objects.filter(name__icontains=value)

    @staticmethod
    def _sanitize_bic(value):
        """El BIC se guarda en mayúsculas, venga como venga.

        La fuente lo hace en ``create`` **y** en ``write``
        (``odoo19c: res_bank.py:50-60``) porque su ORM tiene dos entradas de
        escritura. Aquí las dos son ``save()``, así que la normalización vive
        una vez y ``save()`` la invoca: duplicarla para parecerse a la fuente
        crearía dos copias que pueden divergir.
        """
        return value.upper() if value else value

    def _onchange_country_id(self):
        """≙ ``_onchange_country_id`` (``odoo19c: res_bank.py:62-65``).

        Cambiar el país invalida el estado si ése pertenecía a otro. Sin esto,
        un banco puede quedar con «Jalisco» y país «Francia».
        """
        if self.country_id and self.country_id != (
                self.state.country_id if self.state is not None else None):
            self.state = None

    def _onchange_state(self):
        """≙ ``_onchange_state`` (``odoo19c: res_bank.py:67-70``).

        La dirección contraria: elegir un estado fija su país. La fuente lo
        hace sin condición sobre el país actual —el estado manda— y aquí igual.
        """
        if self.state is not None and self.state.country_id:
            self.country = self.state.country

    def save(self, *args, **kwargs):
        """``create`` y ``write`` de la fuente, que aquí son la misma entrada."""
        self.bic = self._sanitize_bic(self.bic)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self._compute_display_name()
