# test_hf.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("HUGGINGFACE_API_KEY")
print(f"🔑 Key loaded: {key[:5]}******")

url = "https://router.huggingface.co/models/openai-community/roberta-base-openai-detector"
headers = {"Authorization": f"Bearer {key}"}
payload = {"inputs": "This is a test sentence written by AI."}

print(f"📡 Sending request to {url}...")
try:
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"✅ Status Code: {resp.status_code}")
    print(f"📄 Response: {resp.text}")
except Exception as e:
    print(f"❌ Error: {e}")