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
    VALID_TOPICS,
)

console = Console()

# ── AI-based topic parsing ──────────────────────────────────────────
_TOPIC_TAG_RE = re.compile(r'\[DERS:\s*([^\]]+)\]', re.IGNORECASE)
_VALID_SET = {t.lower() for t in VALID_TOPICS}

def parse_topic_from_ai(text: str) -> Optional[str]:
    """Extract topic from [DERS: X] tag in AI response. Returns None if not found."""
    if not text:
        return None
    m = _TOPIC_TAG_RE.search(text[:500])  # only check first 500 chars
    if not m:
        return None
    raw = m.group(1).strip()
    # exact match
    for t in VALID_TOPICS:
        if raw.lower() == t.lower():
            return t
    # fuzzy: startswith
    for t in VALID_TOPICS:
        if raw.lower().startswith(t.lower()[:4]):
            return t
    return None

def strip_topic_tag(text: str) -> str:
    """Remove [DERS: X] tag from solution text so it doesn't show in UI."""
    if not text:
        return text
    return _TOPIC_TAG_RE.sub('', text, count=1).lstrip('\n').lstrip()


# ── Weighted topic patterns ─────────────────────────────────────────
# Format: (weight, pattern)
# weight 5 = very specific to this subject
# weight 3 = moderately specific
# weight 1 = generic / appears in multiple subjects
TOPIC_PATTERNS = {
    'Matematik': [
        # Temel Matematik (TYT)
        r'\b(sayılar|doğal\s*sayı|tam\s*sayı|rasyonel|irrasyonel|gerçek\s*sayı|asal\s*sayı|tek\s*sayı|çift\s*sayı|negatif|pozitif|mutlak\s*değer|ebob|ekok|bölünebilme|kalanlı\s*bölme|faktöriyel|üslü\s*sayı|köklü\s*sayı|üs|kök|radikal|ardışık\s*sayılar|sayı\s*basamakları|taban\s*aritmetiği)\b',
        r'\b(oran|orantı|yüzde|kar|zarar|faiz|maliyet|satış|kesir|ondalık|basit\s*kesir|bileşik\s*kesir|tam\s*sayılı\s*kesir|pay|payda|doğru\s*orantı|ters\s*orantı)\b',
        r'\b(denklem|bilinmeyen|eşitlik|eşitsizlik|birinci\s*derece|ikinci\s*derece|mutlak\s*değerli\s*denklem|köklü\s*denklem|üslü\s*denklem|denklem\s*sistemi|kökler\s*toplamı|kökler\s*çarpımı)\b',
        r'\b(problemler|yaş\s*problemi|işçi\s*problemi|havuz\s*problemi|hareket\s*problemi|hız\s*problemi|karışım\s*problemi|yüzde\s*problemi|kar\s*zarar|rutin\s*olmayan\s*problemler|sayı\s*kesir|grafik\s*problemleri)\b',
        r'\b(mantık|önerme|ve|veya|ya\s*da|ise|ancak\s*ve\s*ancak|totoloji|çelişki|de\s*morgan|açık\s*önerme|niceleyici)\b',
        r'\b(küme|eleman|alt\s*küme|öz\s*alt\s*küme|birleşim|kesişim|fark|tümleyen|evrensel\s*küme|venn\s*şeması|kartezyen\s*çarpım|bağıntı)\b',
        # Geometri (TYT & AYT)
        r'\b(geometri|nokta|doğru|doğru\s*parçası|ışın|açı|dar\s*açı|geniş\s*açı|dik\s*açı|düz\s*açı|tam\s*açı|komşu\s*açı|bütünler\s*açı|tümler\s*açı|iç\s*açı|dış\s*açı|ters\s*açı|yöndeş\s*açı|z\s*kuralı|m\s*kuralı|u\s*kuralı)\b',
        r'\b(üçgen|ikizkenar|eşkenar|çeşitkenar|dik\s*üçgen|dar\s*açılı|geniş\s*açılı|kenarortay|açıortay|yükseklik|çevrel\s*çember|içteğet\s*çember|dışteğet\s*çember|pisagor|öklid|benzerlik|eşlik|thales|menelaus|ceva|stewart|kosinüs\s*teoremi|sinüs\s*teoremi)\b',
        r'\b(dörtgen|çokgen|düzgün\s*çokgen|beşgen|altıgen|sekizgen|kare|dikdörtgen|paralelkenar|yamuk|dik\s*yamuk|ikizkenar\s*yamuk|deltoid|eşkenar\s*dörtgen|köşegen|çevre|alan|orta\s*taban)\b',
        r'\b(çember|daire|yarıçap|çap|teğet|kiriş|yay|merkez\s*açı|çevre\s*açı|teğet\s*kiriş\s*açı|iç\s*açı|dış\s*açı|dilim|halka|kuvvet\s*ekseni|çemberin\s*analitiği|merkezil\s*çember)\b',
        r'\b(prizma|piramit|koni|küre|silindir|küp|dikdörtgenler\s*prizması|kare\s*prizma|altıgen\s*prizma|kesik\s*koni|kesik\s*piramit|hacim|yüzey\s*alanı|katı\s*cisim|cisim\s*köşegeni)\b',
        r'\b(analitik\s*geometri|koordinat|kartezyen|x\s*ekseni|y\s*ekseni|orijin|apsis|ordinat|doğru\s*denklemi|eğim|paralel|dik|uzaklık|orta\s*nokta|simetri|öteleme|döndürme|dönüşüm\s*geometrisi)\b',
        # İleri Matematik ve Kalkülüs (AYT & Üni)
        r'\b(fonksiyon|tanım\s*kümesi|değer\s*kümesi|görüntü\s*kümesi|bire\s*bir|örten|içine|birim|sabit|artan|azalan|ters\s*fonksiyon|bileşke|periyodik|tek|çift|parçalı|mutlak\s*değer|signum|tam\s*değer)\b',
        r'\b(polinom|derece|katsayı|baş\s*katsayı|sabit\s*terim|kök|çarpanlara\s*ayırma|bölme|bölüm|kalan|horner|özdeşlik|tam\s*kare|iki\s*kare\s*farkı|küp\s*açılımı)\b',
        r'\b(ikinci\s*derece|parabol|tepe\s*noktası|simetri\s*ekseni|diskriminant|delta|köklerin\s*toplamı|köklerin\s*çarpımı|eşitsizlik\s*sistemleri|kök\s*tablosu)\b',
        r'\b(karmaşık\s*sayı|kompleks|imajiner|sanal|reel\s*kısım|sanal\s*kısım|eşlenik|argand\s*düzlemi|modül|argüment|kutupsal\s*gösterim|cis|euler\s*formülü)\b',
        r'\b(logaritma|log|ln|doğal\s*logaritma|taban|antilogaritma|üstel\s*fonksiyon|e\s*sayısı|logaritmik|mantis|karakteristik)\b',
        r'\b(trigonometri|sin|cos|tan|cot|sec|csc|sinüs|kosinüs|tanjant|kotanjant|sekant|kosekant|radyan|derece|grad|birim\s*çember|trigonometrik\s*özdeşlik|toplam\s*fark|iki\s*kat|yarım\s*açı|dönüşüm|ters\s*dönüşüm|arcsin|arccos|arctan|arccot)\b',
        r'\b(dizi|seri|aritmetik|geometrik|genel\s*terim|toplam\s*formülü|orta\s*terim|ıraksaklık|yakınsaklık|fibonacci|harmonik|kısmi\s*toplamlar|taylor|maclaurin)\b',
        r'\b(limit|sağdan\s*limit|soldan\s*limit|belirsizlik|sonsuz|süreklilik|süreksizlik|l\'hopital|sandviç\s*teoremi)\b',
        r'\b(türev|türev\s*kuralları|çarpım\s*kuralı|bölüm\s*kuralı|zincir\s*kuralı|kapalı\s*fonksiyon|parametrik|maksimum|minimum|ekstremum|yerel|mutlak|monotonluk|büküm\s*noktası|asimptot|türevli|türevsiz|teğet|normal|diferansiyel|kısmi\s*türev)\b',
        r'\b(integral|belirsiz\s*integral|belirli\s*integral|alan\s*hesabı|hacim\s*hesabı|integrasyon|kısmi\s*integral|değişken\s*değiştirme|riemann\s*toplamı|eğri\s*uzunluğu|yüzey\s*alanı|katlı\s*integral)\b',
        r'\b(olasılık|kombinasyon|permütasyon|faktöriyel|venn|şartlı\s*olasılık|koşullu|bağımsız\s*olay|bağımlı\s*olay|deney|örneklem|olay|beklenen\s*değer|binom|dağılım|normal\s*dağılım|poisson)\b',
        r'\b(istatistik|aritmetik\s*ortalama|geometrik\s*ortalama|harmonik\s*ortalama|medyan|mod|tepe\s*değer|ortanca|standart\s*sapma|varyans|çeyrekler\s*açıklığı|histogram|frekans|veri\s*grubu|açıklık)\b',
        r'\b(matris|determinant|birim\s*matris|ters\s*matris|transpose|transpoze|skaler|satır|sütun|kare\s*matris|kofaktör|minör|sarrus|rank|lineer\s*denklem|cramer|özdeğer|özvektör)\b',
        # İleri Semboller ve Notasyonlar
        r'(?:x\s*[=+\-*/]\s*\d|\d+\s*[+\-*/]\s*\d+|√|∑|∫|∬|∭|∂|∇|π|∞|≤|≥|≠|≡|≈|∈|∉|⊂|⊃|⊆|∪|∩|∅|∀|∃|⇒|⇔)',
    ],
    'Fizik': [
        # Fizik Bilimine Giriş & Vektörler
        r'\b(fizik|birim|ölçme|büyüklük|skaler|vektörel|si\s*birimi|metre|kilogram|saniye|newton|joule|watt|pascal|hertz|coulomb|amper|volt|ohm|boyut\s*analizi|vektör|bileşke|uç\s*uca|paralelkenar|skaler\s*çarpım|vektörel\s*çarpım)\b',
        # İleri Mekanik & Kinematik
        r'\b(hareket|kinematik|dinamik|konum|yer\s*değiştirme|yol|hız|sürat|ivme|düzgün\s*hareket|ivmeli\s*hareket|serbest\s*düşme|düşey\s*atış|yatay\s*atış|eğik\s*atış|bağıl\s*hız|nehir\s*problemi|dairesel\s*hareket|açısal\s*hız|açısal\s*ivme|merkezcil|merkezkaç|kepler|uydu|kütleçekim)\b',
        r'\b(kuvvet|newton|kütle|ağırlık|sürtünme|gerilme|normal\s*kuvvet|yer\s*çekimi|bileşke|bileşen|atwood|eğik\s*düzlem|dinamometre|eylemsizlik|etki\s*tepki|yay\s*sabiti|hooke)\b',
        r'\b(enerji|kinetik\s*enerji|potansiyel\s*enerji|esneklik\s*potansiyel|mekanik\s*enerji|iş|güç|verim|enerjinin\s*korunumu|esnek\s*çarpışma|esnek\s*olmayan|balistik\s*sarkaç)\b',
        r'\b(momentum|itme|impuls|momentumun\s*korunumu|çarpışma|geri\s*tepme|roket|açısal\s*momentum|eylemsizlik\s*momenti|dönme\s*kinetiği|yuvarlanma)\b',
        r'\b(tork|moment|denge|kütle\s*merkezi|ağırlık\s*merkezi|kaldıraç|makara|palanga|eğik\s*düzlem|çıkrık|vida|kasnak|dişli|statik|devrilme|lami\s*teoremi)\b',
        r'\b(basınç|katı\s*basıncı|sıvı\s*basıncı|gaz\s*basıncı|pascal|açık\s*hava|barometre|manometre|kaldırma\s*kuvveti|arşimet|yüzey\s*gerilimi|kılcallık|adezyon|kohezyon|bernoulli|akışkanlar|toricelli)\b',
        # İleri Termodinamik
        r'\b(ısı|sıcaklık|termodinamik|celcius|kelvin|fahrenheit|termometre|ısı\s*kapasitesi|öz\s*ısı|kalori|joule|kalorimetri|faz\s*değişimi|erime|donma|buharlaşma|yoğuşma|süblimleşme|kırağılaşma|gizli\s*ısı|hal\s*değişimi|üçlü\s*nokta|kritik\s*sıcaklık|entalpi|entropi|karnot|ideal\s*gaz|izotermal|izobarik|izokorik|adyabatik)\b',
        r'\b(ısı\s*iletimi|konveksiyon|ışınım|iletken|yalıtkan|genleşme|boyca\s*genleşme|hacimce\s*genleşme|yüzeyce\s*genleşme|stefan\s*boltzmann)\b',
        # Dalgalar ve Optik
        r'\b(dalga|titreşim|frekans|periyot|dalga\s*boyu|genlik|hız|boyuna\s*dalga|enine\s*dalga|mekanik\s*dalga|elektromanyetik\s*dalga|yay|su|deprem|girişim|katar|düğüm|kırınım|doppler|vuru)\b',
        r'\b(ses|ses\s*dalgası|ses\s*hızı|yankı|rezonans|ultrason|infrason|desibel|şiddet|tını)\b',
        r'\b(ışık|optik|aydınlanma|ışık\s*şiddeti|ışık\s*akısı|lüks|yansıma|kırılma|kırılma\s*indisi|snell|tam\s*yansıma|sınır\s*açısı|görünür\s*derinlik|ayna|düz\s*ayna|çukur\s*ayna|tümsek\s*ayna|mercek|ince\s*kenarlı|kalın\s*kenarlı|odak|odak\s*uzaklığı|büyütme|görüntü|prizma|renk|çift\s*yarık|tek\s*yarık|young\s*deneyi|polarizasyon)\b',
        # İleri Elektromanyetizma
        r'\b(elektrik|yük|coulomb|elektron|proton|iletken|yalıtkan|yarı\s*iletken|topraklama|elektroskop|elektriklenme|sürtünme|dokunma|etki|faraday\s*kafesi)\b',
        r'\b(elektrik\s*alan|elektrik\s*potansiyel|potansiyel\s*fark|gerilim|volt|eşpotansiyel|gauss\s*yasası|sığa|kondansatör|farad|dielektrik|sığaç|yük\s*korunumu|elektrostatik)\b',
        r'\b(akım|devre|direnç|ohm|iletken|özdirenç|reosta|seri\s*bağlama|paralel\s*bağlama|kirchhoff|ampermetre|voltmetre|wheatstone|kısa\s*devre|üreteç|emk|iç\s*direnç|elektriksel\s*güç|joule\s*ısınması)\b',
        r'\b(manyetizma|mıknatıs|manyetik\s*alan|manyetik\s*kuvvet|akım\s*geçen\s*tel|solenoid|bobin|elektromıknatıs|lorentz|sağ\s*el\s*kuralı|amper\s*yasası|biot\s*savart|manyetik\s*akı|weber)\b',
        r'\b(indüksiyon|özindüksiyon|faraday|lenz|alternatif\s*akım|transformatör|etkin\s*değer|maksimum\s*değer|empedans|kapasitans|indüktans|rezonans|rcl\s*devresi|eddy\s*akımları)\b',
        # Modern Fizik ve Kuantum
        r'\b(atom|çekirdek|elektron|proton|nötron|kütle\s*numarası|atom\s*numarası|izotop|radyoaktivite|alfa|beta|gama|yarı\s*ömür|fisyon|füzyon|bağlanma\s*enerjisi|kütle\s*defekti)\b',
        r'\b(einstein|özel\s*görelilik|izafiyet|zaman\s*genişlemesi|uzunluk\s*büzülmesi|kütle\s*enerji|kara\s*cisim|wien|planck|foton|fotoelektrik|eşik\s*enerjisi|iş\s*fonksiyonu|compton|de\s*broglie|kuantum|schrödinger|heisenberg|belirsizlik|lazer|yarı\s*iletken|diyot|transistör|süperiletken)\b',
    ],
    'Kimya': [
        # Kimya Bilimi & Temel Kavramlar
        r'\b(kimya|madde|element|bileşik|karışım|homojen|heterojen|saf\s*madde|atom|molekül|simge|formül|allotrop|simya|damıtma|özütleme|kristallendirme|kromatografi)\b',
        # Atom, Periyodik Tablo ve Kuantum Kimyası
        r'\b(atom|dalton|thomson|rutherford|bohr|kuantum|orbital|baş\s*kuantum|açısal\s*momentum|manyetik\s*kuantum|spin|hund|pauli|aufbau|enerji\s*seviyesi|kabuk|alt\s*kabuk|elektron|proton|nötron|kütle\s*numarası|atom\s*numarası|izotop|izobar|izoton|değerlik\s*elektron)\b',
        r'\b(periyodik\s*tablo|periyot|grup|alkali|toprak\s*alkali|halojen|soy\s*gaz|metal|ametal|yarı\s*metal|geçiş\s*metali|aktinit|lantanit|atom\s*yarıçapı|iyonlaşma\s*enerjisi|elektron\s*ilgisi|elektronegatiflik|metalik\s*aktiflik|ametalik\s*aktiflik)\b',
        # Kimyasal Türler Arası Etkileşimler
        r'\b(kimyasal\s*bağ|iyonik\s*bağ|kovalent\s*bağ|polar|apolar|koordine\s*kovalent|metalik\s*bağ|lewis|oktet|dublet|sigma|pi|hibritleşme|sp3|sp2|sp|molekül\s*geometrisi|vsepr|rezonans)\b',
        r'\b(zayıf\s*etkileşim|van\s*der\s*waals|dipol|indüklenmiş|london|hidrojen\s*bağı|moleküller\s*arası)\b',
        # Stokiyometri ve Hesaplamalar
        r'\b(tepkime|reaksiyon|denklem|denkleştirme|katsayı|reaktif|ürün|yanma|sentez|analiz|yer\s*değiştirme|nötürleşme|çökelme|redoks|yükseltgenme|indirgenme|yükseltgenme\s*basamağı)\b',
        r'\b(mol|avogadro|mol\s*kütlesi|akb|bağıl\s*atom\s*kütlesi|molalite|molarite|yüzde\s*derişim|ppm|ppb|verim|sınırlayan\s*bileşen|stokiyometri|ampirik\s*formül|molekül\s*formülü)\b',
        # Maddenin Halleri ve Gazlar
        r'\b(gaz|ideal\s*gaz|gerçek\s*gaz|basınç|sıcaklık|hacim|mol\s*sayısı|avogadro\s*yasası|boyle|charles|gay\s*lussac|dalton|kısmi\s*basınç|graham|difüzyon|efüzyon|kinetik\s*teori|kök\s*ortalama\s*kare|sıkışabilirlik\s*faktörü|faz\s*diyagramı|buhar|kritik\s*sıcaklık)\b',
        # Sıvı Çözeltiler
        r'\b(çözelti|çözücü|çözünen|doymuş|doymamış|aşırı\s*doymuş|çözünürlük|derişim|seyreltme|deriştirme|buhar\s*basıncı|kaynama\s*noktası\s*yükselmesi|ebülyoskopi|donma\s*noktası\s*düşmesi|kriyoskopi|ozmoz|ozmotik\s*basınç|koligatif\s*özellik|çözünürlük\s*çarpımı)\b',
        # İleri Asitler ve Bazlar
        r'\b(asit|baz|arrhenius|bronsted|lowry|lewis|kuvvetli\s*asit|zayıf\s*asit|kuvvetli\s*baz|zayıf\s*baz|ph|poh|otoiyonizasyon|su\s*sabiti|kw|ka|kb|indikatör|turnusol|fenolftalein|nötürleşme|hidroliz|tampon\s*çözelti|titrasyon|eşdeğerlik\s*noktası|dönüm\s*noktası)\b',
        # Termodinamik / Kimyasal Tepkimelerde Enerji
        r'\b(termodinamik|entalpi|entropi|serbest\s*enerji|gibbs|ekzotermik|endotermik|hess\s*yasası|bağ\s*enerjisi|standart\s*oluşum|kalorimetri|sistem|ortam|durum\s*fonksiyonu)\b',
        # Kimyasal Kinetik
        r'\b(tepkime\s*hızı|hız\s*bağıntısı|hız\s*sabiti|aktifleşme\s*enerjisi|katalizör|aktivasyon|derişim|sıcaklık|yüzey\s*alanı|tepkime\s*mekanizması|yavaş\s*basamak|hızlı\s*basamak|ara\s*ürün|aktifleşmiş\s*kompleks)\b',
        # Kimyasal Denge
        r'\b(kimyasal\s*denge|tersinir|dinamik\s*denge|denge\s*sabiti|kc|kp|le\s*chatelier|denge\s*kayması|çözünürlük\s*çarpımı|ksp|ortak\s*iyon|çökelme\s*şartı|qc)\b',
        # İleri Elektrokimya
        r'\b(elektrokimya|pil|galvanik\s*pil|elektroliz|anot|katot|elektrot|yarı\s*pil|standart\s*potansiyel|indirgenme\s*potansiyeli|yükseltgenme\s*potansiyeli|faraday|nernst\s*eşitliği|derişim\s*pili|tuz\s*köprüsü|korozyon|katodik\s*koruma|kurban\s*elektrot|akü|lityum\s*iyon)\b',
        # İleri Organik Kimya
        r'\b(organik\s*kimya|karbon|hidrokarbon|alifatik|alkan|alken|alkin|sikloalkan|doymuş|doymamış|izomer|yapı\s*izomeri|geometrik\s*izomeri|cis\s*trans|optik\s*izomer|kiral|enantiyomer|fonksiyonel\s*grup|homolog\s*sıra|radikal|karbokatyon|karbanyon|nükleofil|elektrofil|markovnikov|zaitsev|katılma|ayrılma|yer\s*değiştirme|polimerleşme)\b',
        r'\b(alkol|eter|aldehit|keton|karboksil\s*asit|ester|amin|amit|aromatik|benzen|toluen|fenol|anilin|naftalin|polimer|kauçuk|plastik|petrokimya|sabun|deterjan|protein|karbonhidrat|yağ)\b',
        # Formüller
        r'(?:H2O|CO2|NaCl|HCl|NaOH|H2SO4|HNO3|H3PO4|NH3|CH4|C2H6|C2H4|C2H2|C6H12O6|C6H6|COOH|OH|NH2|CH3|C2H5)',
    ],
    'Biyoloji': [
        # Yaşam Bilimi ve İnorganik/Organik Bileşikler
        r'\b(canlıların\s*ortak\s*özellikleri|metabolizma|anabolizma|katabolizma|homeostazi|adaptasyon|üreme|boşaltım|solunum|beslenme|ototrof|heterotrof)\b',
        r'\b(karbonhidrat|monosakkarit|disakkarit|polisakkarit|glikoz|fruktoz|galaktoz|maltoz|sükroz|laktoz|nişasta|glikojen|selüloz|kitin|glikozit\s*bağı)\b',
        r'\b(protein|amino\s*asit|peptit|polipeptit|enzim|substrat|aktif\s*merkez|koenzim|kofaktör|inhibitör|denatürasyon|renatürasyon|peptit\s*bağı)\b',
        r'\b(yağ|lipit|yağ\s*asidi|doymuş|doymamış|gliserol|trigliserit|fosfolipit|steroit|kolesterol|ester\s*bağı)\b',
        r'\b(nükleik\s*asit|DNA|RNA|nükleotit|adenin|guanin|sitozin|timin|urasil|riboz|deoksiriboz|çift\s*sarmal|baz\s*eşleşmesi|replikasyon|transkripsiyon|translasyon|mRNA|tRNA|rRNA|fosfodiester|hidrojen\s*bağı)\b',
        r'\b(vitamin|mineral|su|organik|inorganik|ATP|ADP|enerji|fosforilasyon|defosforilasyon)\b',
        # Hücre Yapısı ve Madde Geçişleri
        r'\b(hücre|prokaryot|ökaryot|hücre\s*zarı|sitoplazma|çekirdek|organel|mitokondri|kloroplast|ribozom|endoplazmik\s*retikulum|golgi|lizozom|vakuol|koful|sentrozom|sentriyol|hücre\s*duvarı|çeper|plazmit|sitoiskelet|mikrotübül|mikrofilament|ara\s*filament)\b',
        r'\b(difüzyon|osmoz|aktif\s*taşıma|pasif\s*taşıma|kolaylaştırılmış\s*difüzyon|endositoz|ekzositoz|fagositoz|pinositoz|turgor|plazmoliz|deplazmoliz|izotonik|hipertonik|hipotonik|osmotik\s*basınç|emme\s*kuvveti)\b',
        # Hücre Bölünmeleri
        r'\b(hücre\s*bölünmesi|mitoz|mayoz|interfaz|profaz|metafaz|anafaz|telofaz|kromozom|kromatit|sentromer|kinetokor|iğ\s*ipliği|sitokinez|ara\s*lamel|boğumlanma|homolog|tetrat|sinapsis|kiyazma|krossing\s*over|rekombinasyon|haploit|diploit|somatik|gamet|partenogenez)\b',
        # Kalıtım ve Biyoteknoloji
        r'\b(genetik|kalıtım|mendel|gen|alel|dominant|baskın|resesif|çekinik|genotip|fenotip|homozigot|heterozigot|çaprazlama|monohibrit|dihibrit|kontrol\s*çaprazlaması|bağımsız\s*açılım|soy\s*ağacı|eş\s*baskınlık|eksik\s*baskınlık|çoklu\s*alel|kan\s*grubu|rh\s*faktörü|eşeye\s*bağlı|renk\s*körlüğü|hemofili)\b',
        r'\b(mutasyon|gen\s*mutasyonu|kromozom\s*mutasyonu|delesyon|duplikasyon|inversiyon|translokasyon|nokta\s*mutasyonu|mutagen|poliploidi|varyasyon)\b',
        r'\b(biyoteknoloji|genetik\s*mühendisliği|gen\s*klonlama|rekombinant\s*DNA|plazmit|restriksiyon\s*enzimi|ligaz|pcr|elektroforez|transgenik|gdo|gen\s*tedavisi|aşı|kök\s*hücre|klonlama)\b',
        # Sınıflandırma ve Biyoçeşitlilik
        r'\b(sınıflandırma|taksonomi|sistematik|alem|şube|sınıf|takım|aile|familya|cins|tür|binomiyal|ikili\s*adlandırma|filogenetik|suni\s*sınıflandırma|homolog\s*organ|analog\s*organ)\b',
        r'\b(hayvan|omurgalı|omurgasız|memeli|kuş|sürüngen|iki\s*yaşamlı|amfibi|balık|böcek|eklembacaklı|solucan|sölenter|sünger|derisidikenli|bitki|damarlı|damarsız|tohumlu|tohumsuz|açık\s*tohumlu|kapalı\s*tohumlu|tek\s*çenekli|çift\s*çenekli|mantar|fungi|protista|amip|öglena|paramesyum|monera|bakteri|arkea|virüs|prion|faj)\b',
        # Bitki Biyolojisi
        r'\b(bitki|kök|gövde|yaprak|çiçek|meyve|tohum|epidermis|periderm|kütikula|stoma|lentisel|hidatot|meristem|kambiyum|parankima|kollenkima|sklerenkima|ksilem|floem|odun\s*borusu|soymuk\s*borusu|kılcal\s*kök|kaspari\s*şeridi)\b',
        r'\b(fotosentez|kloroplast|klorofil|ışık\s*reaksiyonu|karanlık\s*reaksiyon|calvin|stomat|mezofil|tilakoit|granum|stroma|fotofosforilasyon|rubisko|kemosentez)\b',
        r'\b(transpirasyon|terleme|gutasyon|turgor|kılcallık|kohezyon\s*gerilim|basınç\s*akış)\b',
        r'\b(çimlenme|büyüme|gelişme|tropizma|fototropizma|geotropizma|nasti|fotonasti|sismonasti|oksin|sitokinin|giberellin|absisik\s*asit|etilen|tozlaşma|döllenme|çift\s*döllenme|eşeyli\s*üreme|eşeysiz\s*üreme|vejetatif|çelikle|daldırma|aşılama)\b',
        # İnsan Fizyolojisi / Sistemler
        r'\b(sindirim|mekanik\s*sindirim|kimyasal\s*sindirim|ağız|tükürük|yemek\s*borusu|peristaltik|mide|pepsin|mukus|gastrin|ince\s*bağırsak|villus|mikrovillus|kalın\s*bağırsak|karaciğer|pankreas|safra|amilaz|lipaz|tripsin|emilim|şikomikron)\b',
        r'\b(solunum|akciğer|soluk\s*borusu|trake|bronş|bronşiyol|alveol|diyafram|plevra|gaz\s*değişimi|hemoglobin|oksijen|karbondioksit|oksihemoglobin|karbaminohemoglobin|karbonik\s*anhidraz)\b',
        r'\b(hücresel\s*solunum|oksijenli|oksijensiz|fermantasyon|laktik\s*asit|etil\s*alkol|glikoliz|krebs|sitrik\s*asit|ets|oksidatif\s*fosforilasyon|kemiozmoz|mitokondri|matriks|krista)\b',
        r'\b(dolaşım|kalp|kulakçık|atrium|karıncık|ventrikül|kapakçık|triküspit|biküspit|yarım\s*ay|sinoatriyal|atriyoventriküler|atardamar|toplardamar|kılcal\s*damar|büyük\s*kan\s*dolaşımı|küçük\s*kan\s*dolaşımı|tansiyon|nabız|kan|eritrosit|alyuvar|lökosit|akyuvar|trombosit|kan\s*pulcuğu|plazma|antijen|antikor|bağışıklık|doğal\s*bağışıklık|kazanılmış\s*bağışıklık|aşı|serum|lenf|lenf\s*düğümü|dalak|timüs)\b',
        r'\b(boşaltım|böbrek|korteks|medulla|pelvis|nefron|glomerül|bowman\s*kapsülü|proksimal|henle|distal|toplama\s*kanalı|süzülme|geri\s*emilim|salgılama|aktif\s*boşaltım|idrar|üre|ürik\s*asit|amonyak|adh|vazopressin|aldosteron)\b',
        r'\b(sinir|nöron|akson|dendrit|hücre\s*gövdesi|miyelin|schwann|ranvier|sinaps|nörotransmitter|impuls|aksiyon\s*potansiyeli|depolarizasyon|repolarizasyon|polarizasyon|merkezi\s*sinir|periferik|otonom|sempatik|parasempatik|duyu|hareket|motor|ara\s*nöron|refleks|meninges|beyin|uç\s*beyin|korteks|ara\s*beyin|talamus|hipotalamus|orta\s*beyin|arka\s*beyin|beyincik|pons|omurilik\s*soğanı|omurilik)\b',
        r'\b(duyu\s*organları|göz|kornea|iris|göz\s*bebeği|mercek|retina|sarı\s*benek|kör\s*nokta|çubuk|koni|miyop|hipermetrop|astigmat|kulak|kulak\s*zarı|çekiç|örs|üzengi|kohlea|salyangoz|korti|yarım\s*daire\s*kanalları|tulumcuk|kesecik|burun|sarı\s*bölge|tat|papilla|deri|epidermis|dermis|reseptör|mekanoreseptör|kemoreseptör|fotoreseptör|termoreseptör)\b',
        r'\b(endokrin|hormon|hipotalamus|releasing|hipofiz|sth|tsh|acth|fsh|lh|lth|msh|oksitosin|adh|tiroit|tiroksin|kalsitonin|paratiroit|parathormon|adrenal|böbrek\s*üstü|kortizol|aldosteron|adrenalin|noradrenalin|pankreas|insülin|glukagon|eşeysel\s*bez|östrojen|progesteron|testosteron|feedback|geribildirim)\b',
        r'\b(üreme|eşeyli|eşeysiz|mitoz|mayoz|gametogenez|spermatogenez|oogenez|sperm|yumurta|zigot|embriyo|fetüs|plasenta|amnion|döllenme|segmentasyon|morula|blastula|gastrula|organogenez|menstrual\s*döngü|folikül|ovulasyon|korpus\s*luteum|rejenerasyon)\b',
        r'\b(destek\s*hareket|iskelet|kemik|osteosit|osteoblast|osteoklast|havers|volkmann|süngerimsi|sıkı\s*kemik|kırmızı\s*ilik|sarı\s*ilik|kıkırdak|kondrosit|hiyaliz|elastik|fibroz|eklem|sinoviyal|kas|düz\s*kas|çizgili\s*kas|iskelet\s*kası|kalp\s*kası|kasılma|miyozin|aktin|sarkomer|sarkoplazmik\s*retikulum|kalsiyum|atp|kreatin|oksijen\s*borcu|tetanoz|tonus)\b',
        # Ekoloji ve Çevre
        r'\b(ekoloji|ekosistem|birey|popülasyon|komünite|biyosfer|habitat|niş|rekabet|avcı|av|simbiyoz|parazitlik|mutualizm|kommensalizm|amensalizm|besin\s*zinciri|besin\s*ağı|trofik\s*düzey|üretici|tüketici|ayrıştırıcı|saprofit|enerji\s*akışı|madde\s*döngüsü)\b',
        r'\b(karbon\s*döngüsü|azot\s*döngüsü|su\s*döngüsü|fosfor|biyokütle|biyolojik\s*birikim|ekolojik\s*piramit|taşıma\s*kapasitesi|çevre\s*direnci|süksesyon|birincil|ikincil|klimaks|biyom|çöl|tundra|tayga|orman|savan|step|sera\s*etkisi|küresel\s*ısınma|ozon|asit\s*yağmuru|karbon\s*ayak\s*izi|endemik|ekoton)\b',
        # Evrim ve Davranış
        r'\b(evrim|darwin|lamarck|doğal\s*seçilim|yapay\s*seçilim|varyasyon|adaptasyon|kalıtsal|mutasyon|gen\s*havuzu|alel\s*frekansı|hardy\s*weinberg|genetik\s*sürüklenme|gen\s*akışı|türleşme|izolasyon|fosil|homolog|analog|vestigiyal|embriyoloji|korelasyon)\b',
    ],
    'Türkçe': [
        # Sözcük Bilgisi ve Anlam
        r'\b(sözcük|kelime|anlam|eş\s*anlam|yakın\s*anlam|karşıt\s*anlam|zıt\s*anlam|sesteş|eş\s*sesli|gerçek\s*anlam|mecaz\s*anlam|yan\s*anlam|somut|soyut|terim|deyim|atasözü|özdeyiş|ikileme|yansıma|dolaylama|ad\s*aktarması|mecazımürsel|güzel\s*adlandırma|kinaye|tariz)\b',
        # Biçim Bilgisi (Sözcük Yapısı)
        r'\b(kök|isim\s*kökü|fiil\s*kökü|gövde|yapım\s*eki|çekim\s*eki|hal\s*eki|bulunma|ayrılma|yönelme|belirtme|çoğul\s*eki|iyelik\s*eki|tamlayan\s*eki|tamlanan|ilgi\s*eki|eşitlik\s*eki|vasıta\s*eki|bildirme\s*eki|basit\s*sözcük|türemiş\s*sözcük|birleşik\s*sözcük|kaynaşmış|kurallı\s*birleşik)\b',
        # Sözcük Türleri
        r'\b(ad|isim|özel\s*isim|cins\s*isim|soyut\s*isim|somut\s*isim|topluluk\s*ismi|isim\s*tamlaması|belirtili|belirtisiz|zincirleme|takısız)\b',
        r'\b(sıfat|ön\s*ad|niteleme\s*sıfatı|belirtme\s*sıfatı|işaret\s*sıfatı|sayı\s*sıfatı|belgisiz\s*sıfat|soru\s*sıfatı|pekiştirme|küçültme|sıfat\s*tamlaması|adlaşmış\s*sıfat)\b',
        r'\b(zamir|adıl|kişi\s*zamiri|dönüşlülük\s*zamiri|işaret\s*zamiri|belgisiz\s*zamir|soru\s*zamiri|ilgi\s*zamiri|iyelik\s*zamiri)\b',
        r'\b(zarf|belirteç|durum\s*zarfı|zaman\s*zarfı|yer\s*yön\s*zarfı|miktar\s*zarfı|azlık\s*çokluk|derecelendirme|soru\s*zarfı)\b',
        r'\b(edat|ilgeç|bağlaç|ünlem)\b',
        r'\b(fiil|eylem|anlamına\s*göre\s*fiiller|kılış|durum|oluş|kip|haber\s*kipleri|dilek\s*kipleri|zaman|şart|istek|gereklilik|emir|bildirme|tasarlama|olumlu|olumsuz|soru|anlam\s*kayması|zaman\s*kayması|ek\s*fiil|ek\s*eylem|birleşik\s*zamanlı|basit\s*zamanlı)\b',
        r'\b(fiilde\s*çatı|öznesine\s*göre|etken|edilgen|dönüşlü|işteş|nesnesine\s*göre|geçişli|geçişsiz|oldurgan|ettirgen)\b',
        r'\b(fiilimsi|eylemsi|isim\s*fiil|mastar|sıfat\s*fiil|ortaç|zarf\s*fiil|ulaç|bağ\s*fiil|kalıcı\s*isim)\b',
        # Cümle Bilgisi (Ögeler ve Türler)
        r'\b(cümle|tümce|cümlenin\s*ögeleri|özne|gerçek\s*özne|gizli\s*özne|sözde\s*özne|yüklem|nesne|dolaylı\s*tümleç|yer\s*tamlayıcısı|zarf\s*tümleci|belirtili\s*nesne|belirtisiz\s*nesne|edat\s*tümleci|vurgu|ara\s*söz|ara\s*cümle)\b',
        r'\b(cümle\s*türleri|devrik|kurallı|eksiltili|isim\s*cümlesi|fiil\s*cümlesi|olumlu|olumsuz|soru|ünlem|biçimce|anlamca|yapısına\s*göre)\b',
        r'\b(basit\s*cümle|birleşik\s*cümle|girişik\s*birleşik|ki\'li\s*birleşik|şartlı\s*birleşik|iç\s*içe\s*birleşik|sıralı\s*cümle|bağımlı\s*sıralı|bağımsız\s*sıralı|bağlı\s*cümle)\b',
        # Anlatım Bozuklukları
        r'\b(anlatım\s*bozukluğu|anlamsal|yapısal|gereksiz\s*sözcük|anlamca\s*çelişen|sözcüğün\s*yanlış\s*anlamda\s*kullanımı|sözcüğün\s*yanlış\s*yerde\s*kullanımı|deyim\s*yanlışlığı|anlam\s*belirsizliği|mantık\s*hatası|özne\s*yüklem\s*uyumsuzluğu|tekillik\s*çoğulluk|kişi\s*uyumu|öge\s*eksikliği|özne\s*eksikliği|nesne\s*eksikliği|tümleç\s*eksikliği|yüklem\s*eksikliği|ek\s*fiil\s*eksikliği|tamlama\s*yanlışlığı|ek\s*yanlışlığı|bağlaç\s*yanlışlığı)\b',
        # Paragraf ve Anlatım Teknikleri
        r'\b(paragraf|ana\s*düşünce|ana\s*fikir|yardımcı\s*düşünce|konu|başlık|giriş|gelişme|sonuç|düşüncenin\s*akışı|anlam\s*bütünlüğü|paragrafı\s*ikiye\s*bölme|yer\s*değiştirme|cümle\s*ekleme|cümle\s*çıkarma)\b',
        r'\b(anlatım\s*biçimleri|öyküleme|öyküleyici|betimleme|betimleyici|izlenimsel|açıklayıcı|tartışma|tartışmacı|kanıtlayıcı|coşku\s*ve\s*heyecan\s*dile\s*getiren|destansı|epik|öğretici|didaktik|mizahi)\b',
        r'\b(düşünceyi\s*geliştirme\s*yolları|tanımlama|örnekleme|karşılaştırma|tanık\s*gösterme|sayısal\s*verilerden\s*yararlanma|benzetme|somutlama|soyutlama|ilişki\s*kurma)\b',
        # Yazım Kuralları ve Noktalama
        r'\b(yazım\s*kuralları|imla|büyük\s*harflerin\s*yazımı|bitişik\s*yazılan|ayrı\s*yazılan|birleşik\s*kelimeler|bağlaç\s*olan\s*ki|ek\s*olan\s*ki|bağlaç\s*olan\s*de|ek\s*olan\s*de|mi\'nin\s*yazımı|satır\s*sonu|sayıların\s*yazımı|tarihlerin\s*yazımı|kısaltmaların\s*yazımı|yön\s*adları|pekiştirmeler|ikilemeler)\b',
        r'\b(noktalama\s*işaretleri|nokta|virgül|noktalı\s*virgül|iki\s*nokta|üç\s*nokta|soru\s*işareti|ünlem|tırnak\s*işareti|tek\s*tırnak|parantez|yay\s*ayraç|köşeli\s*ayraç|kısa\s*çizgi|uzun\s*çizgi|kesme\s*işareti|eğik\s*çizgi|denden)\b',
        # Ses Bilgisi
        r'\b(ses\s*bilgisi|ünlü|ünsüz|kalın\s*ünlü|ince\s*ünlü|düz\s*ünlü|yuvarlak|geniş|dar|sert\s*ünsüz|yumuşak|büyük\s*ünlü\s*uyumu|küçük\s*ünlü\s*uyumu|ünlü\s*düşmesi|hece\s*düşmesi|ünlü\s*daralması|ünlü\s*türemesi|ünlü\s*değişimi|ünsüz\s*benzeşmesi|sertleşme|ünsüz\s*yumuşaması|değişimi|ünsüz\s*türemesi|ikizleşme|ünsüz\s*düşmesi|kaynaştırma|koruyucu\s*ünsüz|ulama|n\s*b\s*çatışması|gerileyici\s*benzeşme)\b',
    ],
    'Edebiyat': [
         # Şiir Bilgisi
        r'\b(şiir|nazım|manzume|beyit|dörtlük|kıta|bent|mısra|dize|ölçü|vezin|aruz|hece|serbest\s*ölçü|durak|kafiye|uyak|redif|tam\s*uyak|yarım\s*uyak|zengin|tunç|cinaslı|çapraz|sarmal|düz\s*uyak|mani\s*tipi|koşma\s*tipi)\b',
        r'\b(nazım\s*biçimi|nazım\s*şekli|nazım\s*türü|gazel|kaside|tevhit|münacat|naat|methiye|mersiye|fahriye|hicviye|mesnevi|rubai|tuyuğ|şarkı|murabba|müstezat|muhammes|terkibibent|terciibent|kıta)\b',
        r'\b(halk\s*şiiri|âşık\s*tarzı|anonim|mani|koşma|güzelleme|koçaklama|taşlama|ağıt|semai|varsağı|destan|türkü|ninni|bilmece|tekerleme)\b',
        r'\b(tekke|tasavvuf|ilahi|nefes|nutuk|şathiye|deme|devriye|vahdetivücut|insanıkamil)\b',
        r'\b(lirik|epik|didaktik|pastoral|satirik|dramatik|idil|eglog)\b',
        # Söz Sanatları (Edebi Sanatlar)
        r'\b(söz\s*sanatı|edebi\s*sanat|mecaz|mecazımürsel|ad\s*aktarması|istiare|eğretileme|açık\s*istiare|kapalı\s*istiare|teşbih|benzetme|kinaye|değinmece|tariz|iğneleme|teşhis|kişileştirme|intak|konuşturma|mübalağa|abartma|hüsnütalil|güzel\s*neden|tecahüliarif|bilmezden\s*gelme|tezat|karşıtlık|tenasüp|uygunluk|leff\s*ü\s*neşir|irsalimesel|cinas|akrostiş|seci|aliterasyon|asonans|telmih|anımsatma|tevriye|iki\s*anlamlılık|tekrir|yineleme|nidâ|istifham|soru\s*sorma|rücu|geriye\s*dönüş|tedric|derecelendirme)\b',
        # Düzyazı Türleri ve Tiyatro
        r'\b(düzyazı|nesir|öykü|hikaye|olay\s*hikayesi|maupassant|durum\s*hikayesi|çehov|roman|tarihi\s*roman|sosyal|psikolojik|macera|polisiye|deneme|makale|fıkra|köşe\s*yazısı|söyleşi|sohbet|eleştiri|tenkit|gezi\s*yazısı|seyahatname|biyografi|yaşam\s*öyküsü|otobiyografi|öz\s*yaşam\s*öyküsü|tezkire|anı|hatıra|günlük|günce|mektup|röportaj|mülakat)\b',
        r'\b(masal|döşeme|serim|düğüm|çözüm|dilek|fabl|efsane|mit|destan|doğal\s*destan|yapay\s*destan|halk\s*hikayesi|cenkname|mesnevi)\b',
        r'\b(tiyatro|geleneksel\s*türk\s*tiyatrosu|modern\s*tiyatro|meddah|karagöz|hacivat|ortaoyunu|kavuklu|pişekar|köy\s*seyirlik|trajedi|tragedya|komedi|komedya|dram|üç\s*birlik\s*kuralı|sahne|perde|diyalog|monolog|tirad|pandomim|suflör|kulis|dekor|kostüm)\b',
        # Edebiyat Akımları
        r'\b(klasisizm|kuralcılık|romantizm|coşumculuk|realizm|gerçekçilik|natüralizm|doğalcılık|parnasizm|şiirde\s*gerçekçilik|sembolizm|simgecilik|empresyonizm|izlenimcilik|ekspresyonizm|dışavurumculuk|kübizm|dadaizm|kuralsızlık|sürrealizm|gerçeküstücülük|fütürizm|gelecekçilik|egzistansiyalizm|varoluşçuluk|postmodernizm|modernizm|sezgicilik)\b',
        # Edebiyat Tarihi - Dönemler ve Şahsiyetler
        r'\b(islamiyet\s*öncesi|koşuk|sagu|sav|destan|şaman|kam|baksı|ozan|yuğ|şölen|sığır|göktürk|orhun\s*abideleri|uygur|kalyanamkara|papançkara)\b',
        r'\b(geçiş\s*dönemi|kutadgu\s*bilig|yusuf\s*has\s*hacip|divan\s*u\s*lügatit\s*türk|kaşgarlı\s*mahmut|atabetül\s*hakayık|edip\s*ahmet|divan\s*ı\s*hikmet|ahmet\s*yesevi)\b',
        r'\b(divan\s*edebiyatı|fuzuli|baki|nedim|şeyh\s*galip|nefi|nabi|kadı\s*burhaneddin|nesimi|ali\s*şir\s*nevai|katip\s*çelebi|evliya\s*çelebi|nâbi|süleyman\s*çelebi)\b',
        r'\b(tanzimat|şinasi|namık\s*kemal|ziya\s*paşa|ahmet\s*mithat|şemsettin\s*sami|abdülhak\s*hamit|recaizade|nabizade\s*nazım|muallim\s*naci|samipaşazade|ilk\s*roman|ilk\s*tiyatro|ilk\s*makale|tercümanı\s*ahval|tasviri\s*efkar)\b',
        r'\b(servetifünun|edebiyatı\s*cedide|tevfik\s*fikret|cenap\s*şahabettin|halit\s*ziya|mehmet\s*rauf|hüseyin\s*cahit|ahmet\s*şuayb|süleyman\s*nazif|mensur\s*şiir|dekadan)\b',
        r'\b(fecriati|ahmet\s*haşim|yakup\s*kadri|refik\s*halit|tahsin\s*nahit)\b',
        r'\b(milli\s*edebiyat|genç\s*kalemler|ömer\s*seyfettin|ziya\s*gökalp|mehmet\s*emin|halide\s*edip|reşat\s*nuri|fuat\s*köprülü|ali\s*canip|türkçülük|yeni\s*lisan)\b',
        r'\b(bağımsızlar|mehmet\s*akif\s*ersoy|yahya\s*kemal|hüseyin\s*rahmi|ahmet\s*rasim)\b',
        r'\b(cumhuriyet|beş\s*hececiler|yedi\s*meşaleciler|garip|birinci\s*yeni|ikinci\s*yeni|maviciler|hisarcılar|toplumcu\s*gerçekçiler|milli\s*ve\s*dini\s*duyarlılık|saf\s*şiir|öz\s*şiir)\b',
        r'\b(nazım\s*hikmet|orhan\s*veli|oktay\s*rifat|melih\s*cevdet|ahmet\s*hamdi\s*tanpınar|necip\s*fazıl|peyami\s*safa|sait\s*faik|kemal\s*tahir|orhan\s*kemal|yaşar\s*kemal|fazıl\s*hüsnü|behçet\s*necatigil|attila\s*ilhan|cemal\s*süreya|edip\s*cansever|turgut\s*uyar|ece\s*ayhan|seza\s*karakoç|ismet\s*özel|ilhan\s*berk|oğuz\s*atay|yusuf\s*atılgan|bilge\s*karasu|adalet\s*ağaoğlu)\b',
    ],
    'Tarih': [
        # Tarih Bilimi ve Temel Kavramlar
        r'\b(tarih|tarih\s*bilimi|kaynak|birinci\s*elden|ikinci\s*elden|belge|kanıt|kronoloji|takvim|çağ|dönem|asır|yüzyıl|milat|hicri|rumi|miladi|celali|on\s*iki\s*hayvanlı|arkeoloji|paleografi|nümizmatik|epigrafi|etnografya|filoloji|diplomatik|antropoloji|heraldik|sigilografi)\b',
        # İlk Çağ Uygarlıkları
        r'\b(ilk\s*çağ|mezopotamya|sümer|akad|babil|asur|elam|ziggurat|çivi\s*yazısı|hammurabi|mısır|firavun|piramit|sfenks|mumya|hiyeroglif|papirüs|nom|kadeş\s*antlaşması)\b',
        r'\b(anadolu\s*uygarlıkları|hitit|pankuş|tavananna|hattutaş|frig|gordion|kibele|tapates|lidya|sardes|kral\s*yolu|para|urartu|tuşpa|şamran|iyon|polis|özgür\s*düşünce)\b',
        r'\b(doğu\s*akdeniz|fenike|harf\s*yazısı|alfabe|cam|ibrani|tek\s*tanrılı|med|pers|satraplık|zodyak|yunan|helen|atina|sparta|demokrasi|olimpiyat|iskender|helenistik|roma|patrici|plep|on\s*iki\s*levha)\b',
        # Türk Tarihi (İslamiyet Öncesi ve Sonrası)
        r'\b(türk|orta\s*asya|göç|anayurt|kurgan|balbal|uçmağ|tamu|kut|töre|kurultay|toy|boy|budun|ikili\s*teşkilat|hun|mete|asya\s*hun|avrupa\s*hun|attila|kavimler\s*göçü|göktürk|bumin|mukan|bilge|kül\s*tigin|tonyukuk|uygur|bögü|maniheizm|yerleşik\s*hayat|matbaa|kırgız|hazar|karluk|macar|peçenek|kuman|kıpçak|uzlar)\b',
        r'\b(türk\s*islam|karahanlı|satuk\s*buğra|gazneli|mahmut|büyük\s*selçuklu|tuğrul|çağrı|alparslan|dandanakan|malazgirt|melikşah|nizamülmülk|nizamiye|atabey|batinilik|anadolu\s*selçuklu|süleyman\s*şah|kılıçarslan|miryokefalon|yassıçemen|kösedağ|haçlı\s*seferleri|danişmentli|mengücekli|saltuklu|artuklu|ahilik|lonca|vakıf|kervansaray)\b',
        # İslam Tarihi
        r'\b(islam|cahiliye|hz\.\s*muhammed|bedir|uhud|hendek|hudeybiye|mekke|medine|hicret|dört\s*halife|ebubekir|ömer|osman|ali|kuran|emevi|muaviye|kerbela|endülüs|abbasi|bağdat|beytül\s*hikme|tavaif\s*i\s*mülük|mevali|avasım)\b',
        # Osmanlı Tarihi
        r'\b(osmanlı|beylik|kuruluş|yükselme|duraklama|gerileme|dağılma|çöküş|padişah|sultan|divan|sadrazam|vezir|kazasker|defterdar|nişancı|şeyhülislam|reisülküttap|kaptan\s*ı\s*derya|yeniçeri|devşirme|kapıkulu|tımarlı\s*sipahi|tımar|dirlik|has|zeamet|iltizam|malikane|miri\s*arazi|mülk|vakıf|lonca|narh|gedik)\b',
        r'\b(osman|orhan|bursa|murat|kosova|yıldırım\s*bayezid|niğbolu|ankara\s*savaşı|fetret|çelebi\s*mehmet|ikinci\s*murat|varna|fatih|istanbul|karadeniz|ikinci\s*bayezid|cem\s*sultan|yavuz|selim|çaldıran|mercidabık|ridaniye|halifelik|kanuni|süleyman|mohaç|viyana|preveze|hint\s*deniz|sokullu)\b',
        r'\b(celali\s*isyanları|suhte|yeniçeri\s*isyanı|vakay\s*ı\s*vakvakiye|karlofça|prut|pasarofça|lale\s*devri|patrona\s*halil|belgrad|küçük\s*kaynarca|kırım|nizam\s*ı\s*cedit|kabakçı\s*mustafa|sened\s*i\s*ittifak|mahmut|yeniçeri\s*ocağı|vaka\s*i\s*hayriye|tanzimat|ferman|ıslahat|meşrutiyet|kanun\s*i\s*esasi|istibdat|abdülhamit|jön\s*türk|ittihat\s*ve\s*terakki|babıali)\b',
        # İnkılap Tarihi ve Milli Mücadele
        r'\b(trablusgarp|balkan\s*savaşı|birinci\s*dünya|üçlü\s*ittifak|üçlü\s*itilaf|suikast|sarıkamış|çanakkale|kut\s*ül\s*amare|kanal|suriye|filistin|hicaz|yemen|wilson\s*ilkeleri|mütareke|mondros|paris\s*barış|izmirin\s*işgali|cemiyetler|yararlı|zararlı|kuvayi\s*milliye)\b',
        r'\b(mustafa\s*kemal|samsun|havza|amasya\s*genelgesi|erzurum\s*kongresi|sivas\s*kongresi|heyet\s*i\s*temsiliye|amasya\s*görüşmeleri|misak\s*ı\s*milli|tbmm|sevr|istiklal\s*mahkemeleri)\b',
        r'\b(doğu\s*cephesi|gümrü|güney\s*cephesi|ankara\s*antlaşması|batı\s*cephesi|düzenli\s*ordu|birinci\s*inönü|teşkilat\s*ı\s*esasiye|istiklal\s*marşı|londra\s*konferansı|moskova|ikinci\s*inönü|kütahya\s*eskişehir|maarife|tekalif\s*i\s*milliye|sakarya|kars\s*antlaşması|büyük\s*taarruz|başkomutanlık|mudanya|lozan)\b',
        r'\b(inkılap|devrim|saltanatın\s*kaldırılması|cumhuriyetin\s*ilanı|halifeliğin\s*kaldırılması|tevhid\s*i\s*tedrisat|şapka|tekke\s*ve\s*zaviye|medeni\s*kanun|harf|millet\s*mektebi|tarih\s*kurumu|dil\s*kurumu|kılık\s*kıyafet|soyadı|laiklik|atatürk\s*ilkeleri|cumhuriyetçilik|milliyetçilik|halkçılık|devletçilik|inkılapçılık|bütünleyici\s*ilkeler)\b',
        # Çağdaş Türk ve Dünya Tarihi
        r'\b(dış\s*politika|nüfus\s*mübadelesi|yabancı\s*okullar|musul|montrö|hatay|sadabat|balkan\s*antantı|ikinci\s*dünya\s*savaşı|mihver|müttefik|pearl\s*harbor|normandiya|soğuk\s*savaş|truman|marshall|nato|varşova|demir\s*perde|kore|küba|kıbrıs|bağlantısızlar|yumuşama|detant|küreselleşme)\b',
    ],
    'Coğrafya': [
        # Doğa Coğrafyası ve Harita Bilgisi
        r'\b(coğrafya|fiziki|beşeri|ekonomik|bölgesel|harita|kroki|ölçek|büyük\s*ölçek|küçük\s*ölçek|kesir|çizik|projeksiyon|silindirik|konik|düzlem|koordinat|enlem|boylam|paralel|meridyen|ekvator|kutup|yengeç|oğlak|greenwich|yerel\s*saat|ulusal\s*saat|tarih\s*değiştirme|izohips|eş\s*yükselti|profil|eğim|kabartma|renklendirme)\b',
        r'\b(dünya|yerküre|geoid|yörünge|elips|eksen|eksen\s*eğikliği|dönence|kutup\s*dairesi|aydınlanma|gece\s*gündüz|mevsim|ekinoks|solstis|yer\s*yapısı|kabuk|sial|sima|manto|çekirdek|levha\s*tektoniği|pangea|jeolojik\s*zaman|kambriyen|mezozoik|senozoik)\b',
        # İklim ve Atmosfer
        r'\b(atmosfer|troposfer|stratosfer|mezosfer|termosfer|ekzosfer|iklim|hava\s*durumu|klimatoloji|sıcaklık|izoterm|basınç|izobar|alçak\s*basınç|siklon|yüksek\s*basınç|antisiklon|rüzgar|meltem|muson|alize|batı\s*rüzgarları|kutup\s*rüzgarları|nem|mutlak\s*nem|maksimum\s*nem|bağıl\s*nem|yağış|izohiyet|yamaç|orografik|konveksiyonel|cephe|bulut|sis|çiy|kırağı|kırç|dolu|kar)\b',
        r'\b(iklim\s*tipi|makroklima|mikroklima|ekvatoral|tropikal|savan|muson|çöl|akdeniz|maki|ılıman\s*okyanusal|karasal|step|bozkır|sert\s*karasal|tayga|tundra|kutup|biyom)\b',
        # İç ve Dış Kuvvetler
        r'\b(iç\s*kuvvet|orojenez|epirojenez|kıta\s*oluşumu|volkanizma|magma|lav|krater|kaldera|maar|deprem|sismik|fay|tsunami|dış\s*kuvvet|aşınma|erozyon|kütle\s*hareketi|heyelan)\b',
        r'\b(akarsu|havza|açık\s*havza|kapalı\s*havza|debi|rejim|dengel\s*profili|vadi|çentik|boğaz|kanyon|menderes|ırmak\s*adası|dev\s*kazanı|peribacası|kırgıbayır|delta|birikinti\s*konisi)\b',
        r'\b(karstik|lapya|dolin|uvala|polye|obruk|mağara|sarkıt|dikit|sütun|traverten|rüzgar\s*şekilleri|mantar\s*kaya|barkan|löss|buzul|sirk|hörgüç|moren|dalga|akıntı|falez|yalıyar|kıyı\s*oku|tombolo|lagün|kıyı\s*tipleri|boyuna|enine|ria|dalmaçya|fiyort|limanlı)\b',
        # Su, Toprak ve Bitki
        r'\b(su|hidrosfer|okyanus|deniz|göl|tektonik|karstik|volkanik|buzul|set\s*gölü|alüvyal|heyelan\s*seti|kıyı\s*seti|yapay\s*göl|baraj|yeraltı\s*suyu|taban\s*suyu|kaynak|fay\s*kaynağı|karstik\s*kaynak|artezyen|gayzer|sıcak\s*su)\b',
        r'\b(toprak|pedoloji|horizon|zonal|azonal|intrazonal|laterit|terra\s*rossa|podzol|kahverengi\s*orman|çernezyom|çöl\s*toprağı|tundra|alüvyal|kolüvyal|litokol|lös|moren|regosol|halomorfik|hidromorfik|kalsimorfik|vertisol|rendzina)\b',
        r'\b(bitki|formasyon|ağaç|orman|çalı|maki|garig|psödomaki|ot|savan|step|bozkır|çayır|tundra|endemik|relikt|kozmopolit)\b',
        # Beşeri ve Ekonomik Coğrafya
        r'\b(nüfus|demografi|nüfus\s*sayımı|doğum|ölüm|doğal\s*artış|gerçek\s*artış|nüfus\s*yoğunluğu|aritmetik|fizyolojik|tarımsal|nüfus\s*piramidi|bağımlı\s*nüfus|aktif\s*nüfus|göç|iç\s*göç|dış\s*göç|beyin\s*göçü|mülteci|sığınmacı|mübadele|yerleşme|kırsal|kentsel|köy\s*altı|yaylas|kom|ağıl|oba|mezra|divan|çiftlik|toplu|dağınık|çizgisel|dairesel|kent|metropol|megakent)\b',
        r'\b(ekonomi|üretim|dağıtım|tüketim|birincil|ikincil|üçüncül|dördüncül|beşincil\s*faaliyet|tarım|intansif|modern|ekstansif|ilkel|nadas|nöbetleşe|sera|tahıl|buğday|arpa|sanayi\s*bitkisi|pamuk|tütün|şeker\s*pancarı|yağ\s*bitkisi|ayçiçeği|zeytin|meyve|fındık|turunçgil|muz|incir|üzüm|çay|hayvancılık|mera|besi|ahır|kümes|arıcılık|ipekböcekçiliği|balıkçılık|ormancılık)\b',
        r'\b(maden|rezerv|tenör|kömür|taş\s*kömürü|linyit|petrol|doğalgaz|demir|bakır|krom|bordan|bauxite|alüminyum|altın|mermer|kükürt|zımpara|barit|fosfat|uranyum|toryum|enerji|hidroelektrik|termik|nükleer|jeotermal|rüzgar|güneş|biyokütle|yenilenebilir)\b',
        r'\b(sanayi|endüstri|hammaddde|sermaye|pazar|ulaşım|organize\s*sanayi|ticaret|iç\s*ticaret|dış\s*ticaret|ithalat|ihracat|dış\s*ticaret\s*açığı|serbest\s*bölge|sınır\s*ticareti|turizm|bacasız\s*sanayi|kış\s*turizmi|yaz\s*turizmi|sağlık|inanç|kültür|ulaşım|karayolu|demiryolu|denizyolu|boğaz|kanal|havayolu|boru\s*hattı)\b',
        # Bölgeler ve Ülkeler
        r'\b(bölge|şekilsel|işlevsel|kalkınma\s*projesi|gap|dokap|zbg|dap|kop|türkiye|anadolu|trakya|marmara|ege|akdeniz|karadeniz|iç\s*anadolu|doğu\s*anadolu|güneydoğu|kıtalar|avrupa|asya|afrika|amerika|antarktika|okyanusya|gelişmişlik|uluslararası\s*örgüt|bm|nato|avrupa\s*birliği|opec|oecd|g20|g8|karadeniz\s*ekonomik|çevre\s*sorunları|afet|doğal\s*afet|deprem|sel|çığ|orman\s*yangını)\b',
    ],
    'Felsefe': [
        r'\b(felsefe|filozof|düşünür|düşünce|akıl|us|hikmet|bilgelik|refleksif|kümülatif|tutarlılık|temellendirme|eleştirel|öznel|evrensel|mitoloji)\b',
        r'\b(bilgi|epistemoloji|bilen|özne|suje|bilinen|nesne|obje|doğruluk|hakikat|gerçeklik|kesinlik|kuşku|şüphe|akılcılık|rasyonalizm|deneycilik|empirizm|kritisizm|eleştiricilik|sezgicilik|entüisyonizm|pragmatizm|faydacılık|pozitivizm|olguculuk|fenomenoloji|görüngübilim|analitik|septisizm|şüphecilik|sofist|rölativizm|görecelilik|apriori|aposteriori|tümdengelim|tümevarım|analoji)\b',
        r'\b(varlık|ontoloji|arkhe|öz|töz|cevher|idea|idealizm|materyalizm|maddecilik|düalizm|ikicilik|monizm|tekçilik|nihilizm|hiççilik|oluş|varoluşçuluk|egzistansiyalizm|panteizm|panenteizm|determinizm|fatalizm)\b',
        r'\b(ahlak|etik|iyi|kötü|erdem|değer|ödev|sorumluluk|özgürlük|özerk|otonomi|heteronomi|vicdan|ahlak\s*yasası|eudaimonia|mutluluk|haz|hedonizm|faydacılık|utilitarizm|ödev\s*ahlakı|kategorik\s*imperatif|egoizm|bencillik|altruizm|diğerkamlık)\b',
        r'\b(din\s*felsefesi|tanrı|allah|inanç|iman|teizm|deizm|ateizm|agnostisizm|bilinmezcilik|panteizm|vahiy|kutsal|mucize|kötülük\s*problemi|teodise|ontolojik\s*kanıt|kozmolojik\s*kanıt|teleolojik\s*kanıt)\b',
        r'\b(siyaset|politika|devlet|yönetim|iktidar|egemenlik|meşruiyet|hak|adalet|eşitlik|özgürlük|demokrasi|liberalizm|sosyalizm|anarşizm|toplum\s*sözleşmesi|birey|toplum|ütopya|distopya|monarşi|oligarşi|teokrasi|laiklik|hukuk)\b',
        r'\b(sanat|estetik|güzel|güzellik|çirkin|yüce|trajik|komik|sanat\s*eseri|taklit|mimesis|yaratıcılık|dışavurum|form|biçim|ifade|oyun|kurgu)\b',
        r'\b(bilim\s*felsefesi|bilimsel\s*yöntem|hipotez|teori|kuram|yasa|kanun|yanlışlanabilirlik|doğrulanabilirlik|paradigma|normal\s*bilim|kuhn|popper|tarihselcilik|mantıksal\s*pozitivizm|viyana\s*çevresi)\b',
        r'\b(mantık|geçerlilik|geçersiz|tutarlı|çelişik|önerme|yargı|kavram|terim|tanım|çıkarım|kıyas|gerekçe|argüman|safsata|kıyas|kavram\s*ağı|nelik|gerçeklik|kimlik|içlem|kaplam|tümel|tikel|tekil|olumlu|olumsuz|çelişiklik|karşıtlık|altık|kıyas\s*kuralları)\b',
        r'\b(antik\s*yunan|thales|anaksimandros|anaksimenes|sokrates|maiotik|ironi|platon|mağara\s*alegorisi|aristoteles|altın\s*orta|madde\s*form|herakleitos|parmenides|demokritos|epikuros|stoa|kinizm|zenon|orta\s*çağ|patristik|skolastik|aqiunalı\s*thomas|augustinus|ibn\s*sina|farabi|rönesans|hümanizm|descartes|kant|hegel|karl\s*marx|nietzsche|heidegger|sartre|kierkegaard|hume|locke|spinoza|leibniz|machiavelli|hobbes|rousseau|comte|wittgenstein)\b',
    ],
    'Din Kültürü': [
        r'\b(din|islam|müslüman|tevhid|şirk|allah|esmaül\s*hüsna|ilah|rab|kuran|ayet|sure|cüz|hafız|tecvid|mukabele|meal|tefsir|müfessir|peygamber|nebi|resul|hz\.\s*muhammed|vahiy|cebrail|sünnet|hadis|kütüb\s*i\s*sitte|siyer)\b',
        r'\b(iman|inanç|amentü|melek|azrail|mikail|israfil|kiramen\s*katibin|ahiret|mahşer|cennet|cehennem|mizan|sırat|kıyamet|kader|kaza|tevekkül|cüzi\s*irade|külli\s*irade|ecel|rızık|ömür)\b',
        r'\b(ibadet|farz|vacip|sünnet|müstehap|mubah|mekruh|haram|helal|niyet|ihlas|riya|namaz|sabah|öğle|ikindi|akşam|yatsı|cuma|cenaze|teravih|vitir|bayram|rekât|kıyam|kıraat|rüku|secde|kade|tahiyyat|ezan|kamet|kıble|cami|mescit|mihrap|minber|kürsü|şadırvan|minare|abdest|gusül|teyemmüm|oruç|imsak|iftar|sahur|ramazan|fidye|kefaret|zekat|nisap|öşür|sadaka|fitre|hac|umre|ihram|tavaf|vakfe|say|kabe|arafat|mina|müzdelife|kurban)\b',
        r'\b(kandil|mevlid|kadir|miraç|regaip|berat|aşure|muharrem|zilhicce|arefe|hicri|haram\s*aylar)\b',
        r'\b(mezhep|itikadi|ameli|hanefi|ebu\s*hanife|şafi|maliki|hanbeli|alevilik|bektaşilik|caferi|cem|cemevi|musahiplik|semah|sünni|maturidi|eşari|tasavvuf|tarikat|mutasavvıf|fıkıh|kelam|akaid|islam\s*hukuku)\b',
        r'\b(ahlak|erdem|huy|doğruluk|dürüstlük|adalet|merhamet|sevgi|saygı|hoşgörü|sabır|şükür|alçakgönüllülük|tevazu|cömertlik|infak|israf|yardımlaşma|haset|kibir|gıybet|iftira|yalan|kul\s*hakkı)\b',
        r'\b(diğer\s*dinler|yahudilik|hristiyanlık|budizm|hinduizm|sihizm|taoizm|şintoizm|tevrat|tora|zebur|incil|kutsal\s*kitap|peygamber|musa|isa|ibrahim|davut|süleyman|nuh|semavi\s*din|kilise|sinagog|havra|havari|teslis|papa|vaftiz|nirvana|karma|reankarnasyon)\b',
    ],
}



def detect_topic(text: str) -> Tuple[str, Optional[str]]:
    """
    Detect topic from solution text using weighted scoring.
    Multi-word matches score higher (more specific).
    Requires minimum confidence gap between top 2 topics.
    Returns: (topic, subtopic)
    """
    if not text:
        return "Genel", None

    # First try AI tag
    ai_topic = parse_topic_from_ai(text)
    if ai_topic:
        return ai_topic, None

    text_lower = text.lower()
    scores = {}

    for topic, patterns in TOPIC_PATTERNS.items():
        score = 0.0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                # Multi-word matches are more specific → higher weight
                if isinstance(match, tuple):
                    match = match[0]
                word_count = len(match.split())
                if word_count >= 3:
                    score += 5.0   # very specific compound phrase
                elif word_count == 2:
                    score += 3.0   # moderately specific
                else:
                    score += 1.0   # single generic word
        if score > 0:
            scores[topic] = score

    if not scores:
        return "Genel", None

    sorted_topics = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_topic, best_score = sorted_topics[0]

    # Confidence check: require 40% gap over second-best
    if len(sorted_topics) >= 2:
        second_score = sorted_topics[1][1]
        gap_ratio = (best_score - second_score) / best_score if best_score > 0 else 0
        if gap_ratio < 0.15:
            # Too close → ambiguous, check if best has at least 2x
            if best_score < second_score * 1.5:
                return "Genel", None

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
                
                # Try AI-based topic detection first, fall back to regex
                ai_topic = parse_topic_from_ai(solution)
                clean_solution = strip_topic_tag(solution)
                
                if ai_topic:
                    topic = ai_topic
                    subtopic = None
                else:
                    topic, subtopic = detect_topic(clean_solution)
                
                return {
                    "filename": filename,
                    "success": True,
                    "solution": clean_solution,
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

