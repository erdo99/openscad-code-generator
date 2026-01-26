# 3D Obje → OpenSCAD Kodu Üretici

AI destekli bir sistem ile 3D objelerin görsellerinden veya açıklamalarından OpenSCAD kodu üreten full-stack uygulama.

## 🚀 Özellikler

- **Görsel Analiz**: 3D obje fotoğraflarından OpenSCAD kodu üretme (Vision destekleyen model ile)
- **Metin Açıklaması**: Metin açıklamalarından OpenSCAD kodu üretme
- **3D Render**: Üretilen kodun OpenSCAD ile render edilmesi
- **Temperature Kontrolü**: Model yaratıcılığını ayarlama
- **OpenAI-Compatible API**: Standart OpenAI client formatı

## 📋 Gereksinimler

- Python 3.8+
- Node.js 16+ (Frontend için)
- **OpenSCAD** - Sisteminizde kurulu olmalıdır (3D render için)
  - Windows: [OpenSCAD İndirme](https://openscad.org/downloads.html)
  - Kurulum sonrası `openscad.exe` yolunun sistem PATH'inde olması veya varsayılan konumda olması gerekir
- API Keys:
  - io_net API Key - `IO_NET_KEY` (Qwen, Llama modelleri için)

## 🛠️ Kurulum

### 1. Projeyi Klonlayın

```bash
git clone https://github.com/erdo99/openscad-code-generator.git
cd openscad-code-generator
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

`.env.example` dosyasını `.env` olarak kopyalayın ve API key'inizi ekleyin:

```env
# io_net API (Qwen, Llama modelleri için)
IO_NET_KEY=your_io_net_api_key
IO_NET_MODEL=Qwen/Qwen2.5-VL-32B-Instruct
IO_NET_BASE_URL=https://api.intelligence.io.solutions/api/v1
```

### 4. Frontend Kurulumu

```bash
cd frontend
npm install
```

## 🎯 Kullanım

### Backend'i Başlatma

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

### Frontend'i Başlatma

```bash
start_frontend.bat
```

veya manuel olarak:
```bash
cd frontend
npm run dev
```

Frontend `http://localhost:3000` adresinde çalışacaktır.

### Testleri Çalıştırma

```bash
test_ionet.bat
```

**Not:** Test çalıştırmadan önce backend'in çalışıyor olması gerekir.

## 📁 Proje Yapısı

```
.
├── backend_api_ionet.py        # io_net backend (Vision desteği)
├── test_ionet_api.py           # io_net backend testleri
├── requirements.txt            # Python bağımlılıkları
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx            # Ana uygulama
│   │   └── App.css            # Stiller
│   ├── package.json
│   └── vite.config.js         # Proxy ayarları
├── setup.bat                   # Otomatik kurulum
├── start_backend_ionet.bat     # Backend başlatma (Port 5002)
├── start_frontend.bat          # Frontend başlatma
├── test_ionet.bat              # Backend testleri
├── install_requests.bat        # requests paketi kurulumu
├── .env.example                # Environment variables şablonu
└── README.md                   # Bu dosya
```

## 🔧 API Endpoints

### io_net Backend (Port 5002)

- `POST /api/generate` - OpenSCAD kodu üretme (Görsel analizi destekler)
  - Body: `{ "image": "base64", "description": "text", "temperature": 0.7 }`
  - Model: `Qwen/Qwen2.5-VL-32B-Instruct` (Vision destekliyor)
  
- `POST /api/render` - Kodu render etme
  - Body: `{ "code": "openscad_code" }`
  
- `GET /api/health` - API sağlık kontrolü

## ✨ Özellikler

### Vision Desteği
- Görsel analizi destekleyen model (`Qwen/Qwen2.5-VL-32B-Instruct`)
- 3D obje fotoğraflarından direkt OpenSCAD kodu üretme
- OpenAI-compatible vision formatı

### OpenAI-Compatible API
- OpenAI client kütüphanesi ile entegrasyon
- Standart API formatı
- Retry mekanizması ile güvenilir bağlantı

### Temperature Kontrolü
- Frontend'den model yaratıcılığını ayarlama
- 0.0 (Deterministik) - 1.0 (Yaratıcı) arası

## 🧪 Test

API testleri `test_ionet_api.py` dosyasında bulunmaktadır:

```bash
test_ionet.bat
```

Testler şunları kapsar:
- Health Check
- Text Description ile kod üretme
- Image ile kod üretme (vision desteği)
- API bağlantı testleri

**Not:** Test çalıştırmadan önce backend'in çalışıyor olması gerekir.

## 📝 Notlar

- OpenSCAD'ın sisteminizde yüklü olması gerekmektedir (render için)
- API rate limit'leri için retry mekanizması mevcuttur
- Backend port: `5002`
- Frontend port: `3000`
- Frontend proxy ayarları `frontend/vite.config.js` dosyasında yapılandırılabilir
- io_net backend OpenAI client kütüphanesi kullanır (`openai>=1.0.0`)
- Model: `Qwen/Qwen2.5-VL-32B-Instruct` (Vision destekliyor)

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
- [io_net Intelligence API](https://api.intelligence.io.solutions)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [React Documentation](https://react.dev/)
