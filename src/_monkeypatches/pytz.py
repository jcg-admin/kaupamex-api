"""Parche de ``pytz`` — porte de ``odoo/_monkeypatches/pytz.py`` (Odoo 19).

Adaptación de ``odoo/_monkeypatches/pytz.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3 → copia con atribución, DEC-KX-03).

Traducción del docstring de la fuente, que explica el porqué: en Ubuntu
noble se retiraron algunas zonas horarias, lo que provoca errores al
asignarlas o leerlas. En el código se arregló en parte quitando toda
referencia a las zonas viejas, pero queda un problema: si una base contiene
zonas que el sistema operativo no define, la resolución falla y revienta en
ejecución. Este parche altera ``timezone`` para que caiga en la zona
canónica nueva cuando la vieja se retiró. La lista se generó revisando los
enlaces simbólicos de ``/usr/share/zoneinfo`` de Ubuntu 22.04 que
desaparecen en 24.04. Funciona al mover una base de un servidor a otro,
incluso sin migración.

**El parche NO es un no-op aquí, y se midió.** ``pytz`` trae su propia base
de zonas, no la del sistema operativo, así que resuelve por su cuenta 98 de
las 99 entradas del mapa. La que no: ``Türkiye``, que **no** está en
``pytz.all_timezones_set`` de ``pytz==2026.3.post1`` y que el mapa manda a
``Europe/Istanbul``. Sin el parche, una fila con esa zona levanta
``UnknownTimeZoneError``.

*Métrica:* entradas de ``_tz_mapping`` ausentes de ``pytz.all_timezones_set``
con ``pytz==2026.3.post1``, medido 2026-08-29.
*Ciega a:* lo que ocurra con otra versión de ``pytz`` — la base de zonas
cambia varias veces al año, así que el conteo es de hoy, no una propiedad
del parche. Lo que no cambia es que el mapa cubre el caso, lo haya o no.

El resto de la raíz ``_monkeypatches/`` de la referencia —21 módulos más,
con su cargador perezoso por ``sys.meta_path``— **no está portada**: aquí el
único consumidor es ``tools/safe_eval``, que llama a ``patch_module()``
directamente antes de envolver ``pytz``. Portar la raíz entera con su gancho
de importación es trabajo propio, registrado como tarea aparte.
"""
import pytz

_tz_mapping = {
    "Africa/Asmera": "Africa/Nairobi",
    "America/Argentina/ComodRivadavia": "America/Argentina/Catamarca",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Cordoba": "America/Argentina/Cordoba",
    "America/Fort_Wayne": "America/Indiana/Indianapolis",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "America/Jujuy": "America/Argentina/Jujuy",
    "America/Knox_IN": "America/Indiana/Knox",
    "America/Louisville": "America/Kentucky/Louisville",
    "America/Mendoza": "America/Argentina/Mendoza",
    "America/Rosario": "America/Argentina/Cordoba",
    "Antarctica/South_Pole": "Pacific/Auckland",
    "Asia/Ashkhabad": "Asia/Ashgabat",
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Chungking": "Asia/Shanghai",
    "Asia/Dacca": "Asia/Dhaka",
    "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Macao": "Asia/Macau",
    "Asia/Rangoon": "Asia/Yangon",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Asia/Thimbu": "Asia/Thimphu",
    "Asia/Ujung_Pandang": "Asia/Makassar",
    "Asia/Ulan_Bator": "Asia/Ulaanbaatar",
    "Atlantic/Faeroe": "Atlantic/Faroe",
    "Australia/ACT": "Australia/Sydney",
    "Australia/LHI": "Australia/Lord_Howe",
    "Australia/North": "Australia/Darwin",
    "Australia/NSW": "Australia/Sydney",
    "Australia/Queensland": "Australia/Brisbane",
    "Australia/South": "Australia/Adelaide",
    "Australia/Tasmania": "Australia/Hobart",
    "Australia/Victoria": "Australia/Melbourne",
    "Australia/West": "Australia/Perth",
    "Brazil/Acre": "America/Rio_Branco",
    "Brazil/DeNoronha": "America/Noronha",
    "Brazil/East": "America/Sao_Paulo",
    "Brazil/West": "America/Manaus",
    "Canada/Atlantic": "America/Halifax",
    "Canada/Central": "America/Winnipeg",
    "Canada/Eastern": "America/Toronto",
    "Canada/Mountain": "America/Edmonton",
    "Canada/Newfoundland": "America/St_Johns",
    "Canada/Pacific": "America/Vancouver",
    "Canada/Saskatchewan": "America/Regina",
    "Canada/Yukon": "America/Whitehorse",
    "Chile/Continental": "America/Santiago",
    "Chile/EasterIsland": "Pacific/Easter",
    "Cuba": "America/Havana",
    "Egypt": "Africa/Cairo",
    "Eire": "Europe/Dublin",
    "Europe/Kiev": "Europe/Kyiv",
    "Europe/Uzhgorod": "Europe/Kyiv",
    "Europe/Zaporozhye": "Europe/Kyiv",
    "GB": "Europe/London",
    "GB-Eire": "Europe/London",
    "GMT+0": "Etc/GMT",
    "GMT-0": "Etc/GMT",
    "GMT0": "Etc/GMT",
    "Greenwich": "Etc/GMT",
    "Hongkong": "Asia/Hong_Kong",
    "Iceland": "Africa/Abidjan",
    "Iran": "Asia/Tehran",
    "Israel": "Asia/Jerusalem",
    "Jamaica": "America/Jamaica",
    "Japan": "Asia/Tokyo",
    "Kwajalein": "Pacific/Kwajalein",
    "Libya": "Africa/Tripoli",
    "Mexico/BajaNorte": "America/Tijuana",
    "Mexico/BajaSur": "America/Mazatlan",
    "Mexico/General": "America/Mexico_City",
    "Navajo": "America/Denver",
    "NZ": "Pacific/Auckland",
    "NZ-CHAT": "Pacific/Chatham",
    "Pacific/Enderbury": "Pacific/Kanton",
    "Pacific/Ponape": "Pacific/Guadalcanal",
    "Pacific/Truk": "Pacific/Port_Moresby",
    "Poland": "Europe/Warsaw",
    "Portugal": "Europe/Lisbon",
    "PRC": "Asia/Shanghai",
    "ROC": "Asia/Taipei",
    "ROK": "Asia/Seoul",
    "Singapore": "Asia/Singapore",
    "Türkiye": "Europe/Istanbul",
    "UCT": "Etc/UTC",
    "Universal": "Etc/UTC",
    "US/Alaska": "America/Anchorage",
    "US/Aleutian": "America/Adak",
    "US/Arizona": "America/Phoenix",
    "US/Central": "America/Chicago",
    "US/Eastern": "America/New_York",
    "US/East-Indiana": "America/Indiana/Indianapolis",
    "US/Hawaii": "Pacific/Honolulu",
    "US/Indiana-Starke": "America/Indiana/Knox",
    "US/Michigan": "America/Detroit",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "US/Samoa": "Pacific/Pago_Pago",
    "W-SU": "Europe/Moscow",
    "Zulu": "Etc/UTC",
}

original_pytz_timezone = pytz.timezone


def patch_module():
    def timezone(name):
        if name not in pytz.all_timezones_set and name in _tz_mapping:
            name = _tz_mapping[name]
        return original_pytz_timezone(name)

    pytz.timezone = timezone
