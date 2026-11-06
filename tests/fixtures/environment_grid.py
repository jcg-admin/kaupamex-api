"""Rejilla de contratos de ``Environment``, compartida por los dos procesos.

Como ``model_domain_grid``, no importa ni ``odoo`` ni ``orm``: cada lado le
pasa una fábrica ``factory(uid, context, su)`` que construye su
``Environment``. En la referencia, ``Environment(cursor, uid, context, su)``;
aquí, ``Environment(None, uid, context, su)``.

Sólo entran contratos que no dependen de los datos de cada base: la
agrupación por ejes de ``__new__``, la elevación implícita del uid 1, la
identidad (``==``/``!=``/``hash``, por objeto como en la fuente), la
coherencia entre ``iter`` y ``len``, la guarda de ``__setattr__``, la
pertenencia de un modelo, la derivación con ``__call__``, ``lang`` y
``tz`` leídos del contexto del propio entorno, y ``is_superuser``. El uid 2
nunca se materializa como registro: ningún paso lee ``env.user``.

El contexto se publica como sus pares ordenados, y la zona como ``str``: la
referencia los da como ``frozendict`` y ``pytz``, el puerto como ``dict`` y
``zoneinfo``, y esa diferencia de tipo no es el contrato.
"""
ADMIN = 2
SUPERUSER = 1
#: Claves ``default_*`` que ``clean_context`` retira al elevar.
CONTEXT = {'default_name': 'x', 'k': 1}


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso: se compara
        # entre los dos procesos, y su mensaje no.
        return f'raises {type(error).__name__}'


def _context(env):
    return sorted(env.context.items())


def trace(factory):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    plain = factory(ADMIN, {}, False)
    steps = [
        ('grouping', lambda: factory(ADMIN, {}, False)
         is factory(ADMIN, {}, False)),
        ('grouping by context', lambda: factory(ADMIN, {'a': 1}, False)
         is factory(ADMIN, {}, False)),
        ('superuser elevates', lambda: factory(SUPERUSER, {}, False).su),
        ('admin not elevated', lambda: plain.su),
        ('explicit su', lambda: factory(ADMIN, {}, True).su),
        ('is_superuser', lambda: factory(ADMIN, {}, True).is_superuser()),
        ('eq same', lambda: plain == factory(ADMIN, {}, False)),
        ('eq is identity', lambda: plain.__eq__(ADMIN)),
        ('ne is identity', lambda: plain.__ne__(ADMIN)),
        ('hash is identity', lambda: hash(plain) == object.__hash__(plain)),
        ('iter yields names', lambda: all(isinstance(name, str)
                                          for name in plain)),
        ('len matches iter', lambda: len(plain) == len(list(plain))),
        ('eq other', lambda: plain == factory(ADMIN, {'a': 1}, False)),
        ('ne other', lambda: plain != factory(ADMIN, {'a': 1}, False)),
        ('setattr uid', lambda: setattr(plain, 'uid', 3)),
        ('contains model', lambda: 'res.partner' in plain),
        ('contains missing', lambda: 'no.such.model' in plain),
        ('getitem missing', lambda: plain['no.such.model']),
        ('call keeps uid', lambda: plain(context={'a': 1}).uid),
        ('call context', lambda: _context(plain(context={'a': 1}))),
        ('call su elevates', lambda: plain(su=True).su),
        ('call su cleans context', lambda: _context(
            factory(ADMIN, CONTEXT, False)(su=True))),
        ('call su keeps explicit context', lambda: _context(
            factory(ADMIN, CONTEXT, False)(context=CONTEXT, su=True))),
        ('call user drops su', lambda: factory(ADMIN, {}, True)(
            user=ADMIN).su),
        ('call keeps su', lambda: factory(ADMIN, {}, True)(
            context={'a': 1}).su),
        ('call is grouped', lambda: plain(context={'a': 1})
         is factory(ADMIN, {'a': 1}, False)),
        ('lang en_US', lambda: factory(ADMIN, {'lang': 'en_US'}, False).lang),
        ('lang empty', lambda: factory(ADMIN, {'lang': ''}, False).lang),
        ('lang absent', lambda: plain.lang),
        ('lang unknown', lambda: factory(ADMIN, {'lang': 'xx_YY'},
                                         False).lang),
    ]
    for zone in ('America/Mexico_City', 'Europe/Madrid', 'UTC',
                 'Not/AZone'):
        steps.append((f'tz {zone}', lambda zone=zone: str(
            factory(ADMIN, {'tz': zone}, False).tz)))
    return [f'{name} {_step(function)}' for name, function in steps]
