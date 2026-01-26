"""
Backend API for OpenSCAD Code Generator using io_net API
io_net API entegrasyonu ile OpenSCAD kodu üretme
Model: zai-org/GLM-4.7-Flash
"""
import os
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
io_net_client = None  # OpenAI client instance
io_net_api_key = None
# io_net API base URL - .env'den oku veya varsayılan kullan (load_dotenv() sonrası)
io_net_base_url = os.getenv('IO_NET_BASE_URL', 'https://api.intelligence.io.solutions/api/v1')  # io_net API base URL
openscad_path = None
model_name = "Qwen/Qwen2.5-VL-32B-Instruct"  # Vision destekleyen model
last_api_call_time = 0
min_api_interval = 1.0

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def init_app():
    """Uygulamayı başlat"""
    global io_net_client, io_net_api_key, openscad_path, model_name, io_net_base_url
    
    io_net_api_key = os.getenv('IO_NET_KEY') or os.getenv('IOINTELLIGENCE_API_KEY')
    if not io_net_api_key:
        raise Exception("API key bulunamadı! .env dosyasına IO_NET_KEY veya IOINTELLIGENCE_API_KEY ekleyin.")
    
    # Model adını .env'den oku (varsa)
    env_model = os.getenv('IO_NET_MODEL', 'Qwen/Qwen2.5-VL-32B-Instruct')
    model_name = env_model
    
    # Base URL'in sonunda slash olduğundan emin ol (OpenAI client formatı)
    base_url = io_net_base_url.rstrip('/') + '/'
    
    # OpenAI client oluştur (io_net API OpenAI-compatible)
    io_net_client = OpenAI(
        api_key=io_net_api_key,
        base_url=base_url
    )
    
    print(f"✅ io_net API başlatıldı (OpenAI client)")
    print(f"✅ Model: {model_name}")
    print(f"✅ API Base URL: {base_url}")
    
    openscad_path = find_openscad()

def find_openscad():
    """OpenSCAD'ın yolunu bulur"""
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

def api_call_with_retry(max_retries=3, model=None, messages=None, temperature=0.7, max_tokens=4000):
    """io_net API çağrısı ile retry mekanizması (OpenAI client kullanarak)"""
    global io_net_client
    
    if not io_net_client:
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
            response = io_net_client.chat.completions.create(
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

def try_render(code):
    """Kodu render etmeye çalışır"""
    if not openscad_path:
        return False, "OpenSCAD bulunamadı"
    
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
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, "Render timeout (30 seconds exceeded)"
    except Exception as e:
        return False, str(e)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """API sağlık kontrolü"""
    return jsonify({
        'status': 'ok',
        'openscad_available': openscad_path is not None,
        'model': model_name,
        'api_provider': 'io_net'
    })

@app.route('/api/generate', methods=['POST'])
def generate_code():
    """OpenSCAD kodu üret (io_net API ile)"""
    try:
        print("📥 /api/generate isteği alındı (io_net API)")
        
        if not request.json:
            return jsonify({'error': 'JSON verisi gereklidir'}), 400
        
        data = request.json
        image_base64 = data.get('image', None)
        text_description = data.get('description', '')
        additional_instruction = data.get('instruction', '')
        temperature = data.get('temperature', 0.7)
        custom_model = data.get('model', None)  # Frontend'den model override
        
        print(f"📊 Gelen veri: image={image_base64 is not None}, description={bool(text_description)}, instruction={bool(additional_instruction)}")
        
        if not image_base64 and not text_description:
            return jsonify({'error': 'Görsel veya metin açıklaması gereklidir'}), 400
        
        if not io_net_api_key:
            return jsonify({'error': 'API key başlatılmamış'}), 500
        
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
        
        # io_net API için messages formatı
        # Qwen/Qwen2.5-VL-32B-Instruct modeli görsel desteği VAR (supports_images_input: true)
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
        model_to_use = custom_model or model_name
        
        print(f"🤖 Model: {model_to_use}, API çağrısı yapılıyor...")
        if image_base64:
            print("   📷 Görsel analizi aktif")
        
        # OpenAI client ile API çağrısı
        response_data = api_call_with_retry(
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
            'api_provider': 'io_net'
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
    """OpenSCAD kodunu render et"""
    try:
        data = request.json
        code = data.get('code', '')
        
        if not code:
            return jsonify({'error': 'Kod gereklidir'}), 400
        
        success, result = try_render(code)
        
        if success:
            return jsonify({
                'success': True,
                'image': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
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
        print(f"🚀 io_net Backend API başlatılıyor...")
        print(f"📦 Model: {model_name}")
        print(f"🔧 OpenSCAD: {'✅ Bulundu' if openscad_path else '❌ Bulunamadı'}")
        print(f"🌐 API: http://localhost:5002")
        print(f"🔗 API Provider: io_net")
        app.run(debug=True, host='0.0.0.0', port=5002)  # Farklı port (5002)
    except Exception as e:
        import traceback
        print(f"❌ Hata: {e}")
        print(traceback.format_exc())
