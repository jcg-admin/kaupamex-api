"""¿Se puede extender un modelo **sin importarlo**, nombrándolo?

Origen: directiva del ejecutor 2026-08-14 — *"y nosotros no podemos usar algo
similar a «allá un addon extiende a otro sin importarlo»"*, tras una afirmación
falsa de que la cadena por nombre «sería una indirección sin nada que
resolver».

Esta prueba **mide el binario de Django**, no lo supone. Ejercita el mecanismo
de acoplamiento tardío que la referencia resuelve con su registro
(``odoo19c: odoo/orm/model_classes.py:152`` — ``add_to_registry``, que busca el
padre por su cadena ``_inherit`` en ``registry[parent_name]``) y que Django
resuelve con ``Apps.lazy_model_operation``
(``django/apps/registry.py:388-426``) + ``Apps.do_pending_operations``
(``:428-435``).

Los tres casos que se miden son los tres estados del mecanismo:

1. el modelo **ya está registrado** → la función corre en el acto;
2. el modelo **no está registrado** → la función queda en cola, no corre;
3. el modelo **se registra después** → la cola se vacía y la función corre.

El caso 3 es el que decide la pregunta: si sólo existiera el 1, el acoplamiento
seguiría siendo de import y habría que garantizar el orden de carga.
"""
import pytest
from django.apps import apps

import fields
from orm.model_extension import extend_model, model_key


def test_modelo_ya_registrado_corre_en_el_acto():
    """Caso 1 — ``lazy_model_operation`` sobre un modelo vivo no difiere nada."""
    recibidos = []
    apps.lazy_model_operation(recibidos.append, ('base', 'irmodel'))

    assert len(recibidos) == 1, (
        'con el modelo ya registrado la función debe correr sin diferirse'
    )
    assert recibidos[0] is apps.get_model('base', 'IrModel')


def test_modelo_no_registrado_queda_en_cola():
    """Caso 2 — la función NO corre, y la clave queda pendiente.

    Es la mitad que hace posible el acoplamiento tardío: sin ella, nombrar un
    modelo que aún no se cargó sería un ``LookupError``.
    """
    clave = ('stock', 'modeloquenoexisteparalaprueba')
    corridas = []

    assert clave not in apps._pending_operations, 'la clave debe empezar limpia'
    try:
        apps.lazy_model_operation(corridas.append, clave)

        assert corridas == [], 'sin el modelo registrado la función no corre'
        assert clave in apps._pending_operations
        assert len(apps._pending_operations[clave]) == 1
    finally:
        apps._pending_operations.pop(clave, None)


def test_la_cola_se_vacia_cuando_el_modelo_aparece():
    """Caso 3 — al registrarse el modelo, la función diferida corre con él.

    Se ejercita el despachador real (``do_pending_operations``), que es lo que
    ``Apps.register_model`` llama en su última línea (``registry.py:239``). El
    doble es el **modelo**, no el mecanismo: lo único que el despachador mira
    de él son ``_meta.app_label`` y ``_meta.model_name``, que es justo la clave.
    """
    clave = ('stock', 'modelotardioparalaprueba')
    recibidos = []

    class _MetaDoble:
        app_label, model_name = clave

    class _ModeloTardio:
        _meta = _MetaDoble()

    try:
        apps.lazy_model_operation(recibidos.append, clave)
        assert recibidos == [], 'todavía no debe haber corrido'

        apps.do_pending_operations(_ModeloTardio)

        assert recibidos == [_ModeloTardio], (
            'la función diferida debe correr con el modelo recién registrado'
        )
        assert clave not in apps._pending_operations, (
            'la cola se vacía: do_pending_operations hace pop de la clave'
        )
    finally:
        apps._pending_operations.pop(clave, None)


def test_varias_extensiones_esperan_al_mismo_modelo():
    """Dos addons pueden colgar del mismo destino sin conocerse entre sí.

    Es la propiedad que la referencia obtiene de que ``_inherit`` sea una lista
    de cadenas: N módulos extienden ``product.template`` sin que ninguno
    importe a los otros.
    """
    clave = ('stock', 'destinocompartidoparalaprueba')
    addon_a, addon_b = [], []

    class _MetaDoble:
        app_label, model_name = clave

    class _Destino:
        _meta = _MetaDoble()

    try:
        apps.lazy_model_operation(addon_a.append, clave)
        apps.lazy_model_operation(addon_b.append, clave)
        assert len(apps._pending_operations[clave]) == 2

        apps.do_pending_operations(_Destino)

        assert addon_a == [_Destino] and addon_b == [_Destino]
    finally:
        apps._pending_operations.pop(clave, None)


@pytest.mark.parametrize('etiqueta,nombre', [
    ('base', 'IrModel'),
    ('stock', 'StockLocation'),
    ('product', 'ProductTemplate'),
])
def test_con_el_destino_vivo_la_mayuscula_da_igual(etiqueta, nombre):
    """Con el destino ya registrado, la caja alta de la clave no importa.

    ``get_registered_model`` normaliza (``django/apps/registry.py:278`` —
    ``self.all_models[app_label].get(model_name.lower())``), así que la
    resolución inmediata acepta ``StockLocation`` y ``stocklocation`` por igual.

    Esta mitad es la que engaña: ver el test siguiente.
    """
    modelo = apps.get_model(etiqueta, nombre)
    assert modelo._meta.label == f'{etiqueta}.{nombre}'
    assert modelo._meta.model_name == nombre.lower()

    for clave in ((etiqueta, nombre), (etiqueta, nombre.lower())):
        recibidos = []
        apps.lazy_model_operation(recibidos.append, clave)
        assert recibidos == [modelo], f'{clave} debió resolver en el acto'


def test_con_el_destino_ausente_la_mayuscula_cuelga_la_operacion():
    """La trampa: la MISMA clave funciona o se cuelga según el orden de carga.

    Asimetría medida en el binario de Django:

    - la resolución **inmediata** normaliza (``registry.py:278``, ``.lower()``);
    - la **cola** indexa la clave **verbatim** (``registry.py:424`` —
      ``self._pending_operations[next_model].append(...)``);
    - el **despachador** la reconstruye en minúscula (``registry.py:432`` —
      ``key = model._meta.app_label, model._meta.model_name``).

    Consecuencia: con caja alta, si el destino ya estaba cargado el addon
    funciona; si aún no lo estaba, la extensión **nunca corre** y no hay error
    — el fallo es silencioso y depende del orden de ``INSTALLED_APPS``.

    Por eso ``orm.model_extension.extend_model`` normaliza la clave: es la
    única defensa contra un bug que sólo aparece al reordenar la lista de apps.
    """
    clave_camel = ('stock', 'ModeloAusenteCamel')
    corridas = []

    class _MetaNormalizada:
        # Como Django la registra de verdad: ``model_name`` va en minúscula.
        app_label, model_name = 'stock', 'modeloausentecamel'

    class _ModeloTardio:
        _meta = _MetaNormalizada()

    try:
        apps.lazy_model_operation(corridas.append, clave_camel)
        assert clave_camel in apps._pending_operations, 'se encoló verbatim'

        apps.do_pending_operations(_ModeloTardio)

        assert corridas == [], (
            'con caja alta la extensión NO corre al registrarse el destino'
        )
        assert clave_camel in apps._pending_operations, (
            'y la operación queda colgada para siempre, sin error'
        )
    finally:
        apps._pending_operations.pop(clave_camel, None)


# ---------------------------------------------------------------------------
# El adaptador: ``orm.model_extension.extend_model``
# ---------------------------------------------------------------------------


def test_extend_model_cuelga_campo_metodo_y_propiedad_en_destino_vivo():
    """Los tres bloques del adaptador sobre un modelo ya registrado."""
    modelo = apps.get_model('base', 'IrModel')
    extend_model(
        'base', 'IrModel',
        campos={'campo_de_prueba': fields.Char(
            max_length=8, blank=True, default='')},
        metodos={'metodo_de_prueba': lambda self: 'del-extensor'},
        propiedades={'propiedad_de_prueba': lambda self: f'probe:{self.model}'},
    )

    instancia = modelo(model='base.IrModel')
    assert any(f.name == 'campo_de_prueba' for f in modelo._meta.get_fields())
    assert instancia.metodo_de_prueba() == 'del-extensor'
    assert instancia.propiedad_de_prueba == 'probe:base.IrModel'


def test_extend_model_es_idempotente():
    """Aplicar dos veces no duplica la columna.

    ``ready()`` puede correr más de una vez en el mismo proceso (autoreloader),
    y los tests invocan ``apply_*_extensions()`` explícitamente.
    """
    modelo = apps.get_model('base', 'IrModel')
    campo = lambda: fields.Char(max_length=8, blank=True, default='')  # noqa: E731

    extend_model('base', 'IrModel', campos={'campo_idempotente': campo()})
    antes = len(modelo._meta.get_fields())
    extend_model('base', 'IrModel', campos={'campo_idempotente': campo()})

    assert len(modelo._meta.get_fields()) == antes


def test_extend_model_normaliza_la_clave_y_por_eso_no_se_cuelga():
    """El caso que justifica el envoltorio, con su control negativo.

    Mismo argumento en caja alta y mismo destino ausente: por ``extend_model``
    la extensión corre; por la llamada cruda a Django, no. La única diferencia
    entre las dos ramas es la normalización de la clave.
    """
    camel = ('stock', 'DestinoTardioParaLaPrueba')
    normal = model_key(*camel)

    class _Meta:
        app_label, model_name = normal

    class _Destino:
        _meta = _Meta()

    por_el_adaptador, por_django_crudo = [], []
    try:
        extend_model(*camel, luego=por_el_adaptador.append)
        assert normal in apps._pending_operations, 'se encoló normalizada'
        assert camel not in apps._pending_operations, 'no se encoló verbatim'

        apps.do_pending_operations(_Destino)
        assert por_el_adaptador == [_Destino], 'el adaptador SÍ corre'

        # Control negativo: la misma clave sin normalizar queda muda.
        apps.lazy_model_operation(por_django_crudo.append, camel)
        apps.do_pending_operations(_Destino)
        assert por_django_crudo == [], 'la llamada cruda NO corre'
    finally:
        apps._pending_operations.pop(camel, None)
        apps._pending_operations.pop(normal, None)
