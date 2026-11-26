# Qadam Market

[![CI](https://github.com/Yunus08444/qadam-market/actions/workflows/ci.yml/badge.svg)](https://github.com/Yunus08444/qadam-market/actions/workflows/ci.yml)

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

- **Backend:** Python 3.12+, Django 6, PostgreSQL (SQLite for quick local runs)
- **Infrastructure:** Docker, docker-compose, gunicorn, WhiteNoise
- **Quality:** Django test suite (~95% coverage), ruff, GitHub Actions CI
- **Frontend:** server-rendered Django templates, plain CSS

## Getting started

### With Docker (recommended)

```bash
git clone https://github.com/Yunus08444/qadam-market.git
cd qadam-market
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

This starts PostgreSQL and the app (gunicorn) at http://localhost:8000.

### Without Docker

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
pip install -r requirements-dev.txt
ruff check .
coverage run manage.py test && coverage report
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

- [x] PostgreSQL and Docker Compose
- [x] CI with GitHub Actions (tests + linter)
- [ ] Orders saved in the database with statuses
- [ ] Telegram notifications for new orders
- [ ] REST API (Django REST Framework) with OpenAPI docs
- [ ] Accounts for wholesale customers with order history
- [ ] Background tasks with Celery + Redis (notifications, image thumbnails)
- [ ] Deployment with HTTPS
