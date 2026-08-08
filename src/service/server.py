"""``server`` — fiel a ``odoo/service/server.py`` (Odoo 19).

En Odoo ``service/server.py`` **es el runtime del servidor**: el WSGI server y sus
variantes (``ThreadedServer``, ``GeventServer``, ``PreforkServer``), los workers
(``WorkerHTTP`` para requests, ``WorkerCron`` para el scheduler), el auto-reload
por watchdog/inotify (``FSWatcher*``), ``cron_database_list`` y el bootstrap
(``load_server_wide_modules``). Es puro proceso/red — no toca modelos ni datos.

Mapeo a la pila — stub delgado documentado; **el runtime de servidor lo provee
Gunicorn**, no se reimplementa (mismo criterio que los stubs de motor del ORM y
``registry``). Desde ADR-027 el servidor **viaja dentro del producto**: es una
dependencia de producción declarada en ``pyproject.toml``, configurada en
``setup/gunicorn.conf.py``. Antes lo proveía Apache + ``mod_wsgi`` desde el
submódulo ``server``, lo que ataba la instalación a que el destino tuviera
Apache — incompatible con distribuir el producto L0 a terceros.

===================================  ===================================================
Odoo ``service/server``              Equivalente en la pila
===================================  ===================================================
``ThreadedServer`` / ``PreforkServer``  **prod:** Gunicorn en prefork síncrono
/ ``GeventServer`` (WSGI + workers)  (``setup/gunicorn.conf.py``); **dev:** ``runserver``
``WorkerHTTP``                       worker ``sync`` de Gunicorn
``WorkerCron`` + ``cron_database_list``  ``ir.cron`` (modelo de control + runner
                                     portados, ``addons/base/models/ir_cron.py``)
                                     disparado por el subcomando ``cron``
                                     (``addons/base/management/commands/cron.py``,
                                     ``kaupamex-bin cron``); el "por-DB" lo cubre
                                     ``service.db.list_company_db_names`` +
                                     ``install_company_aliases`` (DB-per-company
                                     SOL-091)
``FSWatcherInotify`` / autoreload    autoreload de ``runserver`` (dev); en prod no
                                     aplica (deploy inmutable)
``load_server_wide_modules``         ``INSTALLED_APPS`` + ``apps.populate()`` de Django
``set_limit_memory_hard`` (rlimit)   el reciclado por peticiones lo cubre
                                     ``max_requests``; el límite duro de memoria lo fija
                                     el supervisor (systemd), no el código
===================================  ===================================================

La propia referencia documenta esta opción: ``odoo19c: setup/odoo-wsgi.example.py``
publica la invocación de Gunicorn con su configuración (``bind``, ``workers``,
``timeout``, ``max_requests``), de modo que adoptarlo es **derivado** de la
referencia, no invención.

Por qué stub: recrear el servidor WSGI, el prefork y el watcher duplicaría
Gunicorn y ``runserver``. Ningún addon importa ``service/server`` —es bootstrap—;
se documenta para que el layout espeje ``odoo/service/`` y el lector sepa dónde
vive cada pieza del runtime (Gunicorn + Django), no en Python de aplicación.
"""
