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
- Order list stored in the session; checkout saves the order to the database (or sends it to WhatsApp)
- Order workflow with statuses (new → confirmed → shipped → completed / cancelled) managed from the admin
- Instant Telegram notification to the manager about every new order
- Prices are copied into the order, so later price changes do not affect placed orders
- Size selection (the same product in several sizes is several order lines; wholesale price counts all of them)
- Delivery across Kyrgyzstan: region, district / town, street, second phone; or pickup at Dordoi bazaar
- Deposit tracking and amount due; managers enter orders from the WhatsApp group in the admin with auto-filled prices
- CSV import of products via a management command (creates categories, updates existing items by article)
- Admin panel with inline photo upload and inline editing of prices and stock
- SEO basics: `sitemap.xml`, `robots.txt`, custom 404/500 pages
- Configuration through environment variables

## Tech stack

- **Backend:** Python 3.12+, Django 6, PostgreSQL (SQLite for quick local runs)
- **Infrastructure:** Docker, docker-compose, gunicorn, WhiteNoise
- **API:** Django REST Framework, django-filter, drf-spectacular (OpenAPI / Swagger)
- **Quality:** 63 tests (~98% coverage), ruff, GitHub Actions CI
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

### Telegram notifications

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Send any message to the bot (or add it to the managers group) and get the chat id from
   `https://api.telegram.org/bot<token>/getUpdates`.
3. Put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` into `.env`.

Without these variables orders are still saved, only the notification is skipped.

### Running tests

```bash
pip install -r requirements-dev.txt
ruff check .
coverage run manage.py test && coverage report
```

## REST API

Interactive docs: **`/api/docs/`** (Swagger UI), schema: `/api/schema/`.

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/v1/categories/` | public | active categories with product counts |
| GET | `/api/v1/products/` | public | catalog: `?search=`, `?category=`, `?in_stock=`, `?min_price=`, `?ordering=price` |
| GET | `/api/v1/products/{id}/` | public | product with sizes and photos |
| POST | `/api/v1/orders/` | public, rate limited | place an order |
| GET | `/api/v1/orders/{public_id}/` | public | order status (no personal data) |
| POST | `/api/v1/auth/token/` | — | get a token by username and password |
| GET | `/api/v1/manager/orders/` | staff token | all orders: `?status=`, `?source=`, `?search=` |
| POST | `/api/v1/manager/orders/{id}/status/` | staff token | move the order to the next status |

Placing an order:

```bash
curl -X POST http://localhost:8000/api/v1/orders/   -H "Content-Type: application/json"   -d '{
    "customer_name": "Azamat",
    "phone": "+996 555 12 34 56",
    "region": "batken",
    "locality": "Kyzyl-Kiya",
    "items": [
      {"product": 1, "size": "41", "quantity": 6},
      {"product": 1, "size": "43", "quantity": 4}
    ]
  }'
```

Prices are always calculated on the server with the same code as the website
(wholesale price from the total quantity of a product across sizes).

## Project structure

```
qadam/                  project settings and URLs
products/
    models.py           Category, Product, ProductImage
    views.py            catalog and product page
    context_processors.py   shop contacts and order counter for all templates
    management/commands/import_products.py
    tests.py
orders/
    models.py           Order, OrderItem, status transitions
    cart.py             order list stored in the session
    services.py         creating an order in a transaction
    notifications.py    Telegram notifications
api/
    serializers.py      validation and output of catalog and orders
    views.py            viewsets, filters, permissions, throttling
templates/              HTML templates
static/css/             styles
```

## Roadmap

- [x] PostgreSQL and Docker Compose
- [x] CI with GitHub Actions (tests + linter)
- [x] Orders saved in the database with statuses
- [x] Telegram notifications for new orders
- [x] REST API (Django REST Framework) with OpenAPI docs
- [ ] Accounts for wholesale customers with order history
- [ ] Background tasks with Celery + Redis (notifications, image thumbnails)
- [ ] Deployment with HTTPS
