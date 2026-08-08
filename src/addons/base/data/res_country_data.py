"""Los 251 países y 8 agrupaciones de la referencia.

Extraídos de ``odoo19c: odoo/addons/base/data/res_country_data.xml``
(``odoo-tools@622ddc2a``, addon ``base``, **LGPL-3** — copia con atribución por
DEC-KX-03). **Generados leyendo el XML, no transcritos a mano:** 251 filas
escritas a mano serían 251 oportunidades de equivocarse en un dígito.

Qué desbloquea, y por qué su ausencia dolía. Sin países sembrados, tres
mecanismos quedaban inertes aunque su código estuviera escrito: el ``country``
de ``account.account.tag``, el que ``create_tax_tags`` asigna a las etiquetas
del reporte (:ref:`h-api-358`), y ``account_fiscal_country`` de la empresa, de
quien cuelgan a su vez el ``fiscal_country_codes`` de los bancos mexicanos y el
override de cuentas de diferencia de efectivo del plan de México.

``vat_label`` es el que nombra el identificador fiscal de cada país — **RFC**
en México — y es lo que la interfaz debe mostrar en vez de un genérico «VAT».

``members`` de cada agrupación son los códigos que su ``Command.set([ref(...)])``
enumera; se guardan como códigos y no como identificadores externos porque el
sembrador resuelve por ``code``, que es la clave estable del país.
"""

from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_country import ResCountry
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_currency import ResCurrency

#: Un dict por país, en el orden del XML.
COUNTRIES = (
    {'xmlid': 'ad', 'name': 'Andorra', 'code': 'AD', 'currency': 'EUR', 'phone_code': 376, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ae', 'name': 'United Arab Emirates', 'code': 'AE', 'currency': 'AED', 'phone_code': 971, 'vat_label': 'TRN', 'address_format': None, 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'af', 'name': 'Afghanistan', 'code': 'AF', 'currency': 'AFN', 'phone_code': 93, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ag', 'name': 'Antigua and Barbuda', 'code': 'AG', 'currency': 'XCD', 'phone_code': 1268, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ai', 'name': 'Anguilla', 'code': 'AI', 'currency': 'XCD', 'phone_code': 1264, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'al', 'name': 'Albania', 'code': 'AL', 'currency': 'ALL', 'phone_code': 355, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'am', 'name': 'Armenia', 'code': 'AM', 'currency': 'AMD', 'phone_code': 374, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'ao', 'name': 'Angola', 'code': 'AO', 'currency': 'AOA', 'phone_code': 244, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'aq', 'name': 'Antarctica', 'code': 'AQ', 'currency': 'XCD', 'phone_code': 672, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ar', 'name': 'Argentina', 'code': 'AR', 'currency': 'ARS', 'phone_code': 54, 'vat_label': 'CUIT', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'as', 'name': 'American Samoa', 'code': 'AS', 'currency': 'USD', 'phone_code': 1684, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'at', 'name': 'Austria', 'code': 'AT', 'currency': 'EUR', 'phone_code': 43, 'vat_label': 'USt', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'au', 'name': 'Australia', 'code': 'AU', 'currency': 'AUD', 'phone_code': 61, 'vat_label': 'ABN', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'aw', 'name': 'Aruba', 'code': 'AW', 'currency': 'AWG', 'phone_code': 297, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ax', 'name': 'Åland Islands', 'code': 'AX', 'currency': 'EUR', 'phone_code': 358, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'az', 'name': 'Azerbaijan', 'code': 'AZ', 'currency': 'AZN', 'phone_code': 994, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ba', 'name': 'Bosnia and Herzegovina', 'code': 'BA', 'currency': 'BAM', 'phone_code': 387, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bb', 'name': 'Barbados', 'code': 'BB', 'currency': 'BBD', 'phone_code': 1246, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bd', 'name': 'Bangladesh', 'code': 'BD', 'currency': 'BDT', 'phone_code': 880, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'be', 'name': 'Belgium', 'code': 'BE', 'currency': 'EUR', 'phone_code': 32, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bf', 'name': 'Burkina Faso', 'code': 'BF', 'currency': 'XOF', 'phone_code': 226, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bg', 'name': 'Bulgaria', 'code': 'BG', 'currency': 'EUR', 'phone_code': 359, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bh', 'name': 'Bahrain', 'code': 'BH', 'currency': 'BHD', 'phone_code': 973, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bi', 'name': 'Burundi', 'code': 'BI', 'currency': 'BIF', 'phone_code': 257, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bj', 'name': 'Benin', 'code': 'BJ', 'currency': 'XOF', 'phone_code': 229, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'bl', 'name': 'Saint Barthélémy', 'code': 'BL', 'currency': 'EUR', 'phone_code': 590, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bm', 'name': 'Bermuda', 'code': 'BM', 'currency': 'BMD', 'phone_code': 1441, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bn', 'name': 'Brunei Darussalam', 'code': 'BN', 'currency': 'BND', 'phone_code': 673, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bo', 'name': 'Bolivia', 'code': 'BO', 'currency': 'BOB', 'phone_code': 591, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bq', 'name': 'Bonaire, Sint Eustatius and Saba', 'code': 'BQ', 'currency': 'USD', 'phone_code': 599, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'br', 'name': 'Brazil', 'code': 'BR', 'currency': 'BRL', 'phone_code': 55, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_code)s\n%(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bs', 'name': 'Bahamas', 'code': 'BS', 'currency': 'BSD', 'phone_code': 1242, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bt', 'name': 'Bhutan', 'code': 'BT', 'currency': 'BTN', 'phone_code': 975, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bv', 'name': 'Bouvet Island', 'code': 'BV', 'currency': 'NOK', 'phone_code': 55, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bw', 'name': 'Botswana', 'code': 'BW', 'currency': 'BWP', 'phone_code': 267, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'by', 'name': 'Belarus', 'code': 'BY', 'currency': 'BYN', 'phone_code': 375, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'bz', 'name': 'Belize', 'code': 'BZ', 'currency': 'BZD', 'phone_code': 501, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'ca', 'name': 'Canada', 'code': 'CA', 'currency': 'CAD', 'phone_code': 1, 'vat_label': 'GST/HST number', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'cc', 'name': 'Cocos (Keeling) Islands', 'code': 'CC', 'currency': 'AUD', 'phone_code': 61, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cf', 'name': 'Central African Republic', 'code': 'CF', 'currency': 'XAF', 'phone_code': 236, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cd', 'name': 'Congo (DRC)', 'code': 'CD', 'currency': 'CDF', 'phone_code': 243, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cg', 'name': 'Congo (Republic)', 'code': 'CG', 'currency': 'XAF', 'phone_code': 242, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ch', 'name': 'Switzerland', 'code': 'CH', 'currency': 'CHF', 'phone_code': 41, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ci', 'name': "Côte d'Ivoire", 'code': 'CI', 'currency': 'XOF', 'phone_code': 225, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ck', 'name': 'Cook Islands', 'code': 'CK', 'currency': 'NZD', 'phone_code': 682, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cl', 'name': 'Chile', 'code': 'CL', 'currency': 'CLP', 'phone_code': 56, 'vat_label': 'RUT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'cm', 'name': 'Cameroon', 'code': 'CM', 'currency': 'XAF', 'phone_code': 237, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cn', 'name': 'China', 'code': 'CN', 'currency': 'CNY', 'phone_code': 86, 'vat_label': '', 'address_format': '%(country_name)s, %(zip)s\n%(state_name)s %(city)s %(street)s %(street2)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'co', 'name': 'Colombia', 'code': 'CO', 'currency': 'COP', 'phone_code': 57, 'vat_label': 'NIT', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cr', 'name': 'Costa Rica', 'code': 'CR', 'currency': 'CRC', 'phone_code': 506, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cu', 'name': 'Cuba', 'code': 'CU', 'currency': 'CUP', 'phone_code': 53, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cv', 'name': 'Cape Verde', 'code': 'CV', 'currency': 'CVE', 'phone_code': 238, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cw', 'name': 'Curaçao', 'code': 'CW', 'currency': 'XCG', 'phone_code': 599, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cx', 'name': 'Christmas Island', 'code': 'CX', 'currency': 'AUD', 'phone_code': 61, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cy', 'name': 'Cyprus', 'code': 'CY', 'currency': 'EUR', 'phone_code': 357, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'cz', 'name': 'Czech Republic', 'code': 'CZ', 'currency': 'CZK', 'phone_code': 420, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'de', 'name': 'Germany', 'code': 'DE', 'currency': 'EUR', 'phone_code': 49, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'dj', 'name': 'Djibouti', 'code': 'DJ', 'currency': 'DJF', 'phone_code': 253, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'dk', 'name': 'Denmark', 'code': 'DK', 'currency': 'DKK', 'phone_code': 45, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'dm', 'name': 'Dominica', 'code': 'DM', 'currency': 'XCD', 'phone_code': 1767, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'do', 'name': 'Dominican Republic', 'code': 'DO', 'currency': 'DOP', 'phone_code': 1849, 'vat_label': 'RNC', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'dz', 'name': 'Algeria', 'code': 'DZ', 'currency': 'DZD', 'phone_code': 213, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ec', 'name': 'Ecuador', 'code': 'EC', 'currency': 'USD', 'phone_code': 593, 'vat_label': 'RUC', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'ee', 'name': 'Estonia', 'code': 'EE', 'currency': 'EUR', 'phone_code': 372, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'eg', 'name': 'Egypt', 'code': 'EG', 'currency': 'EGP', 'phone_code': 20, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'eh', 'name': 'Western Sahara', 'code': 'EH', 'currency': 'MAD', 'phone_code': 212, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'er', 'name': 'Eritrea', 'code': 'ER', 'currency': 'ERN', 'phone_code': 291, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'es', 'name': 'Spain', 'code': 'ES', 'currency': 'EUR', 'phone_code': 34, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'et', 'name': 'Ethiopia', 'code': 'ET', 'currency': 'ETB', 'phone_code': 251, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fi', 'name': 'Finland', 'code': 'FI', 'currency': 'EUR', 'phone_code': 358, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fj', 'name': 'Fiji', 'code': 'FJ', 'currency': 'FJD', 'phone_code': 679, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fk', 'name': 'Falkland Islands', 'code': 'FK', 'currency': 'FKP', 'phone_code': 500, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fm', 'name': 'Micronesia', 'code': 'FM', 'currency': 'USD', 'phone_code': 691, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fo', 'name': 'Faroe Islands', 'code': 'FO', 'currency': 'DKK', 'phone_code': 298, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'fr', 'name': 'France', 'code': 'FR', 'currency': 'EUR', 'phone_code': 33, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ga', 'name': 'Gabon', 'code': 'GA', 'currency': 'XAF', 'phone_code': 241, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gd', 'name': 'Grenada', 'code': 'GD', 'currency': 'XCD', 'phone_code': 1473, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ge', 'name': 'Georgia', 'code': 'GE', 'currency': 'GEL', 'phone_code': 995, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gf', 'name': 'French Guiana', 'code': 'GF', 'currency': 'EUR', 'phone_code': 594, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gh', 'name': 'Ghana', 'code': 'GH', 'currency': 'GHS', 'phone_code': 233, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gi', 'name': 'Gibraltar', 'code': 'GI', 'currency': 'GIP', 'phone_code': 350, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gg', 'name': 'Guernsey', 'code': 'GG', 'currency': 'GBP', 'phone_code': 44, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gl', 'name': 'Greenland', 'code': 'GL', 'currency': 'DKK', 'phone_code': 299, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gm', 'name': 'Gambia', 'code': 'GM', 'currency': 'GMD', 'phone_code': 220, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gn', 'name': 'Guinea', 'code': 'GN', 'currency': 'GNF', 'phone_code': 224, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gp', 'name': 'Guadeloupe', 'code': 'GP', 'currency': 'EUR', 'phone_code': 590, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gq', 'name': 'Equatorial Guinea', 'code': 'GQ', 'currency': 'XAF', 'phone_code': 240, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gr', 'name': 'Greece', 'code': 'GR', 'currency': 'EUR', 'phone_code': 30, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gs', 'name': 'South Georgia and the South Sandwich Islands', 'code': 'GS', 'currency': 'GBP', 'phone_code': 500, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gt', 'name': 'Guatemala', 'code': 'GT', 'currency': 'GTQ', 'phone_code': 502, 'vat_label': 'NIT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gu', 'name': 'Guam', 'code': 'GU', 'currency': 'USD', 'phone_code': 1671, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gw', 'name': 'Guinea-Bissau', 'code': 'GW', 'currency': 'XOF', 'phone_code': 245, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'gy', 'name': 'Guyana', 'code': 'GY', 'currency': 'GYD', 'phone_code': 592, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'hk', 'name': 'Hong Kong', 'code': 'HK', 'currency': 'HKD', 'phone_code': 852, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'hm', 'name': 'Heard Island and McDonald Islands', 'code': 'HM', 'currency': 'AUD', 'phone_code': 672, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'hn', 'name': 'Honduras', 'code': 'HN', 'currency': 'HNL', 'phone_code': 504, 'vat_label': 'RTN', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'hr', 'name': 'Croatia', 'code': 'HR', 'currency': 'EUR', 'phone_code': 385, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s \n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ht', 'name': 'Haiti', 'code': 'HT', 'currency': 'HTG', 'phone_code': 509, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'hu', 'name': 'Hungary', 'code': 'HU', 'currency': 'HUF', 'phone_code': 36, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'id', 'name': 'Indonesia', 'code': 'ID', 'currency': 'IDR', 'phone_code': 62, 'vat_label': 'NPWP', 'address_format': None, 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'ie', 'name': 'Ireland', 'code': 'IE', 'currency': 'EUR', 'phone_code': 353, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'il', 'name': 'Israel', 'code': 'IL', 'currency': 'ILS', 'phone_code': 972, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'im', 'name': 'Isle of Man', 'code': 'IM', 'currency': 'GBP', 'phone_code': 44, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'in', 'name': 'India', 'code': 'IN', 'currency': 'INR', 'phone_code': 91, 'vat_label': 'GSTIN', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(zip)s\n%(state_name)s %(state_code)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'io', 'name': 'British Indian Ocean Territory', 'code': 'IO', 'currency': 'USD', 'phone_code': 246, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'iq', 'name': 'Iraq', 'code': 'IQ', 'currency': 'IQD', 'phone_code': 964, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ir', 'name': 'Iran', 'code': 'IR', 'currency': 'IRR', 'phone_code': 98, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'is', 'name': 'Iceland', 'code': 'IS', 'currency': 'ISK', 'phone_code': 354, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'it', 'name': 'Italy', 'code': 'IT', 'currency': 'EUR', 'phone_code': 39, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'je', 'name': 'Jersey', 'code': 'JE', 'currency': 'GBP', 'phone_code': 44, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'jm', 'name': 'Jamaica', 'code': 'JM', 'currency': 'JMD', 'phone_code': 1876, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'jo', 'name': 'Jordan', 'code': 'JO', 'currency': 'JOD', 'phone_code': 962, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'jp', 'name': 'Japan', 'code': 'JP', 'currency': 'JPY', 'phone_code': 81, 'vat_label': '', 'address_format': '%(zip)s\n%(state_name)s %(city)s\n%(street)s\n%(street2)s\n%(country_name)s', 'name_position': 'after', 'state_required': True, 'zip_required': True},
    {'xmlid': 'ke', 'name': 'Kenya', 'code': 'KE', 'currency': 'KES', 'phone_code': 254, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kg', 'name': 'Kyrgyzstan', 'code': 'KG', 'currency': 'KGS', 'phone_code': 996, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'kh', 'name': 'Cambodia', 'code': 'KH', 'currency': 'KHR', 'phone_code': 855, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ki', 'name': 'Kiribati', 'code': 'KI', 'currency': 'AUD', 'phone_code': 686, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'km', 'name': 'Comoros', 'code': 'KM', 'currency': 'KMF', 'phone_code': 269, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kn', 'name': 'Saint Kitts and Nevis', 'code': 'KN', 'currency': 'XCD', 'phone_code': 1869, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kp', 'name': 'North Korea', 'code': 'KP', 'currency': 'KPW', 'phone_code': 850, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kr', 'name': 'South Korea', 'code': 'KR', 'currency': 'KRW', 'phone_code': 82, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kw', 'name': 'Kuwait', 'code': 'KW', 'currency': 'KWD', 'phone_code': 965, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ky', 'name': 'Cayman Islands', 'code': 'KY', 'currency': 'KYD', 'phone_code': 1345, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'kz', 'name': 'Kazakhstan', 'code': 'KZ', 'currency': 'KZT', 'phone_code': 7, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'la', 'name': 'Laos', 'code': 'LA', 'currency': 'LAK', 'phone_code': 856, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lb', 'name': 'Lebanon', 'code': 'LB', 'currency': 'LBP', 'phone_code': 961, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lc', 'name': 'Saint Lucia', 'code': 'LC', 'currency': 'XCD', 'phone_code': 1758, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'li', 'name': 'Liechtenstein', 'code': 'LI', 'currency': 'CHF', 'phone_code': 423, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lk', 'name': 'Sri Lanka', 'code': 'LK', 'currency': 'LKR', 'phone_code': 94, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lr', 'name': 'Liberia', 'code': 'LR', 'currency': 'LRD', 'phone_code': 231, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ls', 'name': 'Lesotho', 'code': 'LS', 'currency': 'LSL', 'phone_code': 266, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lt', 'name': 'Lithuania', 'code': 'LT', 'currency': 'EUR', 'phone_code': 370, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lu', 'name': 'Luxembourg', 'code': 'LU', 'currency': 'EUR', 'phone_code': 352, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s \n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'lv', 'name': 'Latvia', 'code': 'LV', 'currency': 'EUR', 'phone_code': 371, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ly', 'name': 'Libya', 'code': 'LY', 'currency': 'LYD', 'phone_code': 218, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ma', 'name': 'Morocco', 'code': 'MA', 'currency': 'MAD', 'phone_code': 212, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mc', 'name': 'Monaco', 'code': 'MC', 'currency': 'EUR', 'phone_code': 377, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'md', 'name': 'Moldova', 'code': 'MD', 'currency': 'MDL', 'phone_code': 373, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'me', 'name': 'Montenegro', 'code': 'ME', 'currency': 'EUR', 'phone_code': 382, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mf', 'name': 'Saint Martin (French part)', 'code': 'MF', 'currency': 'EUR', 'phone_code': 590, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mg', 'name': 'Madagascar', 'code': 'MG', 'currency': 'MGA', 'phone_code': 261, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mh', 'name': 'Marshall Islands', 'code': 'MH', 'currency': 'USD', 'phone_code': 692, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mk', 'name': 'North Macedonia', 'code': 'MK', 'currency': 'MKD', 'phone_code': 389, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ml', 'name': 'Mali', 'code': 'ML', 'currency': 'XOF', 'phone_code': 223, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mm', 'name': 'Myanmar', 'code': 'MM', 'currency': 'MMK', 'phone_code': 95, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mn', 'name': 'Mongolia', 'code': 'MN', 'currency': 'MNT', 'phone_code': 976, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mo', 'name': 'Macau', 'code': 'MO', 'currency': 'MOP', 'phone_code': 853, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'mp', 'name': 'Northern Mariana Islands', 'code': 'MP', 'currency': 'USD', 'phone_code': 1670, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mq', 'name': 'Martinique', 'code': 'MQ', 'currency': 'EUR', 'phone_code': 596, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mr', 'name': 'Mauritania', 'code': 'MR', 'currency': 'MRU', 'phone_code': 222, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ms', 'name': 'Montserrat', 'code': 'MS', 'currency': 'XCD', 'phone_code': 1664, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mt', 'name': 'Malta', 'code': 'MT', 'currency': 'EUR', 'phone_code': 356, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mu', 'name': 'Mauritius', 'code': 'MU', 'currency': 'MUR', 'phone_code': 230, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mv', 'name': 'Maldives', 'code': 'MV', 'currency': 'MVR', 'phone_code': 960, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mw', 'name': 'Malawi', 'code': 'MW', 'currency': 'MWK', 'phone_code': 265, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mx', 'name': 'Mexico', 'code': 'MX', 'currency': 'MXN', 'phone_code': 52, 'vat_label': 'RFC', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s, %(state_code)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'my', 'name': 'Malaysia', 'code': 'MY', 'currency': 'MYR', 'phone_code': 60, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'mz', 'name': 'Mozambique', 'code': 'MZ', 'currency': 'MZN', 'phone_code': 258, 'vat_label': 'NUIT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'na', 'name': 'Namibia', 'code': 'NA', 'currency': 'NAD', 'phone_code': 264, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nc', 'name': 'New Caledonia', 'code': 'NC', 'currency': 'XPF', 'phone_code': 687, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ne', 'name': 'Niger', 'code': 'NE', 'currency': 'XOF', 'phone_code': 227, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nf', 'name': 'Norfolk Island', 'code': 'NF', 'currency': 'AUD', 'phone_code': 672, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ng', 'name': 'Nigeria', 'code': 'NG', 'currency': 'NGN', 'phone_code': 234, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ni', 'name': 'Nicaragua', 'code': 'NI', 'currency': 'NIO', 'phone_code': 505, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nl', 'name': 'Netherlands', 'code': 'NL', 'currency': 'EUR', 'phone_code': 31, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'no', 'name': 'Norway', 'code': 'NO', 'currency': 'NOK', 'phone_code': 47, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'np', 'name': 'Nepal', 'code': 'NP', 'currency': 'NPR', 'phone_code': 977, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nr', 'name': 'Nauru', 'code': 'NR', 'currency': 'AUD', 'phone_code': 674, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nu', 'name': 'Niue', 'code': 'NU', 'currency': 'NZD', 'phone_code': 683, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'nz', 'name': 'New Zealand', 'code': 'NZ', 'currency': 'NZD', 'phone_code': 64, 'vat_label': 'GST', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'om', 'name': 'Oman', 'code': 'OM', 'currency': 'OMR', 'phone_code': 968, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pa', 'name': 'Panama', 'code': 'PA', 'currency': 'PAB', 'phone_code': 507, 'vat_label': 'RUC', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pe', 'name': 'Peru', 'code': 'PE', 'currency': 'PEN', 'phone_code': 51, 'vat_label': 'RUC', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'pf', 'name': 'French Polynesia', 'code': 'PF', 'currency': 'XPF', 'phone_code': 689, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pg', 'name': 'Papua New Guinea', 'code': 'PG', 'currency': 'PGK', 'phone_code': 675, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ph', 'name': 'Philippines', 'code': 'PH', 'currency': 'PHP', 'phone_code': 63, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pk', 'name': 'Pakistan', 'code': 'PK', 'currency': 'PKR', 'phone_code': 92, 'vat_label': 'NTN', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pl', 'name': 'Poland', 'code': 'PL', 'currency': 'PLN', 'phone_code': 48, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pm', 'name': 'Saint Pierre and Miquelon', 'code': 'PM', 'currency': 'EUR', 'phone_code': 508, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pn', 'name': 'Pitcairn Islands', 'code': 'PN', 'currency': 'NZD', 'phone_code': 64, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pr', 'name': 'Puerto Rico', 'code': 'PR', 'currency': 'USD', 'phone_code': 1939, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ps', 'name': 'State of Palestine', 'code': 'PS', 'currency': 'ILS', 'phone_code': 970, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pt', 'name': 'Portugal', 'code': 'PT', 'currency': 'EUR', 'phone_code': 351, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'pw', 'name': 'Palau', 'code': 'PW', 'currency': 'USD', 'phone_code': 680, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'py', 'name': 'Paraguay', 'code': 'PY', 'currency': 'PYG', 'phone_code': 595, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'qa', 'name': 'Qatar', 'code': 'QA', 'currency': 'QAR', 'phone_code': 974, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 're', 'name': 'Réunion', 'code': 'RE', 'currency': 'EUR', 'phone_code': 262, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ro', 'name': 'Romania', 'code': 'RO', 'currency': 'RON', 'phone_code': 40, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'rs', 'name': 'Serbia', 'code': 'RS', 'currency': 'RSD', 'phone_code': 381, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ru', 'name': 'Russian Federation', 'code': 'RU', 'currency': 'RUB', 'phone_code': 7, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'rw', 'name': 'Rwanda', 'code': 'RW', 'currency': 'RWF', 'phone_code': 250, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sa', 'name': 'Saudi Arabia', 'code': 'SA', 'currency': 'SAR', 'phone_code': 966, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sb', 'name': 'Solomon Islands', 'code': 'SB', 'currency': 'SBD', 'phone_code': 677, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sc', 'name': 'Seychelles', 'code': 'SC', 'currency': 'SCR', 'phone_code': 248, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sd', 'name': 'Sudan', 'code': 'SD', 'currency': 'SDG', 'phone_code': 249, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'se', 'name': 'Sweden', 'code': 'SE', 'currency': 'SEK', 'phone_code': 46, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sg', 'name': 'Singapore', 'code': 'SG', 'currency': 'SGD', 'phone_code': 65, 'vat_label': 'GST No.', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sh', 'name': 'Saint Helena, Ascension and Tristan da Cunha', 'code': 'SH', 'currency': 'SHP', 'phone_code': 290, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'si', 'name': 'Slovenia', 'code': 'SI', 'currency': 'EUR', 'phone_code': 386, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sj', 'name': 'Svalbard and Jan Mayen', 'code': 'SJ', 'currency': 'NOK', 'phone_code': 47, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sk', 'name': 'Slovakia', 'code': 'SK', 'currency': 'EUR', 'phone_code': 421, 'vat_label': 'VAT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sl', 'name': 'Sierra Leone', 'code': 'SL', 'currency': 'SLE', 'phone_code': 232, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sm', 'name': 'San Marino', 'code': 'SM', 'currency': 'EUR', 'phone_code': 378, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sn', 'name': 'Senegal', 'code': 'SN', 'currency': 'XOF', 'phone_code': 221, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'so', 'name': 'Somalia', 'code': 'SO', 'currency': 'SOS', 'phone_code': 252, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sr', 'name': 'Suriname', 'code': 'SR', 'currency': 'SRD', 'phone_code': 597, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ss', 'name': 'South Sudan', 'code': 'SS', 'currency': 'SSP', 'phone_code': 211, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'st', 'name': 'São Tomé and Príncipe', 'code': 'ST', 'currency': 'STD', 'phone_code': 239, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sv', 'name': 'El Salvador', 'code': 'SV', 'currency': 'SVC', 'phone_code': 503, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sx', 'name': 'Sint Maarten (Dutch part)', 'code': 'SX', 'currency': 'XCG', 'phone_code': 1721, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sy', 'name': 'Syria', 'code': 'SY', 'currency': 'SYP', 'phone_code': 963, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'sz', 'name': 'Eswatini', 'code': 'SZ', 'currency': 'SZL', 'phone_code': 268, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tc', 'name': 'Turks and Caicos Islands', 'code': 'TC', 'currency': 'USD', 'phone_code': 1649, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'td', 'name': 'Chad', 'code': 'TD', 'currency': 'XAF', 'phone_code': 235, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tf', 'name': 'French Southern Territories', 'code': 'TF', 'currency': 'EUR', 'phone_code': 262, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tg', 'name': 'Togo', 'code': 'TG', 'currency': 'XOF', 'phone_code': 228, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'th', 'name': 'Thailand', 'code': 'TH', 'currency': 'THB', 'phone_code': 66, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tj', 'name': 'Tajikistan', 'code': 'TJ', 'currency': 'TJS', 'phone_code': 992, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'tk', 'name': 'Tokelau', 'code': 'TK', 'currency': 'NZD', 'phone_code': 690, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tm', 'name': 'Turkmenistan', 'code': 'TM', 'currency': 'TMT', 'phone_code': 993, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'tn', 'name': 'Tunisia', 'code': 'TN', 'currency': 'TND', 'phone_code': 216, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'to', 'name': 'Tonga', 'code': 'TO', 'currency': 'TOP', 'phone_code': 676, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tl', 'name': 'Timor-Leste', 'code': 'TL', 'currency': 'USD', 'phone_code': 670, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tr', 'name': 'Türkiye', 'code': 'TR', 'currency': 'TRY', 'phone_code': 90, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_name)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tt', 'name': 'Trinidad and Tobago', 'code': 'TT', 'currency': 'TTD', 'phone_code': 1868, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tv', 'name': 'Tuvalu', 'code': 'TV', 'currency': 'AUD', 'phone_code': 688, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tw', 'name': 'Taiwan', 'code': 'TW', 'currency': 'TWD', 'phone_code': 886, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'tz', 'name': 'Tanzania', 'code': 'TZ', 'currency': 'TZS', 'phone_code': 255, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ua', 'name': 'Ukraine', 'code': 'UA', 'currency': 'UAH', 'phone_code': 380, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ug', 'name': 'Uganda', 'code': 'UG', 'currency': 'UGX', 'phone_code': 256, 'vat_label': 'TIN', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'uk', 'name': 'United Kingdom', 'code': 'GB', 'currency': 'GBP', 'phone_code': 44, 'vat_label': 'VAT', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s\n%(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'um', 'name': 'USA Minor Outlying Islands', 'code': 'UM', 'currency': 'USD', 'phone_code': 699, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'us', 'name': 'United States', 'code': 'US', 'currency': 'USD', 'phone_code': 1, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s', 'name_position': 'before', 'state_required': True, 'zip_required': True},
    {'xmlid': 'uy', 'name': 'Uruguay', 'code': 'UY', 'currency': 'UYU', 'phone_code': 598, 'vat_label': 'RUT', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'uz', 'name': 'Uzbekistan', 'code': 'UZ', 'currency': 'UZS', 'phone_code': 998, 'vat_label': 'TIN', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'va', 'name': 'Holy See (Vatican City State)', 'code': 'VA', 'currency': 'EUR', 'phone_code': 379, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'vc', 'name': 'Saint Vincent and the Grenadines', 'code': 'VC', 'currency': 'XCD', 'phone_code': 1784, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 've', 'name': 'Venezuela', 'code': 'VE', 'currency': 'VEF', 'phone_code': 58, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'vg', 'name': 'Virgin Islands (British)', 'code': 'VG', 'currency': 'USD', 'phone_code': 1284, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'vi', 'name': 'Virgin Islands (USA)', 'code': 'VI', 'currency': 'USD', 'phone_code': 1340, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'vn', 'name': 'Vietnam', 'code': 'VN', 'currency': 'VND', 'phone_code': 84, 'vat_label': '', 'address_format': '%(street)s\n%(street2)s\n%(city)s\n%(state_name)s %(country_name)s', 'name_position': 'before', 'state_required': False, 'zip_required': False},
    {'xmlid': 'vu', 'name': 'Vanuatu', 'code': 'VU', 'currency': 'VUV', 'phone_code': 678, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'wf', 'name': 'Wallis and Futuna', 'code': 'WF', 'currency': 'XPF', 'phone_code': 681, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ws', 'name': 'Samoa', 'code': 'WS', 'currency': 'WST', 'phone_code': 685, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'ye', 'name': 'Yemen', 'code': 'YE', 'currency': 'YER', 'phone_code': 967, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'yt', 'name': 'Mayotte', 'code': 'YT', 'currency': 'EUR', 'phone_code': 262, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'za', 'name': 'South Africa', 'code': 'ZA', 'currency': 'ZAR', 'phone_code': 27, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'zm', 'name': 'Zambia', 'code': 'ZM', 'currency': 'ZMW', 'phone_code': 260, 'vat_label': 'TPIN', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'zw', 'name': 'Zimbabwe', 'code': 'ZW', 'currency': 'ZIG', 'phone_code': 263, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'xi', 'name': 'Northern Ireland', 'code': 'XI', 'currency': 'GBP', 'phone_code': 44, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
    {'xmlid': 'xk', 'name': 'Kosovo', 'code': 'XK', 'currency': 'EUR', 'phone_code': 383, 'vat_label': '', 'address_format': None, 'name_position': 'before', 'state_required': False, 'zip_required': True},
)

#: Las ocho agrupaciones (la Unión Europea entre ellas).
#: ``members`` son **xmlids**, no códigos ISO: el XML los cita con
#: ``ref('sa')`` y ``ref('base.sa')`` indistintamente, y para el Reino
#: Unido el xmlid es ``uk`` mientras su código es ``GB`` — resolver por
#: código perdía ese país en dos agrupaciones.
COUNTRY_GROUPS = (
    {'xmlid': 'europe', 'name': 'European Union', 'code': 'EU', 'members': ('at', 'be', 'bg', 'hr', 'cy', 'cz', 'dk', 'ee', 'fi', 'fr', 'de', 'gr', 'hu', 'ie', 'it', 'lv', 'lt', 'lu', 'mt', 'nl', 'pl', 'pt', 'ro', 'sk', 'si', 'es', 'se')},
    {'xmlid': 'europe_prefix', 'name': 'European Union Prefixed Countries', 'code': 'EU_PREFIX', 'members': ('at', 'be', 'bg', 'hr', 'cy', 'cz', 'dk', 'ee', 'fi', 'fr', 'de', 'gr', 'hu', 'ie', 'it', 'lv', 'lt', 'lu', 'mt', 'nl', 'pl', 'pt', 'ro', 'sk', 'si', 'es', 'se', 'ch', 'no', 'uk', 'sm')},
    {'xmlid': 'south_america', 'name': 'South America', 'code': 'SA', 'members': ('ar', 'bo', 'br', 'cl', 'co', 'ec', 'fk', 'gs', 'gf', 'gy', 'py', 'pe', 'sr', 'uy', 've')},
    {'xmlid': 'sepa_zone', 'name': 'SEPA Countries', 'code': 'SEPA', 'members': ('ad', 'at', 'ax', 'be', 'bg', 'bl', 'ch', 'cy', 'cz', 'de', 'dk', 'ee', 'es', 'fi', 'fr', 'uk', 'gf', 'gg', 'gi', 'gp', 'gr', 'hr', 'hu', 'ie', 'im', 'is', 'it', 'je', 'li', 'lt', 'lu', 'lv', 'mc', 'mf', 'mq', 'mt', 'nl', 'no', 'pl', 'pm', 'pt', 're', 'ro', 'se', 'si', 'sk', 'sm', 'va', 'yt')},
    {'xmlid': 'gulf_cooperation_council', 'name': 'Gulf Cooperation Council (GCC)', 'code': 'GCC', 'members': ('sa', 'ae', 'bh', 'om', 'qa', 'kw')},
    {'xmlid': 'eurasian_economic_union', 'name': 'Eurasian Economic Union', 'code': 'EEU', 'members': ('ru', 'by', 'am', 'kg', 'kz')},
    {'xmlid': 'ch_and_li', 'name': 'Switzerland and Liechtenstein', 'code': 'CH-LI', 'members': ('ch', 'li')},
    {'xmlid': 'dom-tom', 'name': 'DOM-TOM', 'code': 'DOM-TOM', 'members': ('yt', 'gp', 'mq', 'gf', 're', 'pf', 'pm', 'mf', 'bl', 'nc')},
)


def _seed(ResCountry, ResCountryGroup, ResCurrency, IrModelData, using):
    """La siembra, parametrizada por las clases de modelo.

    Una sola implementación con dos entradas: ``seed()`` la llama con los
    modelos **vivos** (lo que necesita el catálogo de semillas de los tests) y
    ``seed_countries()`` con los **históricos** de una migración. El *spec* —
    ``COUNTRIES`` y ``COUNTRY_GROUPS`` — es el mismo en ambos caminos, así que
    no hay dos copias que puedan divergir.

    Idempotente por ``code`` del país y ``name`` del grupo, y por
    ``(module, name)`` de ``ir.model.data`` — que es lo que ``noupdate="1"``
    garantiza en el XML original: un segundo pase repunta la fila en vez de
    duplicarla.

    **La moneda se resuelve por nombre y se tolera ausente.** ``res.currency``
    no tiene sembrador en este árbol (medido: sólo aparece en el
    ``0001_initial`` de esquema), así que la mayoría de los 251 países nacerá
    sin moneda. Es una divergencia declarada, no un descuido: fabricar aquí un
    catálogo de monedas sería inventar datos que la referencia declara en otro
    archivo, y el país es útil sin ella — lo que el CFDI necesita de México es
    su ``code`` y su ``vat_label``, no su divisa.
    """
    currencies = {c.name: c for c in ResCurrency.objects.using(using).all()}
    by_xmlid = {}

    for row in COUNTRIES:
        defaults = {
            'name': row['name'],
            'phone_code': row['phone_code'],
            'vat_label': row['vat_label'],
            'name_position': row['name_position'],
            'state_required': row['state_required'],
            'zip_required': row['zip_required'],
            'currency': currencies.get(row['currency']),
        }
        if row['address_format']:
            defaults['address_format'] = row['address_format']
        country, _created = ResCountry.objects.using(using).update_or_create(
            code=row['code'], defaults=defaults)
        by_xmlid[row['xmlid']] = country
        IrModelData.objects.using(using).update_or_create(
            module='base', name=row['xmlid'],
            defaults={'model': ResCountry._meta.label,
                      'res_id': country.pk, 'noupdate': True},
        )

    for row in COUNTRY_GROUPS:
        group, _created = ResCountryGroup.objects.using(using).update_or_create(
            name=row['name'], defaults={'code': row['code']})
        IrModelData.objects.using(using).update_or_create(
            module='base', name=row['xmlid'],
            defaults={'model': ResCountryGroup._meta.label,
                      'res_id': group.pk, 'noupdate': True},
        )
        members = [by_xmlid[m] for m in row['members'] if m in by_xmlid]
        if members:
            group.country_ids.set(members)

    return by_xmlid


def seed(using=DEFAULT_DB_ALIAS):
    """Siembra sobre los modelos vivos — entrada del catálogo de semillas.

    El catálogo de ``tests/conftest.py`` la re-aplica al arrancar la sesión y
    tras cada test transaccional: un ``flush`` borra las filas que sembró la
    migración, y ``django_migrations`` las sigue dando por aplicadas, así que
    sin esta entrada la sesión siguiente arranca con cero países y el fallo
    aparece lejos de su causa (H-API-337).
    """
    return _seed(ResCountry, ResCountryGroup, ResCurrency, IrModelData, using)


def seed_countries(apps, alias):
    """Siembra sobre los modelos históricos — entrada de la migración.

    ``apps.get_model`` y no el modelo vivo porque ejecutar comportamiento de la
    app viva desde una migración la ata a un estado del código que cambia bajo
    sus pies. Mismo criterio que ``account: data/account_tags.py``.
    """
    return _seed(
        apps.get_model('base', 'ResCountry'),
        apps.get_model('base', 'ResCountryGroup'),
        apps.get_model('base', 'ResCurrency'),
        apps.get_model('base', 'IrModelData'),
        alias,
    )
