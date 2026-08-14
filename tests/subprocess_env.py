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

La lista NO se escribe a mano: sale de ``required_options()``, el registro de
opciones sin default. Si mañana se declara una nueva obligatoria, el
subproceso la recibe sin que nadie toque este archivo — que es justo lo que
evita que esta trampa vuelva por otra clave.
"""
import os

from config.settings.options import required_options

BASE_ENV = {
    'PATH': '/usr/bin:/bin',
    'HOME': '/root',
    'DJANGO_SETTINGS_MODULE': 'config.settings.testing',
}


def subprocess_env(**extra):
    """Env cerrado, más las claves obligatorias que estén en ``os.environ``.

    En un entorno con ``src/.env`` el filtro no aporta nada (decouple lee el
    archivo) y en CI aporta las once. Las dos rutas quedan cubiertas sin
    heredar el entorno entero.
    """
    env = dict(BASE_ENV)
    env.update({k: os.environ[k] for k in required_options() if k in os.environ})
    env.update(extra)
    return env
