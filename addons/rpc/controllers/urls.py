"""URLs — addon ``rpc``.

La referencia declara dos rutas: el despacho y un catch-all que devuelve 404
con un mensaje útil (*"Did you mean POST /json/2/<model>/<method>?"*). Se
conservan las dos: el catch-all es lo que convierte un error de forma en un
mensaje accionable en vez de un 404 mudo del router.
"""
from django.urls import path, re_path

from .json2 import json2_404, json2_rpc

app_name = 'rpc_v2'

urlpatterns = [
    path('<str:model_name>/<str:method_name>', json2_rpc, name='call'),
    # ≙ `@http.route(['/json/2', '/json/2/<path:subpath>'])`, el catch-all.
    re_path(r'^(?P<subpath>.*)$', json2_404, name='hint'),
]
