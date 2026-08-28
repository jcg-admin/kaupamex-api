"""``res.currency.rate`` — historial de tipos de cambio (Odoo ``base``).

Adaptación de ``odoo/addons/base/models/res_currency.py`` (clase
``ResCurrencyRate``, Odoo Community, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03). Una fila = el tipo de cambio de una moneda en una
fecha para una empresa.

Cross-app (DEC-SALE-01): ``currency`` → ``base.ResCurrency``; ``company`` →
``base.ResCompany``.

El archivo NO está donde la referencia lo declara
==================================================

``odoo19c: odoo/addons/base/models/`` declara **un solo** archivo de moneda —
``res_currency.py``— con las **dos** clases dentro; aquí la tasa vive aparte.
Es el defecto de :ref:`h-api-578`, el mismo que ``res_bank.py`` registra para
``ResPartnerBank``. ``check_porte_completo`` lo reporta como CLASE FUERA DE
SITIO y seguirá haciéndolo hasta que se junten.

No se mueve en este pase: el movimiento arrastra migraciones que importan el
módulo por ruta, igual que el caso de ``res_partner_bank.py``. Registrado como
**#119**.

Las tres tasas son la misma cantidad vista desde tres lados
============================================================

La fuente declara ``rate``, ``company_rate`` e ``inverse_company_rate``, y sólo
la primera es columna: las otras dos son computadas **con inverso**, es decir,
se pueden leer y escribir, y escribir una reescribe ``rate``.

======================  ==============================================
Campo                   Qué expresa
======================  ==============================================
``rate``                unidades de ESTA moneda por 1 de la de tasa 1
``company_rate``        lo mismo, relativo a la moneda de la empresa
``inverse_company_rate``  su recíproco — cuántas de la empresa por 1 de ésta
======================  ==============================================

La distinción no es cosmética: quien captura una tasa piensa en una de las tres
formas según el mercado, y las tres tienen que llevar a la misma fila. Aquí las
dos derivadas son métodos (leer) más su inverso (escribir), no columnas: una
columna almacenada podría divergir de ``rate``, que es justo lo que el
``compute``/``inverse`` de la fuente evita.

Qué NO se porta, con su medición
=================================

- **``_get_view`` / ``_get_view_cache_key``** — infraestructura de vistas XML de
  Odoo. Sin análogo: este stack no tiene vistas declarativas.
- **``_search_display_name``** — su trabajo es parsear la fecha que el usuario
  teclea en el buscador (``parse_date``) antes de delegar. El parseo de entrada
  de usuario pertenece a la capa DRF, no al modelo; aquí un ``DateField`` recibe
  la fecha ya tipada. Divergencia de capa, declarada.
- **``create``/``write``** son un ``save()`` aquí; ``_sanitize_vals`` sí se
  porta, porque su lógica —qué campo gana cuando llegan dos de las tres tasas—
  es del dominio y no del ORM.

Dos divergencias medidas dentro de métodos que SÍ se portan
============================================================

Ninguna cambia el comportamiento observable **mientras la restricción
``rate > 0`` exista**; las dos se declaran porque el día que alguien la retire
sí lo cambiarían.

1. **La precedencia de ``_get_last_rates_for_companies``.** La fuente filtra
   ``x.rate and x.company_id == company or not x.company_id``, y en Python
   ``and`` liga más que ``or``: la condición real es
   ``(x.rate and x.company_id == company) or (not x.company_id)``. O sea, una
   tasa **global** entra aunque su ``rate`` sea 0 — y entonces el ``or 1`` del
   final la convierte en 1. Aquí el ``rate__gt=0`` se aplica a las dos ramas,
   así que una tasa global con 0 se salta y gana la anterior. La restricción de
   tabla hace la fila imposible, de modo que hoy los dos caminos coinciden.

2. **La guarda de división en ``_onchange_rate_warning``.** La fuente divide
   entre ``latest_rate.rate`` habiendo comprobado sólo que el recordset no esté
   vacío; con ``rate = 0`` reventaría. Aquí se comprueba también el valor. Mismo
   motivo: la restricción lo hace inalcanzable, y la guarda cuesta una condición.

Y una del ORM, sin efecto: la fuente indexa el diccionario de
``_get_last_rates_for_companies`` por **registro** de empresa y aquí por su PK.
El único consumidor es ``_divisor_for``, que usa la misma llave para escribir y
para leer.
"""
from decimal import Decimal

import fields
import models
from django.core.exceptions import ValidationError

from orm.environments import get_current_company


class ResCurrencyRate(models.Model):
    """``res.currency.rate`` — tipo de cambio de una moneda en una fecha."""

    _name = 'res.currency.rate'
    _description = "Currency Rate"
    _rec_names_search = ['name', 'rate']
    _order = "name desc, id"

    name         = fields.Date(
        db_index=True,
        help_text='Fecha del tipo de cambio (Odoo name, requerido).',
    )
    rate         = fields.Monetary(
        max_digits=24, decimal_places=12, default=Decimal('1.0'),
        help_text='Tasa por unidad de la moneda de tasa 1 (Odoo rate). Es la '
                  'ÚNICA de las tres que se almacena.',
    )
    currency     = fields.Many2one(
        'base.ResCurrency', on_delete=models.CASCADE, related_name='rates',
        db_index=True,
        help_text='Moneda (Odoo currency_id).',
    )
    company      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='currency_rates',
        null=True, blank=True,
        help_text='Empresa (Odoo company_id). Null = la tasa aplica a todas.',
    )

    class Meta:
        db_table = 'res_currency_rate'
        # Derivado de ``_order``: ``name desc, id``.
        ordering = ['-name', 'id']
        constraints = [
            # ≙ ``_unique_name_per_day`` (``odoo19c: res_currency.py:379-382``).
            models.UniqueConstraint(
                fields=['currency', 'company', 'name'],
                name='unique_currency_rate_per_day',
            ),
            # ≙ ``_currency_rate_check`` (``odoo19c: res_currency.py:383-386``),
            # objeto de tabla de la referencia. Su hogar aquí es
            # ``Meta.constraints`` con el nombre conservado
            # (``atributos-de-clase-de-modelo.md``).
            #
            # Una tasa de 0 no es «sin tasa»: hace que toda conversión que la
            # use dé 0 o reviente al invertirla. La restricción impide la fila,
            # que es lo que ningún método puede impedir.
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name='res_currency_rate_currency_rate_check',
                violation_error_message='El tipo de cambio debe ser estrictamente positivo.',
            ),
        ]
        verbose_name = 'Tipo de cambio'
        verbose_name_plural = 'Tipos de cambio'

    def _get_latest_rate(self):
        """≙ ``_get_latest_rate`` (``odoo19c: res_currency.py:404-412``).

        La última tasa **anterior** a la de esta fila, para la misma moneda y
        empresa. Es lo que da sentido a ``company_rate``: una tasa nueva se
        interpreta contra la que había.

        El ``< self.name`` es estricto en la fuente y aquí igual: la del mismo
        día es **esta**, no la anterior.
        """
        if not self.name:
            raise ValidationError(
                'La fecha de la tasa está vacía. Hay que ponerla.')
        company = self.company or self._current_company()
        return type(self).objects.filter(
            currency=self.currency_id,
            company=company,
            name__lt=self.name,
            rate__gt=0,
        ).order_by('name').last()

    @classmethod
    def _get_last_rates_for_companies(cls, companies):
        """≙ ``_get_last_rates_for_companies`` (``odoo19c: :414-421``).

        La última tasa de la moneda **de cada empresa**, indexada por empresa.
        Cae a 1 cuando no hay ninguna — que es lo correcto: sin tasa, la moneda
        de la empresa vale una unidad de sí misma.

        El filtro de la fuente es ``x.company_id == company or not
        x.company_id``: cuenta también la tasa **sin empresa**, que es la
        global. Se porta entero; quedarse sólo con la de la empresa haría que
        una instalación que sólo declara tasas globales midiera 1 siempre.
        """
        rates = {}
        for company in companies:
            if company is None:
                continue
            latest = cls.objects.filter(
                currency=company.currency_id,
                rate__gt=0,
            ).filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            ).order_by('name').last()
            rates[company.pk] = latest.rate if latest is not None else Decimal('1.0')
        return rates

    def _compute_rate(self):
        """≙ ``_compute_rate`` (``odoo19c: res_currency.py:423-425``).

        El default de la columna cuando nadie la fija: la tasa anterior, o 1.
        """
        if self.rate:
            return self.rate
        latest = self._get_latest_rate()
        return latest.rate if latest is not None else Decimal('1.0')

    def _compute_company_rate(self):
        """≙ ``_compute_company_rate`` (``odoo19c: res_currency.py:427-431``).

        La tasa relativa a la moneda de la empresa: ``rate`` dividido entre la
        última tasa de esa moneda. Con la moneda de la empresa como la de tasa
        1, el divisor es 1 y las dos coinciden — que es el caso de una
        instalación mono-divisa.
        """
        company = self.company or self._current_company()
        divisor = self._divisor_for(company)
        return self._compute_rate() / divisor

    def _inverse_company_rate(self, company_rate):
        """≙ ``_inverse_company_rate`` (``odoo19c: res_currency.py:433-437``).

        El lado de escritura: fijar ``company_rate`` reescribe ``rate``, que es
        la única columna. Devuelve el valor en vez de asignarlo — quien lo llama
        decide si guarda.
        """
        company = self.company or self._current_company()
        return Decimal(company_rate) * self._divisor_for(company)

    def _compute_inverse_company_rate(self):
        """≙ ``_compute_inverse_company_rate`` (``odoo19c: :439-443``).

        El recíproco de ``company_rate``. La fuente cae a 1 cuando la tasa de la
        empresa es falsa, y con eso evita la división por cero; aquí igual.
        """
        company_rate = self._compute_company_rate() or Decimal('1.0')
        return Decimal('1.0') / company_rate

    def _inverse_inverse_company_rate(self, inverse_company_rate):
        """≙ ``_inverse_inverse_company_rate`` (``odoo19c: :445-449``).

        El lado de escritura del recíproco, con la misma caída a 1.
        """
        value = Decimal(inverse_company_rate) or Decimal('1.0')
        return self._inverse_company_rate(Decimal('1.0') / value)

    def _onchange_rate_warning(self):
        """≙ ``_onchange_rate_warning`` (``odoo19c: res_currency.py:451-464``).

        Avisa —no rechaza— cuando la tasa nueva se aleja más de un 20 % de la
        anterior. Es la mitad de ``warning`` del ``onchange`` de la fuente, y
        aquí sí se porta: devuelve el diccionario, y el motor de avisos que le
        falta a ``ir.actions.server`` no hace falta porque el llamador es quien
        decide qué hacer con él.

        ``None`` = no hay nada que avisar.
        """
        latest = self._get_latest_rate()
        if latest is None or not latest.rate:
            return None
        difference = (latest.rate - self.rate) / latest.rate
        if abs(difference) <= Decimal('0.2'):
            return None
        return {
            'warning': {
                'title': f'Aviso para {self.currency.name}',
                'message': (
                    'La tasa nueva está bastante lejos de la anterior.\n'
                    'Un tipo de cambio incorrecto causa problemas críticos; '
                    'conviene verificarla.'
                ),
            },
        }

    def _check_company_id(self):
        """≙ ``_check_company_id`` (``odoo19c: res_currency.py:466-469``).

        Una tasa pertenece a una empresa **matriz**, nunca a una sucursal. La
        razón está en el modelo: una sucursal hereda la moneda de su raíz
        (``get_company_root_delegated_field_names``), así que una tasa colgada
        de ella describiría una moneda que no es suya.
        """
        if self.company is not None and self.company.parent_id:
            raise ValidationError(
                'Los tipos de cambio sólo se crean para empresas matrices.')

    @staticmethod
    def _sanitize_vals(vals):
        """≙ ``_sanitize_vals`` (``odoo19c: res_currency.py:388-393``).

        Cuál de las tres tasas gana cuando llegan varias. El orden de la fuente
        es explícito y se porta verbatim: ``rate`` gana sobre ``company_rate``,
        y ``company_rate`` sobre ``inverse_company_rate``.

        Es lógica de dominio, no del ORM — por eso se porta aunque
        ``create``/``write`` sean un ``save()`` aquí.
        """
        vals = dict(vals)
        if 'inverse_company_rate' in vals and (
                'company_rate' in vals or 'rate' in vals):
            del vals['inverse_company_rate']
        if 'company_rate' in vals and 'rate' in vals:
            del vals['company_rate']
        return vals

    def save(self, *args, **kwargs):
        """``create`` y ``write`` de la fuente, que aquí son la misma entrada."""
        self._check_company_id()
        return super().save(*args, **kwargs)

    # --- ayudantes de este porte, sin contraparte de nombre en la fuente ---

    def _current_company(self):
        """La empresa RAÍZ en contexto, o ``None``.

        La fuente escribe ``self.env.company.root_id`` en cuatro sitios; aquí
        vive una vez. No lleva el nombre de ningún símbolo de la referencia
        porque no lo tiene: allá es un atributo del ``env``.

        El ``.root_id`` no es adorno: ``_check_company_id`` prohíbe que una
        tasa cuelgue de una sucursal, así que buscar la tasa anterior con la
        sucursal en contexto no encontraría ninguna. Omitirlo hacía que toda
        conversión bajo una sucursal cayera al 1.0 por defecto.
        """
        company_id = get_current_company()
        if company_id is None:
            return None
        company = type(self).company.field.related_model.objects.filter(
            pk=company_id).first()
        return company.root_id if company is not None else None

    def _divisor_for(self, company):
        """La última tasa de la moneda de ``company``, o 1 si no hay empresa."""
        if company is None:
            return Decimal('1.0')
        return type(self)._get_last_rates_for_companies([company]).get(
            company.pk, Decimal('1.0'))

    def __str__(self) -> str:
        return f'{self.currency_id} @ {self.name}: {self.rate}'
