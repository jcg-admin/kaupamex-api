# Kaupamex — Seed data

Real Yoruba/Lukumí product seed for end-to-end testing. Used to populate the
local PostgreSQL database (`kaupamex_core`) with the canonical demo catalogue.

## Files

- `products-seed.csv` — 41 products spanning 8 categories. UTF-8, header row,
  columns per the inventory bulk-import contract (UC-INV-05).
- `seed_categories.py` — idempotent Django shell script that creates the
  canonical category tree.

## CSV column shape (UC-INV-05)

Required: `name, sku, base_price, category_slug`
Optional: `description, short_description, stock`

The endpoint maps `base_price` → `Product.price`, `category_slug` →
`Category.slug` lookup, and stores English-keyed JSON in the response per
DEC-DOC-005 (`products_created`, `products_failed`, `error_report`,
`download_url`).

## Run the seed

```bash
cd kaupamex-api
source .venv/bin/activate
cd src

# 1. Apply migrations + create the admin user (one-off).
python manage.py migrate
python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
u, _ = U.objects.get_or_create(
    username='admin',
    defaults={'email': 'admin@kaupamex.com',
              'is_superuser': True, 'is_staff': True})
u.is_superuser = u.is_staff = u.is_active = True
u.set_password('Adm1n!Kaupamex')
u.save()
"

# 2. Create the category tree (idempotent).
python manage.py shell < scripts/seed-data/seed_categories.py

# 3. Start the api in another terminal.
python manage.py runserver 127.0.0.1:8000

# 4. Get an admin JWT and import the CSV.
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
    -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"Adm1n!Kaupamex"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")

curl -s -X POST http://127.0.0.1:8000/api/v1/admin/inventory/import/ \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@scripts/seed-data/products-seed.csv" \
    -F "initial_state=ACTIVO"
```

Expected response:

```json
{"status":"COMPLETED","products_created":41,"products_failed":0,
 "error_report":[],"download_url":null}
```

## Idempotency

The seed is safe to re-run. Categories use `get_or_create(slug=...)`. Products
collide on the unique `sku` column — a second import returns a fully populated
`error_report` (`SKU "PY-…" ya existe en el catálogo.`) without inserting
duplicates. To re-seed from scratch, truncate first:

```sql
DELETE FROM catalogue_product;
```

## Category coverage

| slug        | products |
|-------------|----------|
| collares    | 9        |
| pulseras    | 6        |
| ofrendas    | 5        |
| sahumerios  | 4        |
| aceites     | 5        |
| jabones     | 4        |
| polvos      | 4        |
| semillas    | 4        |
| **Total**   | **41**   |
