# JOBAGENT — İş Başvuru Otomasyonu

CV'nizi ve mesleğinizi verin; **eleman.net**, **isinolsun.com** ve **kariyer.net** üzerindeki uygun
iş ilanlarını otomatik bulsun, dilediklerinize tek tıkla başvurusun.

> **Önemli:** Başvuru yapılacak sitelere tarayıcıdan **önceden giriş yapılmış olmalıdır**.
> Oturum kalıcı profilde saklanır, bir daha sormaz.

---

## Neler Yapıyor?

- **CV analizi** — `.pdf`, `.docx`, `.txt` yükleyin; anahtar kelimeler otomatik çıkarılır
- **Akıllı eşleştirme** — ilanlar puanlanır: `Uygun` / `Düşük` / `Hariç`
- **3 kaynak site** — eleman.net, isinolsun.com, kariyer.net (arayüzden seçilir)
- **Seç-başvur** — listeden işaretlediklerinize toplu otomatik başvuru
- **Şirket soruları** — ilk sorulu ilanda sorulur, cevaplar kaydedilir, sonrasında otomatik doldurulur
- **Tikli takip listesi** — biten başvuruların HTML raporu
- **Kalıcı oturum** — her site için tarayıcı profili (giriş bir kez yapılır)

---

## Hızlı Başlangıç

### A) Tek dosya — Python gerektirmez

1. `JOBAGENT.exe` dosyasını indirin (GitHub Releases)
2. Çift tıklayın veya komut satırında `JOBAGENT.exe` yazın
3. Tek gereksinim: kurulu bir **Google Chrome veya Microsoft Edge**

> `data` klasörü ve `config.json` exe'nin **yanında** otomatik oluşur — profiller, oturumlar
> ve cevap bankanız kalıcıdır.

### B) Kaynaktan (Python)

Windows:

```bat
setup.bat          rem sanal ortam + bağımlılıklar kurulur
kur.bat            rem JOBAGENT komutunu PATH'e ekler (isteğe bağlı)
JOBAGENT           rem tam ekran arayüzü
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python tui.py
```

---

## Kullanım

### Tam ekran arayüz (önerilen)

```bash
JOBAGENT
```

```
1. Mesleğinizi yazın           → "Elektrik Teknisyeni"
2. CV dosyasının yolunu girin   → C:\kullanici\CV.pdf (isteğe bağlı)
3. Kaynak siteleri seçin        → 1, 2 veya 3'ü birden işaretleyin
4. "Uygun İşleri Bul"           → tarayıcı açılır, ilanlar puanlanır
5. İlanları seçin               → Boşluk tuşu
6. Başvurun                     → A tuşu veya "Seçililere Başvur"
7. Rapor                        → data\takip_<site>_<sid>.html
```

**Klavye kısayolları:** `↑ ↓` gezin · `Boşluk` seç/kaldır · `A` başvur · `Ctrl+Q` çıkış

### Komut satırı modları

| Komut | Açıklama |
| --- | --- |
| `JOBAGENT` | Tam ekran terminal arayüzü (ana kullanım) |
| `JOBAGENT web` | Web arayüzü → `http://127.0.0.1:5000` |
| `JOBAGENT --cli` | Satır tabanlı akış |
| `JOBAGENT --help` | Tüm seçenekler |

---

## Şirket Soruları

Bazı ilanların formlarında şirket soruları vardır ("Neden bu işe başvurmak istiyorsunuz?",
"Beklenen maaş", "Deneyim yılı" gibi). JOBAGENT şöyle çalışır:

1. **İlk sorulu ilanda** sorular size terminal ekranında sorulur
2. Cevaplar `data\answers.json` dosyasına kaydedilir
3. **Sonraki ilanlarda aynı soru** hiç sorulmadan otomatik doldurulur
4. Yeni bir soru çıkarsa onu tekrar sorar
5. Kişisel alanlar (ad, e-posta, telefon vb.) tespit edilip **atlanır**

İsterseniz `data\answers.json`'ı metin editörüyle düzenleyebilirsiniz.

---

## Tarayıcı ve Giriş

- Otomasyon **görünür bir tarayıcı** açar (headless değil) — antibot korumaları tetiklenmez
- Varsayılan sıra: **Chrome** → **Edge** → Playwright Chromium
- Bir site "challenge" gösterirse pencereyi manuel çözün; akış otomatik devam eder
- Kariyer.net tek tık "Hemen Başvur" akışı kullanır

---

## Proje Yapısı

```
JOBAGENT.bat      JOBAGENT komutu (kur.bat her yerden erişim sağlar)
kur.bat / kur.ps1 JOBAGENT'i PATH'e ekleyen kurulum
setup.bat         Sanal ortam + bağımlılık kurulumu
build.bat         JOBAGENT.exe derler (PyInstaller, Python gerektirmez)
paket.bat         Kullanıcılar için temiz kaynak zip'i üretir
tui.py            Tam ekran terminal arayüzü (Textual)
cli.py            Satır tabanlı arayüz
app.py            Web arayüzü (Flask)
browser.py        Tarayıcı / profil yönetimi
worker.py         Arama + başvuru motoru
cv_reader.py      CV metni + anahtar kelime üretimi
matcher.py        İlan eşleştirme / puanlama
export.py         Tikli takip listesi (HTML)
sites/            Site adapterları (base, eleman, isinolsun, kariyer)
templates/        Web arayüzü sayfaları
static/           Web arayüzü stilleri
data/             Çalışma zamanı verileri (oluşturulur)
```

---

## Kullanıcıya Dağıtım

**Tek dosya:** `build.bat` → `dist\JOBAGENT.exe` (~57 MB). Kullanıcı indirir, çalıştırır.
**Kaynak:** `paket.bat` → `JOBAGENT_paket.zip`. Kullanıcı açıp `setup.bat` çalıştırır.

---

## Notlar

- Her site aynı arayüzle çalışır; DOM değişirse `sites/<site>.py` seçicileri güncellenebilir
- Başvuru durumları: `daha-once`, `basvuru-alindi`, `challenge`, `belirsiz`, hata
- Yoğun ardışık isteklerde isinolsun doğrulama isteyebilir; pencereden çözün
