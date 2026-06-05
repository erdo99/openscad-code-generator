# 3D Obje → OpenSCAD Kodu Üretici

AI destekli bir sistem ile 3D objelerin görsellerinden veya açıklamalarından OpenSCAD kodu üreten full-stack uygulama.

## Özellikler

- **Görsel Analiz**: 3D obje fotoğraflarından OpenSCAD kodu üretme (Vision destekleyen model ile)
- **Metin Açıklaması**: Metin açıklamalarından OpenSCAD kodu üretme
- **Çoklu API**: HuggingFace Router veya ZAI (GLM) — frontend'den seçilebilir
- **3D Render**: Üretilen kodun OpenSCAD ile render edilmesi
  - **Local Render**: OpenSCAD kuruluysa otomatik local render
  - **Online Render**: OpenSCAD yoksa Selenium ile online editor'de render
  - **Online Editor Linki**: Her render sonrası kodu online editor'de açma linki
- **Temperature Kontrolü**: Model yaratıcılığını ayarlama
- **OpenAI-Compatible API**: Standart OpenAI client formatı

## Gereksinimler

- Python 3.8+
- Node.js 16+ (Frontend için)
- **OpenSCAD** (Opsiyonel - Önerilir)
- **Selenium & ChromeDriver** (Online render için - Opsiyonel)
- API Keys (en az biri):
  - **HuggingFace**: `HF_TOKEN`
  - **ZAI**: `NEW_KEY` veya `SECOND_API_KEY`

## Kurulum

### 1. Projeyi Klonlayın

```bash
git clone https://github.com/erdo99/openscad-code-generator.git
cd openscad-code-generator
```

### 2. Backend Kurulumu

```bash
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 3. Environment Variables

`.env.example` dosyasını `.env` olarak kopyalayın:

```env
API_PROVIDER=huggingface

HF_TOKEN=your_huggingface_token
HF_MODEL=Qwen/Qwen2.5-VL-7B-Instruct

NEW_KEY=your_zai_api_key
ZAI_MODEL=glm-4.6v-flash
```

### 4. Frontend Kurulumu

```bash
cd frontend
npm install
```

## Kullanım

### Backend

```bash
venv\Scripts\activate
python backend_api_ionet.py
```

Backend `http://localhost:5002` adresinde çalışır.

### Frontend

```bash
cd frontend
npm run dev
```

Frontend `http://localhost:3000` adresinde açılır. Arayüzden **HuggingFace** veya **ZAI** sağlayıcısını seçebilirsiniz.

### Test

```bash
venv\Scripts\activate
python test_api.py
```

Backend çalışırken health check ve kod üretim testlerini çalıştırır.

## Proje Yapısı

```
.
├── backend_api_ionet.py   # Ana backend (HuggingFace / ZAI)
├── test_api.py            # API testleri
├── test_online_editor_link.py
├── requirements.txt
├── frontend/              # React frontend
├── data/files/            # OpenSCAD örnek veri seti
├── scripts/               # Yardımcı scriptler
├── .env.example
└── README.md
```

## API Endpoints (Port 5002)

- `POST /api/generate` — OpenSCAD kodu üretme
  - Body: `{ "image": "base64", "description": "text", "api_provider": "huggingface|zai", "temperature": 0.7 }`
- `POST /api/render` — Kodu render etme
  - Response: `{ "success": true, "image": "base64", "online_editor_link": "url" }`
- `GET /api/health` — Sağlık kontrolü ve yapılandırılmış sağlayıcılar

## Notlar

- Backend port: `5002`, Frontend port: `3000`
- `.bat` dosyaları yerel kullanım içindir ve GitHub'a push edilmez
- OpenSCAD yoksa online render + editor linki kullanılır
- Online editor: [OpenSCAD Playground](https://ochafik.com/openscad2/)

## Lisans

MIT
