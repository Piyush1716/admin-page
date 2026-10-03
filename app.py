import os
import uuid
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Prefer service role key to bypass RLS for admin backend operations
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", ""))
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text

# ─── Serve frontend ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# ─── Categories ───────────────────────────────────────────────────────────────

@app.route("/api/categories", methods=["GET"])
def get_categories():
    res = supabase.table("categories").select("*").order("created_at", desc=True).execute()
    return jsonify(res.data)

@app.route("/api/categories", methods=["POST"])
def create_category():
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    payload = {
        "name": name,
        "slug": data.get("slug") or slugify(name),
        "image_url": data.get("image_url", ""),
    }
    res = supabase.table("categories").insert(payload).execute()
    return jsonify(res.data[0]), 201

@app.route("/api/categories/<int:cat_id>", methods=["PUT"])
def update_category(cat_id):
    data = request.json
    payload = {}
    if "name" in data:
        payload["name"] = data["name"]
        if "slug" not in data:
            payload["slug"] = slugify(data["name"])
    if "slug" in data:
        payload["slug"] = data["slug"]
    if "image_url" in data:
        payload["image_url"] = data["image_url"]
    res = supabase.table("categories").update(payload).eq("id", cat_id).execute()
    return jsonify(res.data[0])

@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def delete_category(cat_id):
    supabase.table("categories").delete().eq("id", cat_id).execute()
    return jsonify({"ok": True})

# ─── Products ─────────────────────────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
def get_products():
    res = (
        supabase.table("products")
        .select("*, categories(name), product_images(id, image_url, sort_order)")
        .order("created_at", desc=True)
        .execute()
    )
    return jsonify(res.data)

@app.route("/api/products/<int:prod_id>", methods=["GET"])
def get_product(prod_id):
    res = (
        supabase.table("products")
        .select("*, categories(name), product_images(id, image_url, sort_order)")
        .eq("id", prod_id)
        .single()
        .execute()
    )
    return jsonify(res.data)

@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.json
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400
    price = data.get("price")
    if price is None:
        return jsonify({"error": "Price required"}), 400
    payload = {
        "title": title,
        "slug": data.get("slug") or slugify(title),
        "description": data.get("description", ""),
        "price": float(price),
        "old_price": float(data["old_price"]) if data.get("old_price") else None,
        "image_url": data.get("image_url", ""),
        "category_id": data.get("category_id"),
        "available": data.get("available", True),
        "bestseller": data.get("bestseller", False),
    }
    res = supabase.table("products").insert(payload).execute()
    product = res.data[0]

    # Insert extra images
    extra_images = data.get("extra_images", [])
    for i, img_url in enumerate(extra_images):
        if img_url:
            supabase.table("product_images").insert({
                "product_id": product["id"],
                "image_url": img_url,
                "sort_order": i,
            }).execute()

    return jsonify(product), 201

@app.route("/api/products/<int:prod_id>", methods=["PUT"])
def update_product(prod_id):
    try:
        data = request.json
        payload = {}
        for field in ["title", "description", "price", "old_price", "image_url", "category_id", "available", "slug", "bestseller"]:
            if field in data:
                payload[field] = data[field]
        
        if "price" in payload and payload["price"] is not None:
            payload["price"] = float(payload["price"])
        if "old_price" in payload:
            payload["old_price"] = float(payload["old_price"]) if payload["old_price"] is not None and str(payload["old_price"]).strip() != "" else None

        if payload:
            supabase.table("products").update(payload).eq("id", prod_id).execute()

        # Handle extra images replacement
        if "extra_images" in data:
            supabase.table("product_images").delete().eq("product_id", prod_id).execute()
            for i, img_url in enumerate(data["extra_images"]):
                if img_url:
                    supabase.table("product_images").insert({
                        "product_id": prod_id,
                        "image_url": img_url,
                        "sort_order": i,
                    }).execute()

        res = (
            supabase.table("products")
            .select("*, categories(name), product_images(id, image_url, sort_order)")
            .eq("id", prod_id)
            .single()
            .execute()
        )
        return jsonify(res.data)
    except Exception as e:
        print(f"Error updating product: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/products/<int:prod_id>", methods=["DELETE"])
def delete_product(prod_id):
    supabase.table("product_images").delete().eq("product_id", prod_id).execute()
    supabase.table("products").delete().eq("id", prod_id).execute()
    return jsonify({"ok": True})

# ─── Image Upload ─────────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def upload_image():
    bucket = request.form.get("bucket", "products")  # 'products' or 'categories'
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400

    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        return jsonify({"error": "Invalid file type"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    file_bytes = file.read()

    try:
        supabase.storage.from_(bucket).upload(
            filename,
            file_bytes,
            file_options={"content-type": file.content_type},
        )
        public_url = supabase.storage.from_(bucket).get_public_url(filename)
        return jsonify({"url": public_url})
    except Exception as e:
        print(f"Error uploading image: {e}")
        return jsonify({"error": str(e)}), 500

# ─── Orders ───────────────────────────────────────────────────────────────────

@app.route("/api/orders", methods=["GET"])
def get_orders():
    try:
        # Fetch orders along with their order items
        res = (
            supabase.table("orders")
            .select("*, order_items(*)")
            .order("created_at", desc=True)
            .execute()
        )
        return jsonify(res.data)
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    try:
        data = request.json
        if "status" not in data:
            return jsonify({"error": "Status is required"}), 400
            
        res = supabase.table("orders").update({"status": data["status"]}).eq("id", order_id).execute()
        
        if not res.data:
            return jsonify({"error": "Order not found"}), 404
            
        return jsonify(res.data[0])
    except Exception as e:
        print(f"Error updating order: {e}")
        return jsonify({"error": str(e)}), 500

# ─── Stats ────────────────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    products = supabase.table("products").select("id, available").execute()
    categories = supabase.table("categories").select("id").execute()
    orders = supabase.table("orders").select("id, total, status").execute()
    total_products = len(products.data)
    active_products = sum(1 for p in products.data if p.get("available"))
    total_categories = len(categories.data)
    total_orders = len(orders.data)
    total_revenue = sum(float(o.get("total", 0)) for o in orders.data if o.get("status") not in ("cancelled", "failed"))
    return jsonify({
        "total_products": total_products,
        "active_products": active_products,
        "total_categories": total_categories,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
    })

# ─── Reviews ──────────────────────────────────────────────────────────────────

@app.route("/api/reviews", methods=["GET"])
def get_admin_reviews():
    try:
        product_id = request.args.get("product_id")
        query = (
            supabase.table("reviews")
            .select("*, products(id, title, image_url), review_images(id, image_url, sort_order)")
            .order("created_at", desc=True)
        )
        if product_id:
            query = query.eq("product_id", int(product_id))
        res = query.execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Error fetching reviews: {e}")
        return jsonify([]), 200

@app.route("/api/reviews", methods=["POST"])
def create_admin_review():
    try:
        data = request.json or {}
        product_id = data.get("product_id")
        reviewer_name = (data.get("reviewer_name") or "").strip()
        rating = data.get("rating")
        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        verified = bool(data.get("verified", True))
        image_urls = data.get("image_urls") or []

        if not product_id or not reviewer_name or not rating:
            return jsonify({"error": "product_id, reviewer_name, and rating are required"}), 400

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return jsonify({"error": "rating must be between 1 and 5"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "invalid rating"}), 400

        payload = {
            "product_id": int(product_id),
            "reviewer_name": reviewer_name,
            "rating": rating,
            "title": title or None,
            "body": body or None,
            "verified": verified,
            "source": "admin",
        }

        res = supabase.table("reviews").insert(payload).execute()
        if not res.data:
            return jsonify({"error": "Failed to create review"}), 500

        review = res.data[0]

        # Insert review images
        if image_urls:
            image_rows = [
                {
                    "review_id": review["id"],
                    "image_url": url,
                    "sort_order": idx,
                }
                for idx, url in enumerate(image_urls)
                if url
            ]
            if image_rows:
                supabase.table("review_images").insert(image_rows).execute()

        # Fetch complete review record
        full_res = (
            supabase.table("reviews")
            .select("*, products(id, title, image_url), review_images(id, image_url, sort_order)")
            .eq("id", review["id"])
            .single()
            .execute()
        )
        return jsonify(full_res.data), 201
    except Exception as e:
        print(f"Error creating review: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/reviews/<int:review_id>", methods=["GET"])
def get_single_admin_review(review_id):
    try:
        res = (
            supabase.table("reviews")
            .select("*, products(id, title, image_url), review_images(id, image_url, sort_order)")
            .eq("id", review_id)
            .single()
            .execute()
        )
        if not res.data:
            return jsonify({"error": "Review not found"}), 404
        return jsonify(res.data)
    except Exception as e:
        print(f"Error fetching review: {e}")
        return jsonify({"error": str(e)}), 404

@app.route("/api/reviews/<int:review_id>", methods=["PUT"])
def update_admin_review(review_id):
    try:
        data = request.json or {}
        payload = {}

        if "product_id" in data and data["product_id"]:
            payload["product_id"] = int(data["product_id"])
        if "reviewer_name" in data:
            reviewer_name = str(data["reviewer_name"]).strip()
            if not reviewer_name:
                return jsonify({"error": "reviewer_name cannot be empty"}), 400
            payload["reviewer_name"] = reviewer_name
        if "rating" in data and data["rating"]:
            try:
                rating = int(data["rating"])
                if rating < 1 or rating > 5:
                    return jsonify({"error": "rating must be between 1 and 5"}), 400
                payload["rating"] = rating
            except (ValueError, TypeError):
                return jsonify({"error": "invalid rating"}), 400
        if "title" in data:
            payload["title"] = str(data["title"]).strip() or None
        if "body" in data:
            payload["body"] = str(data["body"]).strip() or None
        if "verified" in data:
            payload["verified"] = bool(data["verified"])

        if payload:
            supabase.table("reviews").update(payload).eq("id", review_id).execute()

        # Handle images replacement if provided
        if "image_urls" in data:
            image_urls = data.get("image_urls") or []
            supabase.table("review_images").delete().eq("review_id", review_id).execute()
            if image_urls:
                image_rows = [
                    {
                        "review_id": review_id,
                        "image_url": url,
                        "sort_order": idx,
                    }
                    for idx, url in enumerate(image_urls)
                    if url
                ]
                if image_rows:
                    supabase.table("review_images").insert(image_rows).execute()

        full_res = (
            supabase.table("reviews")
            .select("*, products(id, title, image_url), review_images(id, image_url, sort_order)")
            .eq("id", review_id)
            .single()
            .execute()
        )
        return jsonify(full_res.data)
    except Exception as e:
        print(f"Error updating review: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/reviews/<int:review_id>", methods=["DELETE"])
def delete_admin_review(review_id):
    try:
        supabase.table("review_images").delete().eq("review_id", review_id).execute()
        supabase.table("reviews").delete().eq("id", review_id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error deleting review: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(debug=True, port=5000)
