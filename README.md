# 🧠 Gemini Question Solver

Soru fotoğraflarını paralel olarak Gemini AI ile çözen modern web uygulaması.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Özellikler

- 📷 **Drag & Drop** - Soru fotoğraflarını sürükle bırak
- 📁 **Klasör Tarama** - `questions/` klasöründen otomatik algılama
- ⚡ **Paralel İşlem** - Tüm sorular eş zamanlı çözülür
- 📊 **Gerçek Zamanlı İlerleme** - Canlı progress bar
- 📄 **Rapor Görüntüleme** - MD raporları web'de görüntüle
- 🧮 **LaTeX Desteği** - Matematik formülleri güzel render edilir
- 🎨 **Modern UI** - Glassmorphism tasarım

## 🚀 Kurulum

### 1. Repoyu Klonla

```bash
git clone https://github.com/yourusername/gemini-question-solver.git
cd gemini-question-solver
```

### 2. Virtual Environment Oluştur

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### 4. API Key Ayarla

```bash
cp .env.example .env
# .env dosyasını düzenle ve API key'ini ekle
```

API key almak için: [Google AI Studio](https://aistudio.google.com/apikey)

### 5. Çalıştır

```bash
python server.py
```

Tarayıcıda aç: **http://localhost:8000**

## 📖 Kullanım

### Web Arayüzü

1. **Klasörden Tara**: `questions/` klasörüne fotoğrafları at, "Yenile" butonuna tıkla
2. **Dosya Yükle**: Drag & drop ile fotoğraf yükle
3. **🚀 Soruları Çöz**: Butona tıkla ve bekle
4. **📄 Raporlar**: Çözüm raporlarını görüntüle/indir

### CLI Kullanımı

```bash
python main.py --input questions/ --output output/
```

## 📁 Proje Yapısı

```
gemini-question-solver/
├── server.py           # FastAPI web sunucusu
├── main.py             # CLI giriş noktası
├── config.py           # Yapılandırma ayarları
├── requirements.txt    # Python bağımlılıkları
├── .env.example        # Örnek environment dosyası
├── src/
│   ├── gemini_client.py      # Gemini API istemcisi
│   ├── image_loader.py       # Görüntü yükleme
│   ├── parallel_processor.py # Paralel işlem
│   └── report_generator.py   # Rapor oluşturma
├── web/
│   └── index.html      # Web arayüzü
├── questions/          # Soru fotoğrafları (gitignore)
└── output/             # Çözüm raporları (gitignore)
```

## ⚙️ Yapılandırma

`.env` dosyasında ayarlanabilir:

| Değişken                  | Açıklama                   | Varsayılan |
| ------------------------- | -------------------------- | ---------- |
| `GEMINI_API_KEY`          | Google AI API anahtarı     | (zorunlu)  |
| `MAX_CONCURRENT_REQUESTS` | Eş zamanlı istek sayısı    | 10         |
| `REQUEST_TIMEOUT`         | İstek zaman aşımı (saniye) | 60         |

## 🛠️ Teknolojiler

- **Backend**: Python, FastAPI, Uvicorn
- **AI**: Google Gemini 2.0 Flash
- **Frontend**: HTML, CSS, JavaScript
- **Math Rendering**: KaTeX

## 📝 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 🤝 Katkıda Bulunma

1. Fork et
2. Feature branch oluştur (`git checkout -b feature/amazing-feature`)
3. Commit et (`git commit -m 'Add amazing feature'`)
4. Push et (`git push origin feature/amazing-feature`)
5. Pull Request aç

---

Made with ❤️ using Gemini AI
