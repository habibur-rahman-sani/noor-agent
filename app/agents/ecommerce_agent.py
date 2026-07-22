"""
E-commerce এজেন্ট — Shopify-র জন্য Agno-র নেটিভ টুলকিট আছে (key লাগবে)।
WooCommerce/Daraz/অন্যান্য প্ল্যাটফর্মের জন্য নেটিভ টুলকিট নেই, তাই PythonTools
দিয়ে সেগুলোর REST API কল করা হবে (যেই প্ল্যাটফর্মের key দেবে, সেটাই কাজ করবে)।
"""
from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from tools_free import DATA_TOOLS
from agno.tools.python import PythonTools
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION

ecom_tools = [PythonTools(), ApprovalTools()] + [t for t in DATA_TOOLS if t.name in ("pandas_tools", "csv_tools")]

if has_key("SHOPIFY_ACCESS_TOKEN", "SHOPIFY_STORE_URL"):
    from agno.tools.shopify import ShopifyTools
    ecom_tools.append(ShopifyTools())

shopify_ready = has_key("SHOPIFY_ACCESS_TOKEN", "SHOPIFY_STORE_URL")
woocommerce_ready = has_key("WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET", "WOOCOMMERCE_STORE_URL")

ecommerce_agent = Agent(
    name="E-commerce Agent",
    role="প্রোডাক্ট/অর্ডার/ইনভেন্টরি ম্যানেজমেন্ট, দাম আপডেট, সেলস রিপোর্ট, F-commerce integration",
    model=get_model("social"),
    db=get_db(),
    tools=ecom_tools,
    instructions=[
        "Shopify থাকলে ShopifyTools ব্যবহার করো।",
        "WooCommerce/Daraz/অন্য প্ল্যাটফর্মের জন্য PythonTools দিয়ে সেই প্ল্যাটফর্মের REST API কল করো "
        "(env: WOOCOMMERCE_CONSUMER_KEY/SECRET/STORE_URL ইত্যাদি)।",
        "দাম/ইনভেন্টরি বদলানো বা অর্ডার ক্যানসেলের মতো অ্যাকশনের আগে " + APPROVAL_INSTRUCTION,
        "যেই প্ল্যাটফর্মের key নেই সেটার জন্য কী লাগবে বলো, থেমে থেকো না।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)

if not (shopify_ready or woocommerce_ready):
    print("⚠️  E-commerce Agent-এ কোনো স্টোর কানেক্টেড নেই — .env-এ SHOPIFY_* বা WOOCOMMERCE_* বসাও।")
