"""
Improved Backend API for OpenSCAD Code Generator
3 Yeni Özellik ile Geliştirilmiş Versiyon:
1. Syntax Validation & Pre-check
2. Few-Shot Learning
3. Self-Correction Loop
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
from zai import ZaiClient
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
CORS(app)

# Global değişkenler
client = None
client_second = None
openscad_path = None
model_name = None
model_name_second = None
last_api_call_time = 0
last_api_call_time_second = 0
min_api_interval = 1.0
min_api_interval_second = 2.0

# ============================================================================
# ÖZELLİK 1: SYNTAX VALIDATION & PRE-CHECK
# ============================================================================

class OpenSCADSyntaxChecker:
    """OpenSCAD syntax kontrolü ve otomatik düzeltme önerileri"""
    
    def __init__(self):
        self.error_patterns = {
            "missing_semicolon": {
                "pattern": r"(cube|cylinder|sphere|translate|rotate|scale|mirror|union|difference|intersection|hull|minkowski)\s*\([^)]*\)\s*(?!;|{|\n)",
                "fix": lambda m: m.group(0) + ";",
                "description": "Missing semicolon after statement"
            },
            "wrong_brackets": {
                "pattern": r"(cube|cylinder)\s*\(\s*(\d+(?:\.\d+)?)\s*(?:,\s*(\d+(?:\.\d+)?))?\s*(?:,\s*(\d+(?:\.\d+)?))?\s*\)",
                "fix": self._fix_wrong_brackets,
                "description": "Wrong parameter syntax (should use [x, y, z])"
            },
            "python_for": {
                "pattern": r"for\s+(\w+)\s+in\s+range\s*\(\s*(\d+)\s*\)",
                "fix": lambda m: f"for({m.group(1)}=[0:{int(m.group(2))-1}])",
                "description": "Python-style for loop detected"
            },
            "python_def": {
                "pattern": r"def\s+\w+\s*\(",
                "fix": lambda m: m.group(0).replace("def", "module"),
                "description": "Python 'def' instead of 'module'"
            },
            "wrong_translate": {
                "pattern": r"translate\s*\(\s*(x|y|z)\s*=\s*([^,)]+)",
                "fix": lambda m: f"translate([{m.group(2) if m.group(1)=='x' else '0'}, {m.group(2) if m.group(1)=='y' else '0'}, {m.group(2) if m.group(1)=='z' else '0'}])",
                "description": "Wrong translate syntax (should use [x, y, z])"
            }
        }
    
    def _fix_wrong_brackets(self, match):
        """cube(10) -> cube([10, 10, 10])"""
        func = match.group(1)
        params = [g for g in match.groups()[1:] if g]
        
        if len(params) == 1:
            val = params[0]
            return f"{func}([{val}, {val}, {val}])"
        elif len(params) == 2:
            return f"{func}([{params[0]}, {params[1]}, {params[1]}])"
        elif len(params) == 3:
            return f"{func}([{params[0]}, {params[1]}, {params[2]}])"
        else:
            return match.group(0)
    
    def check(self, code):
        """Kodda syntax hatalarını kontrol et"""
        errors = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Boş satırları atla
            if not line_stripped or line_stripped.startswith('//') or line_stripped.startswith('/*'):
                continue
            
            # Her hata tipini kontrol et
            for error_type, error_info in self.error_patterns.items():
                pattern = error_info["pattern"]
                matches = list(re.finditer(pattern, line, re.IGNORECASE))
                
                for match in matches:
                    errors.append({
                        "line": i,
                        "type": error_type,
                        "description": error_info["description"],
                        "code": line_stripped,
                        "match": match.group(0)
                    })
            
            # Semicolon kontrolü (daha detaylı)
            if re.search(r'(cube|cylinder|sphere|translate|rotate|scale)\s*\([^)]*\)', line, re.IGNORECASE):
                if not line_stripped.endswith(';') and not line_stripped.endswith('{') and not line_stripped.endswith('}'):
                    # Module tanımı değilse semicolon olmalı
                    if not re.search(r'module\s+\w+\s*\(', line, re.IGNORECASE):
                        errors.append({
                            "line": i,
                            "type": "missing_semicolon",
                            "description": "Missing semicolon after statement",
                            "code": line_stripped,
                            "match": line_stripped
                        })
        
        return errors
    
    def auto_fix_common_errors(self, code):
        """Yaygın hataları otomatik düzelt"""
        fixed_code = code
        
        # Her hata tipi için düzeltme yap
        for error_type, error_info in self.error_patterns.items():
            pattern = error_info["pattern"]
            fix_func = error_info["fix"]
            
            # Tüm eşleşmeleri bul ve düzelt
            matches = list(re.finditer(pattern, fixed_code, re.IGNORECASE))
            for match in reversed(matches):  # Ters sırada (pozisyon kaymasını önlemek için)
                fixed = fix_func(match)
                fixed_code = fixed_code[:match.start()] + fixed + fixed_code[match.end():]
        
        # Semicolon ekleme (basit durumlar için)
        lines = fixed_code.split('\n')
        fixed_lines = []
        for line in lines:
            line_stripped = line.strip()
            if (line_stripped and 
                not line_stripped.endswith(';') and 
                not line_stripped.endswith('{') and 
                not line_stripped.endswith('}') and
                not line_stripped.startswith('//') and
                not line_stripped.startswith('/*') and
                re.search(r'(cube|cylinder|sphere|translate|rotate|scale)\s*\([^)]*\)', line, re.IGNORECASE) and
                not re.search(r'module\s+\w+\s*\(', line, re.IGNORECASE)):
                fixed_lines.append(line.rstrip() + ';')
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def validate_before_generation(self, description):
        """Üretim öncesi açıklamada yaygın hataları tespit et"""
        warnings = []
        
        if "def " in description or "for i in range" in description:
            warnings.append({
                "type": "python_syntax",
                "message": "Python syntax detected in description. Model may generate incorrect code.",
                "suggestion": "Use OpenSCAD syntax: 'module' instead of 'def', 'for(i=[0:4])' instead of 'for i in range(5)'"
            })
        
        # Cube syntax kontrolü (daha güvenli)
        if "cube(" in description:
            try:
                cube_part = description.split("cube(")[1]
                if ")" in cube_part:
                    params = cube_part.split(")")[0]
                    if "[" not in params:
                        warnings.append({
                            "type": "wrong_syntax",
                            "message": "Possible wrong syntax in description (cube should use [x, y, z])",
                            "suggestion": "Use cube([10, 20, 30]) instead of cube(10, 20, 30)"
                        })
            except (IndexError, ValueError):
                pass  # Hata durumunda sessizce geç
        
        return warnings


# ============================================================================
# ÖZELLİK 2: FEW-SHOT LEARNING
# ============================================================================

class FewShotExamples:
    """Başarılı OpenSCAD kod örnekleri ve dinamik seçim"""
    
    def __init__(self):
        self.examples = [
            {
                "id": "simple_cube",
                "description": "Simple cube with dimensions",
                "image_type": "cube",
                "code": """// Simple cube example
cube([50, 30, 20]);
""",
                "success_rate": 0.98,
                "keywords": ["cube", "box", "rectangular", "simple"]
            },
            {
                "id": "rounded_box",
                "description": "Rounded box with corner radius",
                "image_type": "rounded_box",
                "code": """// Rounded box example
module rounded_box(size, radius) {
    hull() {
        for (x = [radius, size[0]-radius]) {
            for (y = [radius, size[1]-radius]) {
                translate([x, y, 0])
                    cylinder(h=size[2], r=radius);
            }
        }
    }
}
rounded_box([50, 30, 20], 5);
""",
                "success_rate": 0.95,
                "keywords": ["rounded", "box", "corner", "radius", "hull"]
            },
            {
                "id": "box_with_hole",
                "description": "Box with cylindrical hole",
                "image_type": "box_with_hole",
                "code": """// Box with hole example
difference() {
    cube([50, 30, 20]);
    translate([25, 15, -1])
        cylinder(h=22, r=5);
}
""",
                "success_rate": 0.96,
                "keywords": ["hole", "difference", "cylinder", "through"]
            },
            {
                "id": "cylinder",
                "description": "Simple cylinder",
                "image_type": "cylinder",
                "code": """// Simple cylinder example
cylinder(h=30, r=10);
""",
                "success_rate": 0.99,
                "keywords": ["cylinder", "tube", "round", "circular"]
            },
            {
                "id": "complex_union",
                "description": "Multiple shapes combined with union",
                "image_type": "complex",
                "code": """// Complex shape with union
union() {
    cube([40, 40, 10]);
    translate([20, 20, 10])
        cylinder(h=20, r=8);
    translate([20, 20, 30])
        sphere(r=10);
}
""",
                "success_rate": 0.92,
                "keywords": ["union", "multiple", "combined", "complex", "sphere"]
            }
        ]
    
    def select_relevant_examples(self, description, image_type=None, top_k=3):
        """Açıklamaya ve görsel tipine göre en uygun örnekleri seç"""
        description_lower = description.lower()
        
        scored_examples = []
        for ex in self.examples:
            score = 0.0
            
            # Keyword eşleşmesi
            for keyword in ex["keywords"]:
                if keyword in description_lower:
                    score += 1.0
            
            # Görsel tipi eşleşmesi
            if image_type and ex["image_type"] == image_type:
                score += 2.0
            
            # Başarı oranı
            score += ex["success_rate"] * 0.5
            
            scored_examples.append((score, ex))
        
        # En yüksek skorlu örnekleri döndür
        sorted_examples = sorted(scored_examples, key=lambda x: x[0], reverse=True)
        return [ex for score, ex in sorted_examples[:top_k]]
    
    def format_examples_for_prompt(self, examples):
        """Örnekleri prompt formatına çevir"""
        if not examples:
            return ""
        
        formatted = "\n**SUCCESSFUL EXAMPLES (Follow this style and structure):**\n\n"
        
        for i, ex in enumerate(examples, 1):
            formatted += f"""**Example {i}:**
Description: {ex['description']}
Code:
```openscad
{ex['code']}
```

"""
        
        formatted += "**IMPORTANT:** Generate code following the same style, structure, and syntax as the examples above.\n"
        
        return formatted


# ============================================================================
# ÖZELLİK 3: SELF-CORRECTION LOOP
# ============================================================================

class SelfCorrectionLoop:
    """Modelin kendi kodunu gözden geçirip düzeltmesi"""
    
    def __init__(self, api_client, model_name, syntax_checker):
        self.api_client = api_client
        self.model_name = model_name
        self.syntax_checker = syntax_checker
    
    def self_review(self, code, original_prompt, max_iterations=3):
        """Kodu iteratif olarak gözden geçir ve düzelt"""
        current_code = code
        iteration = 0
        syntax_errors = []  # Başlangıç değeri
        
        while iteration < max_iterations:
            iteration += 1
            print(f"🔄 Self-correction iteration {iteration}/{max_iterations}")
            
            # 1. Syntax kontrolü
            syntax_errors = self.syntax_checker.check(current_code)
            if not syntax_errors:
                print(f"✅ No syntax errors found after {iteration} iterations")
                return current_code, {"iterations": iteration, "fixed": True}
            
            # 2. Self-review prompt
            review_prompt = self._build_review_prompt(current_code, original_prompt, syntax_errors)
            
            # 3. API çağrısı ile düzeltme
            try:
                corrected_code = self._call_api_for_correction(review_prompt)
                if corrected_code and corrected_code != current_code:
                    current_code = corrected_code
                    print(f"✅ Code corrected in iteration {iteration}")
                else:
                    # Otomatik düzeltme dene
                    current_code = self.syntax_checker.auto_fix_common_errors(current_code)
                    print(f"✅ Auto-fix applied in iteration {iteration}")
            except Exception as e:
                print(f"⚠️ API correction failed: {e}, using auto-fix")
                current_code = self.syntax_checker.auto_fix_common_errors(current_code)
            
            # 4. Tekrar syntax kontrolü
            syntax_errors = self.syntax_checker.check(current_code)
            if not syntax_errors:
                print(f"✅ All errors fixed after {iteration} iterations")
                return current_code, {"iterations": iteration, "fixed": True}
        
        # Maksimum iterasyon sayısına ulaşıldı
        # syntax_errors burada zaten tanımlı (while loop'tan sonra)
        return current_code, {"iterations": iteration, "fixed": len(syntax_errors) == 0, "remaining_errors": len(syntax_errors)}
    
    def _build_review_prompt(self, code, original_prompt, syntax_errors):
        """Self-review için prompt oluştur"""
        errors_summary = "\n".join([
            f"Line {e['line']}: {e['description']} - {e['match']}"
            for e in syntax_errors[:10]  # İlk 10 hatayı göster
        ])
        
        prompt = f"""You just generated this OpenSCAD code:
```openscad
{code}
```

Original request: {original_prompt}

**SYNTAX ERRORS DETECTED:**
{errors_summary}

**YOUR TASK:**
1. Review the code carefully
2. Fix ALL syntax errors listed above
3. Ensure the code matches the original request
4. Check for common mistakes (missing semicolons, wrong brackets, etc.)
5. Return ONLY the corrected OpenSCAD code

**CRITICAL RULES:**
✓ All statements MUST end with semicolon: `cube([10,20,30]);`
✓ Arrays use square brackets: `[x, y, z]`
✓ Module calls: `module_name();`
✓ Boolean operations: `union() {{ shape1(); shape2(); }}`
✗ NO Python syntax (def, for i in range, etc.)
✗ NO undefined variables

**OUTPUT:**
Return ONLY the corrected OpenSCAD code, nothing else.
Do NOT include markdown fences (```) or explanations.
"""
        return prompt
    
    def _call_api_for_correction(self, prompt):
        """API çağrısı ile kod düzeltme"""
        global last_api_call_time, min_api_interval
        
        # Rate limiting
        current_time = time.time()
        time_since_last_call = current_time - last_api_call_time
        if time_since_last_call < min_api_interval:
            time.sleep(min_api_interval - time_since_last_call)
        last_api_call_time = time.time()
        
        try:
            completion = self.api_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                thinking={"type": "disabled"},  # Hızlı düzeltme için thinking kapalı
                temperature=0.1,  # Çok düşük - deterministik düzeltme
                max_tokens=4000,
            )
            
            if completion and completion.choices:
                corrected_code = completion.choices[0].message.content
                
                # Markdown temizle
                if corrected_code:
                    corrected_code = corrected_code.strip()
                    if corrected_code.startswith("```"):
                        corrected_code = corrected_code.split("```")[1]
                        if corrected_code.startswith("openscad"):
                            corrected_code = corrected_code[8:]
                        corrected_code = corrected_code.strip()
                
                return corrected_code
        except Exception as e:
            print(f"❌ API correction error: {e}")
            return None


# ============================================================================
# MEVCUT FONKSİYONLAR (backend_api.py'den)
# ============================================================================

def init_app():
    """Uygulamayı başlat"""
    global client, client_second, openscad_path, model_name, model_name_second
    
    token = os.getenv('NEW_KEY') or os.getenv('ZAI_API_KEY') or os.getenv('HF_TOKEN')
    if not token:
        raise Exception("API key bulunamadı! .env dosyasına NEW_KEY veya ZAI_API_KEY ekleyin.")
    
    client = ZaiClient(api_key=token)
    
    model_env = os.getenv('MODEL_NAME', 'zai-org/GLM-4.6V-Flash')
    if 'GLM-4.6V-Flash' in model_env or 'glm-4.6v-flash' in model_env.lower():
        model_name = 'glm-4.6v-flash'
    elif 'GLM-4.6V' in model_env or 'glm-4.6v' in model_env.lower():
        model_name = 'glm-4.6v'
    elif 'GLM-4.7' in model_env or 'glm-4.7' in model_env.lower():
        model_name = 'glm-4.7'
    else:
        model_name = 'glm-4.6v-flash'
        print(f"⚠️ Model adı '{model_env}' tanınmadı, varsayılan 'glm-4.6v-flash' kullanılıyor.")
    
    print(f"✅ ZAI SDK başlatıldı")
    print(f"✅ Model: {model_name}")
    
    second_token = os.getenv('SECOND_API_KEY')
    if second_token:
        client_second = ZaiClient(api_key=second_token)
        model_env_2 = os.getenv('MODEL_NAME_2', '').strip()
        if model_env_2:
            if 'GLM-4.6V-Flash' in model_env_2 or 'glm-4.6v-flash' in model_env_2.lower():
                model_name_second = 'glm-4.6v-flash'
            elif 'GLM-4.6V' in model_env_2 or 'glm-4.6v' in model_env_2.lower():
                model_name_second = 'glm-4.6v'
            elif 'GLM-4.7' in model_env_2 or 'glm-4.7' in model_env_2.lower():
                model_name_second = 'glm-4.7'
            else:
                model_name_second = 'glm-4.6v'
        else:
            model_name_second = 'glm-4.6v'
        print(f"✅ İkinci Model: {model_name_second}")
    else:
        client_second = None
        model_name_second = model_name
    
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

def wait_for_rate_limit(use_second_client=False):
    """API çağrıları arasında minimum bekleme süresi"""
    global last_api_call_time, last_api_call_time_second
    
    if use_second_client and client_second:
        current_time = time.time()
        time_since_last_call = current_time - last_api_call_time_second
        if time_since_last_call < min_api_interval_second:
            wait_time = min_api_interval_second - time_since_last_call
            time.sleep(wait_time)
        last_api_call_time_second = time.time()
    else:
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
    active_client = client_second if (use_second_client and client_second) else client
    
    if not active_client:
        raise Exception("API client başlatılmamış. Token kontrol edin.")
    
    base_wait_time = 3  # Varsayılan değer
    if use_second_client and client_second:
        max_retries = 1
        print(f"🔑 İkinci API key kullanılıyor")
    
    for attempt in range(max_retries):
        try:
            completion = active_client.chat.completions.create(**kwargs)
            # Type check: completion'un choices attribute'u var mı kontrol et
            if not completion:
                raise Exception("API yanıtı alınamadı")
            if not hasattr(completion, 'choices'):
                raise Exception("API yanıtı beklenen biçimde değil (choices yok)")
            if not completion.choices:  # type: ignore
                raise Exception("API yanıtı beklenen biçimde değil (choices boş)")
            return completion
        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__
            
            if use_second_client and client_second:
                print(f"❌ İkinci API key ile hata: {error_str}")
                if client:
                    try:
                        original_model = kwargs.get('model', model_name)
                        if original_model == model_name_second:
                            kwargs['model'] = model_name
                        completion = client.chat.completions.create(**kwargs)
                        if completion and hasattr(completion, 'choices') and getattr(completion, 'choices', None):
                            return completion
                    except Exception as e2:
                        raise e
                raise
            
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
                    wait_time = (2 ** attempt) * base_wait_time
                    print(f"⏳ Rate limit - {wait_time} saniye bekleniyor (Deneme {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitException(
                        f"Rate limit hatası: API şu anda çok yoğun. "
                        f"{max_retries} deneme yapıldı ancak başarısız oldu."
                    )
            else:
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
# GLOBAL INSTANCES (Yeni özellikler için)
# ============================================================================

syntax_checker = None
few_shot_examples = None
self_correction = None

def init_improvements():
    """Yeni özellikleri başlat"""
    global syntax_checker, few_shot_examples, self_correction
    
    syntax_checker = OpenSCADSyntaxChecker()
    few_shot_examples = FewShotExamples()
    
    if client and model_name:
        self_correction = SelfCorrectionLoop(client, model_name, syntax_checker)
    
    print("✅ Syntax Checker initialized")
    print("✅ Few-Shot Examples initialized")
    print("✅ Self-Correction Loop initialized")


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
        'improvements': {
            'syntax_checker': syntax_checker is not None,
            'few_shot': few_shot_examples is not None,
            'self_correction': self_correction is not None
        }
    })

@app.route('/api/generate', methods=['POST'])
def generate_code():
    """OpenSCAD kodu üret (3 yeni özellik ile)"""
    try:
        print("📥 /api/generate isteği alındı (IMPROVED VERSION)")
        
        if not request.json:
            return jsonify({'error': 'JSON verisi gereklidir'}), 400
        
        data = request.json
        image_base64 = data.get('image', None)
        text_description = data.get('description', '')
        additional_instruction = data.get('instruction', '')
        thinking_mode = data.get('thinking_mode', False)
        enable_self_correction = data.get('enable_self_correction', True)  # Varsayılan: açık
        enable_few_shot = data.get('enable_few_shot', True)  # Varsayılan: açık
        
        print(f"📊 Özellikler: Self-Correction={enable_self_correction}, Few-Shot={enable_few_shot}")
        
        if not image_base64 and not text_description:
            return jsonify({'error': 'Görsel veya metin açıklaması gereklidir'}), 400
        
        if not client:
            return jsonify({'error': 'API client başlatılmamış'}), 500
        
        # ÖZELLİK 1: Pre-generation validation
        if syntax_checker:
            warnings = syntax_checker.validate_before_generation(text_description + " " + additional_instruction)
            if warnings:
                print(f"⚠️ Pre-generation warnings: {warnings}")
        
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
        
        # ÖZELLİK 2: Few-Shot Examples ekle
        if enable_few_shot and few_shot_examples:
            examples = few_shot_examples.select_relevant_examples(
                text_description + " " + additional_instruction,
                top_k=3
            )
            examples_text = few_shot_examples.format_examples_for_prompt(examples)
            user_prompt_parts.append(examples_text)
        
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
        
        final_prompt = system_instruction + "".join(user_prompt_parts)
        
        content = [{"type": "text", "text": final_prompt}]
        
        if image_base64:
            encoded_image = encode_image(image_base64)
            content.append({  # type: ignore
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                }
            })
        
        print(f"🤖 Model: {model_name}, API çağrısı yapılıyor...")
        
        if not model_name:
            return jsonify({'error': 'Model adı belirlenmemiş'}), 500
        
        completion = client.chat.completions.create(
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
        
        if not completion:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        if not hasattr(completion, 'choices'):
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices yok)'}), 500
        
        choices = getattr(completion, 'choices', None)
        if not choices:
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices boş)'}), 500
        
        message = choices[0].message
        answer = message.content if hasattr(message, 'content') else None
        
        # Reasoning content kontrolü (thinking mode için)
        if not answer or (isinstance(answer, str) and len(answer.strip()) == 0):
            reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
            if reasoning and len(reasoning) > 100:
                import re
                code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                if code_blocks:
                    answer = code_blocks[-1].strip()
        
        if not answer or (isinstance(answer, str) and len(answer.strip()) == 0):
            return jsonify({
                'error': 'OpenSCAD kodu üretilemedi - API yanıtı boş',
                'suggestion': 'Thinking mode kapatılabilir veya model farklı bir formatta yanıt veriyor olabilir.'
            }), 500
        
        # Markdown temizle
        clean_code = answer.strip()
        if clean_code.startswith("```openscad") or clean_code.startswith("```"):
            clean_code = clean_code.split("```")[1]
            if clean_code.startswith("openscad"):
                clean_code = clean_code[8:]
            clean_code = clean_code.strip()
        
        # ÖZELLİK 1: Syntax validation
        syntax_errors = []
        if syntax_checker:
            syntax_errors = syntax_checker.check(clean_code)
            if syntax_errors:
                print(f"⚠️ {len(syntax_errors)} syntax errors detected")
                # Otomatik düzeltme dene
                clean_code = syntax_checker.auto_fix_common_errors(clean_code)
                # Tekrar kontrol et
                syntax_errors = syntax_checker.check(clean_code)
        
        # ÖZELLİK 3: Self-Correction Loop
        correction_info = None
        if enable_self_correction and self_correction and syntax_errors:
            print(f"🔄 Self-correction başlatılıyor...")
            original_prompt = text_description + " " + additional_instruction
            clean_code, correction_info = self_correction.self_review(
                clean_code,
                original_prompt,
                max_iterations=3
            )
            print(f"✅ Self-correction tamamlandı: {correction_info}")
        
        print(f"✅ Final kod uzunluğu: {len(clean_code)} karakter")
        if syntax_errors:
            print(f"⚠️ Kalan syntax hataları: {len(syntax_errors)}")
        
        return jsonify({
            'code': clean_code,
            'success': True,
            'improvements': {
                'syntax_errors_found': len(syntax_errors) if syntax_checker else 0,
                'syntax_errors_fixed': correction_info.get('fixed', False) if correction_info else False,
                'self_correction_iterations': correction_info.get('iterations', 0) if correction_info else 0,
                'few_shot_examples_used': enable_few_shot
            }
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

@app.route('/api/improve', methods=['POST'])
def improve_code():
    """Orijinal görsel ve render edilmiş görseli karşılaştırarak kodu iyileştir"""
    try:
        data = request.json
        code = data.get('code', '')
        original_image = data.get('original_image', None)
        rendered_image = data.get('rendered_image', None)
        thinking_mode = data.get('thinking_mode', False)
        
        if not code:
            return jsonify({'error': 'Kod gereklidir'}), 400
        
        if not original_image or not rendered_image:
            return jsonify({'error': 'Orijinal ve render edilmiş görsel gereklidir'}), 400
        
        wait_for_rate_limit(use_second_client=True)
        
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
        
        improve_model = model_name_second if model_name_second else model_name
        print(f"🤖 İyileştirme Model: {improve_model}")
        
        completion = api_call_with_retry(
            max_retries=3,
            use_second_client=True,
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
        
        if not completion:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        if not hasattr(completion, 'choices'):
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices yok)'}), 500
        
        choices = getattr(completion, 'choices', None)
        if not choices:
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices boş)'}), 500
        
        message = choices[0].message
        improved_code = message.content if hasattr(message, 'content') else None
        
        # Reasoning content kontrolü
        if not improved_code or (isinstance(improved_code, str) and len(improved_code.strip()) == 0):
            reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
            if reasoning and len(reasoning) > 100:
                import re
                code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                if code_blocks:
                    improved_code = code_blocks[-1].strip()
        
        if not improved_code or (isinstance(improved_code, str) and len(improved_code.strip()) == 0):
            return jsonify({'error': 'İyileştirilmiş kod üretilemedi'}), 500
        
        improved_code = improved_code.strip()
        if improved_code.startswith("```"):
            improved_code = improved_code.split("```")[1]
            if improved_code.startswith("openscad"):
                improved_code = improved_code[8:]
            improved_code = improved_code.strip()
        
        print(f"✅ İyileştirilmiş kod üretildi: {len(improved_code)} karakter")
        
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
        thinking_mode = data.get('thinking_mode', False)
        
        if not code or not error_message:
            return jsonify({'error': 'Kod ve hata mesajı gereklidir'}), 400
        
        wait_for_rate_limit()
        
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
        
        content = [{"type": "text", "text": prompt}]
        
        if original_image:
            encoded_original = encode_image(original_image)
            image_item: dict = {  # type: ignore
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_original}"
                }
            }
            content.append(image_item)  # type: ignore
        
        if rendered_image:
            encoded_rendered = encode_image(rendered_image)
            image_item: dict = {  # type: ignore
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_rendered}"
                }
            }
            content.append(image_item)  # type: ignore
        
        print(f"🔧 Hata ile kod düzeltiliyor: {error_message[:100]}...")
        
        if not model_name:
            return jsonify({'error': 'Model adı belirlenmemiş'}), 500
        
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
        
        if not completion:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        if not hasattr(completion, 'choices'):
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices yok)'}), 500
        
        choices = getattr(completion, 'choices', None)
        if not choices:
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices boş)'}), 500
        
        message = choices[0].message
        fixed_code = message.content if hasattr(message, 'content') else None
        
        # Reasoning content kontrolü
        if not fixed_code or (isinstance(fixed_code, str) and len(fixed_code.strip()) == 0):
            reasoning = message.reasoning_content if hasattr(message, 'reasoning_content') else None
            if reasoning and len(reasoning) > 100:
                import re
                code_blocks = re.findall(r'```(?:openscad)?\s*\n(.*?)\n```', reasoning, re.DOTALL)
                if code_blocks:
                    potential_code = code_blocks[-1].strip()
                    if any(keyword in potential_code.lower() for keyword in ['cube', 'cylinder', 'sphere', 'translate', 'rotate', 'union', 'difference', 'module']):
                        fixed_code = potential_code
        
        if not fixed_code or (isinstance(fixed_code, str) and len(fixed_code.strip()) == 0):
            return jsonify({'error': 'Kod düzeltilemedi'}), 500
        
        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```"):
            fixed_code = fixed_code.split("```")[1]
            if fixed_code.startswith("openscad"):
                fixed_code = fixed_code[8:]
            fixed_code = fixed_code.strip()
        
        print(f"✅ Kod düzeltildi: {len(fixed_code)} karakter")
        
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
        
        if not model_name:
            return jsonify({'error': 'Model adı belirlenmemiş'}), 500
        
        completion = api_call_with_retry(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            thinking={
                "type": "disabled"
            },
            temperature=0.2,
            max_tokens=2000,
        )
        
        if not completion:
            return jsonify({'error': 'API yanıtı alınamadı'}), 500
        
        if not hasattr(completion, 'choices'):
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices yok)'}), 500
        
        choices = getattr(completion, 'choices', None)
        if not choices:
            return jsonify({'error': 'API yanıtı beklenen biçimde değil (choices boş)'}), 500
        
        message = choices[0].message
        fixed_code = message.content if hasattr(message, 'content') else None
        
        if not fixed_code:
            return jsonify({'error': 'Kod düzeltilemedi'}), 500
        
        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```"):
            fixed_code = fixed_code.split("```")[1]
            if fixed_code.startswith("openscad"):
                fixed_code = fixed_code[8:]
            fixed_code = fixed_code.strip()
        
        print(f"✅ Kod düzeltildi: {len(fixed_code)} karakter")
        
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
        init_improvements()
        print(f"🚀 Improved Backend API başlatılıyor...")
        print(f"📦 Model: {model_name}")
        print(f"🔧 OpenSCAD: {'✅ Bulundu' if openscad_path else '❌ Bulunamadı'}")
        print(f"🌐 API: http://localhost:5001")
        print(f"✨ Yeni Özellikler: Syntax Checker, Few-Shot Learning, Self-Correction")
        app.run(debug=True, host='0.0.0.0', port=5001)  # Farklı port (5001)
    except Exception as e:
        import traceback
        print(f"❌ Hata: {e}")
        print(traceback.format_exc())
