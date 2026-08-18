"""``base.partner.merge`` — fusionar contactos duplicados.

Adaptación de ``odoo19c: odoo/addons/base/wizard/base_partner_merge.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03).

Dos ``TransientModel`` → un contenedor y una clase de ``classmethod``
=====================================================================

La referencia declara dos modelos transitorios: ``base.partner.merge.line``
(``:19-27``), que es puro contenedor de datos —``min_id`` y la lista de ids del
grupo—, y ``base.partner.merge.automatic.wizard`` (``:30``), que lleva la
lógica y el estado del formulario.

Aquí, por el precedente de ``account_check_printing.print_prenumbered_checks``
("formulario, no tabla"):

===================================  =======================================
Símbolo de la referencia               Qué es aquí
===================================  =======================================
``base.partner.merge.line``            ``MergeGroup`` — dataclass congelada
``…automatic.wizard`` (los campos)     parámetros de los ``classmethod``
``…automatic.wizard`` (los métodos)    ``PartnerMerge``, sin instancia
===================================  =======================================

Los campos ``group_by_*`` del wizard pasan a ser un diccionario de opciones
(``{'group_by_email': True}``) porque ``_compute_selected_groupby`` los lee
**por prefijo**, no uno a uno: mantenerlos como diccionario conserva ese
mecanismo intacto en vez de sustituirlo por una lista literal.

El SQL de introspección se copia, no se traduce
================================================

``_get_fk_on`` y ``_has_check_or_unique_constraint`` consultan ``pg_constraint``
y ``pg_class`` directamente. No se reescriben con el ORM: son PostgreSQL nativo
y el motor aquí es el mismo, así que la consulta de la referencia es **la
consulta correcta** (``porte-completo-no-parcial.md``: PostgreSQL nativo es una
de las tres vías sancionadas). Lo único que cambia es el cursor —
``django.db.connection.cursor()`` donde allá va ``self.env.cr`` — y que el
nombre de la columna FK lo pone Django (``partner_id``), no el ORM de la
fuente; el ``SELECT`` lo devuelve tal cual está en el catálogo, así que la
diferencia no se codifica en ninguna parte.

Divergencias declaradas
=======================

**1. Los cuatro métodos de pantalla no se portan.** ``default_get``
(``:38-49``), ``action_skip`` (``:645``), ``_action_next_screen`` (``:...``) y
``action_merge`` (``:...``) existen para pilotar un formulario de varios pasos
del cliente web de Odoo: rellenan valores por defecto, borran la línea actual y
devuelven un ``ir.actions.act_window`` que reabre el mismo wizard en la
siguiente pantalla. Aquí no hay pantallas — el llamador recibe los grupos y
decide. Su **contenido** sí está portado y accesible: el destino que
``default_get`` calcula es ``_get_ordered_partner(ids)[-1]``, y la fusión que
``action_merge`` dispara es ``_merge``.

**2. Los dos bloques ``company_dependent`` de ``_update_reference_fields_generic``
(``:240-320``) quedan BLOQUEADOS.** Reasignan los valores por empresa que
viven en un ``jsonb`` y en ``ir_default.json_value``. Medido: **0** apariciones
de ``company_dependent`` en ``src/orm/`` — el campo dependiente de empresa no
es un mecanismo de este ORM todavía. Su construcción es la tarea **#381**; en
cuanto exista, estos dos bloques se portan verbatim (son SQL puro y el motor
coincide). Hasta entonces no hay valores por empresa que reasignar, así que su
ausencia no pierde dato: pierde una capacidad que aún no se tiene.

**3. ``SET is_company = NULL`` se porta como ``= false``.** Dos consultas de
cierre de la fuente anulan la columna (``:...``, en
``parent_migration_process_cb`` y ``action_update_all_process``). Aquí
``res_partner.is_company`` es ``BooleanField`` **NOT NULL**, así que el ``NULL``
verbatim revienta con ``IntegrityError`` — medido, no supuesto: es lo que
destapó ``test_the_parent_migration_flattens_a_self_parented_partner`` al
correrlo por primera vez.

No es una pérdida de semántica sino su preservación: el ORM de la fuente lee un
booleano ``NULL`` **como falso**, de modo que su ``= NULL`` y este ``= false``
producen la misma lectura. Lo que cambia es que aquí el estado "ni sí ni no" no
existe en la columna, y por eso el segundo ``WHERE`` también se ajusta —
``is_company IS NOT NULL`` sería siempre cierto y reescribiría filas que la
fuente no toca; el predicado equivalente es ``is_company`` a secas.

**4. ``self.env.cr.commit()`` por grupo no se porta** (``:674``, ``:...``). La
referencia commitea dentro del bucle para no perder el trabajo ya hecho si un
grupo falla; su propio comentario lo marca como dudoso (*"TODO JEM : explain
why"*). Aquí el llamador decide la frontera transaccional — un ``commit`` a
mitad de un test o de una petición rompería el atomic de Django.
"""
import logging
from dataclasses import dataclass

from django.apps import apps
from django.db import connection, transaction
from django.db.utils import IntegrityError

from exceptions import UserError
from tools.sql import table_columns

logger = logging.getLogger('kaupamex.base.partner.merge')

#: Prefijo de las casillas de agrupación del wizard (``:52-56``).
GROUP_BY_PREFIX = 'group_by_'

#: Máximo de contactos por fusión — ``:423`` lo justifica: "por razones de
#: seguridad no puedes fusionar más de 3 contactos a la vez".
MAX_PARTNERS_PER_MERGE = 3

#: Los criterios que la referencia normaliza antes de agrupar (``:487-492``).
LOWERCASED_CRITERIA = ('email', 'name')
SPACELESS_CRITERIA = ('vat',)

#: Modelos cuyos registros apuntan a un contacto por **referencia genérica**
#: —el par ``(columna con el modelo, columna con el id)``— y no por FK
#: (``:213-217``). Una FK la ve ``pg_constraint`` y la arregla
#: ``_update_foreign_keys_generic``; esto no, porque para PostgreSQL es un
#: entero cualquiera.
#:
#: Se declaran por ``(app_label, clase)`` y no por nombre punteado: el registro
#: por nombre de la referencia (``orm.registry.MODELS_BY_ODOO_NAME``) se puebla
#: con los modelos que declaran ``_name``, y hoy son **tres** en todo el árbol
#: (``atributos-de-clase-de-modelo.md``). Resolver por ahí devolvería ``None``
#: para los cinco. Cuando el barrido prospectivo de esa regla llegue a estos
#: modelos, el nombre punteado pasa a ser la vía natural.
GENERIC_REFERENCE_MODELS = (
    ('base', 'IrAttachment', 'res_model', 'res_id'),
    ('base', 'IrModelData', 'model', 'res_id'),
    ('mail', 'MailFollowers', 'res_model', 'res_id'),
    ('mail', 'MailActivity', 'res_model', 'res_id'),
    ('mail', 'MailMessage', 'model', 'res_id'),
)


def _resolve(app_label, class_name):
    """≙ ``self.env[model] if model in self.env else None`` (``:194-196``).

    La referencia consulta su registro y devuelve ``None`` si el addon que
    declara ese modelo no está instalado; aquí, el registro es el de Django y
    la ausencia es ``LookupError``.
    """
    try:
        return apps.get_model(app_label, class_name)
    except LookupError:
        return None


@dataclass(frozen=True)
class MergeGroup:
    """≙ ``base.partner.merge.line`` (``odoo19c: :19-27``).

    Un grupo de contactos candidatos a fusionarse. La referencia lo guarda como
    fila transitoria con ``wizard_id``/``min_id``/``aggr_ids``; aquí es un valor
    inmutable que el barrido devuelve. ``wizard_id`` desaparece con el wizard:
    sin fila que agrupe, no hay a quién apuntar.
    """

    min_id: int
    aggr_ids: tuple


class PartnerMerge:
    """≙ ``base.partner.merge.automatic.wizard`` (``odoo19c: :30-36``).

    Su docstring en la fuente: *"la idea de este asistente es construir una
    lista de contactos potencialmente fusionables"*. Eso es exactamente lo que
    ``_process_query`` devuelve aquí.
    """

    # ------------------------------------------------------------------
    # Introspección del catálogo — PostgreSQL nativo, copiado de la fuente
    # ------------------------------------------------------------------

    @classmethod
    def _get_fk_on(cls, table):
        """≙ ``_get_fk_on`` (``:80-101``): las relaciones que apuntan a ``table``.

        Devuelve una lista de tuplas ``(tabla, columna)``.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cl1.relname AS table, att1.attname AS column
                FROM pg_constraint AS con, pg_class AS cl1, pg_class AS cl2,
                     pg_attribute AS att1, pg_attribute AS att2
                WHERE con.conrelid = cl1.oid
                    AND con.confrelid = cl2.oid
                    AND array_lower(con.conkey, 1) = 1
                    AND con.conkey[1] = att1.attnum
                    AND att1.attrelid = cl1.oid
                    AND cl2.relname = %s
                    AND cl2.relnamespace = current_schema::regnamespace
                    AND att2.attname = 'id'
                    AND array_lower(con.confkey, 1) = 1
                    AND con.confkey[1] = att2.attnum
                    AND att2.attrelid = cl2.oid
                    AND con.contype = 'f'
            """, [table])
            return cursor.fetchall()

    @classmethod
    def _has_check_or_unique_constraint(cls, table, column):
        """≙ ``_has_check_or_unique_constraint`` (``:103-117``).

        Decide si la reasignación masiva puede hacerse de un tirón o necesita
        red: con CHECK o UNIQUE encima, un UPDATE puede violar la restricción y
        hay que atrapar el error por fila.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class r ON (c.conrelid = r.oid)
                CROSS JOIN LATERAL unnest(c.conkey) AS cattr(attnum)
                JOIN pg_attribute a
                  ON (a.attrelid = c.conrelid AND a.attnum = cattr.attnum)
                WHERE c.contype IN ('c', 'u')
                    AND r.relname = %s
                    AND r.relnamespace = current_schema::regnamespace
                    AND a.attname = %s
                LIMIT 1
            """, [table, column])
            return cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Reasignación — el núcleo de la fusión
    # ------------------------------------------------------------------

    @classmethod
    def _update_foreign_keys_generic(cls, model, src_records, dst_record):
        """≙ ``_update_foreign_keys_generic`` (``:119-177``).

        Repunta al destino toda FK que apuntara a alguno de los orígenes.

        :param model: la clase de modelo cuyo destino se reasigna (allá, el
            nombre punteado; aquí la clase, de la que sale ``_meta.db_table``).
        :param src_records: los registros origen — nunca incluye al destino.
        :param dst_record: el registro destino.
        """
        # ``= ANY(%s)`` con lista, no ``IN %s`` con tupla: la forma de la
        # referencia es de psycopg2, y psycopg3 —el driver de este árbol— no
        # adapta una tupla a una lista de valores. Medido: ``syntax error at
        # or near "'(14576)'"``.
        ids_origen = [r.pk for r in src_records]
        if not ids_origen:
            return

        logger.debug('_update_foreign_keys_generic destino=%s origenes=%s',
                     dst_record.pk, ids_origen)

        relaciones = cls._get_fk_on(model._meta.db_table)

        with connection.cursor() as cursor:
            for tabla, columna in relaciones:
                # La fuente salta sus dos tablas de wizard (``:133``); aquí el
                # wizard no tiene tabla, así que no hay nada que saltar.
                columnas = [c for c in table_columns(cursor, tabla)
                            if c != columna]
                if not columnas:
                    continue

                cursor.execute(
                    f'SELECT 1 FROM "{tabla}" WHERE "{columna}" = ANY(%s) '
                    f'LIMIT 1', [ids_origen])
                if cursor.fetchone() is None:
                    continue                      # ninguna fila que reasignar

                if len(columnas) <= 1:
                    # Clave única de hecho: sólo se reasigna la fila que no
                    # colisionaría con una ya existente del destino (``:150``).
                    testigo = columnas[0]
                    for id_origen in ids_origen:
                        cursor.execute(f"""
                            UPDATE "{tabla}" AS ___tu
                            SET "{columna}" = %s
                            WHERE "{columna}" = %s
                              AND NOT EXISTS (
                                  SELECT 1 FROM "{tabla}" AS ___tw
                                  WHERE "{columna}" = %s
                                    AND ___tu."{testigo}" = ___tw."{testigo}"
                              )
                        """, [dst_record.pk, id_origen, dst_record.pk])
                elif not cls._has_check_or_unique_constraint(tabla, columna):
                    cursor.execute(
                        f'UPDATE "{tabla}" SET "{columna}" = %s '
                        f'WHERE "{columna}" = ANY(%s)',
                        [dst_record.pk, ids_origen])
                else:
                    # Con restricción encima, el UPDATE puede violarla. La
                    # fuente usa un savepoint y, si falla, BORRA las filas:
                    # "conservar un registro con un partner inexistente es
                    # inútil" (``:172-176``).
                    try:
                        with transaction.atomic():
                            cursor.execute(
                                f'UPDATE "{tabla}" SET "{columna}" = %s '
                                f'WHERE "{columna}" = ANY(%s)',
                                [dst_record.pk, ids_origen])
                    except IntegrityError:
                        cursor.execute(
                            f'DELETE FROM "{tabla}" '
                            f'WHERE "{columna}" = ANY(%s)', [ids_origen])

    @classmethod
    def _update_reference_fields_generic(cls, referenced_model, src_records,
                                         dst_record,
                                         additional_update_records=None):
        """≙ ``_update_reference_fields_generic`` (``:179-320``).

        Repunta las referencias **genéricas** — las que guardan el modelo y el
        id en dos columnas sueltas (``res_model``/``res_id``) en vez de una FK.
        Una FK la ve el catálogo y la arregla ``_update_foreign_keys_generic``;
        esto no, porque para PostgreSQL es un entero cualquiera.

        Los dos bloques ``company_dependent`` de la fuente (``:240-320``) están
        BLOQUEADOS por la tarea **#381** — ver la divergencia 2 del módulo.
        """
        logger.debug('_update_reference_fields_generic destino=%s origenes=%r',
                     dst_record.pk, [r.pk for r in src_records])

        objetivos = list(GENERIC_REFERENCE_MODELS)
        objetivos += list(additional_update_records or ())

        for app_label, clase, campo_modelo, campo_id in objetivos:
            modelo = _resolve(app_label, clase)
            if modelo is None:
                continue                 # ≙ ``if Model is None: return`` (:196)
            for registro in src_records:
                filas = modelo.objects.filter(**{
                    campo_modelo: referenced_model,
                    campo_id: registro.pk,
                })
                if not filas.exists():
                    continue
                tabla = modelo._meta.db_table
                if not cls._has_check_or_unique_constraint(tabla, campo_id):
                    filas.update(**{campo_id: dst_record.pk})
                    continue
                try:
                    with transaction.atomic():
                        filas.update(**{campo_id: dst_record.pk})
                except IntegrityError:
                    filas.delete()

    @classmethod
    def _update_foreign_keys(cls, src_partners, dst_partner):
        """≙ ``_update_foreign_keys`` (``:316-322``)."""
        cls._update_foreign_keys_generic(
            type(dst_partner), src_partners, dst_partner)

    @classmethod
    def _update_reference_fields(cls, src_partners, dst_partner):
        """≙ ``_update_reference_fields`` (``:324-332``).

        La fuente añade ``calendar`` a la lista genérica; ese modelo no existe
        en este árbol, así que ``_resolve`` lo devolverá como ``None`` y
        el bucle lo saltará — el mismo desenlace que su propio guard.
        """
        adicionales = [('calendar', 'Calendar', 'model_id__model', 'res_id')]
        cls._update_reference_fields_generic(
            'res.partner', src_partners, dst_partner, adicionales)

    @classmethod
    def _get_summable_fields(cls):
        """≙ ``_get_summable_fields`` (``:334-338``): los campos que se suman
        al fusionar. La base no suma ninguno; los addons que lo necesiten
        sobreescriben este método."""
        return []

    @classmethod
    def _update_values(cls, src_partners, dst_partner):
        """≙ ``_update_values`` (``:340-397``).

        El destino recoge, campo a campo, el valor que tuviera puesto: primero
        el de los orígenes en orden, y por último el suyo — así el propio valor
        del destino gana si lo tiene (``:365-372``).
        """
        logger.debug('_update_values destino=%s origenes=%r',
                     dst_partner.pk, [p.pk for p in src_partners])

        sumables = cls._get_summable_fields()
        valores = {}

        for campo in dst_partner._meta.concrete_fields:
            nombre = campo.name
            if nombre in ('id', 'created_at', 'updated_at'):
                continue
            for registro in list(src_partners) + [dst_partner]:
                valor = getattr(registro, nombre, None)
                if not valor:
                    continue
                if nombre in sumables and valores.get(nombre):
                    valores[nombre] += valor
                else:
                    valores[nombre] = valor

        # ``parent`` se aparta: puede introducir un ciclo y la fuente lo
        # intenta por separado, tragando el error (``:393-397``).
        parent = valores.pop('parent', None)

        for nombre, valor in valores.items():
            setattr(dst_partner, nombre, valor)
        dst_partner.save()

        if parent is not None and parent.pk != dst_partner.pk:
            try:
                dst_partner.parent = parent
                dst_partner.save(update_fields=['parent', 'updated_at'])
            except (UserError, ValueError):
                logger.info(
                    'Se omite la jerarquía recursiva parent=%s del contacto %s',
                    parent.pk, dst_partner.pk)

    @classmethod
    def _merge_bank_accounts(cls, src_partners, dst_partner):
        """≙ ``_merge_bank_accounts`` (``:399-413``).

        Una cuenta que el destino ya tiene no se muda: se absorbe (lo que la
        apuntaba pasa al duplicado del destino) y la del origen se borra.
        """
        modelo_banco = _resolve('base', 'ResPartnerBank')
        if modelo_banco is None:
            return

        cuentas_destino = list(modelo_banco.objects.filter(partner=dst_partner))
        for cuenta in modelo_banco.objects.filter(partner__in=src_partners):
            duplicada = next(
                (c for c in cuentas_destino
                 if c.sanitized_acc_number == cuenta.sanitized_acc_number),
                None)
            if duplicada is not None:
                cls._update_foreign_keys_generic(
                    modelo_banco, [cuenta], duplicada)
                cls._update_reference_fields_generic(
                    'res.partner.bank', [cuenta], duplicada)
                cuenta.delete()
            else:
                cuenta.partner = dst_partner
                # Sin ``update_fields``: ``ResPartnerBank`` es ``models.Model``
                # a secas, no ``TimeStampedModel``, así que no tiene
                # ``updated_at`` que acompañar al campo tocado.
                cuenta.save()

    @classmethod
    def _merge(cls, partner_ids, dst_partner=None, extra_checks=True):
        """≙ ``_merge`` (``:415-471``): la fusión propiamente dicha.

        :param partner_ids: ids de los contactos a fusionar.
        :param dst_partner: destino explícito; si falta, el último del orden.
        :param extra_checks: ``False`` salta la comprobación de correo — allá
            la salta el super-admin (``:419-420``); aquí la decide el llamador,
            porque no hay sesión implícita de la que leer el rol.
        """
        modelo = _resolve('base', 'ResPartner')
        contactos = list(modelo.objects.filter(pk__in=partner_ids))
        if len(contactos) < 2:
            return

        if len(contactos) > MAX_PARTNERS_PER_MERGE:
            raise UserError(
                'Por razones de seguridad no se pueden fusionar más de '
                f'{MAX_PARTNERS_PER_MERGE} contactos a la vez. Se puede repetir '
                'la operación las veces que haga falta.')

        # Ni padre ni hijo entre los seleccionados (``:427-433``).
        ids = {c.pk for c in contactos}
        for contacto in contactos:
            descendientes = cls._descendant_ids(contacto)
            if ids & (descendientes - {contacto.pk}):
                raise UserError(
                    'No se puede fusionar un contacto con uno de sus padres.')

        # Un solo usuario entre todos (``:435-436``).
        modelo_usuario = _resolve('base', 'ResUsers')
        if modelo_usuario is not None:
            usuarios = modelo_usuario.objects.filter(partner__in=contactos)
            if usuarios.count() > 1:
                raise UserError(
                    'No se pueden fusionar contactos ligados a más de un '
                    'usuario, aunque sólo uno esté activo.')

        if extra_checks and len({c.email for c in contactos}) > 1:
            raise UserError(
                'Todos los contactos deben tener el mismo correo. Sólo el '
                'administrador puede fusionar contactos con correos distintos.')

        if dst_partner is not None and dst_partner.pk in ids:
            origenes = [c for c in contactos if c.pk != dst_partner.pk]
        else:
            ordenados = cls._get_ordered_partner([c.pk for c in contactos])
            dst_partner = ordenados[-1]
            origenes = ordenados[:-1]

        logger.info('destino de la fusión: %s', dst_partner.pk)

        cls._merge_bank_accounts(origenes, dst_partner)
        cls._update_foreign_keys(origenes, dst_partner)
        cls._update_reference_fields(origenes, dst_partner)
        cls._update_values(origenes, dst_partner)
        cls._log_merge_operation(origenes, dst_partner)

        for origen in origenes:
            origen.delete()

    @classmethod
    def _log_merge_operation(cls, src_partners, dst_partner):
        """≙ ``_log_merge_operation`` (``:473-474``)."""
        logger.info('se fusionaron los contactos %r en %s',
                    [p.pk for p in src_partners], dst_partner.pk)

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------

    @classmethod
    def _descendant_ids(cls, partner):
        """Ids del contacto y de toda su descendencia.

        La fuente lo resuelve con el operador ``child_of`` del dominio
        (``:431``). ``res.partner`` no declara ``parent_path``, así que el
        recorrido se hace por niveles — mismo conjunto, distinto camino.
        """
        modelo = type(partner)
        vistos = {partner.pk}
        frontera = [partner.pk]
        while frontera:
            hijos = list(modelo.objects
                         .filter(parent_id__in=frontera)
                         .exclude(pk__in=vistos)
                         .values_list('pk', flat=True))
            if not hijos:
                break
            vistos.update(hijos)
            frontera = hijos
        return vistos

    @classmethod
    def _generate_query(cls, fields, maximum_group=100):
        """≙ ``_generate_query`` (``:479-521``): agrupa ``res_partner`` por los
        criterios dados y se queda con los grupos de dos o más."""
        columnas = []
        for campo in fields:
            if campo in LOWERCASED_CRITERIA:
                columnas.append(f'lower({campo})')
            elif campo in SPACELESS_CRITERIA:
                columnas.append(f"replace({campo}, ' ', '')")
            else:
                columnas.append(campo)

        filtros = [f'{campo} IS NOT NULL' for campo in fields
                   if campo in LOWERCASED_CRITERIA + SPACELESS_CRITERIA]

        texto = ['SELECT min(id), array_agg(id)', 'FROM res_partner']
        if filtros:
            texto.append('WHERE %s' % ' AND '.join(filtros))
        texto.extend([
            'GROUP BY %s' % ', '.join(columnas),
            'HAVING COUNT(*) >= 2',
            'ORDER BY min(id)',
        ])
        if maximum_group:
            texto.append('LIMIT %d' % maximum_group)
        return ' '.join(texto)

    @classmethod
    def _compute_selected_groupby(cls, options):
        """≙ ``_compute_selected_groupby`` (``:523-538``).

        Lee las casillas **por prefijo**, igual que la fuente recorre
        ``self._fields`` buscando ``group_by_``.
        """
        grupos = [nombre[len(GROUP_BY_PREFIX):]
                  for nombre, activo in options.items()
                  if nombre.startswith(GROUP_BY_PREFIX) and activo]
        if not grupos:
            raise UserError('Hay que especificar un filtro para la selección.')
        return grupos

    @classmethod
    def _partner_use_in(cls, aggr_ids, models):
        """≙ ``_partner_use_in`` (``:540-548``): ¿alguno del grupo aparece en
        alguno de los modelos de exclusión?"""
        for (app_label, clase), campo in models.items():
            modelo = _resolve(app_label, clase)
            if modelo is None:
                continue
            if modelo.objects.filter(**{f'{campo}__in': aggr_ids}).exists():
                return True
        return False

    @classmethod
    def _get_ordered_partner(cls, partner_ids):
        """≙ ``_get_ordered_partner`` (``:550-556``).

        Orden ``(not active, created_at)`` descendente. Consecuencia, que es lo
        que el llamador usa: **el último es el destino** — el activo más
        antiguo.
        """
        modelo = _resolve('base', 'ResPartner')
        contactos = list(modelo.objects.filter(pk__in=partner_ids))
        contactos.sort(
            key=lambda p: (not p.active, p.created_at),
            reverse=True)
        return contactos

    @classmethod
    def _compute_models(cls, exclude_contact=False, exclude_journal_item=False):
        """≙ ``_compute_models`` (``:558-565``): los modelos cuya presencia
        excluye a un grupo de la propuesta."""
        mapa = {}
        if exclude_contact:
            mapa[('base', 'ResUsers')] = 'partner'
        if exclude_journal_item and _resolve('account', 'AccountMoveLine'):
            mapa[('account', 'AccountMoveLine')] = 'partner'
        return mapa

    # ------------------------------------------------------------------
    # Los procesos
    # ------------------------------------------------------------------

    @classmethod
    def _process_query(cls, query, exclude_contact=False,
                       exclude_journal_item=False):
        """≙ ``_process_query`` (``:618-648``).

        La fuente **escribe** una fila ``base.partner.merge.line`` por grupo y
        cuenta cuántas; aquí devuelve la lista de ``MergeGroup``. Es el mismo
        resultado sin la tabla intermedia.
        """
        mapa = cls._compute_models(exclude_contact, exclude_journal_item)
        modelo = _resolve('base', 'ResPartner')

        with connection.cursor() as cursor:
            cursor.execute(query)
            filas = cursor.fetchall()

        grupos = []
        for min_id, aggr_ids in filas:
            # Sólo los contactos que el llamador puede ver (``:630-634``).
            visibles = list(modelo.objects
                            .filter(pk__in=aggr_ids)
                            .values_list('pk', flat=True))
            if len(visibles) < 2:
                continue
            if mapa and cls._partner_use_in(visibles, mapa):
                continue
            grupos.append(MergeGroup(min_id=min_id, aggr_ids=tuple(visibles)))

        logger.info('grupos de duplicados encontrados: %s', len(grupos))
        return grupos

    @classmethod
    def action_start_manual_process(cls, options, maximum_group=100):
        """≙ ``action_start_manual_process`` (``:650-662``).

        Devuelve los grupos para que el llamador los revise uno a uno. Allá,
        eso mismo se presentaba como la primera pantalla del asistente.
        """
        grupos = cls._compute_selected_groupby(options)
        consulta = cls._generate_query(grupos, maximum_group)
        return cls._process_query(
            consulta,
            exclude_contact=options.get('exclude_contact', False),
            exclude_journal_item=options.get('exclude_journal_item', False))

    @classmethod
    def action_start_automatic_process(cls, options, maximum_group=100):
        """≙ ``action_start_automatic_process`` (``:664-681``).

        Fusiona cada grupo sin revisión. Devuelve cuántos grupos se fusionaron.
        """
        grupos = cls.action_start_manual_process(options, maximum_group)
        for grupo in grupos:
            cls._merge(list(grupo.aggr_ids))
        return len(grupos)

    @classmethod
    def parent_migration_process_cb(cls):
        """≙ ``parent_migration_process_cb`` (``:683-...``).

        Fusiona los pares padre/hijo que comparten correo y nombre — el residuo
        de una migración en la que la empresa y su contacto quedaron duplicados.
        Cierra aplanando los contactos que quedaron como padres de sí mismos.
        """
        consulta = """
            SELECT min(p1.id), array_agg(DISTINCT p1.id)
            FROM res_partner AS p1
            INNER JOIN res_partner AS p2
                ON p1.email = p2.email
               AND p1.name = p2.name
               AND (p1.parent_id = p2.id OR p1.id = p2.parent_id)
            WHERE p2.id IS NOT NULL
            GROUP BY p1.email, p1.name,
                     CASE WHEN p1.parent_id = p2.id THEN p2.id ELSE p1.id END
            HAVING COUNT(*) >= 2
            ORDER BY min(p1.id)
        """
        for grupo in cls._process_query(consulta):
            cls._merge(list(grupo.aggr_ids))

        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE res_partner SET is_company = false, parent_id = NULL '
                'WHERE parent_id = id')

    @classmethod
    def action_update_all_process(cls):
        """≙ ``action_update_all_process`` (``:...``).

        Primero la migración de padres, luego la fusión automática por RFC,
        correo y nombre. Cierra limpiando el ``is_company`` de los contactos
        que quedaron sin jerarquía.
        """
        cls.parent_migration_process_cb()
        cls.action_start_automatic_process({
            'group_by_vat': True,
            'group_by_email': True,
            'group_by_name': True,
        })
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE res_partner SET is_company = false '
                'WHERE parent_id IS NULL AND is_company')
