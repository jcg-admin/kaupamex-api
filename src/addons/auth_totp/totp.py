"""RFC 4226/6238 TOTP — adaptado VERBATIM de Odoo (auth_totp/models/totp.py).

Fuente: ``scratchpad/odoo-enterprise-18/.../addons/auth_totp/models/totp.py``
(Odoo 18.0, LGPL-3). Es un algoritmo hand-rolled (``hmac`` + ``struct``), sin
azúcar sintáctica del framework Odoo — se copia tal cual con atribución
(DEC-KX-03). Verificado idéntico en odoo18-ent y my-odoo-enterprise-18.0
(5/5 marcadores de algoritmo).

Adaptado de @progress-independiente: sólo se removió la dependencia de Odoo
(no había ninguna en este archivo). ``hotp`` devuelve el código como ``int``;
``TOTP.match`` compara ``hotp(key, counter) == code`` — el llamador pasa el
código de 6 dígitos como ``int``.
"""
import hmac
import struct
import time

# 160 bits, as recommended by HOTP RFC 4226, section 4, R6.
# Google Auth uses 80 bits by default but supports 160.
TOTP_SECRET_SIZE = 160

# The algorithm (and key URI format) allows customising these parameters but
# google authenticator doesn't support it
# https://github.com/google/google-authenticator/wiki/Key-Uri-Format
ALGORITHM = 'sha1'
DIGITS = 6
TIMESTEP = 30


class TOTP:
    def __init__(self, key):
        self._key = key

    def match(self, code, t=None, window=TIMESTEP, timestep=TIMESTEP):
        """
        :param code: authenticator code to check against this key
        :param int t: current timestamp (seconds)
        :param int window: fuzz window to account for slow fingers, network
                           latency, desynchronised clocks, ..., every code
                           valid between t-window an t+window is considered
                           valid
        """
        if t is None:
            t = time.time()

        low = int((t - window) / timestep)
        high = int((t + window) / timestep) + 1

        return next((
            counter for counter in range(low, high)
            if hotp(self._key, counter) == code
        ), None)


def hotp(secret, counter):
    # C is the 64b counter encoded in big-endian
    C = struct.pack(">Q", counter)
    mac = hmac.new(secret, msg=C, digestmod=ALGORITHM).digest()
    # the data offset is the last nibble of the hash
    offset = mac[-1] & 0xF
    # code is the 4 bytes at the offset interpreted as a 31b big-endian uint
    # (31b to avoid sign concerns). This effectively limits digits to 9 and
    # hard-limits it to 10: each digit is normally worth 3.32 bits but the
    # 10th is only worth 1.1 (9 digits encode 29.9 bits).
    code = struct.unpack_from('>I', mac, offset)[0] & 0x7FFFFFFF
    r = code % (10 ** DIGITS)
    return r
