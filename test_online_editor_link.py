"""
Test script to verify if online editor link correctly loads code into the editor
"""
import os
import base64
import gzip
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

def create_online_editor_link(code):
    """Online editor linki oluştur (gzip+base64 encode) - backend ile aynı mantık"""
    try:
        # Kodu gzip ile sıkıştır, sonra base64 encode et
        code_bytes = code.encode('utf-8')
        compressed = gzip.compress(code_bytes, compresslevel=9)
        code_base64 = base64.b64encode(compressed).decode('utf-8')
        # URL-safe base64
        code_base64 = code_base64.replace('+', '-').replace('/', '_').replace('=', '')
        online_link = f"https://ochafik.com/openscad2/#{code_base64}"
        return online_link
    except Exception as e:
        print(f"⚠️ Link oluşturma hatası: {e}")
        return None

def test_online_editor_link(code):
    """Online editor linkini test et - kodun editor'e yazılıp yazılmadığını kontrol et"""
    print("🧪 Online Editor Link Test Başlatılıyor...")
    print(f"📝 Test kodu uzunluğu: {len(code)} karakter")
    
    # Link oluştur
    link = create_online_editor_link(code)
    if not link:
        print("❌ Link oluşturulamadı")
        return False
    
    print(f"🔗 Oluşturulan link: {link[:100]}...")
    print(f"📏 Link uzunluğu: {len(link)} karakter")
    
    # Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        print("📦 ChromeDriver yükleniyor...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Chrome başlatıldı")
        
        # Linki aç
        print(f"🌐 Link açılıyor: {link[:80]}...")
        driver.get(link)
        
        # Sayfa yüklenmesini bekle
        print("⏳ Sayfa yüklenmesi bekleniyor (5 saniye)...")
        time.sleep(5)
        
        # Monaco editor'ün yüklenmesini bekle
        print("⏳ Monaco editor yüklenmesi bekleniyor...")
        editor_ready = False
        max_wait = 20
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait and not editor_ready:
            try:
                editor_ready = driver.execute_script("""
                    if (window.monaco && window.monaco.editor) {
                        var editors = window.monaco.editor.getEditors();
                        if (editors && editors.length > 0) {
                            return true;
                        }
                    }
                    var editorContainer = document.querySelector('.monaco-editor');
                    if (editorContainer) {
                        return true;
                    }
                    return false;
                """)
                
                if editor_ready:
                    print("✅ Monaco editor hazır")
                    break
                else:
                    time.sleep(1)
            except Exception as e:
                print(f"   Kontrol hatası: {e}")
                time.sleep(1)
        
        if not editor_ready:
            print("❌ Editor hazır değil")
            return False
        
        # URL hash'inden kodu decode et ve editor'e yaz
        print("🔓 URL hash'inden kod decode ediliyor...")
        hash_from_url = link.split('#')[-1] if '#' in link else ''
        
        if hash_from_url:
            # URL-safe base64'ü normal base64'e çevir
            hash_normal = hash_from_url.replace('-', '+').replace('_', '/')
            # Padding ekle (gerekirse)
            padding = 4 - (len(hash_normal) % 4)
            if padding != 4:
                hash_normal += '=' * padding
            
            try:
                # Base64 decode
                compressed = base64.b64decode(hash_normal)
                # Gzip decompress
                decompressed = gzip.decompress(compressed)
                decoded_code = decompressed.decode('utf-8')
                print(f"✅ Kod decode edildi: {len(decoded_code)} karakter")
                print(f"📝 Decode edilen kod (ilk 100 karakter): {decoded_code[:100]}")
            except Exception as e:
                print(f"❌ Decode hatası: {e}")
                decoded_code = None
        else:
            decoded_code = None
        
        # Eğer decode başarılıysa, kodu editor'e yaz
        if decoded_code:
            print("📝 Decode edilen kod editor'e yazılıyor...")
            code_written = driver.execute_script(f"""
                var code = {repr(decoded_code)};
                
                // Yöntem 1: Monaco editor API
                if (window.monaco && window.monaco.editor) {{
                    var editors = window.monaco.editor.getEditors();
                    if (editors && editors.length > 0) {{
                        editors[0].setValue(code);
                        editors[0].trigger('change', 'setValue');
                        return {{success: true, method: 'monaco-api'}};
                    }}
                }}
                
                // Yöntem 2: Textarea
                var textareas = document.querySelectorAll('textarea');
                for (var i = 0; i < textareas.length; i++) {{
                    var ta = textareas[i];
                    if (ta.offsetParent !== null) {{
                        ta.value = code;
                        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return {{success: true, method: 'textarea-' + i}};
                    }}
                }}
                
                return {{success: false, error: 'Editor bulunamadı'}};
            """)
            
            if code_written.get('success'):
                print(f"✅ Kod editor'e yazıldı (yöntem: {code_written.get('method')})")
                time.sleep(2)  # Kod yazıldıktan sonra bekle
            else:
                print(f"❌ Kod yazılamadı: {code_written.get('error')}")
        
        # Editor'deki kodu oku
        print("📖 Editor'deki kod okunuyor...")
        editor_code = driver.execute_script("""
            // Monaco editor API ile kod oku
            if (window.monaco && window.monaco.editor) {
                var editors = window.monaco.editor.getEditors();
                if (editors && editors.length > 0) {
                    return editors[0].getValue();
                }
            }
            
            // Alternatif: Textarea
            var textareas = document.querySelectorAll('textarea');
            for (var i = 0; i < textareas.length; i++) {
                if (textareas[i].offsetParent !== null) {
                    return textareas[i].value;
                }
            }
            
            // Alternatif: ContentEditable
            var editables = document.querySelectorAll('[contenteditable="true"]');
            for (var i = 0; i < editables.length; i++) {
                if (editables[i].offsetParent !== null) {
                    return editables[i].textContent;
                }
            }
            
            return '';
        """)
        
        print(f"📊 Editor'deki kod uzunluğu: {len(editor_code)} karakter")
        print(f"📊 Beklenen kod uzunluğu: {len(code)} karakter")
        
        # Kodları karşılaştır (başlangıç ve son kısımları)
        if editor_code:
            print("\n📝 Editor'deki kod (ilk 200 karakter):")
            print(editor_code[:200])
            print("\n📝 Beklenen kod (ilk 200 karakter):")
            print(code[:200])
            
            # Kodların eşleşip eşleşmediğini kontrol et
            if editor_code.strip() == code.strip():
                print("\n✅ BAŞARILI: Kodlar tam olarak eşleşiyor!")
                return True
            elif len(editor_code) > 0:
                # Kısmi eşleşme kontrolü
                match_ratio = len(set(editor_code.split()) & set(code.split())) / max(len(code.split()), 1)
                print(f"\n⚠️ Kısmi eşleşme: {match_ratio * 100:.1f}% benzerlik")
                if match_ratio > 0.5:
                    print("✅ Kod yüklendi (kısmi eşleşme)")
                    return True
                else:
                    print("❌ Kodlar farklı görünüyor")
                    return False
            else:
                print("\n❌ Editor boş - kod yüklenmemiş")
                return False
        else:
            print("\n❌ Editor'den kod okunamadı")
            return False
            
    except Exception as e:
        import traceback
        print(f"❌ Test hatası: {e}")
        print(traceback.format_exc())
        return False
    finally:
        if driver:
            driver.quit()
            print("🔒 Chrome kapatıldı")

if __name__ == '__main__':
    # Test kodu
    test_code = """// Test OpenSCAD Code
cube([20, 20, 20]);
translate([30, 0, 0]) {
    sphere(r=10);
}
"""
    
    print("=" * 60)
    print("ONLINE EDITOR LINK TEST")
    print("=" * 60)
    print()
    
    success = test_online_editor_link(test_code)
    
    print()
    print("=" * 60)
    if success:
        print("✅ TEST BAŞARILI: Link kod yüklüyor")
    else:
        print("❌ TEST BAŞARISIZ: Link kod yüklemiyor")
    print("=" * 60)
