"""``manage.py migrate`` arranca: ningún chequeo de sistema de nivel ERROR.

``migrate`` corre los chequeos de sistema antes de migrar
(``BaseCommand.requires_system_checks``) y se detiene con un
``SystemCheckError`` ante uno de nivel ERROR. pytest-django no los corre,
así que la suite no veía uno que bloqueaba toda migración real: el nombre de
34 caracteres del índice de ``product.template`` (``models.E034``).

``models.E034`` sólo sale con la base pedida (``check --database
default``), que es como ``migrate`` los corre: sin ella el chequeo calla.

*Métrica:* mensajes de ``run_checks(databases=['default'])`` con nivel
``ERROR`` o mayor.
*Ciega a:* las otras bases de compañía, que comparten modelos y por tanto
los mismos chequeos de modelo.
"""
from django.core.checks import ERROR, run_checks


def test_no_system_check_blocks_migrate():
    errors = [message for message in run_checks(databases=['default'])
              if message.level >= ERROR]
    assert errors == []
