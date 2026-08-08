# -*- coding: utf-8 -*-
"""
    werkzeug.useragents
    ~~~~~~~~~~~~~~~~~~~

    This module provides a helper to inspect user agent strings.  This module
    is far from complete but should work for most of the currently available
    browsers.


    :copyright: 2007 Pallets
    :license: BSD-3-Clause

    This package was vendored in odoo in order to prevent errors with werkzeug 2.1

    ---

    Vendorizado aquí desde ``odoo19c: odoo/tools/_vendor/useragents.py``
    (``odoo-tools@622ddc2a``), que a su vez lo vendorizó de werkzeug 2.0. Se
    copia por la misma razón que la referencia: werkzeug retiró el parser en
    2.1 y ``UserAgent.platform``/``.browser`` devuelven ``None`` sin él — y
    aquí, además, **werkzeug no está instalado** (medido: ``import werkzeug`` →
    ``ModuleNotFoundError``), porque la pila es Django, no Flask.

    **Divergencia declarada:** se copian ``UserAgentParser`` y sus dos tablas
    verbatim; se omite la clase ``UserAgent`` de la referencia, que sólo envuelve
    un objeto request de werkzeug (``httprequest.user_agent_class``,
    ``odoo19c: odoo/http.py:1482``). Aquí el consumidor lee la cabecera de un
    ``HttpRequest`` de Django, así que la envoltura no aplica: en su lugar se
    expone ``parse_user_agent(string)``.
"""
import re


class UserAgentParser(object):
    """A simple user agent parser.  Used by the `UserAgent`."""

    platforms = (
        ("cros", "chromeos"),
        ("iphone|ios", "iphone"),
        ("ipad", "ipad"),
        (r"darwin|mac|os\s*x", "macos"),
        ("win", "windows"),
        (r"android", "android"),
        ("netbsd", "netbsd"),
        ("openbsd", "openbsd"),
        ("freebsd", "freebsd"),
        ("dragonfly", "dragonflybsd"),
        ("(sun|i86)os", "solaris"),
        (r"x11|lin(\b|ux)?", "linux"),
        (r"nintendo\s+wii", "wii"),
        ("irix", "irix"),
        ("hp-?ux", "hpux"),
        ("aix", "aix"),
        ("sco|unix_sv", "sco"),
        ("bsd", "bsd"),
        ("amiga", "amiga"),
        ("blackberry|playbook", "blackberry"),
        ("symbian", "symbian"),
    )
    browsers = (
        ("googlebot", "google"),
        ("msnbot", "msn"),
        ("yahoo", "yahoo"),
        ("ask jeeves", "ask"),
        (r"aol|america\s+online\s+browser", "aol"),
        ("opera", "opera"),
        ("edge", "edge"),
        ("chrome|crios", "chrome"),
        ("seamonkey", "seamonkey"),
        ("firefox|firebird|phoenix|iceweasel", "firefox"),
        ("galeon", "galeon"),
        ("safari|version", "safari"),
        ("webkit", "webkit"),
        ("camino", "camino"),
        ("konqueror", "konqueror"),
        ("k-meleon", "kmeleon"),
        ("netscape", "netscape"),
        (r"msie|microsoft\s+internet\s+explorer|trident/.+? rv:", "msie"),
        ("lynx", "lynx"),
        ("links", "links"),
        ("Baiduspider", "baidu"),
        ("bingbot", "bing"),
        ("mozilla", "mozilla"),
    )

    _browser_version_re = r"(?:%s)[/\sa-z(]*(\d+[.\da-z]+)?"
    _language_re = re.compile(
        r"(?:;\s*|\s+)(\b\w{2}\b(?:-\b\w{2}\b)?)\s*;|"
        r"(?:\(|\[|;)\s*(\b\w{2}\b(?:-\b\w{2}\b)?)\s*(?:\]|\)|;)"
    )

    def __init__(self):
        self.platforms = tuple((b, re.compile(a, re.I)) for a, b in self.platforms)
        self.browsers = tuple(
            (b, re.compile(self._browser_version_re % a, re.I))
            for a, b in self.browsers
        )

    def __call__(self, user_agent):
        for platform, regex in self.platforms:  # noqa: B007
            match = regex.search(user_agent)
            if match is not None:
                break
        else:
            platform = None
        for browser, regex in self.browsers:  # noqa: B007
            match = regex.search(user_agent)
            if match is not None:
                version = match.group(1)
                break
        else:
            browser = version = None
        match = self._language_re.search(user_agent)
        if match is not None:
            language = match.group(1) or match.group(2)
        else:
            language = None
        return platform, browser, version, language


_parser = UserAgentParser()


def parse_user_agent(user_agent):
    """``(platform, browser, version, language)`` de una cabecera User-Agent.

    Sustituye al acceso ``request.httprequest.user_agent.platform`` /
    ``.browser`` de la referencia (``odoo19c: odoo/http.py:1315-1317``), que
    resuelve contra este mismo parser. Una cadena vacía devuelve la 4-tupla de
    ``None``, igual que el parser ante un agente que no matchea ninguna tabla.
    """
    if not user_agent:
        return (None, None, None, None)
    return _parser(user_agent)
