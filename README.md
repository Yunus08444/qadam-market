# Qadam Market

Online catalog for a wholesale shop of workwear and footwear at Dordoi bazaar (Bishkek).
Customers browse products, collect an order list and send it to the seller in WhatsApp
in one click. The owner manages products through the Django admin or imports them from CSV.

Built for a real family business, still in active development.

## Features

- Product catalog with search by name or article, category and in-stock filters, sorting and pagination
- Product page with photo gallery, sizes, color and a link to a video review (Instagram Reels)
- Retail and wholesale prices — the wholesale price applies automatically from a minimum quantity
- Order list stored in the session; the finished order is sent to WhatsApp as ready-made text
- CSV import of products via a management command (creates categories, updates existing items by article)
- Admin panel with inline photo upload and inline editing of prices and stock
- SEO basics: `sitemap.xml`, `robots.txt`, custom 404/500 pages
- Configuration through environment variables

## Tech stack

Python 3.12+, Django 6, SQLite (PostgreSQL planned), Pillow, plain HTML/CSS templates.

## Getting started

```bash
git clone https://github.com/Yunus08444/qadam-market.git
cd qadam-market

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then edit the values

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000 for the site and http://127.0.0.1:8000/admin for the admin panel.

### Importing products

Fill in `products_template.csv` (`;` or `,` separated) and run:

```bash
python manage.py import_products products_template.csv
```

### Running tests

```bash
python manage.py test
```

## Project structure

```
qadam/                  project settings and URLs
products/
    models.py           Category, Product, ProductImage
    views.py            catalog, product page, order list
    context_processors.py   shop contacts and order counter for all templates
    management/commands/import_products.py
    tests.py
templates/              HTML templates
static/css/             styles
```

## Roadmap

- [ ] PostgreSQL and Docker Compose
- [ ] CI with GitHub Actions (tests + linter)
- [ ] Orders saved in the database with statuses
- [ ] Telegram notifications for new orders
- [ ] REST API (Django REST Framework) with OpenAPI docs
- [ ] Accounts for wholesale customers with order history
- [ ] Background tasks with Celery + Redis (notifications, image thumbnails)
- [ ] Deployment with HTTPS
