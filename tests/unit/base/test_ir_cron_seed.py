"""Los cuatro jobs periódicos se siembran bien y el runner puede invocarlos.

Sin este test, la siembra podía romperse en silencio de dos maneras distintas y
ninguna daría un fallo visible hasta producción:

1. la data-migration deja de correr (dependencia mal declarada) → no hay filas;
2. alguien renombra el método del modelo → la fila sigue ahí, apuntando a un
   método que ya no existe, y el cron falla **en la corrida**, no al desplegar.

El caso 2 es el que importa: es exactamente el defecto que H-API-333 registró
en su forma hermana (un campo que promete algo y no lo cumple). Una fila de
``ir.cron`` cuyo ``method_name`` no resuelve es un job que parece configurado y
no lo está.

Por qué el test siembra en vez de leer lo que sembró la migración
==================================================================

La primera versión afirmaba sobre las filas que dejan las cuatro
data-migrations. **Eso no es verificable en la suite**, y el fallo enseñó por
qué: 13 archivos de tests usan ``django_db(transaction=True)``, y el
``_fixture_teardown`` de ``TransactionTestCase`` hace ``flush`` de **todas** las
tablas. Las filas creadas por una migración se truncan con el resto, y no
vuelven — la migración ya consta en ``django_migrations``, así que su
``RunPython`` no se re-ejecuta. Medido tras una corrida completa:
``IrCron.objects.count()`` → 0, con las cuatro migraciones aplicadas.

**Producción no tiene ese problema** (nadie hace ``flush``), así que la
data-migration sigue siendo el mecanismo correcto de entrega — el mismo que
H-API-263 restauró. Lo que cambia es qué puede afirmar un test: siembra con el
mismo helper que usa la migración y verifica el **spec** y su resolubilidad.
Eso cubre los dos defectos de arriba sin depender de un estado que la suite
destruye.

Lo que este test NO cubre, en consecuencia: que la migración se haya ejecutado
de verdad al desplegar. Eso se verifica en el despliegue
(``manage.py migrate`` + un conteo), no aquí. Registrado como la tarea #138.
"""
import pytest
from django.apps import apps

from addons.base.data import CRON_AUTOVACUUM, sembrar_cron
from addons.base.models import IrCron
from addons.helpdesk.data import CRON_AUTO_CLOSE_TICKETS
from addons.loyalty.data import CRON_EXPIRE_VOUCHERS
from addons.mail.data import CRON_EMAIL_QUEUE

pytestmark = pytest.mark.django_db

# Los cuatro specs sembrados por data-migration. Tres vienen de la tarea #124
# (management commands sueltos que ganaron horario); el cuarto es el barrido de
# ``ir.autovacuum`` (H-API-747), que reemplazó al cron propio de la purga de
# logs: ese método ahora lleva ``@api.autovacuum`` y lo recoge el colector.
#
# Se listan los objetos, no una copia de sus valores: si alguien cambia el
# method_name en el spec, el test lo sigue, y lo que se verifica es que ese
# method_name resuelva — que es el defecto real.
SPECS = [
    CRON_EMAIL_QUEUE,
    CRON_EXPIRE_VOUCHERS,
    CRON_AUTO_CLOSE_TICKETS,
    CRON_AUTOVACUUM,
]


@pytest.fixture
def sembrados():
    """Aplica los cuatro specs con el mismo helper que usan las migraciones."""
    return [sembrar_cron(apps, 'default', spec)[0] for spec in SPECS]


def test_sembrar_crea_los_cuatro_jobs(sembrados):
    esperados = {(s['model_name'], s['method_name']) for s in SPECS}
    reales = {
        (c.ir_actions_server.model_name, c.ir_actions_server.method_name)
        for c in IrCron.objects.select_related('ir_actions_server')
    }
    assert esperados <= reales, f'jobs sin sembrar: {esperados - reales}'


def test_cada_job_resuelve_a_un_metodo_real(sembrados):
    """El runner hace getattr(apps.get_model(model_name), method_name)."""
    for cron in sembrados:
        accion = cron.ir_actions_server
        modelo = apps.get_model(accion.model_name)
        assert hasattr(modelo, accion.method_name), (
            f'{accion.model_name} no tiene {accion.method_name}() — la fila de '
            f'ir.cron apunta a un método inexistente'
        )
        assert callable(getattr(modelo, accion.method_name))


def test_los_jobs_sembrados_estan_activos_con_intervalo_positivo(sembrados):
    for cron in sembrados:
        assert cron.active, f'{cron.ir_actions_server.name} sembrado inactivo'
        # El CheckConstraint lo garantiza en BD; esto lo afirma como contrato
        # del spec, no del esquema.
        assert cron.interval_number > 0


def test_la_siembra_es_idempotente(sembrados):
    """Re-aplicar el spec no duplica: la clave natural es (model, method)."""
    antes = IrCron.objects.count()
    _, creado = sembrar_cron(apps, 'default', CRON_EMAIL_QUEUE)
    assert not creado
    assert IrCron.objects.count() == antes
