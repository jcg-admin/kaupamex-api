"""URLs del addon ``html_editor`` — ≙ los catorce ``@http.route`` de la fuente.

Las rutas conservan **las dos** que la referencia declara por endpoint cuando
declara dos: el prefijo histórico ``/web_editor/…`` y el actual
``/html_editor/…``. Retirar el histórico sería romper el cliente que ya lo
usa, que es justamente lo que la fuente evita declarando los dos.

**Este módulo no está cableado todavía en el ``URLconf`` raíz.** Su línea vive
en ``src/config/urls.py``, que está fuera de los archivos de este puerto. La
línea que hay que añadir es::

    path('', include(('addons.html_editor.controllers.urls', 'html_editor'),
                     namespace='html_editor_v2')),

Va sin prefijo de versión a propósito: las rutas de la fuente son absolutas
(``/web_editor/…``, ``/html_editor/…``) y el cliente del editor las construye
con esa forma. Se reporta al orquestador como sucesor.
"""
from django.urls import path

from .main import (
    add_data_endpoint,
    add_url_endpoint,
    bus_broadcast_endpoint,
    generate_text_endpoint,
    get_ice_servers_endpoint,
    get_image_info_endpoint,
    image_shape_endpoint,
    link_preview_metadata_endpoint,
    link_preview_metadata_internal_endpoint,
    media_library_search_endpoint,
    modify_image_endpoint,
    remove_endpoint,
    save_library_media_endpoint,
    shape_endpoint,
    video_url_data_endpoint,
)

app_name = 'html_editor_v2'

urlpatterns = [
    path('html_editor/attachment/remove', remove_endpoint, name='remove'),

    path('web_editor/get_image_info', get_image_info_endpoint,
         name='get_image_info_legacy'),
    path('html_editor/get_image_info', get_image_info_endpoint,
         name='get_image_info'),

    path('web_editor/video_url/data', video_url_data_endpoint,
         name='video_url_data_legacy'),
    path('html_editor/video_url/data', video_url_data_endpoint,
         name='video_url_data'),

    path('web_editor/attachment/add_data', add_data_endpoint,
         name='add_data_legacy'),
    path('html_editor/attachment/add_data', add_data_endpoint,
         name='add_data'),

    path('web_editor/attachment/add_url', add_url_endpoint,
         name='add_url_legacy'),
    path('html_editor/attachment/add_url', add_url_endpoint, name='add_url'),

    path('web_editor/modify_image/<int:attachment_id>', modify_image_endpoint,
         name='modify_image_legacy'),
    path('html_editor/modify_image/<int:attachment_id>', modify_image_endpoint,
         name='modify_image'),

    path('web_editor/save_library_media', save_library_media_endpoint,
         name='save_library_media_legacy'),
    path('html_editor/save_library_media', save_library_media_endpoint,
         name='save_library_media'),

    path('web_editor/shape/<str:module>/<path:filename>', shape_endpoint,
         name='shape_legacy'),
    path('html_editor/shape/<str:module>/<path:filename>', shape_endpoint,
         name='shape'),

    path('web_editor/image_shape/<str:img_key>/<str:module>/<path:filename>',
         image_shape_endpoint, name='image_shape_legacy'),
    path('html_editor/image_shape/<str:img_key>/<str:module>/<path:filename>',
         image_shape_endpoint, name='image_shape'),

    path('web_editor/generate_text', generate_text_endpoint,
         name='generate_text_legacy'),
    path('html_editor/generate_text', generate_text_endpoint,
         name='generate_text'),

    path('web_editor/get_ice_servers', get_ice_servers_endpoint,
         name='get_ice_servers_legacy'),
    path('html_editor/get_ice_servers', get_ice_servers_endpoint,
         name='get_ice_servers'),

    path('web_editor/bus_broadcast', bus_broadcast_endpoint,
         name='bus_broadcast_legacy'),
    path('html_editor/bus_broadcast', bus_broadcast_endpoint,
         name='bus_broadcast'),

    path('html_editor/link_preview_external', link_preview_metadata_endpoint,
         name='link_preview_external'),
    path('html_editor/link_preview_internal',
         link_preview_metadata_internal_endpoint, name='link_preview_internal'),

    path('html_editor/media_library_search', media_library_search_endpoint,
         name='media_library_search'),
]
