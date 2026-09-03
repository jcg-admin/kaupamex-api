import django; django.setup()
from orm import registry
print('=== 1. check_table_matches_name ya lo sabe? ===')
print(registry.check_table_matches_name() or '(sin divergencias)')
print()
print('=== 2. website.searchable.mixin ===')
c = registry.MODELS_BY_NAME.get('website.searchable.mixin')
print('en MODELS_BY_NAME:', c is not None)
if c is None:
    import addons.website.models.website as w
    for n in dir(w):
        o = getattr(w, n)
        if getattr(o, '_name', None) == 'website.searchable.mixin':
            print('clase:', o, 'meta abstract:', getattr(getattr(o,"_meta",None),"abstract",None))
