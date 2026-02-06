"""
Gemini Client Module
Handles communication with Gemini API for question solving
"""
import asyncio
import time
import base64
import re
from typing import Optional, Tuple
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    QUESTION_PROMPT,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUEST_TIMEOUT,
)

console = Console()

# Topic detection patterns - TYT/AYT için genişletilmiş konu tespiti
TOPIC_PATTERNS = {
    'Matematik': [
        # Temel Matematik (TYT)
        r'\b(sayılar|doğal\s*sayı|tam\s*sayı|rasyonel|irrasyonel|gerçek\s*sayı|asal\s*sayı|tek\s*sayı|çift\s*sayı|negatif|pozitif|mutlak\s*değer|ebob|ekok|bölünebilme|kalanlı\s*bölme|faktöriyel|üslü\s*sayı|köklü\s*sayı|üs|kök|radikal)\b',
        r'\b(oran|orantı|yüzde|kar|zarar|faiz|maliyet|satış|kesir|ondalık|basit\s*kesir|bileşik\s*kesir|tam\s*sayılı\s*kesir|pay|payda)\b',
        r'\b(denklem|bilinmeyen|eşitlik|eşitsizlik|birinci\s*derece|ikinci\s*derece|mutlak\s*değerli\s*denklem|köklü\s*denklem|üslü\s*denklem)\b',
        r'\b(problemler|yaş\s*problemi|işçi\s*problemi|havuz\s*problemi|hareket\s*problemi|hız\s*problemi|karışım\s*problemi|yüzde\s*problemi|kar\s*zarar)\b',
        # Geometri (TYT)
        r'\b(geometri|nokta|doğru|doğru\s*parçası|ışın|açı|dar\s*açı|geniş\s*açı|dik\s*açı|düz\s*açı|tam\s*açı|komşu\s*açı|bütünler\s*açı|tümler\s*açı|iç\s*açı|dış\s*açı|ters\s*açı|yöndeş\s*açı)\b',
        r'\b(üçgen|ikizkenar|eşkenar|çeşitkenar|dik\s*üçgen|dar\s*açılı|geniş\s*açılı|kenarortay|açıortay|yükseklik|çevrel\s*çember|içteğet\s*çember|pisagor|öklid|benzerlik|eşlik)\b',
        r'\b(dörtgen|kare|dikdörtgen|paralelkenar|yamuk|deltoid|eşkenar\s*dörtgen|köşegen|çevre|alan)\b',
        r'\b(çember|daire|yarıçap|çap|teğet|kiriş|yay|merkez\s*açı|çevre\s*açı|dilim|halka)\b',
        r'\b(prizma|piramit|koni|küre|silindir|küp|dikdörtgenler\s*prizması|hacim|yüzey\s*alanı|katı\s*cisim)\b',
        r'\b(analitik\s*geometri|koordinat|kartezyen|x\s*ekseni|y\s*ekseni|orijin|doğru\s*denklemi|eğim|paralel|dik|uzaklık|orta\s*nokta)\b',
        # İleri Matematik (AYT)
        r'\b(fonksiyon|tanım\s*kümesi|değer\s*kümesi|bire\s*bir|örten|birim|sabit|artan|azalan|ters\s*fonksiyon|bileşke|periyodik|tek|çift)\b',
        r'\b(polinom|derece|katsayı|kök|çarpanlara\s*ayırma|bölme|bölüm|kalan|horner|özdeşlik|eşitlik)\b',
        r'\b(ikinci\s*derece|parabol|tepe\s*noktası|simetri\s*ekseni|diskriminant|delta|köklerin\s*toplamı|köklerin\s*çarpımı)\b',
        r'\b(logaritma|log|ln|doğal\s*logaritma|taban|antilogaritma|üstel\s*fonksiyon|e\s*sayısı|logaritmik)\b',
        r'\b(trigonometri|sin|cos|tan|cot|sec|csc|sinüs|kosinüs|tanjant|kotanjant|sekant|kosekant|radyan|derece|birim\s*çember|trigonometrik\s*özdeşlik|toplam\s*fark|iki\s*kat|yarım\s*açı)\b',
        r'\b(dizi|seri|aritmetik|geometrik|genel\s*terim|toplam\s*formülü|orta\s*terim|ıraksaklık|yakınsaklık|fibonacci|harmonik)\b',
        r'\b(limit|sağdan\s*limit|soldan\s*limit|belirsizlik|sonsuz|süreklilik|süreksizlik)\b',
        r'\b(türev|türev\s*kuralları|çarpım\s*kuralı|bölüm\s*kuralı|zincir\s*kuralı|maksimum|minimum|ekstremum|monotonluk|büküm\s*noktası|asimptot|türevli|türevsiz)\b',
        r'\b(integral|belirsiz\s*integral|belirli\s*integral|alan\s*hesabı|hacim\s*hesabı|integrasyon|kısmi\s*integral|değişken\s*değiştirme)\b',
        r'\b(olasılık|kombinasyon|permütasyon|faktöriyel|venn|şartlı\s*olasılık|bağımsız\s*olay|bağımlı\s*olay|deney|örneklem|olay)\b',
        r'\b(istatistik|aritmetik\s*ortalama|geometrik\s*ortalama|harmonik\s*ortalama|medyan|mod|standart\s*sapma|varyans|çeyrekler\s*açıklığı|histogram|frekans)\b',
        r'\b(matris|determinant|birim\s*matris|ters\s*matris|transpose|skaler|satır|sütun|kare\s*matris)\b',
        # Matematik sembolleri
        r'(?:x\s*[=+\-*/]\s*\d|\d+\s*[+\-*/]\s*\d+|√|∑|∫|∂|π|∞|≤|≥|≠|∈|⊂|∪|∩)',
    ],
    'Fizik': [
        # Fizik Bilimine Giriş
        r'\b(fizik|birim|ölçme|büyüklük|skaler|vektörel|si\s*birimi|metre|kilogram|saniye|newton|joule|watt|pascal|hertz|coulomb|amper|volt|ohm)\b',
        # Mekanik
        r'\b(hareket|kinematik|dinamik|konum|yer\s*değiştirme|yol|hız|sürat|ivme|düzgün\s*hareket|ivmeli\s*hareket|serbest\s*düşme|düşey\s*atış|yatay\s*atış|eğik\s*atış|dairesel\s*hareket)\b',
        r'\b(kuvvet|newton|kütle|ağırlık|sürtünme|gerilme|normal\s*kuvvet|yer\s*çekimi|bileşke|bileşen|atwood|eğik\s*düzlem|dinamometre)\b',
        r'\b(enerji|kinetik\s*enerji|potansiyel\s*enerji|mekanik\s*enerji|iş|güç|verim|enerjinin\s*korunumu|esnek\s*çarpışma|esnek\s*olmayan)\b',
        r'\b(momentum|itme|impuls|momentumun\s*korunumu|çarpışma|geri\s*tepme|roket)\b',
        r'\b(tork|moment|denge|kütle\s*merkezi|ağırlık\s*merkezi|kaldıraç|makara|statik|devrilme)\b',
        # Isı ve Sıcaklık
        r'\b(ısı|sıcaklık|termodinamik|celcius|kelvin|fahrenheit|termometre|ısı\s*kapasitesi|öz\s*ısı|kalori|joule|kalorimetri|faz\s*değişimi|erime|donma|buharlaşma|yoğuşma|süblimleşme|kırağılaşma|gizli\s*ısı|hal\s*değişimi)\b',
        r'\b(ısı\s*iletimi|konveksiyon|ışınım|iletken|yalıtkan|genleşme|boyca\s*genleşme|hacimce\s*genleşme)\b',
        # Dalgalar
        r'\b(dalga|titreşim|frekans|periyot|dalga\s*boyu|genlik|hız|boyuna\s*dalga|enine\s*dalga|mekanik\s*dalga|elektromanyetik\s*dalga)\b',
        r'\b(ses|ses\s*dalgası|ses\s*hızı|yankı|rezonans|doppler|ultrason|infrason|desibel)\b',
        r'\b(ışık|optik|yansıma|kırılma|kırılma\s*indisi|ayna|düz\s*ayna|çukur\s*ayna|tümsek\s*ayna|mercek|ince\s*kenarlı|kalın\s*kenarlı|odak|odak\s*uzaklığı|büyütme|görüntü)\b',
        # Elektrik ve Manyetizma
        r'\b(elektrik|yük|coulomb|elektron|proton|iletken|yalıtkan|yarı\s*iletken|topraklama|elektroskop|elektriklenme|sürtünme|dokunma|etki)\b',
        r'\b(elektrik\s*alan|elektrik\s*potansiyel|potansiyel\s*fark|gerilim|volt|sığa|kondansatör|farad)\b',
        r'\b(akım|devre|direnç|ohm|iletken|özdirenç|seri\s*bağlama|paralel\s*bağlama|kirchhoff|ampermetre|voltmetre)\b',
        r'\b(manyetizma|mıknatıs|manyetik\s*alan|manyetik\s*kuvvet|akım\s*geçen\s*tel|solenoid|elektromıknatıs|indüksiyon|faraday|lenz|alternatif\s*akım|transformatör)\b',
        # Modern Fizik
        r'\b(atom|çekirdek|elektron|proton|nötron|kütle\s*numarası|atom\s*numarası|izotop|radyoaktivite|alfa|beta|gama|yarı\s*ömür|fisyon|füzyon|einstein|özel\s*görelilik|foton|fotoelektrik|compton|de\s*broglie|kuantum)\b',
    ],
    'Kimya': [
        # Kimya Bilimi
        r'\b(kimya|madde|element|bileşik|karışım|homojen|heterojen|saf\s*madde|atom|molekül|simge|formül)\b',
        # Atom ve Periyodik Tablo
        r'\b(atom|dalton|thomson|rutherford|bohr|kuantum|orbital|enerji\s*seviyesi|kabuk|alt\s*kabuk|elektron|proton|nötron|kütle\s*numarası|atom\s*numarası|izotop|izobar|izoton|değerlik\s*elektron)\b',
        r'\b(periyodik\s*tablo|periyot|grup|alkali|toprak\s*alkali|halojen|soy\s*gaz|metal|ametal|yarı\s*metal|atom\s*yarıçapı|iyonlaşma\s*enerjisi|elektron\s*ilgisi|elektronegatiflik)\b',
        # Kimyasal Bağlar
        r'\b(kimyasal\s*bağ|iyonik\s*bağ|kovalent\s*bağ|polar|apolar|koordine\s*kovalent|metalik\s*bağ|lewis|oktet|dublet|sigma|pi|hibrit|sp3|sp2|sp|molekül\s*geometrisi)\b',
        r'\b(zayıf\s*etkileşim|van\s*der\s*waals|dipol|london|hidrojen\s*bağı|moleküller\s*arası)\b',
        # Kimyasal Tepkimeler
        r'\b(tepkime|reaksiyon|denklem|denkleştirme|katsayı|reaktif|ürün|yanma|sentez|analiz|yer\s*değiştirme|nötürleşme|çökelme|redoks|yükseltgenme|indirgenme)\b',
        r'\b(mol|avogadro|mol\s*kütlesi|molalite|molarite|yüzde\s*derişim|ppm|verim|sınırlayan\s*bileşen|stokiyometri)\b',
        # Gazlar
        r'\b(gaz|ideal\s*gaz|gerçek\s*gaz|basınç|sıcaklık|hacim|mol\s*sayısı|avogadro\s*yasası|boyle\s*mariotte|charles|gay\s*lussac|dalton|kısmi\s*basınç|graham|difüzyon|efüzyon)\b',
        # Çözeltiler
        r'\b(çözelti|çözücü|çözünen|doymuş|doymamış|aşırı\s*doymuş|çözünürlük|derişim|seyreltme|buhar\s*basıncı|kaynama\s*noktası|donma\s*noktası|ozmoz)\b',
        # Asitler ve Bazlar
        r'\b(asit|baz|arrhenius|bronsted|lowry|lewis|kuvvetli\s*asit|zayıf\s*asit|kuvvetli\s*baz|zayıf\s*baz|ph|poh|indikatör|turnusol|fenolftalein|nötürleşme|hidroliz|tampon)\b',
        # Kimyasal Tepkimelerde Enerji
        r'\b(termodinamik|entalpi|entropi|serbest\s*enerji|gibbs|ekzotermik|endotermik|hess|bağ\s*enerjisi|standart\s*oluşum|kalorimetri)\b',
        # Kimyasal Tepkimelerde Hız
        r'\b(tepkime\s*hızı|hız\s*bağıntısı|hız\s*sabiti|aktifleşme\s*enerjisi|katalizör|aktivasyon|derişim|sıcaklık|yüzey\s*alanı|tepkime\s*mekanizması|yavaş\s*basamak)\b',
        # Denge
        r'\b(kimyasal\s*denge|tersinir|denge\s*sabiti|kc|kp|le\s*chatelier|denge\s*kayması|çözünürlük\s*çarpımı|ksp)\b',
        # Elektrokimya
        r'\b(elektrokimya|pil|galvanik\s*pil|elektroliz|anot|katot|elektrot|yarı\s*pil|standart\s*potansiyel|faraday|korozyon)\b',
        # Organik Kimya
        r'\b(organik\s*kimya|karbon|hidrokarbon|alkan|alken|alkin|doymuş|doymamış|izomer|yapı\s*izomeri|geometri\s*izomeri|fonksiyonel\s*grup)\b',
        r'\b(alkol|eter|aldehit|keton|karboksil\s*asit|ester|amin|amit|aromatik|benzen|toluen|fenol|polimer|kauçuk|plastik|protein|karbonhidrat|yağ)\b',
        # Formüller
        r'(?:H2O|CO2|NaCl|HCl|NaOH|H2SO4|HNO3|H3PO4|NH3|CH4|C2H6|C2H4|C2H2|C6H12O6|C6H6|COOH|OH|NH2)',
    ],
    'Biyoloji': [
        # Hücre
        r'\b(hücre|prokaryot|ökaryot|hücre\s*zarı|sitoplazma|çekirdek|organel|mitokondri|kloroplast|ribozom|endoplazmik\s*retikulum|golgi|lizozom|vakuol|sentrozom|sentriyol|hücre\s*duvarı|plazmit)\b',
        r'\b(difüzyon|osmoz|aktif\s*taşıma|pasif\s*taşıma|endositoz|ekzositoz|fagositoz|pinositoz|turgor|plazmoliz|deplazmoliz)\b',
        # Canlıların Yapısı
        r'\b(karbonhidrat|monosakkarit|disakkarit|polisakkarit|glikoz|fruktoz|galaktoz|maltoz|sükroz|laktoz|nişasta|glikojen|selüloz|kitin)\b',
        r'\b(protein|amino\s*asit|peptit|polipeptit|enzim|substrat|aktif\s*merkez|koenzim|kofaktör|inhibitör|denatürasyon)\b',
        r'\b(yağ|lipit|yağ\s*asidi|doymuş|doymamış|gliserol|trigliserit|fosfolipit|steroit|kolesterol)\b',
        r'\b(nükleik\s*asit|DNA|RNA|nükleotit|adenin|guanin|sitozin|timin|urasil|riboz|deoksiriboz|çift\s*sarmal|baz\s*eşleşmesi|replikasyon|transkripsiyon|translasyon)\b',
        r'\b(vitamin|mineral|su|organik|inorganik|ATP|ADP|enerji)\b',
        # Hücre Bölünmesi
        r'\b(hücre\s*bölünmesi|mitoz|mayoz|interfaz|profaz|metafaz|anafaz|telofaz|kromozom|kromatit|sentromer|iğ\s*ipliği|sitokinez|homolog|tetrat|krossing\s*over|rekombinasyon|haploit|diploit)\b',
        # Kalıtım
        r'\b(genetik|kalıtım|mendel|gen|alel|dominant|resesif|genotip|fenotip|homozigot|heterozigot|çaprazlama|monohibrit|dihibrit|bağımsız\s*açılım|soy\s*ağacı|eş\s*baskınlık|eksik\s*baskınlık|çoklu\s*alel|kan\s*grubu|eşeye\s*bağlı)\b',
        r'\b(mutasyon|gen\s*mutasyonu|kromozom\s*mutasyonu|delesyon|duplikasyon|inversiyon|translokasyon|nokta\s*mutasyonu|mutagen)\b',
        # Biyoteknoloji
        r'\b(biyoteknoloji|genetik\s*mühendisliği|gen\s*klonlama|rekombinant\s*DNA|plazmit|restriksiyon\s*enzimi|pcr|elektroforez|transgenik|gdo|gen\s*tedavisi|aşı)\b',
        # Canlıların Sınıflandırılması
        r'\b(sınıflandırma|taksonomi|alem|şube|sınıf|takım|aile|cins|tür|hayvan|bitki|mantar|protista|monera|bakteri|arkea|virüs|prion)\b',
        # Bitki Biyolojisi
        r'\b(bitki|kök|gövde|yaprak|çiçek|meyve|tohum|fotosentez|kloroplast|klorofil|ışık\s*reaksiyonu|karanlık\s*reaksiyon|calvin|stomat|mezofil|ksilem|floem|transpirasyon|turgor)\b',
        r'\b(çimleme|büyüme|gelişme|tropizma|fototropizma|geotropizma|oksin|sitokinin|giberellin|absisik\s*asit|etilen|tozlaşma|döllenme|eşeyli\s*üreme|eşeysiz\s*üreme|vejetatif)\b',
        # Hayvan Biyolojisi - Sistemler
        r'\b(sindirim|mekanik\s*sindirim|kimyasal\s*sindirim|ağız|yemek\s*borusu|mide|ince\s*bağırsak|kalın\s*bağırsak|karaciğer|pankreas|safra|enzim|emilim)\b',
        r'\b(solunum|akciğer|bronş|bronşiyol|alveol|diyafram|gaz\s*değişimi|hemoglobin|oksijen|karbondioksit|hücresel\s*solunum|oksijenli|oksijensiz|fermantasyon|glikoliz|krebs|ets)\b',
        r'\b(dolaşım|kalp|atardamar|toplardamar|kılcal\s*damar|kan|aritrosit|lökosit|trombosit|plazma|antijen|antikor|bağışıklık|aşı|serum|lenf)\b',
        r'\b(boşaltım|böbrek|nefron|glomerül|bowman|proksimal|henle|distal|toplama\s*kanalı|süzme|geri\s*emilim|salgılama|idrar|üre|ürik\s*asit)\b',
        r'\b(sinir|nöron|akson|dendrit|miyelin|sinaps|nörotransmitter|merkezi\s*sinir|periferik|otonom|sempatik|parasempatik|duyu|hareket|refleks|beyin|beyincik|omurilik|omurilik\s*soğanı)\b',
        r'\b(endokrin|hormon|hipotalamus|hipofiz|tiroit|paratiroit|adrenal|böbrek\s*üstü|pankreas|insülin|glukagon|östrojen|testosteron|oksitosin)\b',
        r'\b(üreme|eşeyli|eşeysiz|mitoz|mayoz|gamet|sperm|yumurta|zigot|embriyo|fetüs|döllenme|gelişme|rejenerasyon)\b',
        r'\b(destek\s*hareket|iskelet|kemik|kıkırdak|eklem|kas|düz\s*kas|çizgili\s*kas|kalp\s*kası|kasılma|miyozin|aktin)\b',
        # Ekoloji
        r'\b(ekoloji|ekosistem|birey|popülasyon|komünite|biyosfer|habitat|niş|rekabet|avcı|av|parazitlik|mutualizm|kommensalizm|besin\s*zinciri|besin\s*ağı|üretici|tüketici|ayrıştırıcı|enerji\s*akışı|madde\s*döngüsü)\b',
        r'\b(karbon\s*döngüsü|azot\s*döngüsü|su\s*döngüsü|fosfor|biyokütle|ekolojik\s*piramit|taşıma\s*kapasitesi|süksesyon|biyom|çöl|tundra|tayga|orman|savan|step)\b',
        # Evrim
        r'\b(evrim|darwin|lamarck|doğal\s*seçilim|yapay\s*seçilim|varyasyon|adaptasyon|kalıtsal|mutasyon|gen\s*havuzu|alel\s*frekansı|genetik\s*sürüklenme|gen\s*akışı|türleşme|izolasyon|fosil|homolog|analog|vestigiyal|embriyoloji)\b',
    ],
    'Türkçe': [
        # Sözcük Bilgisi
        r'\b(sözcük|kelime|anlam|eş\s*anlam|yakın\s*anlam|karşıt\s*anlam|zıt\s*anlam|sesteş|eş\s*sesli|gerçek\s*anlam|mecaz\s*anlam|yan\s*anlam|somut|soyut|terim|deyim|atasözü|özdeyiş)\b',
        r'\b(ad|isim|özel\s*isim|cins\s*isim|soyut\s*isim|somut\s*isim|topluluk\s*ismi|hal\s*eki|çoğul\s*eki|iyelik\s*eki|tamlayan|tamlanan)\b',
        r'\b(sıfat|niteleme|belirtme|işaret|sayı|belgisiz|soru|yapım\s*eki|çekim\s*eki|ad\s*soylu|fiil\s*soylu)\b',
        r'\b(zamir|kişi\s*zamiri|dönüşlülük|işaret\s*zamiri|belgisiz\s*zamir|soru\s*zamiri)\b',
        r'\b(zarf|durum|zaman|yer|yön|miktar|soru\s*zarfı|bağlaç|edat|ilgeç|ünlem)\b',
        r'\b(fiil|eylem|kip|zaman|şart|istek|gereklilik|emir|bildirme|haber|tasarlama|olumlu|olumsuz|soru|yapı|basit|türemiş|birleşik|ek\s*fiil|ek\s*eylem)\b',
        r'\b(fiilimsi|isim\s*fiil|sıfat\s*fiil|zarf\s*fiil|ortaç|ulaç|bağ\s*fiil)\b',
        # Cümle Bilgisi
        r'\b(cümle|özne|yüklem|nesne|dolaylı\s*tümleç|zarf\s*tümleci|belirtili\s*nesne|belirtisiz\s*nesne|edat\s*tümleci)\b',
        r'\b(cümle\s*türleri|devrik|kurallı|isim\s*cümlesi|fiil\s*cümlesi|olumlu|olumsuz|soru|ünlem|yapısına\s*göre|anlamına\s*göre)\b',
        r'\b(basit\s*cümle|birleşik\s*cümle|bağlı\s*cümle|girişik\s*cümle|sıralı\s*cümle|şartlı|ki\'li|iç\s*içe)\b',
        # Anlatım Bozuklukları
        r'\b(anlatım\s*bozukluğu|anlam\s*belirsizliği|gereksiz\s*sözcük|özne\s*yüklem\s*uyumsuzluğu|yapı\s*bozukluğu|mantık\s*hatası|çelişki|sözcüğün\s*yanlış\s*kullanımı|bağdaşıklık|bağlaç\s*eksikliği|tamlama\s*yanlışı|ekeylem\s*eksikliği)\b',
        # Paragraf
        r'\b(paragraf|ana\s*düşünce|ana\s*fikir|yardımcı\s*düşünce|konu|başlık|giriş|gelişme|sonuç|düşüncenin\s*akışı|anlam\s*bütünlüğü)\b',
        r'\b(düşünceyi\s*geliştirme|tanımlama|örnekleme|karşılaştırma|tanık\s*gösterme|sayısal\s*veri|benzetme)\b',
        r'\b(anlatım\s*biçimi|öyküleyici|betimleyici|tartışmacı|açıklayıcı|kanıtlayıcı)\b',
        # Yazım ve Noktalama
        r'\b(yazım\s*kuralları|imla|büyük\s*harf|küçük\s*harf|bitişik|ayrı|bağlaç|ki|de|da|mi|satır\s*sonu|kesme\s*işareti|kısaltma|sayı|tarih|adres)\b',
        r'\b(noktalama|nokta|virgül|noktalı\s*virgül|iki\s*nokta|üç\s*nokta|soru\s*işareti|ünlem|tırnak|parantez|kısa\s*çizgi|uzun\s*çizgi)\b',
        # Ses Bilgisi
        r'\b(ses\s*bilgisi|ünlü|ünsüz|hece|vurgu|tonlama|büyük\s*ünlü|küçük\s*ünlü|ünlü\s*daralması|ünlü\s*düşmesi|ünsüz\s*benzeşmesi|ünsüz\s*yumuşaması|kaynaştırma\s*ünsüzü)\b',
    ],
    'Edebiyat': [
        # Edebiyat Bilgileri
        r'\b(edebiyat|edebi\s*metin|sanatsal\s*metin|edebi\s*tür|edebi\s*akım|edebiyat\s*tarihi|dönem|yazar|şair|eser|yapıt)\b',
        # Şiir
        r'\b(şiir|nazım|manzume|beyit|dörtlük|kıta|bent|mısra|dize|ölçü|aruz|hece|serbest\s*ölçü|durak|kafiye|redif|uyak|tam|yarım|zengin|tunç|cinaslı)\b',
        r'\b(nazım\s*biçimi|gazel|kaside|mesnevi|rubai|tuyuğ|şarkı|murabba|müstezat|kıta|muhammes|terkibibent|terciibent)\b',
        r'\b(halk\s*şiiri|âşık|mani|koşma|semai|varsağı|destan|türkü|ninni|ağıt|tekke|tasavvuf|ilahi|nefes|nutuk|şathiye|deme|devriye)\b',
        r'\b(divan\s*şiiri|divan|aruz|nazım\s*nesir|inşa|münşeat|mazmun|tasavvuf|lirik|epik|didaktik|pastoral|satirik|dramatik)\b',
        # Düzyazı Türleri
        r'\b(düzyazı|nesir|öykü|hikaye|roman|deneme|makale|fıkra|söyleşi|eleştiri|gezi\s*yazısı|biyografi|otobiyografi|anı|günlük|mektup)\b',
        r'\b(masal|fabl|efsane|destan|halk\s*hikayesi|meddah|karagöz|ortaoyunu|manzum\s*hikaye|tiyatro|trajedi|komedi|dram)\b',
        # Söz Sanatları
        r'\b(söz\s*sanatı|edebi\s*sanat|mecaz|mecazımürsel|istiare|açık\s*istiare|kapalı\s*istiare|teşbih|benzetme|kinaye|tariz|teşhis|kişileştirme|intak|konuşturma|mübalağa|abartma|hüsnütalil|güzel\s*neden|tecahüliarif|bilmezden\s*gelme|tezat|tenasüp|uygunluk|leff\s*ü\s*neşir|irsalimesel|cinas|akrostiş|seci|aliterasyon|asonans)\b',
        # Edebiyat Akımları
        r'\b(klasisizm|romantizm|realizm|natüralizm|parnasizm|sembolizm|empresyonizm|ekspresyonizm|kübizm|dadaizm|sürrealizm|fütürizm|egzistansiyalizm|postmodernizm)\b',
        # Türk Edebiyatı Dönemleri
        r'\b(islamiyet\s*öncesi|islamiyet\s*sonrası|geçiş\s*dönemi|divan|halk|tanzimat|servetifünun|fecriati|milli|cumhuriyet)\b',
        r'\b(orhun|göktürk|uygur|kutadgu\s*bilig|divan\s*u\s*lügatit\s*türk|atabetül\s*hakayık|divan\s*ı\s*hikmet)\b',
        r'\b(tanzimat\s*birinci|tanzimat\s*ikinci|şinasi|namık\s*kemal|ziya\s*paşa|ahmet\s*mithat|abdülhak\s*hamit|recaizade\s*ekrem|nabizade\s*nazım|muallim\s*naci|samipaşazade)\b',
        r'\b(servetifünun|edebiyatı\s*cedide|tevfik\s*fikret|cenap\s*şahabettin|halit\s*ziya|mehmet\s*rauf|hüseyin\s*cahit)\b',
        r'\b(fecriati|ahmet\s*haşim|beş\s*hececiler|yedi\s*meşaleciler|garip|ikinci\s*yeni)\b',
        r'\b(milli\s*edebiyat|genç\s*kalemler|ömer\s*seyfettin|ziya\s*gökalp|mehmet\s*emin|halide\s*edip|yakup\s*kadri|reşat\s*nuri|refik\s*halit)\b',
        r'\b(cumhuriyet|nazım\s*hikmet|orhan\s*veli|oktay\s*rifat|melih\s*cevdet|ahmet\s*hamdi|necip\s*fazıl|peyami\s*safa|sait\s*faik|kemal\s*tahir|orhan\s*kemal|yaşar\s*kemal|fazıl\s*hüsnü|behçet\s*necatigil|attila\s*ilhan|cemal\s*süreya)\b',
    ],
    'Tarih': [
        # Tarih Bilimine Giriş
        r'\b(tarih|tarih\s*bilimi|kaynak|belge|kanıt|kronoloji|takvim|çağ|dönem|asır|yüzyıl|milat|hicri|rumi|miladi|arkeoloji|paleografi|nümizmatik|epigrafi|etnografya)\b',
        # İlk Çağ
        r'\b(sümer|akad|babil|asur|elam|hitit|frig|lidya|urartu|med|pers|mısır|firavun|piramit|sfenks|mumyalama|nil|mezopotamya|çivi\s*yazısı|hiyeroglif|hammurabi)\b',
        r'\b(yunan|helen|atina|sparta|demokratia|polis|tiranlık|oligarşi|kolonizasyon|pers\s*savaşları|peloponnes|makedonya|büyük\s*iskender|helenistik)\b',
        r'\b(roma|cumhuriyet|imparatorluk|sezar|augustus|pax\s*romana|hristiyanlık|bizans|doğu\s*roma|konstantinopolis)\b',
        # İslam Tarihi
        r'\b(islam|hz\.\s*muhammed|peygamber|mekke|medine|hicret|vahiy|kur\'an|hadis|sünnet|dört\s*halife|emevi|abbasi|endülüs|haçlı\s*seferleri|kudüs|selahaddin|moğol|timur)\b',
        # Türk Tarihi
        r'\b(türk|orta\s*asya|göç|anayurt|hun|göktürk|uygur|kök\s*tengri|orhun|bilge\s*kağan|kül\s*tigin|tonyukuk|mete\s*han|attila|kavimler\s*göçü)\b',
        r'\b(karahanlı|gazneli|selçuklu|büyük\s*selçuklu|anadolu\s*selçuklu|malazgirt|alparslan|melikşah|nizamiye|danişmentli|artuklu|mengücekli|saltuklu)\b',
        # Osmanlı
        r'\b(osmanlı|beylik|kuruluş|yükselme|duraklama|gerileme|dağılma|padişah|sultan|divan|vezir|sadrazam|şeyhülislam|kazasker|defterdar|nişancı|kaptan\s*paşa|yeniçeri|devşirme|tımar|zeamet|has|miri\s*arazi|iltizam)\b',
        r'\b(fatih|kanuni|süleyman|osman\s*bey|orhan|murat|bayezid|yavuz|selim|mehmet|mahmut|abdülhamit|mehmetçik)\b',
        r'\b(edirne|istanbul|fetih|viyana|preveze|mohaç|ridaniye|çaldıran|mercidabık|niğbolu|kosova|varna|belgrad)\b',
        r'\b(islahat|lale\s*devri|tanzimat|ferman|ıslahat|meşrutiyet|meclis|anayasa|jön\s*türkler|ittihat\s*terakki|kanuniesasi)\b',
        r'\b(trablusgarp|balkan|birinci\s*dünya|sarıkamış|çanakkale|kut\s*ül\s*amare|kafkas|filistin|suriye|mütareke|mondros|sevr)\b',
        # Milli Mücadele ve Cumhuriyet
        r'\b(milli\s*mücadele|kurtuluş\s*savaşı|işgal|kuvayi\s*milliye|mustafa\s*kemal|atatürk|erzurum|sivas|amasya|kongre|heyet\s*i\s*temsiliye|tbmm|ankara)\b',
        r'\b(sakarya|dumlupınar|büyük\s*taarruz|inönü|başkomutanlık|mudanya|lozan|cumhuriyet\s*ilanı|saltanat|hilafet)\b',
        r'\b(inkılap|devrim|harf|tevhid\s*i\s*tedrisat|tekke|şapka|kılık\s*kıyafet|laiklik|soyadı|kadın\s*hakları|ölçü|takvim|türk\s*tarih|türk\s*dil|halkevleri)\b',
        r'\b(atatürk\s*ilkeleri|cumhuriyetçilik|milliyetçilik|halkçılık|devletçilik|laiklik|inkılapçılık|atatürkçülük)\b',
        # Çağdaş Türk ve Dünya
        r'\b(ikinci\s*dünya|soğuk\s*savaş|nato|demir\s*perde|berlin|küba|korea|vietnam|birleşmiş\s*milletler|avrupa\s*birliği|küreselleşme)\b',
        r'\b(demokrat\s*parti|çok\s*partili|menderes|darbe|anayasa|referandum|seçim|demokrasi)\b',
    ],
    'Coğrafya': [
        # Doğa Coğrafyası
        r'\b(coğrafya|harita|ölçek|projeksiyon|koordinat|enlem|boylam|paralel|meridyen|ekvator|kutup|yükselti|kabartma|izohips)\b',
        r'\b(dünya|yerküre|yer\s*kabuğu|manto|çekirdek|levha|tektonik|deprem|fay|volkan|magma|lav)\b',
        r'\b(yer\s*şekli|dağ|ova|plato|yayla|vadi|kanyon|delta|kıyı|körfez|yarımada|ada|burun|akarsu|göl|deniz|okyanus|buzul|karstik)\b',
        r'\b(iç\s*kuvvet|dış\s*kuvvet|aşınma|erozyon|rüzgar|akarsu|buzul|dalga|kimyasal|fiziksel|biyolojik)\b',
        r'\b(atmosfer|iklim|hava|sıcaklık|basınç|rüzgar|nem|yağış|bulut|cephe|alçak\s*basınç|yüksek\s*basınç|hava\s*hareketi)\b',
        r'\b(iklim\s*tipi|ekvatoral|muson|tropikal|subtropikal|akdeniz|karasal|okyanusal|sert\s*karasal|kutup|çöl|step|tundra)\b',
        r'\b(bitki\s*örtüsü|orman|çayır|savan|maki|garig|psödomaki|step|bozkır|tundra|biyom)\b',
        r'\b(toprak|humus|horizon|podzolik|kahverengi|kestane|laterit|alüvyon|verimlilik)\b',
        r'\b(su|hidroloji|su\s*döngüsü|akarsu|havza|kaynak|memba|mansap|hidrografya|yeraltı\s*suyu|akifer|göl|deniz)\b',
        # Beşeri Coğrafya
        r'\b(nüfus|nüfus\s*yoğunluğu|doğum|ölüm|nüfus\s*artışı|nüfus\s*piramidi|demografik|kentleşme|şehirleşme|göç|iç\s*göç|dış\s*göç|beyin\s*göçü|mülteci)\b',
        r'\b(yerleşme|köy|kent|şehir|metropol|megalopolis|toplu|dağınık|kırsal|kentsel)\b',
        # Ekonomik Coğrafya
        r'\b(ekonomi|tarım|hayvancılık|ormancılık|balıkçılık|madencilik|sanayi|hizmet|ticaret|turizm)\b',
        r'\b(tarım|tahıl|buğday|arpa|mısır|pirinç|pamuk|tütün|çay|fındık|zeytin|üzüm|şeker\s*pancarı|ayçiçeği|soya)\b',
        r'\b(maden|kömür|linyit|petrol|doğalgaz|bor|krom|demir|bakır|alüminyum|altın|gümüş|uranyum|toryum|mermer)\b',
        r'\b(enerji|hidroelektrik|termik|nükleer|jeotermal|rüzgar|güneş|yenilenebilir|fosil\s*yakıt)\b',
        r'\b(ulaşım|karayolu|demiryolu|denizyolu|havayolu|boru\s*hattı|liman|köprü|tünel|geçit)\b',
        # Türkiye Coğrafyası
        r'\b(türkiye|anadolu|trakya|marmara|ege|akdeniz|karadeniz|iç\s*anadolu|doğu\s*anadolu|güneydoğu)\b',
        r'\b(istanbul|ankara|izmir|bursa|antalya|adana|konya|kayseri|gaziantep|diyarbakır|erzurum|trabzon|samsun)\b',
        r'\b(toros|pontus|kaçkar|ağrı|erciyes|uludağ|spil|baba|bozdağ|munzur|nemrut|palandöken)\b',
        r'\b(fırat|dicle|kızılırmak|sakarya|yeşilırmak|seyhan|ceyhan|gediz|büyük\s*menderes|ergene|meriç)\b',
        r'\b(van|tuz|beyşehir|eğirdir|iznik|sapanca|abant|burdur|akşehir|çıldır|hazar)\b',
    ],
    'Felsefe': [
        # Felsefenin Temelleri
        r'\b(felsefe|filozof|düşünür|düşünce|akıl|us|bilgi|varlık|değer|ahlak|estetik|mantık|epistemoloji|ontoloji|axioloji|metafizik)\b',
        r'\b(antik|yunan|thales|sokrates|platon|aristoteles|herakleitos|parmenides|demokritos|epikuros|stoa|kinizm)\b',
        # Bilgi Felsefesi
        r'\b(bilgi|bilme|doğru|hakikat|kesinlik|kuşku|şüphe|bilgi\s*kaynağı|akılcılık|rasyonalizm|deneycilik|empirizm|eleştiricilik|kritisizm|sezgicilik|pragmatizm)\b',
        r'\b(özne|nesne|apriori|aposteriori|fenomen|numen|sentetik|analitik|tümdengelim|tümevarım)\b',
        # Varlık Felsefesi
        r'\b(varlık|var\s*olan|öz|töz|idea|idealizm|materyalizm|düalizm|monizm|nihilizm|fenomenoloji|varoluşçuluk|egzistansiyalizm)\b',
        # Ahlak Felsefesi
        r'\b(ahlak|etik|iyi|kötü|erdem|değer|ödev|sorumluluk|özgürlük|özerk|eudaimonia|mutluluk|haz|faydacılık|ödevci|erdem\s*etiği|deontoloji|teleoloji)\b',
        r'\b(kant|bentham|mill|nietzsche|heidegger|sartre|kierkegaard|hume|locke|descartes|spinoza|leibniz)\b',
        # Din Felsefesi
        r'\b(din|tanrı|allah|inanç|iman|teizm|deizm|ateizm|agnostisizm|panteizm|vahiy|akıl\s*yürütme|tanrı\s*kanıtları|kötülük\s*problemi)\b',
        # Siyaset Felsefesi
        r'\b(siyaset|devlet|yönetim|iktidar|egemenlik|hak|adalet|eşitlik|özgürlük|demokrasi|liberalizm|sosyalizm|anarşizm|toplum\s*sözleşmesi|birey|toplum)\b',
        r'\b(hobbes|locke|rousseau|montesquieu|marx|rawls|nozick|machiavelli)\b',
        # Sanat Felsefesi
        r'\b(estetik|sanat|güzel|güzellik|çirkin|yüce|trajik|komik|sanat\s*eseri|taklit|mimesis|yaratıcılık|dışavurum|form|biçim|ifade)\b',
        # Bilim Felsefesi
        r'\b(bilim|bilimsel\s*yöntem|hipotez|teori|yanlışlanabilirlik|doğrulanabilirlik|paradigma|pozitivizm|kuhn|popper|değişmecilik|yığıncılık)\b',
        # Mantık
        r'\b(mantık|geçerlilik|tutarlılık|çelişki|önerme|yargı|kavram|terim|akıl\s*yürütme|tümdengelim|tümevarım|çıkarım|kıyas|gerekçe|argüman|safsata)\b',
    ],
    'Din Kültürü': [
        # İslam Dini
        r'\b(din|islam|müslüman|allah|kur\'an|peygamber|hz\.\s*muhammed|sünnet|hadis|ayet|sure)\b',
        r'\b(iman|ibadet|ahlak|kelime\s*i\s*tevhid|kelime\s*i\s*şehadet|amentü|farz|vacip|sünnet|müstehap|mubah|mekruh|haram|helal)\b',
        r'\b(namaz|oruç|zekat|hac|kurban|sadaka|fitre|abdest|gusül|teyemmüm|ezan|kamet|kıble|cami|mescit|mihrap|minber|kürsü)\b',
        r'\b(ramazan|bayram|kandil|mevlid|kadir|miraç|regaip|berat|aşure|muharrem|zilhicce|arefe)\b',
        r'\b(mezhep|hanefi|şafi|maliki|hanbeli|alevilik|caferi|sünni|tasavvuf|tarikat|fıkıh|kelam|tefsir|akaid)\b',
        # Ahlak ve Değerler
        r'\b(ahlak|erdem|doğruluk|dürüstlük|adalet|merhamet|sevgi|saygı|hoşgörü|sabır|şükür|alçakgönüllülük|cömertlik|yardımlaşma)\b',
        # Diğer Dinler
        r'\b(yahudilik|hristiyanlık|budizm|hinduizm|tevrat|zebur|incil|kutsal\s*kitap|peygamber|musa|isa|ibrahim|semavi\s*din)\b',
    ],
}



def detect_topic(text: str) -> Tuple[str, Optional[str]]:
    """
    Detect topic from solution text
    Returns: (topic, subtopic)
    """
    if not text:
        return "Genel", None
    
    text_lower = text.lower()
    scores = {}
    
    for topic, patterns in TOPIC_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            score += len(matches)
        if score > 0:
            scores[topic] = score
    
    if not scores:
        return "Genel", None
    
    # Get topic with highest score
    best_topic = max(scores, key=scores.get)
    
    # Subtopic detection could be added here
    subtopic = None
    
    return best_topic, subtopic


class GeminiClient:
    """Client for Gemini API with vision capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError(
                "Gemini API key not found! "
                "Set GEMINI_API_KEY in .env file or pass it directly."
            )
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = GEMINI_MODEL
        self._request_count = 0
        self._total_time = 0.0
    
    async def solve_question(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        custom_prompt: Optional[str] = None,
    ) -> dict:
        """
        Solve a question from an image using Gemini Vision
        
        Returns:
            dict with keys: filename, success, solution, error, time_taken, topic, subtopic
        """
        prompt = custom_prompt or QUESTION_PROMPT
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
            try:
                # Create image part for Gemini new SDK
                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
                
                # Generate content with image
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=[prompt, image_part]
                    ),
                    timeout=REQUEST_TIMEOUT
                )
                
                time_taken = time.time() - start_time
                self._request_count += 1
                self._total_time += time_taken
                
                solution = response.text
                topic, subtopic = detect_topic(solution)
                
                return {
                    "filename": filename,
                    "success": True,
                    "solution": solution,
                    "error": None,
                    "time_taken": time_taken,
                    "topic": topic,
                    "subtopic": subtopic,
                }
                
            except asyncio.TimeoutError:
                console.print(f"[yellow]⏱️ Timeout for {filename}, attempt {attempt + 1}/{MAX_RETRIES}[/yellow]")
                
            except Exception as e:
                error_msg = str(e)
                console.print(f"[yellow]⚠️ Error for {filename}: {error_msg}, attempt {attempt + 1}/{MAX_RETRIES}[/yellow]")
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        time_taken = time.time() - start_time
        return {
            "filename": filename,
            "success": False,
            "solution": None,
            "error": f"Failed after {MAX_RETRIES} attempts",
            "time_taken": time_taken,
            "topic": "Genel",
            "subtopic": None,
        }
    
    def get_stats(self) -> dict:
        """Get client statistics"""
        return {
            "total_requests": self._request_count,
            "total_time": self._total_time,
            "avg_time": self._total_time / max(1, self._request_count),
        }


if __name__ == "__main__":
    # Test the client
    async def test():
        client = GeminiClient()
        print(f"Client initialized with model: {client.model_name}")
        print(client.get_stats())
        
        # Test topic detection
        test_texts = [
            "Bu soruda türev alarak çözüm yapacağız.",
            "Newton'un hareket yasaları ile kuvvet hesaplayalım.",
            "H2O molekülünün yapısını inceleyelim.",
        ]
        for text in test_texts:
            topic, subtopic = detect_topic(text)
            print(f"Text: {text[:50]}... -> Topic: {topic}")
    
    asyncio.run(test())

