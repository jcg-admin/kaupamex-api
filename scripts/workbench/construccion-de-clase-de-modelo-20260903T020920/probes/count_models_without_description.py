import django; django.setup()
from orm import registry
sin = [n for n, c in registry.MODELS_BY_NAME.items()
       if not c.__dict__.get('_description')]
print('registrados:', len(registry.MODELS_BY_NAME))
print('sin _description:', len(sin))
print('ejemplos:', sin[:6])
