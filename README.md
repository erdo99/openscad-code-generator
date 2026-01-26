# 3D Obje → OpenSCAD Kodu Üretici

AI destekli bir sistem ile 3D objelerin görsellerinden veya açıklamalarından OpenSCAD kodu üreten full-stack uygulama.

## 🚀 Özellikler

- **Görsel Analiz**: 3D obje fotoğraflarından OpenSCAD kodu üretme
- **Metin Açıklaması**: Metin açıklamalarından OpenSCAD kodu üretme
- **Syntax Validation**: Otomatik syntax kontrolü ve düzeltme
- **Few-Shot Learning**: Başarılı örneklerle model eğitimi
- **Self-Correction Loop**: İteratif kod düzeltme mekanizması
- **3D Render**: Üretilen kodun OpenSCAD ile render edilmesi
- **Kod İyileştirme**: Orijinal ve render edilmiş görselleri karşılaştırarak kod iyileştirme

## 📋 Gereksinimler

- Python 3.8+
- Node.js 16+ (Frontend için)
- OpenSCAD (3D render için)
- API Keys:
  - ZAI API Key (GLM modelleri için)
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
HF_TOKEN=your_huggingface_token
NEW_KEY=your_zai_api_key
SECOND_API_KEY=your_second_zai_api_key
MODEL_NAME=zai-org/GLM-4.6V-Flash
MODEL_NAME_2=zai-org/GLM-4.6V-Flash
```

### 4. Frontend Kurulumu

```bash
cd frontend
npm install
```

## 🎯 Kullanım

### Backend'i Başlatma

**Improved Backend (Önerilen - Yeni özelliklerle):**
```bash
start_backend_improved.bat
```

veya manuel olarak:
```bash
venv\Scripts\activate
python backend_api_improved.py
```

Backend `http://localhost:5001` adresinde çalışacaktır.

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

Frontend `http://localhost:5173` adresinde çalışacaktır.

### Testleri Çalıştırma

```bash
run_tests.bat
```

## 📁 Proje Yapısı

```
.
├── backend_api_improved.py    # Improved backend (Yeni özelliklerle)
├── backend_api.py              # Orijinal backend
├── test_backend_improved.py    # Unit testler
├── requirements.txt            # Python bağımlılıkları
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx            # Ana uygulama
│   │   └── App.css            # Stiller
│   ├── package.json
│   └── vite.config.js
├── setup.bat                   # Otomatik kurulum
├── start_backend.bat           # Backend başlatma
├── start_frontend.bat          # Frontend başlatma
├── run_tests.bat               # Test çalıştırma
└── README.md                   # Bu dosya
```

## 🔧 API Endpoints

### Improved Backend (Port 5001)

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

## ✨ Yeni Özellikler (Improved Backend)

### 1. Syntax Validation & Pre-check
- Üretim öncesi ve sonrası syntax kontrolü
- Otomatik yaygın hata düzeltmeleri

### 2. Few-Shot Learning
- Başarılı kod örnekleriyle model eğitimi
- Benzer objeler için daha iyi sonuçlar

### 3. Self-Correction Loop
- İteratif kod düzeltme
- Maksimum 3 iterasyon ile otomatik iyileştirme

## 🧪 Test

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

## 📝 Notlar

- OpenSCAD'ın sisteminizde yüklü olması gerekmektedir (render için)
- API rate limit'leri için retry mekanizması mevcuttur
- Improved backend varsayılan olarak port 5001'de çalışır
- Frontend proxy ayarları `frontend/vite.config.js` dosyasında yapılandırılabilir

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
- [React Documentation](https://react.dev/)
