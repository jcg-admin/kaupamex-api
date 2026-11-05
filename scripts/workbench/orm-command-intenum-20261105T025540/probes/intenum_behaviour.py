"""Conducta de un ``IntEnum`` en el intérprete instalado, frente a ``int``.

Responde qué cambia para un consumidor si el primer elemento de un triple de
``Command`` pasa de ser un ``int`` a ser un miembro de ``IntEnum``, como en
``odoo19c: odoo/orm/commands.py:7``. Sólo lee; imprime una línea por eje.

Uso: ``.venv/bin/python <banco>/probes/intenum_behaviour.py``
"""
import copy
import enum
import operator
import json
import pickle
import sys


class Code(enum.IntEnum):
    CREATE = 0
    LINK = 4

    @classmethod
    def link(cls, record_id):
        return (cls.LINK, record_id, 0)


def main():
    triple = Code.link(7)
    rows = [
        ('python', sys.version.split()[0]),
        ('str', str(Code.LINK)),
        ('format', f'{Code.LINK}'),
        ('percent_d', '%d' % Code.LINK),
        ('percent_s', '%s' % Code.LINK),
        ('repr', repr(Code.LINK)),
        ('json', json.dumps([triple])),
        ('pickle_equal', pickle.loads(pickle.dumps(triple)) == triple),
        ('deepcopy_member', copy.deepcopy(triple)[0] is Code.LINK),
        ('equal_int', Code.LINK == 4 and 4 == Code.LINK),
        ('hash_int', hash(Code.LINK) == hash(4)),
        ('dict_key_int', {4: 'x'}.get(Code.LINK)),
        ('in_tuple', triple[0] in (3, 4)),
        ('type_is_int', type(Code.LINK) is int),
        ('isinstance_int', isinstance(Code.LINK, int)),
        ('isinstance_bool', isinstance(Code.LINK, bool)),
        ('member_is_zero', operator.is_(Code.CREATE, 0)),
        ('plain_zero_is_zero', operator.is_(int('0'), 0)),
    ]
    for key, value in rows:
        print(f'{key}\t{value}')


if __name__ == '__main__':
    main()
