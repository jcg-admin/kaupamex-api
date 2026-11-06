"""Rejilla de métodos base de ``BaseModel`` que necesitan un recordset.

Como ``model_domain_grid``, no importa ni ``odoo`` ni ``orm``: el proceso de
referencia le pasa ``env[model_name]`` y el puerto la clase del modelo con el
mismo ``_name``; los dos responden a ``browse``. El método se toma de la
clase ``BaseModel`` de la jerarquía, no del modelo, para medir el contrato
base aunque un addon lo redefina.

Cubre ``_can_return_content`` (``odoo19c: odoo/orm/models.py:5841-5855``)
con cero, uno y dos registros, sin argumentos y con nombre de campo y token,
y los tres alias deprecados ``_cr``, ``_uid`` y ``_context``
(``:5911-5924``): a qué atributo del entorno responden y qué advertencia
emiten.
"""
import warnings

IDS = ((), (1,), (1, 2))
#: Alias deprecado y el atributo del entorno al que responde.
ALIASES = (('_cr', 'cr'), ('_uid', 'uid'), ('_context', 'context'))
ARGUMENTS = ((), ('datas', None), ('datas', 'token'))


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso; su mensaje no.
        return f'raises {type(error).__name__}'


def _base(model):
    for cls in type(model).__mro__ + getattr(model, '__mro__', ()):
        if cls.__name__ == 'BaseModel':
            return cls
    raise LookupError('sin BaseModel en la jerarquía')


def trace(Domain, model, model_name):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    del Domain, model_name
    base = _base(model)
    steps = [(f'can_return_content {len(ids)} {arguments}',
              lambda ids=ids, arguments=arguments:
              base._can_return_content(model.browse(ids), *arguments))
             for ids in IDS for arguments in ARGUMENTS]
    for alias, attribute in ALIASES:
        steps += [
            (f'{alias} is env.{attribute}', lambda alias=alias,
             attribute=attribute: _alias(base, model, alias) is getattr(
                 model.browse(()).env, attribute)),
            (f'{alias} warns', lambda alias=alias: _warnings(base, model,
                                                             alias)),
        ]
    return [f'{name} {_step(function)}' for name, function in steps]


def _alias(base, model, alias):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return getattr(base, alias).fget(model.browse(()))


def _warnings(base, model, alias):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        getattr(base, alias).fget(model.browse(()))
    return sorted({warning.category.__name__ for warning in caught})
