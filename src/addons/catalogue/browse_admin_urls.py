"""
Admin browse URLs — addons.catalogue (F7 cleanup).

All price-sync v1-compat paths (preview-csv, apply-csv, preview-percentage,
apply-percentage, template.csv) are consolidated into PriceSyncsV2View at
/api/v2/admin/price-syncs/ with type+mode body params.

This file is kept for the namespace binding in config/urls.py.
"""
app_name = 'catalogue_browse_admin'

urlpatterns = []
