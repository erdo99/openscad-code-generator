# 3D Obje → OpenSCAD Kodu Üretici

AI destekli bir sistem ile 3D objelerin görsellerinden veya açıklamalarından OpenSCAD kodu üreten full-stack uygulama.

## 🚀 Özellikler

- **Görsel Analiz**: 3D obje fotoğraflarından OpenSCAD kodu üretme (Vision destekleyen modellerle)
- **Metin Açıklaması**: Metin açıklamalarından OpenSCAD kodu üretme
- **Syntax Validation**: Otomatik syntax kontrolü ve düzeltme
- **Few-Shot Learning**: Başarılı örneklerle model eğitimi
- **Self-Correction Loop**: İteratif kod düzeltme mekanizması
- **3D Render**: Üretilen kodun OpenSCAD ile render edilmesi
- **Kod İyileştirme**: Orijinal ve render edilmiş görselleri karşılaştırarak kod iyileştirme
- **Çoklu API Desteği**: ZAI API (GLM) ve io_net API (Qwen, Llama, vb.) desteği

## 📋 Gereksinimler

- Python 3.8+
- Node.js 16+ (Frontend için)
- OpenSCAD (3D render için)
- API Keys:
  - ZAI API Key (GLM modelleri için) - `NEW_KEY`, `SECOND_API_KEY`
  - io_net API Key (Qwen, Llama modelleri için) - `IO_NET_KEY`
  - HuggingFace Token (opsiyonel)

## 🛠️ Kurulum

### 1. Projeyi Klonlayın

```bash
git clone <repo-url>
cd "Qwen Apili"
```

### 2. Backend Kurulumu

**Otomatik Kurulum (Önerilen):**
```bash
setup.bat
```

**Manuel Kurulum:**
```bash
# Sanal ortam oluştur
python -m venv venv

# Sanal ortamı aktif et
venv\Scripts\activate

# Paketleri yükle
pip install -r requirements.txt
```

### 3. Environment Variables

`.env.example` dosyasını `.env` olarak kopyalayın ve API key'lerinizi ekleyin:

```env
# ZAI API (GLM modelleri için)
NEW_KEY=your_zai_api_key
SECOND_API_KEY=your_second_zai_api_key
MODEL_NAME=zai-org/GLM-4.6V-Flash
MODEL_NAME_2=zai-org/GLM-4.6V-Flash

# io_net API (Qwen, Llama modelleri için)
IO_NET_KEY=your_io_net_api_key
IO_NET_MODEL=Qwen/Qwen2.5-VL-32B-Instruct
IO_NET_BASE_URL=https://api.intelligence.io.solutions/api/v1

# Opsiyonel
HF_TOKEN=your_huggingface_token
```

### 4. Frontend Kurulumu

```bash
cd frontend
npm install
```

## 🎯 Kullanım

### Backend'i Başlatma

**io_net Backend (Vision Desteği - Önerilen):**
```bash
start_backend_ionet.bat
```

veya manuel olarak:
```bash
venv\Scripts\activate
python backend_api_ionet.py
```

Backend `http://localhost:5002` adresinde çalışacaktır.
- Model: `Qwen/Qwen2.5-VL-32B-Instruct` (Vision destekliyor)
- Görsel analizi destekler
- OpenAI-compatible API formatı

**Improved Backend (Syntax Validation, Few-Shot, Self-Correction):**
```bash
start_backend_improved.bat
```

veya manuel olarak:
```bash
venv\Scripts\activate
python backend_api_improved.py
```

Backend `http://localhost:5001` adresinde çalışacaktır.
- Model: `zai-org/GLM-4.6V-Flash` (ZAI API)
- Syntax validation, few-shot learning, self-correction özellikleri

**Orijinal Backend:**
```bash
start_backend.bat
```

veya manuel olarak:
```bash
venv\Scripts\activate
python backend_api.py
```

Backend `http://localhost:5000` adresinde çalışacaktır.

### Frontend'i Başlatma

```bash
start_frontend.bat
```

veya manuel olarak:
```bash
cd frontend
npm run dev
```

Frontend `http://localhost:3000` adresinde çalışacaktır (Vite default port).

**Not:** Frontend proxy ayarları `frontend/vite.config.js` dosyasında yapılandırılabilir. Varsayılan olarak io_net backend'e (port 5002) yönlendirilir.

### Testleri Çalıştırma

**Improved Backend Testleri:**
```bash
run_tests.bat
```

**io_net Backend Testleri:**
```bash
test_ionet.bat
```

Not: Test çalıştırmadan önce ilgili backend'in çalışıyor olması gerekir.

## 📁 Proje Yapısı

```
.
├── backend_api_ionet.py        # io_net backend (Vision desteği)
├── backend_api_improved.py     # Improved backend (Syntax, Few-Shot, Self-Correction)
├── backend_api.py              # Orijinal backend
├── test_backend_improved.py    # Improved backend unit testleri
├── test_ionet_api.py           # io_net backend testleri
├── requirements.txt            # Python bağımlılıkları
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx            # Ana uygulama
│   │   └── App.css            # Stiller
│   ├── package.json
│   └── vite.config.js         # Proxy ayarları (backend port seçimi)
├── setup.bat                   # Otomatik kurulum
├── start_backend_ionet.bat     # io_net backend başlatma (Port 5002)
├── start_backend_improved.bat  # Improved backend başlatma (Port 5001)
├── start_backend.bat           # Orijinal backend başlatma (Port 5000)
├── start_frontend.bat          # Frontend başlatma
├── run_tests.bat               # Improved backend testleri
├── test_ionet.bat              # io_net backend testleri
├── install_requests.bat        # requests paketi kurulumu
├── .env.example                # Environment variables şablonu
└── README.md                   # Bu dosya
```

## 🔧 API Endpoints

### io_net Backend (Port 5002) - Vision Desteği

- `POST /api/generate` - OpenSCAD kodu üretme (Görsel analizi destekler)
  - Body: `{ "image": "base64", "description": "text", "temperature": 0.7 }`
  - Model: `Qwen/Qwen2.5-VL-32B-Instruct` (Vision destekliyor)
  
- `POST /api/render` - Kodu render etme
  - Body: `{ "code": "openscad_code" }`
  
- `GET /api/health` - API sağlık kontrolü

### Improved Backend (Port 5001) - Gelişmiş Özellikler

- `POST /api/generate` - OpenSCAD kodu üretme
  - Body: `{ "image": "base64", "description": "text", "enable_self_correction": true, "enable_few_shot": true }`
  
- `POST /api/render` - Kodu render etme
  - Body: `{ "code": "openscad_code" }`
  
- `POST /api/improve` - Kodu iyileştirme
  - Body: `{ "code": "openscad_code", "original_image": "base64", "rendered_image": "base64" }`
  
- `POST /api/fix` - Syntax hatası düzeltme
  - Body: `{ "code": "openscad_code", "error": "error_message" }`
  
- `POST /api/fix-with-images` - Görsellerle kod düzeltme
  - Body: `{ "code": "openscad_code", "error": "error_message", "original_image": "base64", "rendered_image": "base64" }`
  
- `GET /api/health` - API sağlık kontrolü

### Orijinal Backend (Port 5000)

- `POST /api/generate` - OpenSCAD kodu üretme
- `POST /api/render` - Kodu render etme
- `POST /api/improve` - Kodu iyileştirme
- `POST /api/fix` - Syntax hatası düzeltme
- `POST /api/fix-with-images` - Görsellerle kod düzeltme
- `GET /api/health` - API sağlık kontrolü

## ✨ Backend Özellikleri

### io_net Backend (Port 5002)
- **Vision Desteği**: Görsel analizi destekleyen model (`Qwen/Qwen2.5-VL-32B-Instruct`)
- **OpenAI-Compatible**: OpenAI client kütüphanesi ile entegrasyon
- **Çoklu Model Desteği**: io_net API üzerinden farklı modeller (Qwen, Llama, vb.)
- **Temperature Kontrolü**: Frontend'den temperature ayarı

### Improved Backend (Port 5001)

#### 1. Syntax Validation & Pre-check
- Üretim öncesi ve sonrası syntax kontrolü
- Otomatik yaygın hata düzeltmeleri

#### 2. Few-Shot Learning
- Başarılı kod örnekleriyle model eğitimi
- Benzer objeler için daha iyi sonuçlar

#### 3. Self-Correction Loop
- İteratif kod düzeltme
- Maksimum 3 iterasyon ile otomatik iyileştirme

## 🧪 Test

### Improved Backend Testleri

Unit testler `test_backend_improved.py` dosyasında bulunmaktadır:

```bash
run_tests.bat
```

Testler şunları kapsar:
- Syntax Checker
- Few-Shot Examples
- Self-Correction Loop
- Integration Tests
- Edge Cases

### io_net Backend Testleri

API testleri `test_ionet_api.py` dosyasında bulunmaktadır:

```bash
test_ionet.bat
```

Testler şunları kapsar:
- Health Check
- Text Description ile kod üretme
- Image ile kod üretme (vision desteği)
- API bağlantı testleri

**Not:** Test çalıştırmadan önce ilgili backend'in çalışıyor olması gerekir.

## 📝 Notlar

- OpenSCAD'ın sisteminizde yüklü olması gerekmektedir (render için)
- API rate limit'leri için retry mekanizması mevcuttur
- **Backend Portları:**
  - io_net Backend: `5002` (Vision desteği)
  - Improved Backend: `5001` (Syntax, Few-Shot, Self-Correction)
  - Orijinal Backend: `5000`
- Frontend proxy ayarları `frontend/vite.config.js` dosyasında yapılandırılabilir
- **Model Seçimi:**
  - Vision desteği için: `Qwen/Qwen2.5-VL-32B-Instruct` (io_net backend)
  - Gelişmiş özellikler için: `zai-org/GLM-4.6V-Flash` (Improved backend)
- io_net backend OpenAI client kütüphanesi kullanır (`openai>=1.0.0`)

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit edin (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje açık kaynaklıdır ve MIT lisansı altında lisanslanmıştır.

## 👥 Yazar

Proje geliştirme sürecinde AI asistanı kullanılarak oluşturulmuştur.

## 🔗 İlgili Linkler

- [OpenSCAD Documentation](https://openscad.org/documentation.html)
- [ZAI API Documentation](https://z.ai/docs)
- [io_net Intelligence API](https://api.intelligence.io.solutions)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [React Documentation](https://react.dev/)
