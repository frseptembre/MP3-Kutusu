# MP3 Kutusu

Tek kutulu, Türkçe, kurulum gerektirmeyen **tarayıcı arayüzü**. Arkadaşın sadece bir internet bağlantısına ve tarayıcıya ihtiyaç duyar. Sitede video URL'sini yapıştırır, **MP3 OLARAK İNDİR** düğmesine basar. MP3 otomatik olarak tarayıcısının **İndirilenler** klasörüne kaydedilir. Chrome ve Edge'de isterse **Klasör seç** düğmesiyle farklı bir klasör de kullanabilir.

> ⚠️ Uygulamanın **sunucuda çalışması** gerekiyor. Bu ZIP'i arkadaşına göndermek, tek başına çevrimiçi site oluşturmaz. Aşağıdaki ilk kurulum bir kez **siteyi paylaşacak kişi** tarafından yapılır. Arkadaşının herhangi bir program kurması gerekmez.

## Siteyi yayına almak (Render + GitHub)

1. ZIP'i kendi bilgisayarında aç. GitHub'da yeni bir depo oluştur. ZIP'in içindeki `app.py`, `static` klasörü, `Dockerfile`, `requirements.txt` ve `render.yaml` dosyalarını depoya yükle. *(ZIP dosyasını tek başına GitHub'a yükleme; içeriğini yükle.)*
2. [render.com](https://render.com/) hesabı oluştur, GitHub hesabını bağla.
3. Render Dashboard'da **New > Blueprint** seç, yeni GitHub deponu seç. `render.yaml` otomatik tanınır. Kurulum sırasında **APP_KEY** için senin seçeceğin rastgele uzun bir şifre gir (örneğin 20+ harf/rakam). Bu şifreyi herkese açık GitHub deposuna yazma.
4. Render deploy tamamlayınca `https://...onrender.com` biçiminde bir site adresi verir. Arkadaşına şu formda **tek bir link** gönder:
   `https://SITE-ADRESI.onrender.com/?key=SENIN-GIRDIGIN-APP_KEY`
5. Arkadaşın bu linki açınca video bağlantısını yapıştırıp MP3 indirir. Şifreyi ayrıca yazmak zorunda kalmaz.

Alternatif: **New > Web Service** ile depoyu seç, **Language: Docker** ve **Free** planını seç. **Environment** bölümüne `APP_KEY` ekle. Render Dockerfile'ı kullanır.

**Uyarı:** Render Free yaklaşık 15 dakika hareketsizlikten sonra sunucuyu uykuya alabilir. Sonraki açılış yavaşlayabilir. Bazı YouTube videoları YouTube tarafındaki erişim/robot kontrolleri veya barındırma hizmetinin IP'si nedeniyle indirilemeyebilir. Ücretsiz sunucuda uzun videolar yavaş olabilir. Bu hizmetin ücretsiz planı ve trafik limitleri zamanla değişebilir.

## Bilgisayarında denemek (siteyi kuracak kişi için)

Docker kuruluysa:

```sh
docker build -t mp3-kutusu .
docker run --rm -p 10000:10000 -e APP_KEY=deneme123 mp3-kutusu
```

Tarayıcıda `http://localhost:10000/?key=deneme123` aç.

Docker olmadan (Python 3.10+, FFmpeg, Deno kurulu ise):

```sh
pip install -r requirements.txt
APP_KEY=deneme123 uvicorn app:app --host 127.0.0.1 --port 10000
```

Windows'ta environment variable belirlemek için `set APP_KEY=deneme123` ve ardından `uvicorn app:app --port 10000` komutlarını kullan.

## Neler var?

- **Tek kutu** ve tek büyük indir düğmesi.
- Tek bir YouTube video/Shorts bağlantısı; oynatma listelerini reddeder.
- 192 kbps MP3 dönüştürme (kaynak ses kalitesiyle sınırlıdır).
- 60 dakikalık video sınırı; ücretsiz barındırmada kaynak kullanımını sınırlar.
- Aynı anda bir dönüştürme, geçici dosyalar iletilince sunucudan silinir.
- Sunucuda FFmpeg, yt-dlp ve YouTube çözümleri için gerekli Deno ve yt-dlp-ejs bulunur.
- `APP_KEY` ile linki bilen kişilerin erişimi. `APP_KEY` boş bırakılırsa API herkese açıktır; internette önerilmez.
- İnternet tarayıcısı, güvenlik nedeniyle izin almadan rastgele bir klasöre yazamaz. Normalde **İndirilenler** klasörü kullanılır; Chrome/Edge'deki klasör seçme özelliği buna bir alternatiftir.

## Sınırlamalar ve kullanım koşulları

Bu uygulama video sahibi olduğun veya indirmeye açıkça izin verilen içerikler için tasarlanmıştır. YouTube'un kullanım koşulları videoların izinsiz indirilmesini kısıtlayabilir. Korunan, özel, oturum açmayı gerektiren veya erişim engelli videolar için garanti verilmez. Uygulama, YouTube'un sürekli değişebilen teknik işleyişi sebebiyle ileride güncelleme gerektirebilir.
