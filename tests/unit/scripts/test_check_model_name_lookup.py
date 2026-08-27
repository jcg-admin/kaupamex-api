"""Pruebas de ``scripts/check_model_name_lookup.py`` (H-API-751, tarea #619).

El control positivo **no está fabricado**: es el archivo real que
``tests/unit/service/test_get_public_method.py`` tenía en ``api@91481df``,
recuperado de git. Es la exigencia de ``hallazgo-abierto-genera-sucesor.md`` —
un incumplidor escrito por quien escribió el patrón hereda su encuadre y
confirma el instrumento en vez de medirlo.

Y ese archivo real es el caso difícil, no uno cualquiera: declara ``_Base``
**abstracta** heredando de ``models.Model`` y ``_Model`` **concreta**
heredando de ``_Base``. Un emparejador que sólo mirara ``models.Model`` en las
bases directas sería ciego justo al ofensor; uno que no mirara ``abstract =
True`` señalaría a ``_Base``, que Django acepta. La prueba fija las dos mitades.
"""
import pathlib
import subprocess

import django.db.models.base as django_model_base
import pytest

from scripts.check_model_name_lookup import main, scan_file

pytestmark = [pytest.mark.unit]

#: Adaptado de ``odoo19c``-style: una raíz abstracta y una concreta que hereda
#: de ella. Reproduce la FORMA del caso real con nombres legales, para el
#: control negativo.
LEGAL_TREE = '''from django.db import models


class Base(models.Model):
    class Meta:
        abstract = True


class Concrete(Base):
    class Meta:
        managed = False
        app_label = 'base'
'''

#: La segunda regla del mismo método de Django (``models.E024``). Se prueba
#: aparte porque el gate implementa las DOS que la fuente declara.
DOUBLE_UNDERSCORE = '''from django.db import models


class My__Model(models.Model):
    class Meta:
        app_label = 'base'
'''

#: Una abstracta con nombre ilegal: Django la acepta porque las abstractas no
#: entran en ``apps.get_models()`` y nunca llegan al check.
ABSTRACT_WITH_UNDERSCORE = '''from django.db import models


class _Helper(models.Model):
    class Meta:
        abstract = True
'''

#: Una clase de apoyo que NO es modelo. Su nombre con guion bajo es idiomático
#: de Python y no tiene nada que ver con el lookup.
PLAIN_HELPER = '''class _Cache:
    def get(self):
        return None
'''


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return path


def _real_offender(tmp_path):
    """El archivo verbatim de ``api@91481df``, traído de git."""
    salida = subprocess.run(
        ['git', 'show', '91481df:tests/unit/service/test_get_public_method.py'],
        capture_output=True, text=True, check=True,
    )
    return _write(tmp_path, 'positivo_real.py', salida.stdout)


def test_the_real_offender_from_git_is_caught(tmp_path):
    """El control positivo real: ``_Model`` de ``api@91481df``.

    Es el modelo que tumbó ``run_checks_or_raise()`` para todo el árbol, y su
    causa vivía en otro archivo y otro directorio que el fallo.
    """
    findings = scan_file(_real_offender(tmp_path))
    nombres = {f[1] for f in findings}
    assert nombres == {'_Model'}, (
        f'esperado sólo _Model; medido {nombres} — si sale _Base, el gate no '
        f'está mirando abstract = True'
    )
    assert findings[0][2] == 'models.E023'


def test_the_abstract_base_of_the_real_offender_is_not_caught(tmp_path):
    """``_Base`` convive con ``_Model`` en el mismo archivo y es legal.

    La mitad que un gate ingenuo rompe: señalar la abstracta obligaría a
    renombrarla sin motivo, y Django nunca la mira.
    """
    findings = scan_file(_real_offender(tmp_path))
    assert '_Base' not in {f[1] for f in findings}


def test_a_concrete_model_inheriting_a_local_abstract_is_recognised(tmp_path):
    """La transitividad dentro del archivo — sin ella el gate es ciego.

    ``Concrete`` no nombra ``models.Model`` en sus bases: llega por ``Base``.
    """
    path = _write(tmp_path, 'legal.py', LEGAL_TREE)
    assert scan_file(path) == []
    # Y con el nombre ilegal, la MISMA forma sí se señala.
    ilegal = _write(tmp_path, 'ilegal.py', LEGAL_TREE.replace('Concrete', '_Concrete'))
    assert {f[1] for f in scan_file(ilegal)} == {'_Concrete'}


def test_the_double_underscore_rule_is_implemented_too(tmp_path):
    """``models.E024`` — la segunda regla del mismo método de Django.

    Se implementa porque la fuente la declara junto a la primera, en el mismo
    ``_check_model_name_db_lookup_clashes`` y por la misma colisión.
    """
    findings = scan_file(_write(tmp_path, 'e024.py', DOUBLE_UNDERSCORE))
    assert [(f[1], f[2]) for f in findings] == [('My__Model', 'models.E024')]


def test_an_abstract_model_may_keep_its_underscore(tmp_path):
    assert scan_file(_write(tmp_path, 'abs.py', ABSTRACT_WITH_UNDERSCORE)) == []


def test_a_plain_helper_class_is_not_a_model(tmp_path):
    assert scan_file(_write(tmp_path, 'helper.py', PLAIN_HELPER)) == []


def test_main_returns_one_on_the_real_offender_and_zero_on_the_tree(tmp_path, capsys):
    """Los dos sentidos, con salida citable.

    El árbol limpio imprime su **denominador** junto al veredicto: sin él, un
    instrumento ciego y uno correcto publican el mismo cero.
    """
    assert main([str(_real_offender(tmp_path))]) == 1
    salida = capsys.readouterr().out
    assert 'models.E023' in salida and 'alcance medido' in salida

    assert main([str(_write(tmp_path, 'legal.py', LEGAL_TREE))]) == 0
    assert 'alcance medido: 1 archivos' in capsys.readouterr().out


def test_the_gate_agrees_with_django_on_the_rule_it_mirrors():
    """El patrón sale de la fuente, no de la memoria.

    Se lee ``django/db/models/base.py`` en el paquete instalado y se confirma
    que la condición sigue siendo la que el gate implementa. Si Django cambia
    la regla, esta prueba lo dice antes de que el gate mienta.
    """
    fuente = pathlib.Path(django_model_base.__file__).read_text(encoding='utf-8')
    assert 'model_name.startswith("_") or model_name.endswith("_")' in fuente
    assert 'id="models.E023"' in fuente
    assert 'elif LOOKUP_SEP in model_name' in fuente
    assert 'id="models.E024"' in fuente
