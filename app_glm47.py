import os
import base64
import subprocess
import tempfile
import shutil
import time
from io import BytesIO
from openai import OpenAI
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from PIL import Image, ImageTk
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class VisionQAApp:
    def __init__(self, root):
        self.root = root
        self.root.title("3D Obje → OpenSCAD Kodu Üretici (GLM-4.6V-Flash)")
        self.root.geometry("900x900")
        self.root.configure(bg="#f0f0f0")
        
        self.image_path = None
        self.client = None
        self.rendered_image_path = None
        self.openscad_path = self.find_openscad()
        
        # Model adını .env'den oku, yoksa varsayılan kullan
        self.model_name = os.getenv('MODEL_NAME', 'zai-org/GLM-4.6V-Flash')
        
        # Rate limiting için son API çağrısı zamanı
        self.last_api_call_time = 0
        self.min_api_interval = 1.0  # API çağrıları arası minimum 1 saniye bekle
        
        # Token'ı .env dosyasından yükle
        self.load_token()
        
        # Fotoğraf Yükleme
        upload_frame = tk.Frame(root, bg="#f0f0f0")
        upload_frame.pack(pady=10)
        
        tk.Button(upload_frame, text="📷 Fotoğraf Yükle", command=self.upload_image, bg="#2196F3", fg="white", font=("Arial", 11, "bold"), width=20).pack()
        
        # Fotoğraf Önizleme
        self.preview_label = tk.Label(root, text="Fotoğraf yüklenmedi", bg="#e0e0e0", width=60, height=12)
        self.preview_label.pack(pady=10)
        
        # Metin Açıklaması Girişi
        text_input_frame = tk.Frame(root, bg="#f0f0f0")
        text_input_frame.pack(pady=10, padx=20, fill="both", expand=False)
        
        tk.Label(text_input_frame, text="Metin Açıklaması (Opsiyonel - Syntax hatalarını önlemek için detaylı açıklama yazın):", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        self.text_input = scrolledtext.ScrolledText(text_input_frame, width=80, height=5, font=("Arial", 10), wrap=tk.WORD)
        self.text_input.pack(fill="x", pady=5)
        self.text_input.insert(1.0, "Bu 3D objenin OpenSCAD kodunu üret. Boyutlar, şekiller ve detaylar hakkında açıklama yapabilirsiniz.")
        
        # Talimat Girişi
        question_frame = tk.Frame(root, bg="#f0f0f0")
        question_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(question_frame, text="Ek Talimat (Opsiyonel):", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        self.question_entry = tk.Entry(question_frame, width=80, font=("Arial", 10))
        self.question_entry.pack(fill="x", pady=5)
        
        # OpenSCAD Kodu Üret Butonu
        tk.Button(root, text="⚙️ OpenSCAD Kodu Üret", command=self.analyze_image, bg="#FF9800", fg="white", font=("Arial", 12, "bold"), width=25, height=2).pack(pady=10)
        
        # Cevap Alanı - İki sütunlu düzen
        answer_frame = tk.Frame(root, bg="#f0f0f0")
        answer_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        answer_header = tk.Frame(answer_frame, bg="#f0f0f0")
        answer_header.pack(fill="x")
        tk.Label(answer_header, text="OpenSCAD Kodu:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(answer_header, text="📋 Kopyala", command=self.copy_code, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side="right", padx=5)
        tk.Button(answer_header, text="🖼️ Render Et", command=self.render_openscad, bg="#9C27B0", fg="white", font=("Arial", 9, "bold")).pack(side="right", padx=5)
        tk.Button(answer_header, text="🔧 Otomatik Düzelt", command=self.auto_fix_code, bg="#FF5722", fg="white", font=("Arial", 9, "bold")).pack(side="right", padx=5)
        tk.Button(answer_header, text="🔍 Prompt Görüntüle", command=self.show_prompt_debug, bg="#607D8B", fg="white", font=("Arial", 8, "bold")).pack(side="right", padx=5)
        
        # İki sütunlu düzen: Kod ve Render
        content_frame = tk.Frame(answer_frame, bg="#f0f0f0")
        content_frame.pack(fill="both", expand=True)
        
        # Sol sütun: Kod
        code_frame = tk.Frame(content_frame, bg="#f0f0f0")
        code_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.answer_text = scrolledtext.ScrolledText(code_frame, width=45, height=12, font=("Courier", 10), wrap=tk.WORD)
        self.answer_text.pack(fill="both", expand=True)
        
        # Sağ sütun: Render görseli
        render_frame = tk.Frame(content_frame, bg="#f0f0f0")
        render_frame.pack(side="right", fill="both", expand=False, padx=(5, 0))
        
        # Render başlık ve buton
        render_header = tk.Frame(render_frame, bg="#f0f0f0")
        render_header.pack(fill="x")
        tk.Label(render_header, text="Render Önizleme:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(side="left")
        self.improve_button = tk.Button(render_header, text="🔄 İyileştir", command=self.improve_with_comparison, bg="#E91E63", fg="white", font=("Arial", 8, "bold"), state="disabled")
        self.improve_button.pack(side="right", padx=2)
        tk.Button(render_header, text="🗑️ Temizle", command=self.clear_render, bg="#757575", fg="white", font=("Arial", 8, "bold")).pack(side="right", padx=2)
        
        self.render_label = tk.Label(render_frame, text="Render edilmedi", bg="#e0e0e0", width=35, height=15, relief=tk.SUNKEN)
        self.render_label.pack(fill="both", expand=True, pady=5)
        
    def find_openscad(self):
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
    
    def load_token(self):
        """Token'ı .env dosyasından yükler"""
        token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_TOKEN')
        
        if not token:
            messagebox.showerror(
                "Hata", 
                "Token bulunamadı!\n\nLütfen .env dosyasına şunu ekleyin:\nHF_TOKEN=your_token_here"
            )
            return
        
        try:
            self.client = OpenAI(
                base_url="https://router.huggingface.co/v1",
                api_key=token
            )
        except Exception as e:
            messagebox.showerror("Hata", f"Token yüklenemedi: {str(e)}")
    
    def upload_image(self):
        file_path = filedialog.askopenfilename(
            title="Fotoğraf Seçin",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp")]
        )
        
        if file_path:
            self.image_path = file_path
            self.show_preview(file_path)
    
    def show_preview(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((400, 300))
            photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo  # type: ignore
        except Exception as e:
            messagebox.showerror("Hata", f"Fotoğraf yüklenemedi: {str(e)}")
    
    def encode_image(self, image_path):
        """Görseli optimize edip base64'e çevirir"""
        img = Image.open(image_path)
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
    
    def copy_code(self):
        """OpenSCAD kodunu panoya kopyalar"""
        code = self.answer_text.get(1.0, tk.END).strip()
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            messagebox.showinfo("Başarılı", "Kod panoya kopyalandı!")
        else:
            messagebox.showwarning("Uyarı", "Kopyalanacak kod yok!")
    
    def clear_render(self):
        """Render alanını temizler"""
        self.render_label.configure(image="", text="Render edilmedi")
        self.render_label.image = None  # type: ignore
        self.rendered_image_path = None
        self.improve_button.configure(state="disabled")
    
    def _wait_for_rate_limit(self):
        """API çağrıları arasında minimum bekleme süresi"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call_time
        
        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            time.sleep(wait_time)
        
        self.last_api_call_time = time.time()
    
    def _api_call_with_retry(self, max_retries=3, **kwargs):
        """Rate limiting için retry mekanizması ile API çağrısı"""
        for attempt in range(max_retries):
            try:
                # API çağrısı - self.client ve ilgili metotların mevcut olup olmadığını kontrol et
                if self.client and hasattr(self.client, "chat") and hasattr(self.client.chat, "completions") and hasattr(self.client.chat.completions, "create"):
                    completion = self.client.chat.completions.create(**kwargs)
                    # Yanıtın doğru yapıda olduğunu doğrula
                    if (not hasattr(completion, "choices") or
                        not completion.choices or
                        not hasattr(completion.choices[0], "message") or
                        not hasattr(completion.choices[0].message, "content")):
                        raise Exception("API yanıtı beklenen biçimde değil.")
                    return completion
                else:
                    raise Exception("API istemcisi veya chat.completions.create metodu başlatılmamış.")
            except Exception as e:
                error_str = str(e)
                # 429 hatası (Rate Limit) kontrolü
                if "429" in error_str or "rate limit" in error_str.lower() or "concurrency" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt saniye bekle
                        wait_time = (2 ** attempt) * 2  # 2, 4, 8 saniye
                        self.answer_text.insert(tk.END, f"\n\n⚠️ Rate limit aşıldı, {wait_time} saniye bekleniyor... (Deneme {attempt + 1}/{max_retries})\n")
                        self.root.update()
                        time.sleep(wait_time)
                        continue
                    else:
                        # Son deneme de başarısız
                        raise Exception(f"Rate limit hatası: API'ye çok fazla istek gönderildi. Lütfen birkaç saniye bekleyip tekrar deneyin.\n\nHata: {error_str}")
                else:
                    # 429 dışındaki hatalar için direkt fırlat
                    raise
    
    def render_openscad(self):
        """OpenSCAD kodunu render eder ve görseli gösterir"""
        code = self.answer_text.get(1.0, tk.END).strip()
        if not code:
            messagebox.showwarning("Uyarı", "Render edilecek kod yok!")
            return
        
        if not self.openscad_path:
            messagebox.showerror(
                "Hata",
                "OpenSCAD bulunamadı!\n\n"
                "Lütfen OpenSCAD'ı yükleyin:\n"
                "https://openscad.org/downloads.html\n\n"
                "Veya PATH'e ekleyin."
            )
            return
        
        try:
            self.render_label.configure(text="Render ediliyor...")
            self.root.update()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scad', delete=False, encoding='utf-8') as scad_file:
                scad_file.write(code)
                scad_path = scad_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as png_file:
                png_path = png_file.name
            
            cmd = [
                self.openscad_path,
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
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Bilinmeyen hata"
                if "ERROR" in error_msg:
                    lines = error_msg.split('\n')
                    error_lines = [line for line in lines if 'ERROR' in line or 'WARNING' in line]
                    if error_lines:
                        error_msg = '\n'.join(error_lines[:5])
                
                self.render_label.configure(text="Hata tespit edildi, düzeltiliyor...")
                self.root.update()
                
                fixed_code = self.fix_syntax_error(code, error_msg)
                if fixed_code and fixed_code != code:
                    self.answer_text.delete(1.0, tk.END)
                    self.answer_text.insert(tk.END, fixed_code)
                    self.root.update()
                    self.root.after(500, self.render_openscad)
                    return
                else:
                    messagebox.showerror("Render Hatası", f"OpenSCAD render hatası:\n\n{error_msg}\n\nOtomatik düzeltme başarısız oldu.")
                    self.clear_render()
                    self.render_label.configure(text="Render hatası")
                    return
            
            if os.path.exists(png_path):
                self.rendered_image_path = png_path
                self.show_render(png_path)
            else:
                messagebox.showerror("Hata", "Render edilmiş görsel bulunamadı!")
                self.clear_render()
                self.render_label.configure(text="Render hatası")
            
            try:
                os.unlink(scad_path)
            except:
                pass
                
        except subprocess.TimeoutExpired:
            messagebox.showerror("Hata", "Render işlemi zaman aşımına uğradı (30 saniye)")
            self.clear_render()
            self.render_label.configure(text="Zaman aşımı")
        except Exception as e:
            messagebox.showerror("Hata", f"Render hatası: {str(e)}")
            self.clear_render()
            self.render_label.configure(text="Render hatası")
    
    def show_render(self, path):
        """Render edilmiş görseli gösterir"""
        try:
            img = Image.open(path)
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.render_label.configure(image=photo, text="")
            self.render_label.image = photo  # type: ignore
            if self.image_path:
                self.improve_button.configure(state="normal")
        except Exception as e:
            messagebox.showerror("Hata", f"Görsel gösterilemedi: {str(e)}")
            self.render_label.configure(text="Görsel yüklenemedi")
            self.improve_button.configure(state="disabled")
    
    def analyze_image(self):
        """GLM-4.6V-Flash için özel format ile kod üretir (VISION DESTEKLİ)"""
        if not self.client:
            messagebox.showerror("Hata", "Önce token'ı kaydedin!")
            return
        
        has_image = self.image_path is not None
        text_description = self.text_input.get(1.0, tk.END).strip()
        has_text = text_description and text_description != "Bu 3D objenin OpenSCAD kodunu üret. Boyutlar, şekiller ve detaylar hakkında açıklama yapabilirsiniz."
        
        if not has_image and not has_text:
            messagebox.showerror("Hata", "Lütfen en az bir resim yükleyin veya metin açıklaması girin!")
            return
        
        try:
            self.clear_render()
            
            self.answer_text.delete(1.0, tk.END)
            self.answer_text.insert(tk.END, "OpenSCAD kodu üretiliyor...\n")
            self.root.update()
            
            text_description = self.text_input.get(1.0, tk.END).strip()
            question = self.question_entry.get().strip()
            
            # GLM-4.7-Flash için özel prompt formatı
            # System instruction'ı user message'a birleştiriyoruz
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
            
            if has_image:
                user_prompt_parts.append("**TASK:** Analyze this image of a 3D object and generate the corresponding OpenSCAD code.\n")
            else:
                user_prompt_parts.append("**TASK:** Based on the following description, generate the corresponding OpenSCAD code.\n")
            
            if has_text:
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
            
            if question:
                user_prompt_parts.append(f"\n**ADDITIONAL USER REQUEST:**\n{question}\n")
            
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
            
            final_prompt = system_instruction + "".join(user_prompt_parts)
            
            # GLM-4.6V-Flash VISION DESTEKLİ - görsel ve metin birlikte gönderilebilir
            # OpenAI-compatible format kullanıyoruz
            content: list = [{"type": "text", "text": final_prompt}]
            
            if has_image:
                base64_image = self.encode_image(self.image_path)
                # Görseli content listesine ekle (interleaved format)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            
            # Rate limiting: API çağrıları arasında bekle
            self._wait_for_rate_limit()
            
            # GLM-4.6V-Flash için API çağrısı - vision destekli (retry ile)
            completion = self._api_call_with_retry(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": content  # Text + Image (varsa)
                    }
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            
            if not completion or not completion.choices:
                self.answer_text.delete(1.0, tk.END)
                self.answer_text.insert(tk.END, "OpenSCAD kodu üretilemedi. API yanıtı alınamadı.")
                return
            
            answer = completion.choices[0].message.content
            self.answer_text.delete(1.0, tk.END)
            
            if answer:
                clean_code = answer.strip()
                if clean_code.startswith("```openscad") or clean_code.startswith("```"):
                    clean_code = clean_code.split("```")[1]
                    if clean_code.startswith("openscad"):
                        clean_code = clean_code[8:]
                    clean_code = clean_code.strip()
                
                self.answer_text.insert(tk.END, clean_code)
                self.root.after(500, self.auto_render)
            else:
                self.answer_text.insert(tk.END, "OpenSCAD kodu üretilemedi.")
        
        except Exception as e:
            self.answer_text.delete(1.0, tk.END)
            self.answer_text.insert(tk.END, f"HATA: {str(e)}")
    
    def auto_render(self):
        """Kod üretildikten sonra otomatik render et"""
        if self.openscad_path:
            self.render_openscad()
        else:
            self.render_label.configure(text="OpenSCAD bulunamadı\n(Manuel render için\nOpenSCAD yükleyin)")
            self.improve_button.configure(state="disabled")
    
    def try_render(self, code):
        """Kodu render etmeye çalışır, başarı durumu ve hata mesajını döner"""
        if not self.openscad_path:
            return False, "OpenSCAD bulunamadı"
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scad', delete=False, encoding='utf-8') as scad_file:
                scad_file.write(code)
                scad_path = scad_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as png_file:
                png_path = png_file.name
            
            cmd = [
                self.openscad_path,
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
                if os.path.exists(png_path):
                    os.unlink(png_path)
            except:
                pass
            
            if result.returncode == 0:
                return True, None
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
    
    def fix_syntax_error(self, code, error_message):
        """LLM'e hatayı gösterip düzeltmesini ister - GLM-4.7 formatı"""
        if not self.client:
            return None
        
        try:
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
            
            # Rate limiting: API çağrıları arasında bekle
            self._wait_for_rate_limit()
            
            # GLM-4.6V-Flash için API çağrısı (retry ile)
            completion = self._api_call_with_retry(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=4000,
            )
            
            if not completion or not completion.choices:
                return None
            
            fixed_code = completion.choices[0].message.content
            
            if fixed_code:
                fixed_code = fixed_code.strip()
                if fixed_code.startswith("```"):
                    fixed_code = fixed_code.split("```")[1]
                    if fixed_code.startswith("openscad"):
                        fixed_code = fixed_code[8:]
                    fixed_code = fixed_code.strip()
                
                return fixed_code
            
            return None
            
        except Exception as e:
            print(f"Düzeltme hatası: {e}")
            return None
    
    def auto_fix_code(self):
        """Render hatasını algılayıp otomatik düzeltme yapar"""
        code = self.answer_text.get(1.0, tk.END).strip()
        if not code:
            messagebox.showwarning("Uyarı", "Düzeltilecek kod yok!")
            return
        
        if not self.openscad_path:
            messagebox.showerror("Hata", "OpenSCAD bulunamadı!")
            return
        
        if not self.client:
            messagebox.showerror("Hata", "LLM client bulunamadı! Token kontrol edin.")
            return
        
        max_attempts = 3
        current_code = code
        
        for attempt in range(max_attempts):
            self.answer_text.delete(1.0, tk.END)
            self.answer_text.insert(tk.END, f"Düzeltme denemesi {attempt + 1}/{max_attempts}...\n\n{current_code}")
            self.render_label.configure(text=f"Düzeltme {attempt + 1}/{max_attempts}...")
            self.root.update()
            
            success, error_message = self.try_render(current_code)
            
            if success:
                messagebox.showinfo("Başarılı", f"{attempt + 1}. denemede kod düzeltildi! ✅")
                self.answer_text.delete(1.0, tk.END)
                self.answer_text.insert(tk.END, current_code)
                self.render_openscad()
                return
            
            if error_message:
                # Her düzeltme denemesi arasında bekle (rate limiting için)
                if attempt < max_attempts - 1:
                    self.answer_text.insert(tk.END, f"\n\n⏳ Rate limiting için 2 saniye bekleniyor...\n")
                    self.root.update()
                    time.sleep(2)
                
                fixed_code = self.fix_syntax_error(current_code, error_message)
                
                if fixed_code and fixed_code != current_code:
                    current_code = fixed_code
                else:
                    break
            else:
                break
        
        messagebox.showerror("Hata", f"{max_attempts} denemede kod düzeltilemedi.\n\nSon hata mesajını kontrol edin ve manuel olarak düzeltmeyi deneyin.")
        self.render_label.configure(text="Düzeltme başarısız")
    
    def improve_with_comparison(self):
        """Render edilmiş görseli ilk resimle karşılaştırarak iyileştir - GLM-4.7 formatı"""
        if not self.client:
            messagebox.showerror("Hata", "Önce token'ı kaydedin!")
            return
        
        if not self.rendered_image_path or not os.path.exists(self.rendered_image_path):
            messagebox.showwarning("Uyarı", "Render edilmiş görsel bulunamadı!")
            return
        
        if not self.image_path or not os.path.exists(self.image_path):
            messagebox.showwarning("Uyarı", "İlk yüklenen görsel bulunamadı! İyileştirme için orijinal görsel gerekli.")
            return
        
        try:
            self.answer_text.delete(1.0, tk.END)
            self.answer_text.insert(tk.END, "İyileştirme yapılıyor...\n")
            self.improve_button.configure(state="disabled", text="İşleniyor...")
            self.root.update()
            
            original_image_base64 = self.encode_image(self.image_path)
            rendered_image_base64 = self.encode_image(self.rendered_image_path)
            
            current_code = self.answer_text.get(1.0, tk.END).strip()
            
            # GLM-4.6V-Flash VISION DESTEKLİ - görsel karşılaştırması yapabilir
            prompt = f"""Compare these two images:
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
{current_code}
```

Based on this comparison, generate an IMPROVED OpenSCAD code that:
1. Better matches the original image
2. Fixes any discrepancies you identified
3. Maintains correct OpenSCAD syntax
4. Includes comments explaining improvements

Output only the improved OpenSCAD code, starting with the code itself. Do not include explanations outside of code comments."""
            
            # GLM-4.6V-Flash VISION DESTEKLİ - görselleri gönderiyoruz
            content: list = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{original_image_base64}"
                    }
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{rendered_image_base64}"
                    }
                }
            ]
            
            # Rate limiting: API çağrıları arasında bekle
            self._wait_for_rate_limit()
            
            completion = self._api_call_with_retry(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": content  # Text + Images
                    }
                ],
            )
            
            if not completion:
                self.answer_text.delete(1.0, tk.END)
                self.answer_text.insert(tk.END, "İyileştirme yapılamadı. API yanıtı alınamadı.")
                self.improve_button.configure(state="normal", text="🔄 İyileştir")
                return
            
            if not hasattr(completion, 'choices') or not completion.choices or len(completion.choices) == 0:
                self.answer_text.delete(1.0, tk.END)
                self.answer_text.insert(tk.END, "İyileştirme yapılamadı. API yanıtı geçersiz.")
                self.improve_button.configure(state="normal", text="🔄 İyileştir")
                return
            
            answer = completion.choices[0].message.content
            self.answer_text.delete(1.0, tk.END)
            if answer:
                self.answer_text.insert(tk.END, answer)
                self.root.after(500, self.auto_render)
            else:
                self.answer_text.insert(tk.END, "İyileştirme yapılamadı.")
            
            self.improve_button.configure(state="normal", text="🔄 İyileştir")
            
        except Exception as e:
            self.answer_text.delete(1.0, tk.END)
            self.answer_text.insert(tk.END, f"HATA: {str(e)}")
            self.improve_button.configure(state="normal", text="🔄 İyileştir")
            messagebox.showerror("Hata", f"İyileştirme hatası: {str(e)}")
    
    def show_prompt_debug(self):
        """Gönderilen prompt'u göster (debug için)"""
        has_image = self.image_path is not None
        text_description = self.text_input.get(1.0, tk.END).strip()
        has_text = text_description and text_description != "Bu 3D objenin OpenSCAD kodunu üret. Boyutlar, şekiller ve detaylar hakkında açıklama yapabilirsiniz."
        question = self.question_entry.get().strip()
        
        system_instruction = """You are an expert OpenSCAD programmer..."""
        
        popup = tk.Toplevel(self.root)
        popup.title("🔍 Gönderilen Prompt (GLM-4.7-Flash Debug)")
        popup.geometry("900x700")
        
        info_label = tk.Label(popup, 
            text=f"✅ GLM-4.6V-Flash VISION DESTEKLİ FORMAT\n📊 Görsel: {'Var' if has_image else 'Yok'} | Metin: {'Var' if has_text else 'Yok'} | Ek Talimat: {'Var' if question else 'Yok'}\n\n✅ GLM-4.6V-Flash vision (görsel) desteği var - görselleri analiz edebilir!", 
            bg="#E8F5E9", 
            font=("Arial", 9, "bold"),
            fg="#2E7D32")
        info_label.pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = VisionQAApp(root)
    root.mainloop()
