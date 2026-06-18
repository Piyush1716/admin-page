# GajananGems Admin Panel

A Flask-based admin panel for managing products and categories in your Supabase store.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create your .env file
cp .env.example .env
# Fill in your SUPABASE_URL and SUPABASE_KEY (service role key)

# 3. Run the server
python app.py
```

Open http://localhost:5000 in your browser.

## Features

- **Dashboard** — Live stats: total products, active products, categories, orders, revenue
- **Products** — Full CRUD: create, edit, delete with main image + gallery (up to 8 extra images)
- **Categories** — Card-based view with CRUD and image management
- **Image Upload** — Drag & drop or click to upload to Supabase Storage (`products` / `categories` buckets)
  - Or paste a direct URL instead
- **Smooth UI** — Dark luxury theme, animated modals, toast notifications, confirm dialogs

## Supabase Storage Buckets

Make sure your storage buckets are created and set to **public**:
- `products` — for product images
- `categories` — for category images

## Notes

- Use your **service role key** (not the anon key) so the backend can bypass RLS for admin operations.
- The panel is not auth-protected by default. Add a simple token check or HTTP Basic Auth if exposing publicly.
