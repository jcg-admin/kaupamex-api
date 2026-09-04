r"""Sonda: ¿el allowlist de opcodes sobrevive a un salto de versión de CPython?

Cierra el DESCONOCIDO que
``docs: analisis-las-tres-piezas-de-forma-nativa.rst`` declaró: *"fail-closed
garantiza que no se abre un agujero; no garantiza que una expresión legítima
siga compilando. Eso se mide al subir de versión, no antes."*

Ahora se puede medir: hay un árbol de CPython **3.16** disponible, y su
``opmap`` está vendorizado en ``tests/fixtures/cpython_opcode_snapshots.py``
con su procedencia. Lo que la sonda compara son **nombres de opcode**, no
conducta: no hay un 3.16 construido con el que ejecutar nada.

*Métrica:* los nombres que ``safe_eval.py`` declara, los del ``opmap`` de este
intérprete, y los del ``opmap`` de 3.16, cruzados entre sí; más los nombres
que las expresiones reales emiten hoy.
*Ciega a:* que el compilador de 3.16 emita un opcode **distinto** para la misma
fuente aunque el nombre viejo siga existiendo. Eso exige construir 3.16 y
ejecutarlo, que no se hace aquí; lo que sí se hace es leer su ``codegen.c``
cuando la instantánea señala una desaparición.
"""
import ast
import dis
import pathlib
import sys
from opcode import opmap

import pytest

import tools.safe_eval as safe_eval_module
from tests.fixtures.cpython_opcode_snapshots import (
    CPYTHON_SNAPSHOT_OPMAP, CPYTHON_SNAPSHOT_VERSION)

#: El corpus de expresiones que un descriptor puede contener. No es una lista
#: inventada: son las formas que las sondas hermanas ya ejercen más las que la
#: plantilla-descriptor necesita (importe de línea, indexado, formato).
EXPRESSION_CORPUS = [
    'a + 1',
    'line.price * line.qty',
    'rows[0]',
    'rows[1:2]',
    'triple(2)',
    "{'a': 1, 'b': 2}",
    '[x * 2 for x in rows]',
    'sum(x for x in rows)',
    "'%s-%s' % (a, b)",
    "f'{a}'",
    'a if b else c',
    'a in rows',
    '-a',
    'not a',
    'a and b or c',
]

#: Lo que 3.16 retira y con qué lo sustituye, leído de su propio árbol. Cada
#: fila se justifica en el caso que la usa; el sustituto tiene que estar en el
#: allowlist para que la expresión siga pasando.
RETIRED_IN_SNAPSHOT_AND_ITS_REPLACEMENT = {
    # BINARY_SUBSCR se pliega dentro de BINARY_OP con un oparg nuevo:
    # `Include/opcode.h:36` declara NB_SUBSCR = 26, y NB_OPARG_LAST pasa a 26.
    'BINARY_SUBSCR': ['BINARY_OP'],
    # `codegen_subdict` emite BUILD_MAP siempre (`Python/codegen.c:3617,3627`);
    # BUILD_CONST_KEY_MAP no aparece ni una vez en el árbol.
    'BUILD_CONST_KEY_MAP': ['BUILD_MAP'],
    # Se vuelve a la pareja de siempre.
    'RETURN_CONST': ['LOAD_CONST', 'RETURN_VALUE'],
    # Los tres de 3.13, que safe_eval.py ya declara en su sección de 3.13.
    'FORMAT_VALUE': ['CONVERT_VALUE', 'FORMAT_SIMPLE', 'FORMAT_WITH_SPEC'],
    'KW_NAMES': ['CALL_KW'],
    'LOAD_METHOD': ['LOAD_ATTR'],
    # `del x` pasa a ser PUSH_NULL + STORE_NAME (`Python/codegen.c:3403-3406`).
    'DELETE_NAME': ['PUSH_NULL', 'STORE_NAME'],
    # Los dos del BLACKLIST: su sustituto también está prohibido, así que la
    # prohibición sobrevive. `codegen.c:3389-3391` y `:5601`.
    'DELETE_GLOBAL': ['PUSH_NULL', 'STORE_GLOBAL'],
    'DELETE_ATTR': ['PUSH_NULL', 'STORE_ATTR'],
}


def declared_opcode_names():
    """Los nombres que ``safe_eval.py`` pasa a ``to_opcodes``, por AST.

    No se leen los conjuntos ya resueltos: `to_opcodes` **descarta** el nombre
    que este intérprete no conoce, así que mirarlos sólo mostraría los que hoy
    existen — justo lo contrario de lo que la sonda quiere medir.
    """
    source = pathlib.Path(safe_eval_module.__file__).read_text()
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'to_opcodes':
            for argument in node.args:
                for element in ast.walk(argument):
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        names.add(element.value)
    # La comprensión sobre `_operations` no deja literales completos.
    names |= {prefix + operation
              for prefix in ('BINARY_', 'INPLACE_')
              for operation in safe_eval_module._operations}
    return names


def emitted_opcode_names(source):
    """Los opcodes que este intérprete emite para una expresión, lambdas dentro."""
    code = compile(source, '<expr>', 'eval')
    names = {instruction.opname for instruction in dis.get_instructions(code)}
    for constant in code.co_consts:
        if hasattr(constant, 'co_code'):
            names |= {i.opname for i in dis.get_instructions(constant)}
    return names


class TestTheSnapshotIsUsableEvidence:
    """Antes de concluir nada: que la instantánea sea de otra versión y esté llena."""

    def test_it_comes_from_a_version_that_is_not_ours(self):
        assert CPYTHON_SNAPSHOT_VERSION > sys.version_info[:2]

    def test_it_carries_a_full_opmap(self):
        # Control de que el extractor no devolvió un dict a medias: el opmap de
        # cualquier CPython moderno pasa del centenar largo de entradas.
        assert len(CPYTHON_SNAPSHOT_OPMAP) > 100
        assert 'RESUME' in CPYTHON_SNAPSHOT_OPMAP


class TestTheAllowlistFailsClosedOnTheJump:
    """La mitad de seguridad: ningún opcode nuevo entra por la puerta de atrás."""

    def test_every_opcode_the_snapshot_adds_is_absent_from_the_allowlist(self):
        """El allowlist es una lista blanca: lo que nadie declaró, se rechaza.

        No es una perogrullada: se mide que ninguno de los nombres nuevos
        coincida por accidente con uno ya declarado para otra cosa.
        """
        declared = declared_opcode_names()
        added = set(CPYTHON_SNAPSHOT_OPMAP) - set(opmap)
        anticipated = added & declared
        unlisted = added - declared
        # El archivo YA anticipa los de 3.13 y 3.14 — no todos los nuevos son
        # sorpresa, y decirlo evita leer el resto como un agujero.
        assert anticipated, 'safe_eval.py declara opcodes de versiones futuras'
        # Y de los que nadie listó, ninguno queda permitido.
        assert not (unlisted & declared)

    @pytest.mark.parametrize('blacklisted, replacement', [
        ('DELETE_ATTR', 'STORE_ATTR'),
        ('DELETE_GLOBAL', 'STORE_GLOBAL'),
    ])
    def test_a_blacklisted_opcode_that_disappears_lands_on_another_blacklisted_one(
            self, blacklisted, replacement):
        """El caso fail-OPEN que había que descartar, y se descarta.

        `to_opcodes` descarta el nombre desconocido, así que un opcode del
        BLACKLIST que desaparece deja de restarse. Sería un agujero **si** su
        sustituto estuviera permitido. No lo está: `del a.b` pasa a emitir
        STORE_ATTR, que el propio BLACKLIST ya prohíbe.
        """
        source = pathlib.Path(safe_eval_module.__file__).read_text()
        blacklist_block = source.split('_BLACKLIST = set(to_opcodes([')[1].split(']))')[0]
        assert f"'{blacklisted}'" in blacklist_block
        assert f"'{replacement}'" in blacklist_block
        assert blacklisted not in CPYTHON_SNAPSHOT_OPMAP
        assert replacement in CPYTHON_SNAPSHOT_OPMAP


class TestNoLegitimateExpressionBreaks:
    """La mitad que fail-closed NO garantiza, y que era el DESCONOCIDO."""

    @pytest.mark.parametrize('source', EXPRESSION_CORPUS)
    def test_every_opcode_it_emits_either_survives_or_has_an_allowed_replacement(
            self, source):
        declared = declared_opcode_names()
        for name in emitted_opcode_names(source):
            if name in CPYTHON_SNAPSHOT_OPMAP:
                continue
            replacement = RETIRED_IN_SNAPSHOT_AND_ITS_REPLACEMENT.get(name)
            assert replacement, (
                '%r emite %s, que la instantánea no nombra y para el que no '
                'hay sustituto declarado' % (source, name))
            for substitute in replacement:
                assert substitute in CPYTHON_SNAPSHOT_OPMAP, substitute
                assert substitute in declared, (
                    '%s sustituye a %s pero no está en el allowlist' % (substitute, name))

    def test_the_corpus_does_exercise_the_retired_opcodes(self):
        """Control positivo del caso anterior, que si no sería un verde vacío.

        Si ninguna expresión emitiera un opcode retirado, el bucle de arriba no
        entraría nunca en su rama interesante y pasaría sin medir nada.
        """
        retired_seen = set()
        for source in EXPRESSION_CORPUS:
            retired_seen |= emitted_opcode_names(source) - set(CPYTHON_SNAPSHOT_OPMAP)
        assert retired_seen, 'el corpus no ejercita ningún opcode retirado'
        assert retired_seen <= set(RETIRED_IN_SNAPSHOT_AND_ITS_REPLACEMENT)


class TestTheOpcodesNobodyListedAreHarmless:
    """Los que quedan fuera: por qué no rompen nada que hoy funcione."""

    def test_the_boolean_operators_survive_because_their_new_opcode_is_pseudo(self):
        """El susto de la medición, y su desenlace.

        `codegen_boolop` de 3.16 emite JUMP_IF_FALSE / JUMP_IF_TRUE
        (`Python/codegen.c:3435-3437`) para `and` y `or`, y ninguno está en el
        allowlist. No rompe: valen 258 y 259, y `co_code` es `bytes` — un
        opcode por encima de 255 no cabe ahí. Son pseudo-opcodes que el
        ensamblador resuelve antes de que exista el objeto de código.
        """
        assert CPYTHON_SNAPSHOT_OPMAP['JUMP_IF_FALSE'] > 255
        assert CPYTHON_SNAPSHOT_OPMAP['JUMP_IF_TRUE'] > 255
        # El mecanismo se comprueba aquí, donde sí hay intérprete: nuestro
        # opmap también tiene pseudo-opcodes y `dis` no los emite nunca.
        ours_pseudo = {n for n, v in opmap.items() if v > 255}
        assert ours_pseudo
        assert not (emitted_opcode_names('a and b or c') & ours_pseudo)
        assert isinstance(compile('a and b', '<e>', 'eval').co_code, bytes)

    def test_the_instrumented_ones_only_appear_under_a_tracer(self):
        instrumented = {n for n in set(CPYTHON_SNAPSHOT_OPMAP) - set(opmap)
                        if n.startswith('INSTRUMENTED_')}
        assert instrumented
        # No los emite el compilador: los inyecta el runtime al instrumentar.
        for source in EXPRESSION_CORPUS:
            assert not (emitted_opcode_names(source) & instrumented)

    def test_the_only_real_gap_is_syntax_that_does_not_exist_here_yet(self):
        """Lo que sí quedaría rechazado bajo 3.16, dicho con su nombre.

        BUILD_TEMPLATE y BUILD_INTERPOLATION son de las *t-strings* (PEP 750),
        sintaxis que este intérprete no tiene. Una expresión que las use sería
        rechazada por el allowlist — no es una regresión, es un hueco que se
        abre el día que alguien escriba una en un descriptor.
        """
        declared = declared_opcode_names()
        for name in ('BUILD_TEMPLATE', 'BUILD_INTERPOLATION'):
            assert name in CPYTHON_SNAPSHOT_OPMAP
            assert CPYTHON_SNAPSHOT_OPMAP[name] < 256, 'es un opcode real'
            assert name not in declared
            assert name not in opmap, 'y este intérprete no lo tiene'
