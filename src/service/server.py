"""``server`` — fiel a ``odoo/service/server.py`` (Odoo 19).

En Odoo ``service/server.py`` **es el runtime del servidor**: el WSGI server y sus
variantes (``ThreadedServer``, ``GeventServer``, ``PreforkServer``), los workers
(``WorkerHTTP`` para requests, ``WorkerCron`` para el scheduler), el auto-reload
por watchdog/inotify (``FSWatcher*``), ``cron_database_list`` y el bootstrap
(``load_server_wide_modules``). Es puro proceso/red — no toca modelos ni datos.

Mapeo a la pila — stub delgado documentado; **el runtime de servidor lo provee la
plataforma de despliegue**, no se reimplementa (mismo criterio que los stubs de
motor del ORM y ``registry``):

===================================  ===================================================
Odoo ``service/server``              Equivalente en la pila
===================================  ===================================================
``ThreadedServer`` / ``PreforkServer``  **prod:** Apache + ``mod_wsgi`` (submódulo
/ ``GeventServer`` (WSGI + workers)  ``server``, Ubuntu 24.04); **dev:** ``runserver``
``WorkerHTTP``                       worker WSGI de mod_wsgi / gunicorn
``WorkerCron`` + ``cron_database_list``  ``ir.cron`` (portado como modelo de control)
                                     disparado por un management command / Celery beat;
                                     el "por-DB" lo cubre el router multi-DB
                                     (``orm/routers.py``, DB-per-company SOL-091)
``FSWatcherInotify`` / autoreload    autoreload de ``runserver`` (dev); en prod no
                                     aplica (deploy inmutable)
``load_server_wide_modules``         ``INSTALLED_APPS`` + ``apps.populate()`` de Django
``set_limit_memory_hard`` (rlimit)   límites del proceso los fija el supervisor de
                                     deploy (systemd / mod_wsgi), no el código
===================================  ===================================================

Por qué stub: recrear el servidor WSGI, el prefork y el watcher duplicaría
``mod_wsgi``/``gunicorn`` y ``runserver``. Ningún addon importa ``service/server``
—es bootstrap—; se documenta para que el layout espeje ``odoo/service/`` y el
lector sepa dónde vive cada pieza del runtime en nuestra pila (submódulo
``server`` + Django), no en Python de aplicación.
"""
