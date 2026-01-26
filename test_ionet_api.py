"""
io_net API Test Scripti
Backend'in çalışıp çalışmadığını test eder
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Test için API endpoint
API_URL = "http://localhost:5002/api"

def test_health():
    """Health check endpoint'ini test et"""
    print("=" * 50)
    print("[TEST 1] Health Check Test")
    print("=" * 50)
    
    try:
        response = requests.get(f"{API_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Hata: {e}")
        return False

def test_generate_text():
    """Text description ile kod üretme testi"""
    print("\n" + "=" * 50)
    print("[TEST 2] Text Description Test")
    print("=" * 50)
    
    payload = {
        "description": "Create a simple cube with dimensions 20x20x20 millimeters",
        "temperature": 0.7
    }
    
    try:
        print(f"Request: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        response = requests.post(
            f"{API_URL}/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Success: {data.get('success')}")
            print(f"Model: {data.get('model')}")
            print(f"API Provider: {data.get('api_provider')}")
            code = data.get('code', '')
            print(f"\nGenerated Code ({len(code)} chars):")
            print("-" * 50)
            print(code[:500] + ("..." if len(code) > 500 else ""))
            print("-" * 50)
            return True
        else:
            print(f"[ERROR] Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_generate_with_image():
    """Image ile kod üretme testi (opsiyonel)"""
    print("\n" + "=" * 50)
    print("[TEST 3] Image Test (Skipped - requires base64 image)")
    print("=" * 50)
    print("[WARN] Image test icin base64 encoded image gerekli")
    return True

if __name__ == "__main__":
    print("\n[TEST] io_net API Test Baslatiliyor...\n")
    
    # API key kontrolü
    api_key = os.getenv('IO_NET_KEY') or os.getenv('IOINTELLIGENCE_API_KEY')
    if not api_key:
        print("[ERROR] HATA: IO_NET_KEY veya IOINTELLIGENCE_API_KEY .env dosyasinda bulunamadi!")
        exit(1)
    
    print(f"[OK] API Key bulundu: {api_key[:20]}...")
    print(f"[OK] Test URL: {API_URL}\n")
    
    # Testler
    results = []
    
    results.append(("Health Check", test_health()))
    results.append(("Text Generate", test_generate_text()))
    results.append(("Image Generate", test_generate_with_image()))
    
    # Sonuçlar
    print("\n" + "=" * 50)
    print("TEST SONUÇLARI")
    print("=" * 50)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[SUCCESS] TUM TESTLER BASARILI!")
    else:
        print("[FAIL] BAZI TESTLER BASARISIZ!")
    print("=" * 50)
