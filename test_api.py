"""
Backend API Test Scripti
HuggingFace ve ZAI sağlayıcılarını test eder
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:5002/api"


def test_health():
    print("=" * 50)
    print("[TEST 1] Health Check")
    print("=" * 50)
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_generate_text(provider=None):
    label = provider or "default"
    print("\n" + "=" * 50)
    print(f"[TEST 2] Text Generate ({label})")
    print("=" * 50)

    payload = {
        "description": "Create a simple cube with dimensions 20x20x20 millimeters",
        "temperature": 0.7,
    }
    if provider:
        payload["api_provider"] = provider

    try:
        response = requests.post(
            f"{API_URL}/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Provider: {data.get('api_provider')}")
            print(f"[OK] Model: {data.get('model')}")
            code = data.get("code", "")
            print(f"[OK] Code length: {len(code)} chars")
            print(code[:300] + ("..." if len(code) > 300 else ""))
            return True
        print(f"[ERROR] {response.text}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    print("\n[TEST] Backend API Test\n")

    hf = bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN"))
    zai = bool(os.getenv("NEW_KEY") or os.getenv("SECOND_API_KEY") or os.getenv("ZAI_API_KEY"))
    print(f"HF_TOKEN: {'SET' if hf else 'NOT SET'}")
    print(f"ZAI KEY: {'SET' if zai else 'NOT SET'}")
    print(f"API_PROVIDER: {os.getenv('API_PROVIDER', 'huggingface')}\n")

    results = [("Health", test_health())]
    results.append(("Generate (default)", test_generate_text()))
    if hf:
        results.append(("Generate (huggingface)", test_generate_text("huggingface")))
    if zai:
        results.append(("Generate (zai)", test_generate_text("zai")))

    print("\n" + "=" * 50)
    print("SONUÇLAR")
    print("=" * 50)
    for name, ok in results:
        print(f"{'[OK]' if ok else '[FAIL]'} {name}")
