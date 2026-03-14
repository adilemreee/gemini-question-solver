# Sunucu ve Proje Deployment Raporu

## 1. Frontend Build
- Komut: `cd frontend && npm run build`
- Açıklama: React/Vite frontend'i production için build edildi.

## 2. Proje Dosyalarını Sunucuya Gönderme
- Komut: `sshpass -p 'Ab20752490.' rsync -avz --exclude='__pycache__' --exclude='node_modules' --exclude='.env' --exclude='uploads' --exclude='.git' --exclude='.DS_Store' -e "ssh -o StrictHostKeyChecking=no" /Users/adilemre/Desktop/geminnnnii/ root@193.35.154.183:/root/geminnnnii/`
- Açıklama: Tüm proje dosyaları sunucuya transfer edildi.

## 3. Sunucuda Ortam Kurulumu
- Komut: `apt update && apt install -y python3 python3-pip python3-venv nginx`
- Açıklama: Python, pip, venv ve nginx kuruldu.

## 4. Python Bağımlılıkları
- Komut: `python3 -m venv /root/geminnnnii/venv && /root/geminnnnii/venv/bin/pip install --upgrade pip`
- Komut: `/root/geminnnnii/venv/bin/pip install -r /root/geminnnnii/requirements.txt`
- Açıklama: Virtual environment oluşturuldu ve requirements.txt ile paketler yüklendi.

## 5. .env Dosyası Oluşturma
- Komut: `.env dosyası sunucuya yazıldı (API anahtarı ve ayarları ile)`

## 6. Systemd Servisi Oluşturma
- Komut: `/etc/systemd/system/geminnnnii.service dosyası oluşturuldu`
- Açıklama: Uygulamanın otomatik başlatılması için systemd servisi kuruldu.

## 7. Nginx Reverse Proxy ve HTTPS
- Komut: `/etc/nginx/sites-available/geminnnnii dosyası oluşturuldu ve reload edildi`
- Açıklama: Nginx reverse proxy yapılandırıldı.

## 8. Diğer Siteleri Devre Dışı Bırakma ve Geri Aktive Etme
- Komut: `rm -f /etc/nginx/sites-enabled/bedrive /etc/nginx/sites-enabled/fetchora /etc/nginx/sites-enabled/geminiparallel && nginx -t && systemctl reload nginx`
- Komut: `ln -sf /etc/nginx/sites-available/bedrive /etc/nginx/sites-enabled/bedrive && ln -sf /etc/nginx/sites-available/fetchora /etc/nginx/sites-enabled/fetchora && ln -sf /etc/nginx/sites-available/geminiparallel /etc/nginx/sites-enabled/geminiparallel && nginx -t && systemctl reload nginx`
- Açıklama: Çakışan siteler devre dışı bırakılıp, sonra tekrar aktive edildi.

## 9. Subdomain'e Taşıma ve Fetchora'yı Ana Domain'e Geri Verme
- Komut: `geminnnnii'yi gemini.adilemree.xyz subdomain'ine taşıdım, fetchora'yı ana domain'e geri verdim.`

## 10. SSL Sertifikası Kurulumu
- Komut: `certbot --nginx -d gemini.adilemree.xyz --non-interactive --agree-tos --email admin@adilemree.xyz --redirect`
- Açıklama: Let's Encrypt ile SSL sertifikası alınıp nginx'e eklendi.

## 11. Durum ve Erişim Testleri
- Komut: `curl -s -o /dev/null -w "%{http_code}" https://gemini.adilemree.xyz/`
- Açıklama: HTTPS erişimi test edildi.

---

Tüm adımlar terminalde çalıştırıldı ve sunucunda uygulandı. Detay veya dosya içeriği istersen, belirtmen yeterli!