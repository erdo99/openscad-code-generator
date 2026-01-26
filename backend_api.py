"""
Backend API for OpenSCAD Code Generator
Flask REST API - Frontend ile iletişim için
"""
import os
import base64
import subprocess
import tempfile
import shutil
import time
from io import BytesIO
from zai import ZaiClient
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
CORS(app)  # Frontend'den gelen isteklere izin ver

# Global değişkenler
client = None
client_second = None  # İyileştirme için ikinci API key
openscad_path = None
model_name = None
model_name_second = None  # İyileştirme için ikinci model
last_api_call_time = 0
last_api_call_time_second = 0  # İkinci API key için ayrı zaman takibi
min_api_interval = 1.0
min_api_interval_second = 2.0  # İkinci API key için daha uzun bekleme (yeni key'ler için)

def init_app():
    """Uygulamayı başlat"""
    global client, client_second, openscad_path, model_name, model_name_second
    
    # ZAI API key'ini yükle (NEW_KEY veya ZAI_API_KEY)
    token = os.getenv('NEW_KEY') or os.getenv('ZAI_API_KEY') or os.getenv('HF_TOKEN')
    if not token:
        raise Exception("API key bulunamadı! .env dosyasına NEW_KEY veya ZAI_API_KEY ekleyin.")
    
    # ZAI SDK kullanarak client oluştur
    client = ZaiClient(api_key=token)
    
    # Model adını yükle ve ZAI formatına çevir
    model_env = os.getenv('MODEL_NAME', 'zai-org/GLM-4.6V-Flash')
    # ZAI API model adları: glm-4.6v, glm-4.6v-flash, glm-4.6v-flashx, glm-4.7, vb.
    if 'GLM-4.6V-Flash' in model_env or 'glm-4.6v-flash' in model_env.lower():
        model_name = 'glm-4.6v-flash'
    elif 'GLM-4.6V' in model_env or 'glm-4.6v' in model_env.lower():
        model_name = 'glm-4.6v'
    elif 'GLM-4.7' in model_env or 'glm-4.7' in model_env.lower():
        model_name = 'glm-4.7'
    else:
        # Varsayılan olarak glm-4.6v-flash kullan
        model_name = 'glm-4.6v-flash'
        print(f"⚠️ Model adı '{model_env}' tanınmadı, varsayılan 'glm-4.6v-flash' kullanılıyor.")
    
    print(f"✅ ZAI SDK başlatıldı (ZaiClient)")
    print(f"✅ Model: {model_name}")
    
    # İkinci API key ve model için (iyileştirme endpoint'i)
    second_token = os.getenv('SECOND_API_KEY')
    if second_token:
        client_second = ZaiClient(api_key=second_token)
        print(f"✅ İkinci ZAI SDK başlatıldı (iyileştirme için)")
        
        # İkinci model adını yükle
        model_env_2 = os.getenv('MODEL_NAME_2', '').strip()
        if model_env_2:
            # MODEL_NAME_2 varsa onu kullan
            if 'GLM-4.6V-Flash' in model_env_2 or 'glm-4.6v-flash' in model_env_2.lower():
                model_name_second = 'glm-4.6v-flash'
            elif 'GLM-4.6V' in model_env_2 or 'glm-4.6v' in model_env_2.lower():
                model_name_second = 'glm-4.6v'
            elif 'GLM-4.7' in model_env_2 or 'glm-4.7' in model_env_2.lower():
                model_name_second = 'glm-4.7'
            else:
                model_name_second = 'glm-4.6v'  # Varsayılan olarak glm-4.6v
                print(f"⚠️ İkinci model adı '{model_env_2}' tanınmadı, varsayılan 'glm-4.6v' kullanılıyor.")
        else:
            # MODEL_NAME_2 yoksa varsayılan olarak glm-4.6v kullan
            model_name_second = 'glm-4.6v'
            print(f"✅ İkinci model belirtilmedi, varsayılan 'glm-4.6v' kullanılıyor.")
        
        print(f"✅ İkinci Model: {model_name_second}")
    else:
        print(f"⚠️ SECOND_API_KEY bulunamadı, iyileştirme endpoint'i birinci API key'i kullanacak.")
        client_second = None
        model_name_second = model_name
    
    # OpenSCAD yolunu bul
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
    # Base64 string'den görseli decode et
    if isinstance(image_data, str):
        if image_data.startswith('data:image'):
            # data:image/jpeg;base64,XXX formatından sadece base64 kısmını al
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

def wait_for_rate_limit(use_second_client=False):
    """API çağrıları arasında minimum bekleme süresi"""
    global last_api_call_time, last_api_call_time_second
    
    if use_second_client and client_second:
        # İkinci API key için daha uzun bekleme
        current_time = time.time()
        time_since_last_call = current_time - last_api_call_time_second
        
        if time_since_last_call < min_api_interval_second:
            wait_time = min_api_interval_second - time_since_last_call
            print(f"⏳ İkinci API key için bekleme: {wait_time:.2f} saniye...")
            time.sleep(wait_time)
        
        last_api_call_time_second = time.time()
    else:
        # Birinci API key için normal bekleme
        current_time = time.time()
        time_since_last_call = current_time - last_api_call_time
        
        if time_since_last_call < min_api_interval:
            wait_time = min_api_interval - time_since_last_call
            time.sleep(wait_time)
        
        last_api_call_time = time.time()

# Rate limit exception sınıfı
class RateLimitException(Exception):
    """Rate limit hatası için özel exception"""
    pass

def api_call_with_retry(max_retries=3, use_second_client=False, **kwargs):
    """Rate limiting için retry mekanizması ile API çağrısı - ZAI SDK"""
    # İkinci client kullanılacaksa onu seç
    active_client = client_second if (use_second_client and client_second) else client
    
    if not active_client:
        raise Exception("API client başlatılmamış. Token kontrol edin.")
    
    # İkinci API key için tek deneme (retry yok)
    if use_second_client and client_second:
        max_retries = 1  # Tek deneme
        print(f"🔑 İkinci API key kullanılıyor (tek deneme - başarısız olursa birinci API key'e dönecek)")
    else:
        # Birinci API key için normal retry mekanizması
        base_wait_time = 3  # Normal bekleme süresi
    
    for attempt in range(max_retries):
        try:
            # ZAI SDK kullanarak API çağrısı
            completion = active_client.chat.completions.create(**kwargs)
            if not completion or not hasattr(completion, 'choices') or not completion.choices:
                raise Exception("API yanıtı beklenen biçimde değil.")
            return completion
        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__
            
            # İkinci API key için tek deneme - başarısız olursa birinci API key'e dön
            if use_second_client and client_second:
                print(f"❌ İkinci API key ile hata: {error_str}")
                print(f"🔄 Birinci API key'e geri dönülüyor...")
                
                # Birinci API key ile tekrar dene
                if client:
                    try:
                        # Model'i birinci API key'in modeline çevir
                        original_model = kwargs.get('model', model_name)
                        if original_model == model_name_second:
                            kwargs['model'] = model_name
                            print(f"🔄 Model değiştirildi: {model_name_second} -> {model_name}")
                        
                        print(f"🔑 Birinci API key ile tekrar deneniyor...")
                        completion = client.chat.completions.create(**kwargs)
                        if completion and hasattr(completion, 'choices') and completion.choices:
                            print(f"✅ Birinci API key ile başarılı!")
                            return completion
                    except Exception as e2:
                        print(f"❌ Birinci API key ile de hata: {str(e2)}")
                        raise e  # Orijinal hatayı fırlat
                else:
                    raise  # Birinci client yoksa orijinal hatayı fırlat
            
            # Birinci API key için retry mekanizması
            # Rate limit hatası kontrolü (ZAI SDK veya genel HTTP hataları)
            is_rate_limit = (
                error_type == "RateLimitError" or
                "429" in error_str or 
                "rate limit" in error_str.lower() or 
                "concurrency" in error_str.lower() or
                "1302" in error_str or
                "too many requests" in error_str.lower()
            )
            
            if is_rate_limit:
                if attempt < max_retries - 1:
                    # Birinci API key için retry
                    wait_time = (2 ** attempt) * base_wait_time
                    print(f"⏳ Rate limit (Birinci API key) - {wait_time} saniye bekleniyor (Deneme {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Son deneme de başarısız - özel RateLimitException fırlat
                    raise RateLimitException(
                        f"Rate limit hatası (Birinci API key): API şu anda çok yoğun. "
                        f"{max_retries} deneme yapıldı ancak başarısız oldu. "
                        f"Lütfen 15-20 saniye bekleyip tekrar deneyin."
                    )
            else:
                # Rate limit dışındaki hatalar
                raise

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
                # PNG'yi base64'e çevir
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """API sağlık kontrolü"""
    return jsonify({
        'status': 'ok',
        'openscad_available': openscad_path is not None,
        'model': model_name
    })

@app.route('/api/generate', methods=['POST'])
def generate_code():
    """OpenSCAD kodu üret"""
    try:
        print("📥 /api/generate isteği alındı")
        
        if not request.json:
            print("❌ JSON verisi yok")
            return jsonify({'error': 'JSON verisi gereklidir'}), 400
            
        data = request.json
        image_base64 = data.get('image', None)
        text_description = data.get('description', '')
        additional_instruction = data.get('instruction', '')
        thinking_mode = data.get('thinking_mode', False)  # Frontend'den gelen thinking mode ayarı
        
        print(f"📊 Gelen veri: image={image_base64 is not None}, description={bool(text_description)}, instruction={bool(additional_instruction)}, thinking_mode={thinking_mode}")
        
        if not image_base64 and not text_description:
            return jsonify({'error': 'Görsel veya metin açıklaması gereklidir'}), 400
        
        if not client:
            print("❌ Client None!")
            return jsonify({'error': 'API client başlatılmamış'}), 500
        
        print("✅ Client mevcut, API çağrısı yapılıyor...")
        
        # Rate limiting - API çağrıları arasında bekle
        wait_for_rate_limit()
        print("⏱️ Rate limit kontrolü yapıldı, API çağrısı yapılıyor...")
        
        # Prompt oluştur
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
IMPORTANT: You MUST output the OpenSCAD code in the 'content' field, NOT in the reasoning.
Generate ONLY the OpenSCAD code. Start immediately with the code itself.
Include comments within the code to explain the structure.
Do NOT include:
- Markdown code fences (```)
- Explanatory text before or after the code
- Alternative versions or options

The code should be ready to copy-paste directly into OpenSCAD and render successfully.

**CRITICAL:** The final OpenSCAD code MUST be in the 'content' field, not just in reasoning.

**BEGIN CODE GENERATION:**
""")
        
        # ZAI API için: System instruction'ı user message'a ekle (GLM modelleri system role'ü desteklemeyebilir)
        final_prompt = system_instruction + "".join(user_prompt_parts)
        
        # Content oluştur
        content = [{"type": "text", "text": final_prompt}]
        
        if image_base64:
            # Görseli encode et
            encoded_image = encode_image(image_base64)
            # ZAI API için görsel formatı: interleaved (text + image)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                }
            })
        
        # API çağrısı - ZAI SDK formatı
        print(f"🤖 Model: {model_name}, API çağrısı yapılıyor...")
        print(f"📤 Content tipi: {type(content)}, uzunluk: {len(content)}")
        
        # ZAI SDK formatı: thinking parametresi
        # Frontend'den gelen thinking mode ayarını kullan
        completion = api_call_with_retry(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            thinking={
                "type": "enabled" if thinking_mode else "disabled"
            },
            temperature=0.3,
            max_tokens=4000,
        )
        
        print(f"✅ API yanıtı alındı: {completion is not None}")
        
        if not completion or not completion.choices:
            print("❌ Completion veya choices None!")
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        # Debug: Response yapısını kontrol et
        print(f"🔍 Choices sayısı: {len(completion.choices)}")
        if len(completion.choices) > 0:
            message = completion.choices[0].message
            
            # Content'i al
            answer = message.content if hasattr(message, 'content') else None
            
            # API yanıtını terminalde göster
            print("\n" + "="*80)
            print("📥 BACKEND API YANITI:")
            print("="*80)
            if answer:
                print(f"📝 Content ({len(answer)} karakter):")
                print("-"*80)
                print(answer[:1000] + ("..." if len(answer) > 1000 else ""))
                print("-"*80)
            
            # Reasoning content varsa göster
            reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
            if reasoning:
                print(f"🧠 Reasoning Content ({len(reasoning)} karakter):")
                print("-"*80)
                print(reasoning[:1000] + ("..." if len(reasoning) > 1000 else ""))
                print("-"*80)
            
            print("="*80 + "\n")
            
            # Eğer content boşsa, reasoning_content'i kontrol et (thinking mode)
            if not answer or (isinstance(answer, str) and len(answer.strip()) == 0):
                print(f"⚠️ Content boş! Reasoning content uzunluğu: {len(reasoning) if reasoning else 0}")
                
                # Reasoning content'ten kod çıkarmayı dene (eğer varsa)
                if reasoning and len(reasoning) > 100:
                    import re
                    
                    # Önce ```openscad veya ``` ile başlayan kod bloklarını ara
                    code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                    if code_blocks:
                        # Son kod bloğunu al ve temizle
                        answer = code_blocks[-1].strip()
                        # Sadece gerçek OpenSCAD kodu olup olmadığını kontrol et
                        if any(keyword in answer.lower() for keyword in ['cube', 'cylinder', 'sphere', 'translate', 'rotate', 'union', 'difference', 'intersection', 'module', 'function']):
                            print(f"✅ Reasoning content'ten kod çıkarıldı: {len(answer)} karakter")
                        else:
                            # Kod değil, düşünme süreci - tekrar ara
                            answer = None
                            print(f"⚠️ Bulunan metin kod değil, düşünme süreci. Tekrar aranıyor...")
                    
                    # Eğer hala kod bulunamadıysa, reasoning'in sonunda kod bloğu ara
                    if not answer:
                        # Reasoning'in son %30'unu kontrol et (kod genellikle sonunda olur)
                        reasoning_end = reasoning[-int(len(reasoning) * 0.3):] if len(reasoning) > 500 else reasoning
                        # ``` ile başlayan blokları ara
                        code_pattern = r'```(?:openscad)?\s*\n(.*?)(?:\n```|$)'
                        matches = re.findall(code_pattern, reasoning_end, re.DOTALL)
                        if matches:
                            potential_code = matches[-1].strip()
                            # Gerçek kod olup olmadığını kontrol et
                            if any(keyword in potential_code.lower() for keyword in ['cube', 'cylinder', 'sphere', 'translate', 'rotate', 'union', 'difference', 'module']):
                                answer = potential_code
                                print(f"✅ Reasoning content'in sonundan kod çıkarıldı: {len(answer)} karakter")
                    
                    # Eğer hala kod bulunamadıysa, reasoning'de OpenSCAD komutları içeren satırları topla
                    if not answer:
                        lines = reasoning.split('\n')
                        code_lines = []
                        in_code_block = False
                        for line in lines:
                            # ``` ile başlayan blokları tespit et
                            if '```' in line:
                                in_code_block = not in_code_block
                                continue
                            if in_code_block:
                                code_lines.append(line)
                            # Eğer kod bloğu içinde değilsek ama OpenSCAD komutları görüyorsak
                            elif any(keyword in line.lower() for keyword in ['cube(', 'cylinder(', 'sphere(', 'translate(', 'rotate(', 'union()', 'difference()']):
                                code_lines.append(line)
                        
                        if code_lines:
                            potential_code = '\n'.join(code_lines).strip()
                            # Minimum kod uzunluğu ve OpenSCAD komutları kontrolü
                            if len(potential_code) > 50 and any(keyword in potential_code.lower() for keyword in ['cube', 'cylinder', 'sphere', 'translate', 'rotate', 'union', 'difference']):
                                answer = potential_code
                                print(f"✅ Reasoning content'ten OpenSCAD komutları çıkarıldı: {len(answer)} karakter")
        else:
            answer = None
        
        print(f"📝 Final cevap uzunluğu: {len(answer) if answer else 0}")
        if answer:
            print(f"📝 Final cevap (ilk 500 karakter):")
            print("-"*80)
            print(answer[:500] + ("..." if len(answer) > 500 else ""))
            print("-"*80)
        
        if not answer or (isinstance(answer, str) and len(answer.strip()) == 0):
            # Daha detaylı hata mesajı
            error_detail = f"API yanıtı geldi ancak içerik boş. Thinking mode aktif olabilir."
            print(f"❌ {error_detail}")
            return jsonify({
                'error': 'OpenSCAD kodu üretilemedi - API yanıtı boş',
                'detail': error_detail,
                'suggestion': 'Thinking mode kapatılabilir veya model farklı bir formatta yanıt veriyor olabilir.'
            }), 500
        
        # Markdown temizle
        clean_code = answer.strip()
        if clean_code.startswith("```openscad") or clean_code.startswith("```"):
            clean_code = clean_code.split("```")[1]
            if clean_code.startswith("openscad"):
                clean_code = clean_code[8:]
            clean_code = clean_code.strip()
        
        print(f"✅ Temizlenmiş kod uzunluğu: {len(clean_code)} karakter")
        print(f"📤 Frontend'e gönderiliyor...\n")
        
        return jsonify({
            'code': clean_code,
            'success': True
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = str(e)
        
        # Rate limit hatası için özel mesaj
        if "rate limit" in error_msg.lower() or "429" in error_msg or "concurrency" in error_msg.lower():
            print(f"⚠️ Rate Limit Hatası: {error_msg}")
            return jsonify({
                'error': error_msg,
                'type': 'rate_limit',
                'suggestion': 'Lütfen 10-15 saniye bekleyip tekrar deneyin.'
            }), 429  # HTTP 429 döndür
        else:
            print(f"❌ Generate Error: {error_details}")
            return jsonify({
                'error': error_msg,
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
                'image': result  # Base64 PNG
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

@app.route('/api/improve', methods=['POST'])
def improve_code():
    """Orijinal görsel ve render edilmiş görseli karşılaştırarak kodu iyileştir"""
    try:
        data = request.json
        code = data.get('code', '')
        original_image = data.get('original_image', None)  # Orijinal görsel (base64)
        rendered_image = data.get('rendered_image', None)  # Render edilmiş görsel (base64)
        thinking_mode = data.get('thinking_mode', False)  # Frontend'den gelen thinking mode ayarı
        
        if not code:
            return jsonify({'error': 'Kod gereklidir'}), 400
        
        if not original_image or not rendered_image:
            return jsonify({'error': 'Orijinal ve render edilmiş görsel gereklidir'}), 400
        
        # İkinci API key için bekleme, ama başarısız olursa birinci API key kullanılacak
        wait_for_rate_limit(use_second_client=True)  # İkinci API key için özel bekleme
        
        # Görselleri encode et
        encoded_original = encode_image(original_image)
        encoded_rendered = encode_image(rendered_image)
        
        prompt = """Compare these two images:
1. The FIRST image is the ORIGINAL 3D object photo that we want to recreate
2. The SECOND image is the RENDERED result from the current OpenSCAD code

Analyze the differences between the original and the rendered result. Identify:
- Missing details or features
- Incorrect dimensions or proportions
- Wrong shapes or geometry
- Missing or incorrect transformations
- Any other discrepancies

Current OpenSCAD code:
```openscad
{code}
```

Based on this comparison, generate an IMPROVED OpenSCAD code that:
1. Better matches the original image
2. Fixes any discrepancies you identified
3. Maintains correct OpenSCAD syntax
4. Includes comments explaining improvements

**CRITICAL SYNTAX RULES:**
✓ All statements end with semicolon: `cube([10,20,30]);`
✓ Arrays use square brackets: `[x, y, z]`
✓ Boolean operations: `union() {{ shape1(); shape2(); }}`
✗ NO Python syntax (def, for i in range, etc.)

**OUTPUT:**
Return ONLY the improved OpenSCAD code, nothing else.
Do NOT include markdown fences (```) or explanations outside of code comments.
The code should be ready to use immediately.""".format(code=code)
        
        # Content oluştur: text + iki görsel
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_original}"
                }
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_rendered}"
                }
            }
        ]
        
        print(f"🔄 İyileştirme yapılıyor: Orijinal ve render edilmiş görsel karşılaştırılıyor...")
        
        # İyileştirme için ikinci client ve model kullan
        improve_model = model_name_second if model_name_second else model_name
        print(f"🤖 İyileştirme Model: {improve_model} (İkinci API key ile)")
        
        completion = api_call_with_retry(
            max_retries=3,
            use_second_client=True,  # İkinci API key'i kullan
            model=improve_model,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            thinking={
                "type": "enabled" if thinking_mode else "disabled"
            },
            temperature=0.3,
            max_tokens=4000,
        )
        
        if not completion or not completion.choices:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        message = completion.choices[0].message
        improved_code = message.content if hasattr(message, 'content') else None
        
        # API yanıtını terminalde göster
        print("\n" + "="*80)
        print("📥 İYİLEŞTİRME API YANITI:")
        print("="*80)
        if improved_code:
            print(f"📝 Content ({len(improved_code)} karakter):")
            print("-"*80)
            print(improved_code[:1000] + ("..." if len(improved_code) > 1000 else ""))
            print("-"*80)
        
        reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
        if reasoning:
            print(f"🧠 Reasoning Content ({len(reasoning)} karakter):")
            print("-"*80)
            print(reasoning[:1000] + ("..." if len(reasoning) > 1000 else ""))
            print("-"*80)
        print("="*80 + "\n")
        
        # Eğer content boşsa, reasoning_content'ten kod çıkarmayı dene
        if not improved_code or (isinstance(improved_code, str) and len(improved_code.strip()) == 0):
            if reasoning and len(reasoning) > 100:
                import re
                code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                if code_blocks:
                    improved_code = code_blocks[-1].strip()
                    print(f"✅ Reasoning content'ten kod çıkarıldı: {len(improved_code)} karakter")
        
        if not improved_code or (isinstance(improved_code, str) and len(improved_code.strip()) == 0):
            return jsonify({'error': 'İyileştirilmiş kod üretilemedi'}), 500
        
        improved_code = improved_code.strip()
        if improved_code.startswith("```"):
            improved_code = improved_code.split("```")[1]
            if improved_code.startswith("openscad"):
                improved_code = improved_code[8:]
            improved_code = improved_code.strip()
        
        print(f"✅ İyileştirilmiş kod üretildi: {len(improved_code)} karakter")
        print(f"📤 Frontend'e gönderiliyor...\n")
        
        return jsonify({
            'code': improved_code,
            'success': True
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Improve Error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details if app.debug else None
        }), 500

@app.route('/api/fix-with-images', methods=['POST'])
def fix_code_with_images():
    """Hata, görseller ve kod ile birlikte düzelt"""
    try:
        data = request.json
        code = data.get('code', '')
        error_message = data.get('error', '')
        original_image = data.get('original_image', None)
        rendered_image = data.get('rendered_image', None)
        thinking_mode = data.get('thinking_mode', False)  # Frontend'den gelen thinking mode ayarı
        
        if not code or not error_message:
            return jsonify({'error': 'Kod ve hata mesajı gereklidir'}), 400
        
        wait_for_rate_limit()
        
        # Content oluştur
        content = []
        
        # Prompt oluştur
        prompt = f"""You are debugging OpenSCAD code that failed to render. Analyze the error, compare with the original image, and fix the code.

**ERROR MESSAGE FROM OPENSCAD:**
```
{error_message}
```

**CURRENT CODE:**
```openscad
{code}
```

**YOUR TASK:**
1. Analyze the error message carefully
2. Compare the original image (if provided) with what the code should produce
3. Look at the rendered result (if provided) to see what went wrong
4. Identify the exact problem (syntax error, logic error, dimension mismatch, etc.)
5. Fix the code to match the original image and resolve the error
6. Return ONLY the corrected OpenSCAD code

**COMMON OPENSCAD ERRORS:**
- Missing semicolons: `cube([10,20,30])` should be `cube([10,20,30]);`
- Incorrect bracket matching: Check all `{{`, `}}`, `[`, `]`, `(`, `)`
- Wrong parameter syntax: `cube(10)` should be `cube([10,10,10])`
- Undefined variables or modules
- Invalid transformation syntax: `translate(x=10)` should be `translate([10,0,0])`
- For loops: `for i in range(5)` should be `for(i=[0:4])`
- Dimension mismatches with the original image

**CRITICAL RULES:**
✓ All statements MUST end with semicolon
✓ Arrays use square brackets: `[x, y, z]`
✓ Module calls: `module_name();`
✓ Boolean operations: `union() {{ shape1(); shape2(); }}`
✗ NO Python syntax (def, for i in range, etc.)
✗ NO undefined variables

**OUTPUT:**
Return ONLY the corrected OpenSCAD code in the 'content' field, nothing else.
Do NOT include markdown fences (```) or explanations.
The code should be ready to use immediately and match the original image."""
        
        content.append({"type": "text", "text": prompt})
        
        # Orijinal görsel varsa ekle
        if original_image:
            encoded_original = encode_image(original_image)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_original}"
                }
            })
            print("📷 Orijinal görsel eklendi")
        
        # Render edilmiş görsel varsa ekle (hata görseli)
        if rendered_image:
            encoded_rendered = encode_image(rendered_image)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_rendered}"
                }
            })
            print("📷 Render edilmiş görsel (hata) eklendi")
        
        print(f"🔧 Hata ile kod düzeltiliyor: {error_message[:100]}...")
        
        completion = api_call_with_retry(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            thinking={
                "type": "enabled" if thinking_mode else "disabled"
            },
            temperature=0.2,
            max_tokens=4000,
        )
        
        if not completion or not completion.choices:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        message = completion.choices[0].message
        fixed_code = message.content if hasattr(message, 'content') else None
        
        # API yanıtını terminalde göster
        print("\n" + "="*80)
        print("📥 DÜZELTME API YANITI (Görseller ile):")
        print("="*80)
        if fixed_code:
            print(f"📝 Content ({len(fixed_code)} karakter):")
            print("-"*80)
            print(fixed_code[:1000] + ("..." if len(fixed_code) > 1000 else ""))
            print("-"*80)
        
        reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
        if reasoning:
            print(f"🧠 Reasoning Content ({len(reasoning)} karakter):")
            print("-"*80)
            print(reasoning[:1000] + ("..." if len(reasoning) > 1000 else ""))
            print("-"*80)
        print("="*80 + "\n")
        
        # Eğer content boşsa, reasoning_content'ten kod çıkarmayı dene
        if not fixed_code or (isinstance(fixed_code, str) and len(fixed_code.strip()) == 0):
            if reasoning and len(reasoning) > 100:
                import re
                code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                if code_blocks:
                    potential_code = code_blocks[-1].strip()
                    # Gerçek kod olup olmadığını kontrol et
                    if any(keyword in potential_code.lower() for keyword in ['cube', 'cylinder', 'sphere', 'translate', 'rotate', 'union', 'difference', 'module']):
                        fixed_code = potential_code
                        print(f"✅ Reasoning content'ten kod çıkarıldı: {len(fixed_code)} karakter")
        
        if not fixed_code or (isinstance(fixed_code, str) and len(fixed_code.strip()) == 0):
            return jsonify({'error': 'Kod düzeltilemedi'}), 500
        
        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```"):
            fixed_code = fixed_code.split("```")[1]
            if fixed_code.startswith("openscad"):
                fixed_code = fixed_code[8:]
            fixed_code = fixed_code.strip()
        
        print(f"✅ Kod düzeltildi: {len(fixed_code)} karakter")
        print(f"📤 Frontend'e gönderiliyor...\n")
        
        return jsonify({
            'code': fixed_code,
            'success': True
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Fix With Images Error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details if app.debug else None
        }), 500

@app.route('/api/fix', methods=['POST'])
def fix_code():
    """Syntax hatasını düzelt"""
    try:
        data = request.json
        code = data.get('code', '')
        error_message = data.get('error', '')
        
        if not code or not error_message:
            return jsonify({'error': 'Kod ve hata mesajı gereklidir'}), 400
        
        wait_for_rate_limit()
        
        prompt = f"""You are debugging OpenSCAD code that failed to render.

**ORIGINAL CODE:**
```openscad
{code}
```

**ERROR MESSAGE FROM OPENSCAD:**
```
{error_message}
```

**YOUR TASK:**
1. Analyze the error message carefully
2. Identify the exact syntax problem
3. Fix ONLY the syntax error (don't change the logic unnecessarily)
4. Return the corrected code

**COMMON OPENSCAD ERRORS:**
- Missing semicolons: `cube([10,20,30])` should be `cube([10,20,30]);`
- Incorrect bracket matching: Check all `{{`, `}}`, `[`, `]`, `(`, `)`
- Wrong parameter syntax: `cube(10)` should be `cube([10,10,10])`
- Undefined variables or modules
- Invalid transformation syntax: `translate(x=10)` should be `translate([10,0,0])`
- For loops: `for i in range(5)` should be `for(i=[0:4])`

**CRITICAL RULES:**
✓ All statements MUST end with semicolon
✓ Arrays use square brackets: `[x, y, z]`
✓ Module calls: `module_name();`
✓ Boolean operations: `union() {{ shape1(); shape2(); }}`
✗ NO Python syntax (def, for i in range, etc.)
✗ NO undefined variables

**OUTPUT:**
Return ONLY the corrected OpenSCAD code, nothing else.
Do NOT include markdown fences (```) or explanations.
The code should be ready to use immediately.
"""
        
        completion = api_call_with_retry(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            thinking={
                "type": "disabled"  # Thinking mode kapalı
            },
            temperature=0.2,
            max_tokens=2000,
        )
        
        if not completion or not completion.choices:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        message = completion.choices[0].message
        fixed_code = message.content if hasattr(message, 'content') else None
        
        # API yanıtını terminalde göster
        print("\n" + "="*80)
        print("📥 DÜZELTME API YANITI (Sadece hata ile):")
        print("="*80)
        if fixed_code:
            print(f"📝 Content ({len(fixed_code)} karakter):")
            print("-"*80)
            print(fixed_code[:1000] + ("..." if len(fixed_code) > 1000 else ""))
            print("-"*80)
        print("="*80 + "\n")
        
        if not fixed_code:
            return jsonify({'error': 'Kod düzeltilemedi'}), 500
        
        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```"):
            fixed_code = fixed_code.split("```")[1]
            if fixed_code.startswith("openscad"):
                fixed_code = fixed_code[8:]
            fixed_code = fixed_code.strip()
        
        print(f"✅ Kod düzeltildi: {len(fixed_code)} karakter")
        print(f"📤 Frontend'e gönderiliyor...\n")
        
        return jsonify({
            'code': fixed_code,
            'success': True
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Fix Error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details if app.debug else None
        }), 500

if __name__ == '__main__':
    try:
        init_app()
        print(f"🚀 Backend API başlatılıyor...")
        print(f"📦 Model: {model_name}")
        if client_second:
            print(f"📦 İyileştirme Model: {model_name_second}")
        print(f"🔧 OpenSCAD: {'✅ Bulundu' if openscad_path else '❌ Bulunamadı'}")
        print(f"🌐 API: http://localhost:5000")
        print(f"🔑 Client: {'✅ Başlatıldı' if client else '❌ Başlatılamadı'}")
        print(f"🔑 İkinci Client: {'✅ Başlatıldı' if client_second else '❌ Kullanılmıyor'}")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        import traceback
        print(f"❌ Hata: {e}")
        print(traceback.format_exc())
