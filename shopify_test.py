import shopify
import json

API_KEY = "13ee4c6d9d6a3531000351c939e86d00"
API_SECRET = "d5c302967ce868ff968313edf4960760"
ACCESS_TOKEN = "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"
url = "https://test-ai-12.myshopify.com/admin/api/2024-07/graphql.json"
api_version = '2024-07'
session = shopify.Session(url, api_version, ACCESS_TOKEN)
shopify.ShopifyResource.activate_session(session)

shop = shopify.Shop.current()  # Get the current shop
print(shop.name)  # Print the shop's name