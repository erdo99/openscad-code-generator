"""
Backend API for OpenSCAD Code Generator
HuggingFace ve ZAI API sağlayıcıları ile OpenSCAD kodu üretme
"""
import os
import sys

# Windows terminalinde emoji/UTF-8 cikti sorunlarini onle
def _configure_stdio_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass

_configure_stdio_utf8()

import base64
import subprocess
import tempfile
import shutil
import time
import re
import json
from io import BytesIO
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
CORS(app)

# Global değişkenler
openscad_path = None
default_provider = os.getenv('API_PROVIDER', 'huggingface').lower()
api_clients = {}
provider_models = {}
provider_base_urls = {}
last_api_call_time = 0
min_api_interval = 1.0

PROVIDER_CONFIG = {
    'huggingface': {
        'key_envs': ['HF_TOKEN', 'HUGGINGFACE_TOKEN'],
        'base_url_env': 'HF_BASE_URL',
        'default_base_url': 'https://router.huggingface.co/v1',
        'model_env': 'HF_MODEL',
        'fallback_model_env': 'MODEL_NAME',
        'default_model': 'Qwen/Qwen2.5-VL-7B-Instruct',
    },
    'zai': {
        'key_envs': ['NEW_KEY', 'SECOND_API_KEY', 'ZAI_API_KEY'],
        'base_url_env': 'ZAI_BASE_URL',
        'default_base_url': 'https://api.z.ai/api/paas/v4',
        'model_env': 'ZAI_MODEL',
        'fallback_model_env': 'MODEL_NAME',
        'default_model': 'glm-4.6v-flash',
    },
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_env_value(env_names):
    """İlk bulunan env değişkenini döndürür."""
    if isinstance(env_names, str):
        env_names = [env_names]
    for name in env_names:
        value = os.getenv(name)
        if value:
            return value
    return None


def normalize_model_for_provider(provider, model):
    """Sağlayıcıya göre model adını normalize eder."""
    if provider == 'zai':
        if '/' in model:
            model = model.split('/')[-1]
        return model.lower().replace('_', '-')
    return model


def get_provider_model(provider):
    """Sağlayıcı için varsayılan model adını döndürür."""
    cfg = PROVIDER_CONFIG[provider]
    model = (
        os.getenv(cfg['model_env'])
        or os.getenv(cfg['fallback_model_env'])
        or cfg['default_model']
    )
    return normalize_model_for_provider(provider, model)


def provider_is_configured(provider):
    """Sağlayıcı için API key tanımlı mı?"""
    cfg = PROVIDER_CONFIG[provider]
    return bool(get_env_value(cfg['key_envs']))


def get_available_providers():
    """API key'i tanımlı sağlayıcıları listeler."""
    return [name for name in PROVIDER_CONFIG if provider_is_configured(name)]


def resolve_provider(provider=None):
    """Geçerli sağlayıcı adını döndürür."""
    chosen = (provider or default_provider).lower()
    if chosen not in PROVIDER_CONFIG:
        raise Exception(f"Desteklenmeyen API sağlayıcısı: {chosen}")
    if not provider_is_configured(chosen):
        available = ', '.join(get_available_providers()) or 'yok'
        raise Exception(
            f"{chosen} için API key bulunamadı. .env dosyasını kontrol edin. "
            f"Yapılandırılmış sağlayıcılar: {available}"
        )
    return chosen


def get_api_client(provider):
    """Sağlayıcı için OpenAI client döndürür (lazy init)."""
    provider = resolve_provider(provider)
    if provider in api_clients:
        return api_clients[provider], provider_models[provider], provider_base_urls[provider]

    cfg = PROVIDER_CONFIG[provider]
    api_key = get_env_value(cfg['key_envs'])
    base_url = (
        os.getenv(cfg['base_url_env'])
        or cfg['default_base_url']
    ).rstrip('/') + '/'
    model = get_provider_model(provider)

    api_clients[provider] = OpenAI(api_key=api_key, base_url=base_url)
    provider_models[provider] = model
    provider_base_urls[provider] = base_url

    print(f"✅ {provider} API client hazır")
    print(f"   Model: {model}")
    print(f"   Base URL: {base_url}")

    return api_clients[provider], model, base_url


def init_app():
    """Uygulamayı başlat"""
    global openscad_path, default_provider

    default_provider = os.getenv('API_PROVIDER', 'huggingface').lower()
    if default_provider not in PROVIDER_CONFIG:
        raise Exception(
            f"Geçersiz API_PROVIDER: {default_provider}. "
            f"Desteklenenler: {', '.join(PROVIDER_CONFIG.keys())}"
        )

    available = get_available_providers()
    if not available:
        raise Exception(
            "Hiçbir API key bulunamadı! .env dosyasına şunlardan birini ekleyin:\n"
            "- HuggingFace: HF_TOKEN\n"
            "- ZAI: NEW_KEY veya SECOND_API_KEY"
        )

    if default_provider not in available:
        default_provider = available[0]
        print(f"⚠️ Varsayılan sağlayıcı yapılandırılmamış, {default_provider} kullanılıyor")

    get_api_client(default_provider)
    print(f"✅ Varsayılan API sağlayıcı: {default_provider}")
    print(f"✅ Yapılandırılmış sağlayıcılar: {', '.join(available)}")

    openscad_path = find_openscad()

def find_openscad():
    """OpenSCAD'ın yolunu bulur"""
    # Geçici olarak OpenSCAD'ı devre dışı bırakmak için False yapın
    OPENSCAD_ENABLED = True  # True yaparak tekrar aktif edebilirsiniz
    
    if not OPENSCAD_ENABLED:
        return None
    
    possible_paths = [
        r"C:\Program Files\OpenSCAD\openscad.exe",
        r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
        r"C:\OpenSCAD\openscad.exe",
        "openscad",
    ]
    
    for path in possible_paths:
        if path == "openscad":
            if shutil.which("openscad"):
                return "openscad"
        elif os.path.exists(path):
            return path
    
    return None

def encode_image(image_data):
    """Base64 görseli optimize edip base64'e çevirir"""
    if isinstance(image_data, str):
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
    else:
        image_bytes = image_data
    
    img = Image.open(BytesIO(image_bytes))
    max_size = 1024
    
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85, optimize=True)
    buffer.seek(0)
    
    return base64.b64encode(buffer.read()).decode('utf-8')

def wait_for_rate_limit():
    """API çağrıları arasında minimum bekleme süresi"""
    global last_api_call_time
    
    current_time = time.time()
    time_since_last_call = current_time - last_api_call_time
    if time_since_last_call < min_api_interval:
        wait_time = min_api_interval - time_since_last_call
        time.sleep(wait_time)
    last_api_call_time = time.time()

def api_call_with_retry(client, max_retries=3, model=None, messages=None, temperature=0.7, max_tokens=4000):
    """OpenAI-compatible API çağrısı ile retry mekanizması"""
    if not client:
        raise Exception("OpenAI client başlatılmamış. init_app() çağrılmalı.")
    
    if not model:
        raise Exception("Model adı gereklidir.")
    
    if not messages:
        raise Exception("Messages gereklidir.")
    
    base_wait_time = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🤖 API çağrısı yapılıyor (Deneme {attempt + 1}/{max_retries})...")
            print(f"   Model: {model}")
            print(f"   Messages: {len(messages)} mesaj")
            
            # OpenAI client ile API çağrısı
            # stream=False olduğu için response bir ChatCompletion objesi döner
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False  # Her zaman False, stream mode desteklenmiyor
            )
            
            # Response'u dict formatına çevir (eski kod uyumluluğu için)
            # stream=False olduğu için response bir ChatCompletion objesi
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return {
                    'choices': [{
                        'message': {
                            'content': response.choices[0].message.content,
                            'role': response.choices[0].message.role
                        }
                    }]
                }
            else:
                raise Exception("API yanıtı beklenen formatta değil (choices yok)")
                
        except Exception as e:
            error_msg = str(e)
            
            # Rate limit hatası kontrolü
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * base_wait_time
                    print(f"⏳ Rate limit - {wait_time} saniye bekleniyor (Deneme {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Rate limit hatası: {error_msg}")
            
            # Diğer hatalar
            print(f"❌ API Hatası (Deneme {attempt + 1}/{max_retries}): {error_msg}")
            
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * base_wait_time
                print(f"⏳ {wait_time} saniye bekleniyor...")
                time.sleep(wait_time)
                continue
            else:
                raise Exception(f"API çağrısı başarısız: {error_msg}")
    
    raise Exception("API çağrısı başarısız oldu - tüm denemeler tükendi.")

def create_online_editor_link(code):
    """Online editor linki oluştur (gzip+base64 encode)"""
    try:
        import gzip
        # Kodu gzip ile sıkıştır, sonra base64 encode et
        code_bytes = code.encode('utf-8')
        compressed = gzip.compress(code_bytes, compresslevel=9)
        code_base64 = base64.b64encode(compressed).decode('utf-8')
        # URL-safe base64
        code_base64 = code_base64.replace('+', '-').replace('/', '_').replace('=', '')
        online_link = f"https://ochafik.com/openscad2/#{code_base64}"
        print(f"🌐 Online editor linki oluşturuldu: {online_link[:100]}...")
        return online_link
    except Exception as e:
        print(f"⚠️ Link oluşturma hatası: {e}")
        return None

def try_render_online(code):
    """Selenium ile online OpenSCAD editor'de render et"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        
        print("🌐 Online render başlatılıyor (Selenium)...")
        
        # Chrome options - Windows için optimize edilmiş
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # Yeni headless mod
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # WebDriver oluştur - hata yönetimi ile
        driver = None
        service = None
        try:
            print("📦 ChromeDriver yükleniyor...")
            service = Service(ChromeDriverManager().install())
            print("✅ ChromeDriver hazır, Chrome başlatılıyor (headless)...")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ Chrome başlatıldı (headless)")
        except Exception as chrome_error:
            # Chrome başlatılamazsa, headless olmadan dene
            print(f"⚠️ Headless mod başarısız, normal mod deneniyor: {str(chrome_error)[:200]}")
            try:
                # Yeni options oluştur (headless olmadan)
                chrome_options_normal = Options()
                chrome_options_normal.add_argument('--no-sandbox')
                chrome_options_normal.add_argument('--disable-dev-shm-usage')
                chrome_options_normal.add_argument('--window-size=1920,1080')
                chrome_options_normal.add_experimental_option('excludeSwitches', ['enable-logging'])
                chrome_options_normal.add_experimental_option('useAutomationExtension', False)
                
                if service is None:
                    service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options_normal)
                print("✅ Chrome normal modda başlatıldı")
            except Exception as e2:
                error_msg = str(e2)
                if "session not created" in error_msg.lower():
                    raise Exception("Chrome başlatılamadı. Lütfen Google Chrome'un yüklü olduğundan ve güncel olduğundan emin olun. Chrome'u manuel olarak açıp çalıştığını kontrol edin.")
                else:
                    raise Exception(f"Chrome başlatılamadı: {error_msg[:300]}")
        
        try:
            # OpenSCAD Playground'u aç
            driver.get("https://ochafik.com/openscad2/")
            print("📄 Sayfa yüklendi, JavaScript ve editor yüklenmesi bekleniyor...")
            
            # Önce sayfanın tamamen yüklenmesini bekle (JavaScript'lerin çalışması için)
            print("⏳ Sayfa yüklenmesi bekleniyor (5 saniye)...")
            time.sleep(5)  # İlk yükleme için bekle
            
            wait = WebDriverWait(driver, 30)
            
            # Editor textarea veya input alanını bul
            # OpenSCAD Playground genellikle Monaco editor kullanır
            # Farklı selector'ları dene
            editor_found = False
            editor_selectors = [
                "textarea",
                "input[type='text']",
                ".monaco-editor textarea",
                "#editor textarea",
                "[contenteditable='true']"
            ]
            
            editor_element = None
            for selector in editor_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        editor_element = elements[0]
                        editor_found = True
                        print(f"✅ Editor bulundu: {selector}")
                        break
                except:
                    continue
            
            if not editor_found:
                # Sayfanın kaynak kodunu kontrol et
                page_source = driver.page_source[:2000]
                print(f"⚠️ Editor bulunamadı. Sayfa kaynağı (ilk 2000 karakter): {page_source}")
                # JavaScript ile editor'e erişmeyi dene
                try:
                    # Monaco editor'e JavaScript ile eriş
                    editor_element = driver.execute_script("""
                        // Monaco editor instance'ını bul
                        if (window.monaco && window.monaco.editor) {
                            var editors = window.monaco.editor.getEditors();
                            if (editors && editors.length > 0) {
                                return editors[0];
                            }
                        }
                        return null;
                    """)
                    if editor_element:
                        # JavaScript ile kodu set et
                        driver.execute_script(f"""
                            var editor = arguments[0];
                            if (editor && editor.setValue) {{
                                editor.setValue({json.dumps(code)});
                            }}
                        """, editor_element)
                        editor_found = True
                        print("✅ JavaScript ile editor'e erişildi")
                except Exception as js_error:
                    print(f"⚠️ JavaScript erişimi başarısız: {js_error}")
            
            if not editor_found:
                raise Exception("Editor elementi bulunamadı")
            
            # JavaScript ile kodu direkt set et (send_keys çok yavaş olabilir)
            print("📝 Kodu editor'e yazılıyor (JavaScript ile)...")
            code_set = driver.execute_script(f"""
                var code = {json.dumps(code)};
                
                // Yöntem 1: Monaco editor API (en hızlı)
                if (window.monaco && window.monaco.editor) {{
                    var editors = window.monaco.editor.getEditors();
                    if (editors && editors.length > 0) {{
                        editors[0].setValue(code);
                        // Değişikliği tetikle
                        editors[0].trigger('change', 'setValue');
                        return {{success: true, method: 'monaco-api', editorCount: editors.length}};
                    }}
                }}
                
                // Yöntem 2: Textarea direkt set (hızlı)
                var textareas = document.querySelectorAll('textarea');
                for (var i = 0; i < textareas.length; i++) {{
                    var ta = textareas[i];
                    if (ta.offsetParent !== null) {{ // Görünür olan
                        ta.value = code;
                        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        // Monaco editor için özel event
                        ta.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
                        return {{success: true, method: 'textarea-' + i, textareaCount: textareas.length}};
                    }}
                }}
                
                // Yöntem 3: ContentEditable
                var editables = document.querySelectorAll('[contenteditable="true"]');
                for (var i = 0; i < editables.length; i++) {{
                    var ed = editables[i];
                    if (ed.offsetParent !== null) {{
                        ed.textContent = code;
                        ed.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return {{success: true, method: 'contenteditable-' + i, editableCount: editables.length}};
                    }}
                }}
                
                return {{success: false, error: 'Editor bulunamadı', monaco: !!window.monaco}};
            """)
            
            if not code_set.get('success'):
                raise Exception(f"Kod yazılamadı: {code_set.get('error', 'Bilinmeyen hata')}. Monaco: {code_set.get('monaco', False)}")
            
            print(f"✅ Kod yazıldı (yöntem: {code_set.get('method')})")
            
            # Kod yazıldıktan sonra kısa bir bekleme
            time.sleep(2)
            
            # Render butonunu bul ve tıkla (eğer varsa)
            print("🔍 Render butonu aranıyor...")
            render_button_clicked = False
            render_button_selectors = [
                "button[title*='render' i]",
                "button[title*='Render' i]",
                "button:contains('Render')",
                ".render-button",
                "#render-button",
                "button[aria-label*='render' i]"
            ]
            
            for selector in render_button_selectors:
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        for btn in buttons:
                            try:
                                if btn.is_displayed() and btn.is_enabled():
                                    print(f"✅ Render butonu bulundu: {selector}")
                                    btn.click()
                                    render_button_clicked = True
                                    print("✅ Render butonuna tıklandı")
                                    time.sleep(2)  # Tıklama sonrası bekle
                                    break
                            except:
                                continue
                        if render_button_clicked:
                            break
                except:
                    continue
            
            if not render_button_clicked:
                print("⚠️ Render butonu bulunamadı, otomatik render bekleniyor...")
            
            # Render için bekle (OpenSCAD Playground render işlemi)
            print("⏳ Render işlemi bekleniyor (20 saniye)...")
            
            # Render'ın tamamlanmasını bekle - model-viewer veya canvas'ın yüklenmesi için
            render_complete = False
            max_render_wait = 30  # 30 saniye bekle
            start_time = time.time()
            
            while (time.time() - start_time) < max_render_wait and not render_complete:
                try:
                    # JavaScript ile render durumunu kontrol et
                    render_status = driver.execute_script("""
                        // Model viewer var mı ve yüklendi mi?
                        var modelViewer = document.querySelector('model-viewer');
                        if (modelViewer) {
                            var loaded = modelViewer.loaded || false;
                            var src = modelViewer.src || '';
                            // Eğer src varsa ve loaded ise, render tamamlanmış
                            if (src && loaded) {
                                return {
                                    found: true,
                                    type: 'model-viewer',
                                    loaded: true,
                                    ready: true
                                };
                            }
                        }
                        
                        // Canvas var mı? (3D render için) - içeriği kontrol et
                        var canvases = document.querySelectorAll('canvas');
                        var readyCanvases = [];
                        for (var i = 0; i < canvases.length; i++) {
                            var canvas = canvases[i];
                            var rect = canvas.getBoundingClientRect();
                            if (rect.width > 200 && rect.height > 200) { // Büyük canvas
                                // Canvas'ın içeriğini kontrol et (pixel data)
                                var ctx = canvas.getContext('2d');
                                if (ctx) {
                                    var imageData = ctx.getImageData(0, 0, Math.min(10, rect.width), Math.min(10, rect.height));
                                    var hasContent = false;
                                    // İlk birkaç pikselin boş olup olmadığını kontrol et
                                    for (var j = 0; j < imageData.data.length; j += 4) {
                                        var r = imageData.data[j];
                                        var g = imageData.data[j + 1];
                                        var b = imageData.data[j + 2];
                                        var a = imageData.data[j + 3];
                                        // Eğer tamamen beyaz değilse veya alpha > 0 ise içerik var
                                        if (!(r === 255 && g === 255 && b === 255) || a > 0) {
                                            hasContent = true;
                                            break;
                                        }
                                    }
                                    if (hasContent) {
                                        readyCanvases.push({
                                            width: rect.width,
                                            height: rect.height,
                                            index: i,
                                            hasContent: true
                                        });
                                    }
                                }
                            }
                        }
                        if (readyCanvases.length > 0) {
                            return {
                                found: true,
                                type: 'canvas',
                                count: readyCanvases.length,
                                ready: true,
                                canvases: readyCanvases
                            };
                        }
                        
                        // Loading indicator var mı? (render devam ediyor mu?)
                        var loadingIndicators = document.querySelectorAll('.loading, .spinner, [class*="loading"], [class*="spinner"]');
                        var isLoading = false;
                        for (var i = 0; i < loadingIndicators.length; i++) {
                            var style = window.getComputedStyle(loadingIndicators[i]);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                isLoading = true;
                                break;
                            }
                        }
                        
                        return {
                            found: false,
                            isLoading: isLoading
                        };
                    """)
                    
                    if render_status.get('found') and render_status.get('ready'):
                        render_complete = True
                        print(f"✅ Render tamamlandı: {render_status.get('type')}")
                        break
                    elif render_status.get('isLoading'):
                        # Hala yükleniyor
                        time.sleep(2)
                        elapsed = int(time.time() - start_time)
                        if elapsed % 5 == 0:
                            print(f"   Render devam ediyor... ({elapsed}s)")
                    else:
                        # Henüz başlamamış olabilir, biraz daha bekle
                        time.sleep(2)
                        elapsed = int(time.time() - start_time)
                        if elapsed % 5 == 0:
                            print(f"   Render bekleniyor... ({elapsed}s)")
                except Exception as e:
                    print(f"   Render kontrol hatası: {e}")
                    time.sleep(2)
            
            if not render_complete:
                print("⚠️ Render tamamlanmamış görünüyor, devam ediliyor...")
            
            # Render tamamlandıktan sonra ekstra bekleme (render'ın stabilize olması için)
            print("⏳ Render'ın stabilize olması bekleniyor (3 saniye)...")
            time.sleep(3)
            
            # Render edilmiş görüntüyü al
            print("🔍 Render edilmiş görüntü aranıyor...")
            screenshot_taken = False
            image_data = None
            
            # Önce model-viewer'dan al (en iyi kalite)
            try:
                model_viewer = driver.find_elements(By.CSS_SELECTOR, "model-viewer")
                if model_viewer:
                    print("📷 Model-viewer bulundu, screenshot alınıyor...")
                    # Model-viewer'ın screenshot'ını al
                    screenshot = model_viewer[0].screenshot_as_png
                    if screenshot and len(screenshot) > 5000:  # En az 5KB olmalı
                        image_data = base64.b64encode(screenshot).decode('utf-8')
                        screenshot_taken = True
                        print(f"✅ Model-viewer screenshot alındı (boyut: {len(screenshot)} bytes)")
            except Exception as e:
                print(f"   Model-viewer hatası: {e}")
            
            # Eğer model-viewer yoksa, büyük canvas'lardan al
            if not screenshot_taken:
                try:
                    all_canvases = driver.find_elements(By.CSS_SELECTOR, "canvas")
                    print(f"   {len(all_canvases)} canvas bulundu")
                    
                    for idx, canvas in enumerate(all_canvases):
                        try:
                            size = canvas.size
                            if size['width'] > 200 and size['height'] > 200:  # Büyük canvas
                                print(f"   Canvas {idx}: {size['width']}x{size['height']}")
                                screenshot = canvas.screenshot_as_png
                                if screenshot and len(screenshot) > 5000:  # En az 5KB
                                    image_data = base64.b64encode(screenshot).decode('utf-8')
                                    screenshot_taken = True
                                    print(f"✅ Canvas {idx} screenshot alındı (boyut: {len(screenshot)} bytes)")
                                    break
                        except Exception as e:
                            print(f"   Canvas {idx} hatası: {e}")
                            continue
                except Exception as e:
                    print(f"   Canvas arama hatası: {e}")
            
            # Eğer hala bulunamadıysa, sayfa screenshot'ı al (ama sadece viewer kısmını)
            if not screenshot_taken or not image_data or len(image_data) < 5000:
                print("⚠️ Canvas/model-viewer bulunamadı, sayfa screenshot alınıyor...")
                try:
                    # Viewer container'ı bul ve sadece onun screenshot'ını al
                    viewer_selectors = [
                        "model-viewer",
                        ".stl-viewer",
                        "#viewer",
                        "[data-viewer]",
                        ".viewer-container"
                    ]
                    
                    viewer_found = False
                    for selector in viewer_selectors:
                        try:
                            viewer = driver.find_elements(By.CSS_SELECTOR, selector)
                            if viewer:
                                screenshot = viewer[0].screenshot_as_png
                                if screenshot and len(screenshot) > 5000:
                                    image_data = base64.b64encode(screenshot).decode('utf-8')
                                    screenshot_taken = True
                                    print(f"✅ Viewer container screenshot alındı: {selector} (boyut: {len(screenshot)} bytes)")
                                    viewer_found = True
                                    break
                        except:
                            continue
                    
                    if not viewer_found:
                        # Son çare: Tüm sayfa
                        screenshot = driver.get_screenshot_as_png()
                        if screenshot and len(screenshot) > 5000:
                            image_data = base64.b64encode(screenshot).decode('utf-8')
                            screenshot_taken = True
                            print(f"✅ Sayfa screenshot alındı (boyut: {len(screenshot)} bytes)")
                except Exception as e:
                    print(f"   Screenshot hatası: {e}")
            
            if image_data and len(image_data) > 5000:  # En az 5KB olmalı
                return True, image_data
            else:
                # Render görüntüsü alınamadı
                return False, "Render görüntüsü alınamadı"
                
        finally:
            driver.quit()
            
    except ImportError:
        return False, "Selenium kurulu değil. 'pip install selenium webdriver-manager' komutu ile kurun."
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Online render hatası: {error_details}")
        return False, f"Online render hatası: {str(e)}"

def try_render(code):
    """
    Kodu render etmeye çalışır (önce local OpenSCAD, sonra online Selenium)
    
    Strateji:
    1. Eğer OpenSCAD executable'ına ulaşılabiliyorsa (openscad_path varsa):
       - Önce local OpenSCAD ile render'ı dene
       - Başarılı olursa: Local render görüntüsünü döndür
       - Başarısız olursa: Online render'ı dene (fallback)
    2. Eğer OpenSCAD yoksa:
       - Direkt online render'ı dene
    3. Her durumda online editor linki oluşturulur (render_code endpoint'inde)
    """
    # Önce local OpenSCAD'ı dene (eğer executable'a ulaşılabiliyorsa)
    if openscad_path:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scad', delete=False, encoding='utf-8') as scad_file:
                scad_file.write(code)
                scad_path = scad_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as png_file:
                png_path = png_file.name
            
            cmd = [
                openscad_path,
                "--render",
                "--imgsize=800,600",
                "--viewall",
                "--autocenter",
                "-o", png_path,
                scad_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            try:
                os.unlink(scad_path)
            except:
                pass
            
            if result.returncode == 0:
                if os.path.exists(png_path):
                    with open(png_path, 'rb') as f:
                        png_data = base64.b64encode(f.read()).decode('utf-8')
                    try:
                        os.unlink(png_path)
                    except:
                        pass
                    return True, png_data
                return False, "Render başarılı ama görsel bulunamadı"
            else:
                error_msg = result.stderr or result.stdout or "Bilinmeyen hata"
                if "ERROR" in error_msg:
                    lines = error_msg.split('\n')
                    error_lines = [line for line in lines if 'ERROR' in line or 'WARNING' in line]
                    if error_lines:
                        error_msg = '\n'.join(error_lines[:10])
                # Local render başarısız, online'ı dene
                print(f"⚠️ Local render başarısız, online render deneniyor...")
                return try_render_online(code)
                
        except subprocess.TimeoutExpired:
            print(f"⚠️ Local render timeout, online render deneniyor...")
            return try_render_online(code)
        except Exception as e:
            print(f"⚠️ Local render hatası: {e}, online render deneniyor...")
            return try_render_online(code)
    else:
        # OpenSCAD yok, direkt online'ı dene
        print("⚠️ OpenSCAD bulunamadı, online render deneniyor...")
        return try_render_online(code)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """API sağlık kontrolü"""
    providers_info = {}
    for name in PROVIDER_CONFIG:
        configured = provider_is_configured(name)
        info: dict = {'configured': configured}
        if configured:
            info['model'] = get_provider_model(name)
            info['base_url'] = (
                os.getenv(PROVIDER_CONFIG[name]['base_url_env'])
                or PROVIDER_CONFIG[name]['default_base_url']
            )
        providers_info[name] = info

    active_model = provider_models.get(default_provider) if default_provider in provider_models else None

    return jsonify({
        'status': 'ok',
        'openscad_available': openscad_path is not None,
        'api_provider': default_provider,
        'default_provider': default_provider,
        'available_providers': get_available_providers(),
        'providers': providers_info,
        'model': active_model,
    })

@app.route('/api/generate', methods=['POST'])
def generate_code():
    """OpenSCAD kodu üret (HuggingFace veya ZAI API ile)"""
    try:
        print("📥 /api/generate isteği alındı")
        
        if not request.json:
            return jsonify({'error': 'JSON verisi gereklidir'}), 400
        
        data = request.json
        image_base64 = data.get('image', None)
        text_description = data.get('description', '')
        additional_instruction = data.get('instruction', '')
        temperature = data.get('temperature', 0.7)
        custom_model = data.get('model', None)  # Frontend'den model override
        requested_provider = data.get('api_provider', None)
        
        print(f"📊 Gelen veri: image={image_base64 is not None}, description={bool(text_description)}, instruction={bool(additional_instruction)}")
        
        if not image_base64 and not text_description:
            return jsonify({'error': 'Görsel veya metin açıklaması gereklidir'}), 400

        try:
            provider = resolve_provider(requested_provider)
            client, default_model, base_url = get_api_client(provider)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
        wait_for_rate_limit()
        
        # System instruction
        system_instruction = """You are an expert OpenSCAD programmer with 10+ years of experience in reverse-engineering 3D objects from images and descriptions. Your specialty is creating accurate, syntactically correct, and render-ready OpenSCAD code.

CRITICAL EXPERTISE AREAS:
- Precise dimensional analysis from visual cues
- Proper OpenSCAD syntax (NO Python, JavaScript, or other language constructs)
- Efficient use of primitives: cube(), sphere(), cylinder(), polyhedron()
- Boolean operations: union(), difference(), intersection()
- Transformations: translate(), rotate(), scale(), mirror()
- Modular code structure with reusable modules

YOUR SYSTEMATIC APPROACH:
1. ANALYZE: Carefully observe the object's geometry, proportions, and features
2. DECOMPOSE: Break complex shapes into primitive combinations
3. ESTIMATE: Determine realistic dimensions (in millimeters)
4. PLAN: Decide on boolean operations and transformations
5. CODE: Write clean, commented, syntactically perfect OpenSCAD code
6. VERIFY: Mentally check for syntax errors before outputting

"""
        
        user_prompt_parts = []
        
        if image_base64:
            user_prompt_parts.append("**TASK:** Analyze this image of a 3D object and generate the corresponding OpenSCAD code.\n")
        else:
            user_prompt_parts.append("**TASK:** Based on the following description, generate the corresponding OpenSCAD code.\n")
        
        if text_description:
            user_prompt_parts.append(f"\n**OBJECT DESCRIPTION:**\n{text_description}\n")
        
        user_prompt_parts.append("""
**STEP-BY-STEP REQUIREMENTS:**

**Step 1: Dimensional Analysis**
- Estimate width, height, depth in millimeters
- Identify key measurements and proportions
- Note any symmetries or patterns

**Step 2: Shape Decomposition**
- List all primitive shapes needed (cubes, cylinders, spheres, etc.)
- Identify which shapes will be added (union) or subtracted (difference)
- Plan the order of operations

**Step 3: Code Structure**
- Start with a comment block describing the object
- Define reusable modules for repeated elements
- Use meaningful variable names for dimensions
- Build from simple to complex (base shape first, then details)

**Step 4: Syntax Correctness**
CRITICAL SYNTAX RULES:
✓ All statements end with semicolon: `cube([10,20,30]);`
✓ Module definition: `module name() { ... }`
✓ Module call: `name();`
✓ Comments: `// single line` or `/* multi line */`
✓ Arrays with commas: `[x, y, z]`
✓ Boolean ops: `union() { shape1(); shape2(); }`
✗ NO Python syntax: NO `def`, NO `for i in range()`, NO indentation-based blocks
✗ NO undefined variables or functions
✗ NO missing semicolons or brackets

**Step 5: Code Quality**
- Add descriptive comments for each major section
- Use consistent indentation (2 or 4 spaces)
- Keep modules small and focused
- Include a final comment showing expected render time if complex

**COMMON MISTAKES TO AVOID:**
❌ `cube(10, 20, 30)` → ✅ `cube([10, 20, 30]);`
❌ `for i in range(5)` → ✅ `for(i=[0:4])`
❌ `translate(x=10, y=20)` → ✅ `translate([10, 20, 0])`
❌ Missing semicolons after operations
❌ Unclosed brackets or parentheses
❌ Using undefined variables
""")
        
        if additional_instruction:
            user_prompt_parts.append(f"\n**ADDITIONAL USER REQUEST:**\n{additional_instruction}\n")
        
        user_prompt_parts.append("""
**OUTPUT FORMAT:**
Generate ONLY the OpenSCAD code. Start immediately with the code itself.
Include comments within the code to explain the structure.
Do NOT include:
- Markdown code fences (```)
- Explanatory text before or after the code
- Alternative versions or options

The code should be ready to copy-paste directly into OpenSCAD and render successfully.

**BEGIN CODE GENERATION:**
""")
        
        # OpenAI-compatible vision formatı
        # Görsel varsa vision formatında gönder
        
        user_content = []
        
        # Metin içeriği ekle
        user_content.append({
            "type": "text",
            "text": "".join(user_prompt_parts)
        })
        
        # Eğer görsel varsa, base64 formatında ekle (OpenAI-compatible vision formatı)
        if image_base64:
            try:
                # Görseli encode et
                encoded_image = encode_image(image_base64)
                
                # OpenAI-compatible vision formatı
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    }
                })
                print("📷 Görsel API'ye eklendi (vision formatında) - Model görsel analizi destekliyor")
            except Exception as e:
                print(f"⚠️ Görsel encode edilemedi, sadece text gönderiliyor: {e}")
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content if image_base64 else "".join(user_prompt_parts)}
        ]
        
        # API çağrısı için parametreler
        model_to_use = custom_model or default_model
        if custom_model:
            model_to_use = normalize_model_for_provider(provider, model_to_use)
        
        print(f"🤖 Provider: {provider}")
        print(f"🤖 Model: {model_to_use}, API çağrısı yapılıyor...")
        if image_base64:
            print("   📷 Görsel analizi aktif")
        
        response_data = api_call_with_retry(
            client=client,
            model=model_to_use,
            messages=messages,
            temperature=temperature,
            max_tokens=4000
        )
        
        if not response_data or 'choices' not in response_data or not response_data['choices']:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        message = response_data['choices'][0]['message']
        answer = message.get('content', None)
        
        if not answer or (isinstance(answer, str) and len(answer.strip()) == 0):
            return jsonify({
                'error': 'OpenSCAD kodu üretilemedi - API yanıtı boş'
            }), 500
        
        # Markdown temizle
        clean_code = answer.strip()
        if clean_code.startswith("```openscad") or clean_code.startswith("```"):
            clean_code = clean_code.split("```")[1]
            if clean_code.startswith("openscad"):
                clean_code = clean_code[8:]
            clean_code = clean_code.strip()
        
        print(f"✅ Final kod uzunluğu: {len(clean_code)} karakter")
        
        return jsonify({
            'code': clean_code,
            'success': True,
            'model': model_to_use,
            'api_provider': provider,
            'base_url': base_url,
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Generate Error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details if app.debug else None
        }), 500

@app.route('/api/render', methods=['POST'])
def render_code():
    """OpenSCAD kodunu render et (önce local, sonra online Selenium ile)"""
    try:
        data = request.json
        code = data.get('code', '')
        
        if not code:
            return jsonify({'error': 'Kod gereklidir'}), 400
        
        print(f"🔄 Render başlatılıyor (kod uzunluğu: {len(code)} karakter)...")
        success, result = try_render(code)
        
        # Her zaman online editor linki oluştur (başarılı olsa bile)
        online_link = create_online_editor_link(code)
        
        if success:
            print("✅ Render başarılı")
            # Base64 string'in uzunluğunu kontrol et
            image_length = len(result) if result else 0
            print(f"📊 Görsel verisi uzunluğu: {image_length} karakter")
            
            return jsonify({
                'success': True,
                'image': result,
                'method': 'local' if openscad_path else 'online',
                'image_size': image_length,  # Debug için
                'online_editor_link': online_link  # Her zaman link gönder
            })
        else:
            print(f"❌ Render başarısız: {result}")
            
            return jsonify({
                'success': False,
                'error': result,
                'openscad_available': openscad_path is not None,
                'online_editor_link': online_link  # Hata durumunda da link gönder
            }), 400
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Render Error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details if app.debug else None
        }), 500

if __name__ == '__main__':
    try:
        init_app()
        print(f"🚀 Backend API başlatılıyor...")
        print(f"📦 Varsayılan sağlayıcı: {default_provider}")
        if default_provider in provider_models:
            print(f"📦 Model: {provider_models[default_provider]}")
        print(f"🔧 OpenSCAD: {'✅ Bulundu' if openscad_path else '❌ Bulunamadı'}")
        print(f"🌐 API: http://localhost:5002")
        print(f"🔗 Yapılandırılmış sağlayıcılar: {', '.join(get_available_providers())}")
        app.run(debug=True, host='0.0.0.0', port=5002)
    except Exception as e:
        import traceback
        print(f"❌ Hata: {e}")
        print(traceback.format_exc())
