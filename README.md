# Spectre

Website mirroring & passive recon tool

```
███████╗██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝
███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗  
╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝  
███████║██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗
╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
```

## Kurulum

```bash
git clone https://github.com/kullanici/spectre
cd spectre
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x spectre
```

## Kullanım

```bash
# Temel mirror
./spectre https://hedef-site.com

# Mirror + pasif analiz
./spectre https://hedef-site.com --analyze

# Stealth + decoy + analiz + rapor
./spectre https://hedef-site.com --stealth --decoy --analyze --report rapor.json

# Mevcut mirror'ı analiz et
./spectre --analyze-only ./mirror_dizini
```

## Özellikler

| Özellik | Açıklama |
|---|---|
| **Mirror** | HTML, CSS, JS, resim, video — tüm kaynakları indirir |
| **Stealth** | User-Agent rotasyonu, gerçekçi başlıklar, insan benzeri gecikmeler |
| **Decoy** | Gerçek istekler arasına zararsız tuzak istekler karıştırır |
| **Recon** | Mirror üzerinden teknoloji tespiti, secret/endpoint keşfi, form analizi |

## Seçenekler

```
-o, --output     Çıktı dizini
-d, --depth      Tarama derinliği (varsayılan: 5)
-t, --threads    Paralel thread sayısı (varsayılan: 4)
--delay          İstekler arası gecikme (saniye)
--max-size       Maksimum dosya boyutu (MB)
--stealth        Stealth modu
--decoy          Decoy modu
--no-videos      Video dosyalarını atla
--analyze        Mirror sonrası pasif analiz
--analyze-only   Sadece analiz (indirme yok)
--report         JSON rapor dosyası
```

## Yasal Uyarı

Bu araç yalnızca **yasal ve izinli** güvenlik testleri, eğitim amaçlı kullanım
ve **kendi sistemlerinizin** analizi için tasarlanmıştır.

İzin alınmamış sistemler üzerinde kullanmak Türkiye'de **5237 sayılı TCK
Madde 243-245** kapsamında suç teşkil eder. Geliştirici kötüye kullanımdan
doğan hiçbir sorumluluk kabul etmez.
