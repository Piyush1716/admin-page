import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    orders = supabase.table("orders").select("*").limit(1).execute()
    print("ORDERS:", orders.data)
except Exception as e:
    print("ORDERS ERR:", e)

try:
    items = supabase.table("order_items").select("*").limit(1).execute()
    print("ORDER_ITEMS:", items.data)
except Exception as e:
    print("ORDER_ITEMS ERR:", e)
