"""Entorno mínimo para los tests que arrancan el producto como subproceso.

Los tests de ``kaupamex-bin`` y del subcomando ``cron`` lanzan un proceso
nuevo con un ``env`` **cerrado** — deliberadamente, para que el subproceso no
herede el entorno del runner y la prueba mida el binario, no la sesión que la
ejecuta. Pero ese cierre dejaba fuera las claves que ``config.settings`` exige
sin ``default=`` (SOL-087, 12-factor fail-loud), así que el subproceso moría
en el import de settings antes de ejercitar aquello que el test declara medir.

Localmente no se notaba: ``python-decouple`` encuentra ``src/.env`` en disco y
resuelve las claves desde ahí. En CI ese archivo no existe —está gitignored— y
las claves viven en ``os.environ``, que el ``env`` cerrado descartaba. El
mismo test verde en el portátil fallaba en el runner con ``SECRET_KEY not
found``. Ver H-API-575.

La lista NO se escribe a mano: sale de ``env_names()``, el registro entero de
opciones reconocidas. Si mañana se declara una nueva, el subproceso la recibe
sin que nadie toque este archivo — que es justo lo que evita que esta trampa
vuelva por otra clave.

**No basta con las requeridas**, y el primer arreglo se quedó ahí: filtraba
por ``required_options()``, así que ``DB_QA_SSL_MODE`` —que tiene
``default=''``— no llegaba al hijo, y su conexión caía en el ``else`` de
``testing.py`` que fija ``verify-full``. El proceso ya no moría importando
settings; moría conectando, con ``server does not support SSL`` en el
contenedor de CI y ``certificate verify failed`` contra un PostgreSQL local.
Un toggle opcional no rompe el import cuando falta, pero sí decide a qué base
y con qué TLS se conecta: el criterio correcto es "qué configura al proceso",
no "qué falta si no está".

**Y la base del hijo NO es la del archivo: es la que Django resolvió.** Con
``pytest-xdist`` cada worker corre contra ``<base>_gwN`` —``pytest_django``
sufija ``TEST.NAME`` con el ``workerid`` (``fixtures.py:77-83``)— mientras
``DB_QA_NAME`` sigue diciendo la base pelada. Un hijo que lea el archivo se
conecta a una base que en ese momento puede no existir.

Pasaba inadvertido porque ``--reuse-db`` deja la base pelada en pie de una
corrida en serie anterior: el hijo la encontraba migrada y el caso salía
verde. Ese verde no distinguía *"el subcomando funciona"* de *"quedó una base
de otra corrida"* — sub-patrón D de ``metrica-decide-la-conclusion.md``. Lo
destapó la primera corrida con ``--create-db`` sobre una base nueva: dos casos
de ``test_ir_cron_runner.py`` murieron con ``FATAL: database
"kaupamex_core_qa2" does not exist``. Ver :ref:`h-api-919`.

Por eso el nombre sale de ``connection.settings_dict['NAME']`` en el momento
de la llamada, que es el único sitio donde vive el valor **efectivo**.
"""
import os

from django.db import connection

from config.settings.options import env_names

BASE_ENV = {
    'PATH': '/usr/bin:/bin',
    'HOME': '/root',
    'DJANGO_SETTINGS_MODULE': 'config.settings.testing',
}


def subprocess_env(**extra):
    """Env cerrado, más las claves reconocidas que estén en ``os.environ``.

    En un entorno con ``src/.env`` el filtro no aporta nada (decouple lee el
    archivo) y en CI aporta las que el runner exporta. Las dos rutas quedan
    cubiertas sin heredar el entorno entero.

    ``DB_QA_NAME`` se sobrescribe con la base **efectiva** de la conexión, que
    bajo ``pytest-xdist`` lleva el sufijo del worker. Ver el docstring del
    módulo: sin esto el hijo se conecta a la base pelada, que con
    ``--create-db`` no existe.

    Un ``extra`` explícito gana sobre las dos fuentes: quien llama sabe más.
    """
    env = dict(BASE_ENV)
    env.update({k: os.environ[k] for k in env_names() if k in os.environ})
    env['DB_QA_NAME'] = connection.settings_dict['NAME']
    env.update(extra)
    return env
