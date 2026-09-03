"""El gate mide el comando que la prosa cita, no el símbolo que uno supone (#228).

Mismo principio que ``test_check_fk_naming.py``: un gate se prueba contra un
**positivo conocido del repo**, no contra un incumplidor fabricado por quien
escribió el patrón — un fabricado hereda el encuadre de su autor y confirma el
instrumento en vez de ponerlo a prueba.

Los cinco controles que discriminan
====================================

Cada uno corresponde a un defecto que una versión del gate tuvo, y que publicó
una cifra falsa antes de corregirse. El caso está escrito para que **caiga** si
la corrección se revierte:

===========================  ==================================  =============
Control                      Qué mide                            Sin el arreglo
===========================  ==================================  =============
``def slugify``              un cero que el porte dejó falso     no se ve
``wkhtmltopdf`` (la cita)    la prosa citándose a sí misma       5 falsos
``^class IrModel`` (código)  el porte contradiciendo su prosa    se silencia
``grep -ic stdnum``          ``-c`` emite el número, no líneas   5 falsos
``Text(store=False`` +       el árbol medido, declarado en la    1 falso
``odoo19c:`` en la prosa     prosa y no dentro del comando
===========================  ==================================  =============

El tercero y el segundo son la misma línea de código con veredictos opuestos, y
por eso van juntos: excluir el archivo entero arregla uno y rompe el otro. El
discriminador que sostiene los dos es el literal RST.

El quinto es de la misma familia que el cuarto —el comando no basta para saber
qué se midió— pero en el otro eje: aquél confunde la **unidad** de la salida,
éste la **población** de la entrada.
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_stale_zero_claims', REPO / 'scripts' / 'check_stale_zero_claims.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

#: Los reclamos se re-ejecutan con el repo como directorio de trabajo: las
#: rutas que citan (``src/``, ``addons/``) son relativas a él.
BASE = pytest.fixture(autouse=True)(
    lambda monkeypatch: monkeypatch.chdir(REPO))


class TestTheClaimIsReadWithItsCommand:
    """``claims_in`` extrae la cita y la ancla a la línea que la escribe."""

    def test_it_finds_the_slugify_claim_of_ir_http(self):
        """``ir_http.py`` declina el porte de ``slugify`` citando un cero.

        **Re-anclado**: el control era el reclamo de ``IrUiView`` en
        ``res_groups.py``, y se cerró al portarse la capa de vistas. Que un
        control de gate caiga al arreglarse su defecto NO es fragilidad del
        test — es el precio de anclarlo a un positivo real del repo, que es lo
        que ``hallazgo-abierto-genera-sucesor.md`` exige. Un incumplidor
        fabricado nunca caería, y tampoco probaría nada.
        """
        claims = gate.claims_in(
            pathlib.Path('src/addons/base/models/ir_http.py'))
        commands = [command for command, _, _ in claims]
        assert any('def slugify' in c for c in commands), commands

    def test_a_repeated_claim_gets_its_own_line(self):
        """Dos archivos repiten su cita; las dos merecen línea propia."""
        claims = gate.claims_in(
            pathlib.Path('addons/account_peppol/models/res_company.py'))
        phone = [line for command, line, _ in claims
                 if 'phonenumbers' in command]
        assert len(phone) == 2, claims
        assert phone[0] != phone[1], phone

    def test_a_quoted_command_with_a_non_zero_is_not_a_claim(self):
        """Citar un comando NO lo convierte en reclamo: el cero es el gancho.

        ``fields_textual.py`` cita **dos** comandos: el del campo sin columna,
        que declara su cero, y el de ``size=``, que declara **33** sitios de la
        referencia. Sin el ``**0**`` en el patrón el gate contaría el segundo y
        re-ejecutaría una medición que nunca prometió estar vacía.

        **Re-anclado**: el control era el reclamo de ``ir_autovacuum.py``, y se
        retiró al portarse ``_gc_orm_signaling`` — su condición de cierre se
        cumplió y un reclamo de cero cumplido ya no mide nada. Que un control
        de gate caiga al cerrarse su positivo es el precio de anclarlo a uno
        real del repo, como ya documenta el caso de ``slugify`` de arriba.
        """
        path = pathlib.Path('src/orm/fields_textual.py')
        commands = [command for command, _, _ in gate.claims_in(path)]
        assert len(commands) == 1, commands
        assert 'Text(store=False' in commands[0], commands[0]
        assert not any('fields\\.Char' in c for c in commands), commands

    def test_the_claim_of_ir_http_does_not_find_itself(self):
        """El comando citado NO se encuentra a sí mismo, y por eso se excluye.

        La cita vive dentro de ``src/`` y su comando busca en ``src/``: sin la
        exclusión el patrón encuentra su propia cita y devuelve **1**, no el
        **0** que la prosa declara. El gate no lo delataría —descuenta la línea
        de cita por el literal RST— así que el control mide lo que un humano ve
        al copiar el comando, no lo que el gate cuenta.

        Es el defecto #2 de H-API-985 reaparecido en la cita que lo corregía.
        """
        path = pathlib.Path('src/addons/base/models/ir_http.py')
        command, _, _ = gate.claims_in(path)[0]
        assert 'grep -v "^src/addons/base/models/ir_http.py:"' in command, command
        salida = subprocess.run(command, shell=True, capture_output=True,
                                text=True, cwd=REPO)
        assert salida.stdout == '', salida.stdout

    def test_the_line_carries_the_grep_it_names(self):
        """El ancla es la cita, no el primer ``grep`` del archivo."""
        path = pathlib.Path('src/addons/base/models/ir_actions_report.py')
        for command, line, _ in gate.claims_in(path):
            if 'wkhtmltopdf' not in command:
                continue
            text = path.read_text().splitlines()[line - 1]
            assert 'grep' in text and 'wkhtmltopdf' in text, text


class TestTheTreeIsReadFromTheWholeQuote:
    """El árbol que el autor midió no siempre cabe dentro del comando.

    ``fields_textual.py`` cita ``grep -rn "Text(store=False…"`` **sobre**
    ``odoo19c:`` — el alias vive en la prosa que une el comando con su cero.
    Medir sólo el comando lo re-ejecuta contra nuestro árbol, que es otra
    población, y publica un caducado que nunca lo fue.
    """

    #: El caso se mide sobre ``survey``, no sobre la regex: comprobar que
    #: ``ANOTHER_TREE`` casa la cita deja verde al gate aunque nadie consulte
    #: esa respuesta. Lo que discrimina es que el reclamo NO salga como
    #: caducado — que es el efecto que la guarda produce.
    def test_the_alias_in_the_prose_takes_the_claim_out_of_scope(self):
        path = 'src/orm/fields_textual.py'
        claims, skipped, stale, _ = gate.survey([path])
        assert claims, 'la cita de Text/Html ya no está en el archivo'
        assert skipped == claims, (skipped, claims)
        assert stale == [], stale

    def test_our_own_tree_is_not_taken_out_of_scope(self):
        """El control positivo: una cita sin alias SÍ se re-ejecuta aquí.

        Lo que discrimina es que el reclamo **no salga como omitido** — que es
        lo contrario del caso de arriba. Anclarlo en que salga *caducado*
        ataba el control a que un defecto siguiera vivo: la cita de
        ``slugify`` lo estaba por dos fallos de su propio comando, y al
        corregirlos (:ref:`h-api-993`) el caso se puso rojo sin que la
        conducta medida cambiara.
        """
        path = 'src/addons/base/models/ir_http.py'
        claims, skipped, _, unrunnable = gate.survey([path])
        assert claims, 'la cita de slugify ya no está en el archivo'
        assert skipped == 0, 'una cita sin alias no se omite'
        assert unrunnable == [], unrunnable


class TestTheCitationIsNotItsOwnEvidence:
    """La prosa que cita el comando vive dentro del árbol que el comando barre.

    Al escribirse la cita el archivo aún no la contenía y el cero era honesto;
    hoy el grep encuentra su propio texto. El discriminador es el literal RST,
    que toda cita de este árbol lleva y ninguna línea de código tiene.
    """

    CLAIMING = pathlib.Path('src/addons/base/models/ir_actions_report.py')

    def test_a_citation_line_is_discarded(self):
        line = f'{self.CLAIMING}:41:``grep -rln "…wkhtmltopdf…" src/`` → **0**'
        assert gate.is_its_own_citation(line, self.CLAIMING)

    def test_a_code_line_of_the_same_file_counts(self):
        """El porte que contradice a su propia prosa es el caso interesante."""
        line = f'{self.CLAIMING}:1264:    def get_wkhtmltopdf_state(cls):'
        assert not gate.is_its_own_citation(line, self.CLAIMING)

    def test_another_file_always_counts(self):
        line = 'src/tools/barcode.py:32:La referencia rasteriza con ``reportlab``'
        assert not gate.is_its_own_citation(line, self.CLAIMING)


class TestTheExclusionIsAnExpressionNotASubstring:
    """``grep -v`` recibe una expresion regular, no una subcadena.

    Las dos citas del arbol que usan esta forma anclan la ruta con ``^``.
    Aplicar el patron con ``in`` deja pasar TODO —``^src/…`` no es subcadena
    de ninguna linea— y el conteo publica las coincidencias que el autor ya
    habia excluido a mano. El filtro pasaba sin discriminar: sub-patron D de
    ``metrica-decide-la-conclusion.md``, dentro del gate que existe para
    atrapar justamente esa clase de verde. Ver :ref:`h-api-993`.
    """

    ANCHORED = '^src/addons/base/models/ir_http.py:'

    def test_an_anchored_pattern_excludes_the_line(self):
        line = 'src/addons/base/models/ir_http.py:224:    def slugify_one(cls'
        assert gate.excludes(self.ANCHORED, line)

    def test_the_anchor_does_not_reach_another_file(self):
        line = 'addons/website_sale/controllers/serializers.py:63: slugify_one'
        assert not gate.excludes(self.ANCHORED, line)

    def test_an_invalid_pattern_falls_back_to_the_substring(self):
        """Un patron que ``re`` no compila no tumba la medicion."""
        assert gate.excludes('[', 'una [ suelta')
        assert not gate.excludes('[', 'sin corchete')


class TestTheRerunReproducesWhatTheAuthorMeasured:
    """Cada caso es un reclamo real del árbol, con su conteo de hoy."""

    def test_a_zero_the_port_left_false_is_seen(self):
        """``ir_ui_view.py`` se portó; el cero de ``res_groups.py`` caducó."""
        claiming = pathlib.Path('src/addons/base/models/res_groups.py')
        count, why = gate.rerun('grep -rn "^class IrUiView" src/', claiming)
        assert why is None, why
        assert count > 0, 'el porte de ir_ui_view.py dejó de verse'

    def test_the_port_contradicting_its_own_prose_is_seen(self):
        """``ir_model.py`` declina citando un cero y declara la clase él mismo.

        Es el control que separa las dos exclusiones: por archivo entero, este
        caso desaparece —la única coincidencia está en el archivo que reclama—
        y el gate publica un falso negativo.
        """
        claiming = pathlib.Path('src/addons/base/models/ir_model.py')
        count, why = gate.rerun(r'grep -rn "^class IrModel\b" src/', claiming)
        assert why is None, why
        assert count == 1, 'la clase que el propio porte añadió debe contar'

    def test_count_mode_reads_the_number_not_the_lines(self):
        """``grep -ic`` imprime UN número en UNA línea: contar líneas daría 1.

        El caso fijaba ``count == 0`` cuando ``stdnum`` no era dependencia. Al
        declararla (``api@414b286f``) el mismo comando pasó a dar **5**, y el
        caso rojo — que es el gate funcionando: un reclamo de cero caducó y lo
        dijo. Lo que el caso prueba no es el cero sino la LECTURA, así que la
        aserción pasa a ser la que de verdad discrimina: un conteo mayor que
        uno sólo puede venir de leer el número impreso, nunca de contar las
        líneas de salida.
        """
        claiming = pathlib.Path('addons/account_peppol/models/res_company.py')
        count, why = gate.rerun('grep -ic stdnum uv.lock', claiming)
        assert why is None, why
        assert count > 1, 'la salida de -c ES el número, no el conteo de líneas'

    def test_a_shell_glob_is_expanded(self):
        """El glob se expande sin shell: ``src/orm/*.py`` llega como archivos.

        El caso fijaba ``count == 0`` cuando ``src/orm/`` no declaraba ningun
        ``def new(``. Al portar :class:`orm.registry.Registry` con su
        ``new`` (tarea #342) el mismo comando pasa a dar **1**, y el caso se
        puso rojo — que es el gate funcionando: un reclamo de cero caduco y lo
        dijo, igual que le paso arriba al de ``stdnum``.

        Lo que el caso prueba no es el cero sino la EXPANSION, asi que la
        asercion pasa a la que discrimina: si el glob llegara literal, grep
        recibiria una ruta inexistente y ``why`` traeria el motivo en vez de
        ``None``. Un conteo positivo sobre archivos reales solo es posible con
        el glob ya expandido.
        """
        claiming = pathlib.Path('addons/web/models/models.py')
        count, why = gate.rerun('grep -rn "def new(" src/orm/*.py', claiming)
        assert why is None, why
        assert count >= 1, 'el glob llego literal: grep no leyo ningun archivo'


    def test_a_grep_v_pipe_filters_in_python(self):
        """Dos autores ya excluían su archivo a mano; se sostiene el filtro."""
        claiming = pathlib.Path('src/addons/base/models/res_company.py')
        count, why = gate.rerun(
            'grep -rn "zeep" src/ | grep -v res_company.py', claiming)
        assert why is None, why
        assert count >= 0

    def test_a_missing_path_is_named_not_counted(self):
        """Una ruta que ya no existe se declara; publicar 0 sería un verde falso."""
        claiming = pathlib.Path('addons/web/models/models.py')
        count, why = gate.rerun(
            'grep -n "_render" src/addons/*/models/template_expressions.py',
            claiming)
        assert count is None
        assert 'ya no existe' in why, why


class TestTheGateRefusesRatherThanPublishAFalseGreen:
    """Un cero sin alcance no distingue «no hay» de «no medí»."""

    def test_it_exits_two_without_emitting_a_count(self, tmp_path):
        (tmp_path / 'src').mkdir()
        (tmp_path / 'addons').mkdir()
        done = subprocess.run(
            [sys.executable, str(REPO / 'scripts' / 'check_stale_zero_claims.py')],
            cwd=tmp_path, capture_output=True, text=True)
        assert done.returncode == 2, done.stdout
        assert 'caducado' not in done.stdout, done.stdout
        assert 'verde falso' in done.stderr, done.stderr

    def test_strict_blocks_a_claim_outside_the_baseline(self, tmp_path):
        """Un reclamo caducado fuera del baseline bloquea en ``--strict``.

        Es el par discriminante del congelado: si el baseline no se leyera,
        este caso y el siguiente darían lo mismo.

        El control positivo era la deuda viva del árbol —*"con el baseline
        vacío bloquean los 24 reclamos reales"*— y el barrido de la tarea
        #250 la consumió entera: con el baseline vacío el gate da hoy exit 0
        sobre el árbol real, así que el caso dejó de poder fallar por la vía
        que medía. Ahora fabrica su propio reclamo caducado en un árbol
        sintético, como ``test_it_exits_two_without_emitting_a_count``: un
        docstring cita un ``grep`` con **0** y el archivo de al lado hace
        que ese ``grep`` devuelva 1.
        """
        (tmp_path / 'addons').mkdir()
        src = tmp_path / 'src'
        src.mkdir()
        (src / 'declared.py').write_text('class Declared:\n    pass\n')
        (src / 'claim.py').write_text(
            '"""Razón caducada a propósito.\n\n'
            'Medido: ``grep -rn "^class Declared" src/`` → **0**.\n"""\n')
        empty = tmp_path / 'vacio.txt'
        empty.write_text('')
        env = dict(os.environ, STALE_ZERO_BASELINE=str(empty))
        done = subprocess.run(
            [sys.executable,
             str(REPO / 'scripts' / 'check_stale_zero_claims.py'), '--strict'],
            cwd=tmp_path, capture_output=True, text=True, env=env)
        assert done.returncode == 1, done.stdout + done.stderr
        assert 'fuera del baseline' in done.stdout, done.stdout
        assert 'claim.py' in done.stdout, done.stdout

    def test_the_frozen_debt_does_not_block(self):
        done = self._run('--strict')
        assert done.returncode == 0, done.stdout
        assert 'en baseline:' in done.stdout, done.stdout

    def test_an_explicit_file_list_without_claims_is_not_a_refusal(self):
        """El rehúse es del barrido del árbol, no de una lista de archivos.

        El ``pre-commit`` invoca el gate con los ``.py`` en *staging*, y un
        commit que no toca prosa de porte da 0 citas legítimamente. Sin la
        distinción, el gate bloqueó su propio commit —medido: el commit de
        este cambio— y bloquearía todos los demás.
        """
        done = self._run('--strict', 'src/tools/mail.py')
        assert done.returncode == 0, done.stdout + done.stderr
        assert 'verde falso' not in done.stderr, done.stderr
        assert '0 cita(s) con comando' in done.stdout, done.stdout

    def test_an_explicit_file_list_still_reads_its_claims(self):
        """CONTROL del par: sin él, «no rehúsa» y «no mide» dan lo mismo."""
        done = self._run('--strict', 'src/addons/base/models/ir_http.py')
        assert done.returncode == 0, done.stdout + done.stderr
        assert '1 cita(s) con comando' in done.stdout, done.stdout

    @staticmethod
    def _run(*flags, baseline=None):
        env = dict(os.environ)
        if baseline is not None:
            env['STALE_ZERO_BASELINE'] = str(baseline)
        return subprocess.run(
            [sys.executable,
             str(REPO / 'scripts' / 'check_stale_zero_claims.py'), *flags],
            cwd=REPO, capture_output=True, text=True, env=env)
