# Öneri: Kanıt temelli stakeholder alan kartı

> **Durum: kavramsal yeniden tasarım önerisi.** Hedef, **yarışmada güvenle gösterilebilecek ve farklı cümlelerde sınanabilecek sürümdür**; sonraki faz fikirleri bu belgenin kapsamında değildir. Bu belge mevcut kodun veya yayımlanmış API'nin davranışını tarif etmez; uygulama kararı değildir.
Sayısal sınırlar aşağıda başlangıç varsayımıdır; değerlendirmeyle doğrulanmalıdır.

## Amaç ve sınır

Workbot'un işi, Maya'nın yeni bir proje fikrine **kimleri, hangi alanda ve hangi amaçla dahil edebileceğini** bulmaktır. Binlerce kişinin çalıştığı şirkette konuya göre önceden atanmış bir temas listesi yoktur. Workbot, dağınık iş izleri ile güncel organizasyon bilgisinden kişileri **keşfeder**. Geçmişte aynı işi yapmış birini bulmak değerlidir ama yeni projede böyle bir iz olmayabilir. İncelenen alanda tamamlanmış değerlendirme güvenli bir doğrudan temas önermediğinde kart otomatik boş kalmaz: alanın takımla bağı kuvvetliyse ve güncel yönetici doğrulanıyorsa model onu **doğru uygulayıcıyı bulmak için yönlendirme teması** olarak önerebilir. Yönetici olmak geçmiş proje sahipliğinin veya konu uzmanlığının kanıtı değildir.

Workbot bir ödeme çözümü, teknik mimari veya kodlama planı tasarlamaz. Nihai çıktısı, sınırlı aday havuzundan **modelin önerdiği ve kişi başına denetimden geçen herkesi** doğrudan temas, danışılacak kişi veya yalnız yönlendirme teması rolleriyle gösteren kaynaklı alan kartıdır; küresel bir “ilk iki kişi” sırası veya keyfî kişi sayısı hedefi üretmez. Bu, şirketteki tüm uygun kişilerin bulunduğu anlamına gelmez; kaçırılan kişiler ayrıca ölçülür. Maya kullanıcı arayüzünde kişileri yeniden seçmez veya sıralamaz. Kartın gösterimi mesaj, arama, davet veya koordinasyon kaydı oluşturmaz; Maya gösterilen kişilerle isterse kendisi iletişime geçer. Ürün, resmi bir Alexa+ istemcisi değil, etiketli bir simülasyon olarak kalır. Yarışma sürümü sentetik veri ve Maya için simüle edilmiş erişim yetkileri kullanır; canlı kurumsal bağlayıcıları, gerçek şirket kimliği/yetkilendirmesini, üretim ölçeğini veya güvenlik sertifikasyonunu kanıtlamaz. Prototipin kendi veri kümesindeki erişim kuralları yine de uygulanır ve sınanır; yeni connector, uzak arama servisi veya üretim altyapısı gerekmez.

## Örnek istek

> “We should accept stablecoin payments in our Android app, APP2.”

Bu cümle örnektir. Aşağıdaki alanlar ve kişi rolleri **temsili**dir; şirket dizininde belirli bir APP2 uzmanı veya stablecoin kaydı bulunduğu varsayılmaz. İkinci, yine hayalî örnek “I want to assign campaing management to AI instead of people” cümlesidir: özgün yazım korunur, `campaign` aramada düzeltilebilir; Workbot kampanya türünü varsaymaz. **Bütün operasyonel süreç İngilizcedir:** Maya'nın girdi ve cevapları, korpus, arama sorguları, model prompt ve çıktıları, kart gerekçeleri ve kullanıcıya gösterilen metinler. Bu Türkçe belge ürün metni değildir. Çok dilli arama bu önerinin konusu değildir.

## Veri ve teknoloji tercihleri

**Maya'ya görünür iş izi**, Maya'nın önceden gördüğü veya Workbot'un önceden seçtiği belge değildir: bu istekte simüle edilmiş yetkileriyle okuyabileceği kayıttır. İndekslenmiş kayıtlar arasından izinli aramayla bulunur. İstekten **önce** sentetik Slack mesajları, Jira işleri, GitHub değişiklikleri ve doküman parçaları hazırlanır. Her kayıtta tür, kaynak ID'si, tarih, metin, erişim kapsamı, sürüm veya içerik özeti ve kişi bağlantılarının türü tutulur. Erişilebilir belge parçalarının embedding'leri hesaplanmış, erişim kapsamıyla birlikte **Qdrant'ta indekslenmiş ve aramaya hazırdır**. Erişilebilir kayıtlar için BM25 indeksi de isteğe hazırdır. İstek sırasında korpus yeniden parçalanmaz, belge embedding'leri yeniden hesaplanmaz ve indeks kurulmaz; vektör araması için yalnız **sorgu embedding'i** üretilebilir. İki arama yolu kullanılır:

- **BM25 / ters indeks:** `APP2` gibi ürün adları ve tam ödeme terimleri için.
- **Qdrant vektör araması:** Aynı kelimeleri kullanmayan ilgili mobil checkout ve ödeme çalışmalarını bulmak için.

Sentetik korpusta Maya'nın erişim izni olmayan **temsili restricted dokümanlar** bulunur. Restricted metin Maya'nın erişilebilir BM25/Qdrant arama görünümüne veya model girdisine girmez; ayrıca restricted içerikte konu araması yapan bir katalog kurulmaz. Fiziksel indekslerin düzeni burada kararlaştırılmaz; istek sırasında erişim kapsamı aday seçimine ve kullanıcıya yansıyan sıralamaya yetkisiz kayıtların katkısını engellemelidir. Örneğin restricted kayıt eklemek, izinli sonuçları BM25 istatistikleri veya arama sırası üzerinden değiştirmemelidir. Kaynak okuma aşamasında erişim yeniden denetlenir: yetkisiz kaydın metni, başlığı, ID'si veya yalnız bu kayda bağlı kişileri arama sonucuna, model girdisine, karta ya da kullanıcıya görünen başka bir sinyale dönüşmez. Kart restricted dokümanların varlığına ilişkin not göstermez. Güncel ve geçmiş kişi–takım–görev ilişkileri ile yönetici ilişkisi **ayrı, yapılandırılmış dizin verisidir**; dizin hazır konu teması veya uydurma biyografi içermez. Dizin kişilerini vektör yakınlığıyla seçmeyiz. İzinli arama sonuçları Reciprocal Rank Fusion gibi bir yöntemle birleştirilebilir. Bu birleşim **aday bulur**, sahiplik veya nihai kişi kararı vermez. Qdrant burada önceden hazırlanmış yerel arama indeksi olarak varsayılır; uzak servis veya üretim dağıtımı kararı değildir. BM25 ve vektör sonuçlarının katkısı ayrı ölçülmeden daha karmaşık arama altyapısı seçilmez.

Kişi–kayıt bağı kaybolmaz: Jira assignee'si, GitHub değişikliğinin yazarı, Slack mesajının yazarı ve bir dokümanda yalnızca adı geçen kişi aynı iddia gücünü taşımaz. Slack'te birinin başkası hakkında yazdığı mesaj da o başkasının işi üstlendiğini tek başına kanıtlamaz. Bütün bunlar **aday sinyalleridir**, otomatik sahiplik hükümleri değildir.

Kaynak özeti üretiliyorsa her olgusal iddia görünür bir özgün kayda geri bağlanmalıdır. Görüşme sorusu ve “doğrulanmadı” etiketi, doğrulanmış bir olguymuş gibi kaynaklandırılmaz. Arama skorunun yüksekliği veya ortada herhangi bir citation bulunması, o citation'ın *bu projeye ilişkin iddiayı* desteklediğini tek başına kanıtlamaz.

## Modelin üç görevi

| Görev | Girdi | Model çıktısı |
| --- | --- | --- |
| **Etki analizi** | Proje cümlesi, aynı oturumdaki cevaplar ve gerçek org unit'ler | Alanlar, gerekçeleri ve arama niyetleri; gerekiyorsa sıradaki kritik soru |
| **Alan başına kişi değerlendirmesi** | Bir alanın erişilebilir çok kaynaklı iş izi adayları ve güncel org/yönetici adayları | Tek kazanan yerine birden çok önerilebilir kişi; her birinin rolü, görüşme sorusu, dayanakları ve belirsizliği |
| **Kart genelinde önceliklendirme** | Etki analizinden geçmiş alanların doğrulanmış kişi veya boş/tamamlanamamış sonuçları | Kişileri seçmeden veya sıralamadan mevcut alan ID'lerinin dikkat sırası ve varsa alanlar arasında henüz cevaplanmamış tek ortak soru |

Bunlar **üç görev türü**, mutlaka üç model çağrısı değildir: soru sorulmazsa bir etki çağrısı, adaylı alan başına bir değerlendirme çağrısı ve etki analizinden geçmiş alanlar için bir kart-geneli çağrı vardır. Örneğin beş adaylı alan için `1 + 5 + 1 = 7` çağrı; alan çağrıları paralel olabilir. Gösterilebilir kişi olmasa bile boş alanların önemini açıklamak için kart-geneli çağrı yapılabilir; etki analizi refusal ile sonuçlanırsa yapılmaz. Yanıtlanan her kritik soru aynı etki görevinin yeni çağrısıdır; başlangıç önerisi en fazla **iki, sırayla sorulan soru** olduğundan bu örnekte en çok iki ek etki çağrısı olabilir. Kaçırılmış alanlar için otomatik ek etki çağrısı bu akışta yoktur. BM25, sorgu embedding'i ve dizin sorgusu bu üretici LLM görevlerinden değildir. Çağrı sayısı ve gecikme ölçülür; sırf toplamı üçe indirmek için bütün adaylar tek dev prompt'a yığılmaz.

## İstek akışı: her aşamanın girdi ve çıktısı

### 1. İsteği ve durumu aç

- **Girdi:** Maya'nın kimliği, workspace, tam proje cümlesi ve oturum açma işlemine ait idempotency anahtarı.
- **İşlem:** İzinleri doğrula; cümleyi oturumun değişmez girdisi olarak bağla. Aynı anahtarla yinelenen oturum açma işleminin başka bir proje cümlesine dönüşmesine izin verme; bu anahtar, sonraki soru cevaplarını veya kartın yeniden görüntülenmesini yeni bir açılış isteği yapmaz.
- **Çıktı:** Proje cümlesine bağlı çalışma oturumu. Bu aşamada kişi veya alan hakkında gerçeklik iddiası yoktur.

### 2. Etki alanlarını tahmin et

- **Girdi:** Cümle, aynı oturumdaki cevaplar ve gerçek org-unit ID/ad listesi. Kişiler, iş izleri ve kısıtlı metin bu çağrının girdisi değildir. Çok sayıda org unit olduğunda listenin bağlam bütçesine etkisi ölçülür; bütün birimleri bu çağrıya sığdırabildiğimiz varsayılmaz.
- **Teknoloji:** Sınırlı, şemalı LLM çıktısı; kodla org-unit ve alan doğrulaması.
- **Çıktı:** Örneğin APP2 satın alma deneyimi, ödeme operasyonları, finans/muhasebe, hukuk/uyum, fraud/risk ve güvenlik alanları. Karta alınacak her alanın gerekçesi, birkaç sınırlı arama sorgusu ve doğrulanmış **tek bir birincil org-unit ID'si** bulunur. Alan bir konu/inceleme kapsamıdır, org unit ise yapılandırılmış dizin birimidir; bire bir isim eşitliği aranmaz. Başka birimdeki ilgili kişiler iş izi yoluyla bulunabilir. Alanlar hipotezdir; bir takımın projeyi üstlendiği iddiası değildir. Eksik bir proje olgusu alanı veya eşlemeyi değiştirecekse modelin şemalı çıktısı önce kritik soru isteyebilir; bu aşamada henüz doğrulanmamış alan kişi aramasına veya karta girmez. Soru sonrası alanların ve eşlemelerinin doğrulanması gerekir.
- **Başarısızlık:** Geçersiz model çıktısı veya bağlam bütçesine sığmayan org-unit listesi güvenli bir refusal oluşturur. Gerekli kritik soru yanıtlanmış, yanıtlanmamış ya da soru sınırına ulaşılmış olsun, soru aşaması bittiğinde hiç alan üretilemiyorsa veya üretilen herhangi bir alan için tek bir birincil gerçek org unit hâlâ güvenle seçilemiyorsa **tüm istek için** refusal uygulanır; kısmi kişi kartı veya uydurma funnel gösterilmez. Listeyi daraltma yöntemi kararlaştırılmadan keyfî bir alt küme kullanılmaz.

### 3. Gerekirse kritik soruları sırayla sor

- **Girdi:** Alanları, kişi rollerini veya görüşme sorularını maddi biçimde değiştirecek eksik olgular.
- **Sınır:** Başlangıç için en fazla **iki**, birer birer sorulan soru; her istekte iki soru sormak hedef değildir. Her yanıt özgün cümleye bağlı aynı oturumda saklanır ve etki analizi yanıtla yeniden çalışır; eski alan ve aday sonuçları güncelmiş gibi taşınmaz. Gereksiz soru ve sınırsız röportaj yoktur; sınır kullanıcı yüküyle birlikte ölçülür.
- **APP2 örneği:** “Is this only a payment option for existing purchases, or would APP2 also hold customer balances or support transfers?” → “Only a payment option for existing purchases.” Ülke kapsamı yanıtlanmadıysa bilinmiyor kalır.
- **Kampanya örneği:** “What kind of campaigns do you mean?” → “Retail marketing campaigns.” Ardından hâlâ belirleyiciyse: “Would AI only prepare campaigns, or also launch them and spend budget without human approval?” → “A person approves every launch.” Bu cevaplar sonraki aday değerlendirmesinin kapsamını belirler; AI'a sahiplik atamaz.
- **Çıktı:** Cevaplar özgün cümleye bağlıdır. Maya bir soruyu yanıtlamazsa Workbot gerçeği uydurmaz: güvenle tanımlanıp eşlenebilen alanın kişi değerlendirmesindeki belirsizlik kartta taşınabilir veya inceleme tamamlanmamış kalabilir. Soru aşaması bittiğinde belirsizlik yüzünden etki analizi geçerli alan çıktısı üretemiyorsa ya da üretilen bir alanın birincil org unit'i güvenle belirlenemiyorsa kısmi kart yerine istek düzeyinde refusal uygulanır. Bekleyen soru sessizce yanıtlanmış sayılmaz.

### 4. Alan başına iş izi adaylarını üret

- **Girdi:** Alanın gerekçesi, tam terimleri koruyan keyword sorgusu ve kişi henüz bilinmeden ilgili işi/konuyu tarif eden semantic sorgu.
- **Örnek — ödeme operasyonları:** `APP2 payment method / checkout` tam terimleri; “operating or adding a payment option for mobile purchases” anlamsal sorgusu.
- **Teknoloji:** BM25 + vektör arama önce erişilebilir **Slack/Jira/GitHub/doküman kayıtlarını** bulur; sonuçlar birleştirilir, sonra kayıtlardaki kişi bağlantılarından adaylar üretilir. Assignee, yazar veya gerçek katkıcı salt anılmadan daha kuvvetli bir sinyal olabilir. Kaynağın konuya ilgisi ve kişinin kaynaktaki rolü birbirinden ayrı tutulur.
- **Çıktı:** Alan başına sınırlı sayıda iş izi adayı: kişi ID'si, görünür kaynak ID'leri, türleri ve tarihleri, kişinin kayıtla bağı ve neden aday olduğu. Örneğin ilk denemede en çok yaklaşık 10 iş izi adayı değerlendirilebilir; bu sayı kalite ve gecikme ölçümüyle ayarlanır. “Yeterli ilgili, Maya'nın okuyabildiği iz bulunamadı” sonucu, şirkette böyle bir iş hiç yapılmadığının kanıtı değildir.

APP2'nin önceki bir ödeme seçeneği üzerinde çalışmış kişi ilgili aday olabilir; bu kayıttan “stablecoin uzmanı” sonucu çıkarılmaz. Yalnız “wallet” kelimesini paylaşan loyalty kaydı doğrudan ödeme iş izi sayılmaz.

### 5. Aynı alan için güncel organizasyon adaylarını üret

- **Girdi:** Her alanın doğrulanmış birincil org-unit eşlemesi ve güncel/önceki takım, görev ve yönetici ilişkileri. Dizin “bu konu için aranacak kişi” alanı içermez.
- **Teknoloji:** Vektör veya LLM yerine denetlenebilir bir dizin filtresi. Org havuzunun iki kaynağı vardır: alanın birincil org unit'inin **güncel aktif yöneticisi** ve aynı birimdeki, **ünvan/görev tanımı** alanın arama niyetinden çıkarılan anahtar kelimelerle deterministik eşleşen **güncel aktif üyeler**. Ünvanı eşleşmeyen üyeler bu yoldan havuza alınmaz; sırf departman üyeliği adaylık için yeterli değildir. Başka birimlerden iş iziyle bulunan kişiler (adım 4) aynı alanın aday havuzuna kendi yollarından girer. Yönetici için yer ayrılarak org adayları örneğin toplam **10–15 kişiyle** sınırlandırılır; sabit, denetlenebilir sıralama ve kesin sınır ölçümle kararlaştırılır. Dizinin tamamı modele gönderilmez. Ünvan anahtar kelimesi eşleşmesi yalnız **adaylık** sağlar; tek başına geçmiş iş veya doğrudan temas kanıtı değildir.
- **Çıktı:** Aday kişinin güncel konumu, ünvan/görev eşleşmesi veya yönetici ilişkisi ve hangi alandan geldiği. Doğrudan temas için ilgili, Maya'ya görünür iş izi **veya** yapılandırılmış dizinde ayrıca doğrulanabilen güçlü bir güncel görev bağı gerekir; yalnız ünvan kelimesinin eşleşmesi ya da departman üyeliği yetmez. Ayrılmış kişi güncel havuza girmez. İki aday yolunun başarılı ve tamamlanmış değerlendirmesi güvenli bir doğrudan temas önermiyorsa, alan–birincil takım eşleşmesi güçlü ve yöneticilik güncelse **model** yöneticiyi yalnız doğru uygulayıcıyı bulmak için önerebilir. İz veya güçlü güncel görev bağı bulunmaması, izdeki kişinin ayrılmış olması bu koşula yol açabilir; model hatası veya tekil önerinin denetimde elenmesi ise kodun yöneticiyi kendiliğinden eklemesine izin vermez. Takım veya yönetici ilişkisi doğrulanamıyorsa bu yönlendirme de yapılamaz.

Yönetici önerisinin gerekçesi yalnız dizinin kanıtladığı şeyi söyler: “Currently manages the relevant team; ask who should take this idea forward. Ownership and subject expertise are unverified.” Daha kuvvetli bir iddia için ek görünür kaynak gerekir. İş izi yolundan da gelen kişi tekilleştirilir, fakat iki ayrı dayanağı korunur. **Her iki yolun kişileri de aynı alanın aday havuzuna girer; alan-başı model birden çok kişiyi rolleriyle önerebilir, kod her öneriyi ayrı denetler.**

### 6. Alan başına adayları değerlendir ve gösterilebilir kişileri belirle

- **Girdi:** Tek alanın sınırlı, tekilleştirilmiş aday havuzu: erişilebilir Slack/Jira/GitHub/doküman parçaları, her parçanın kişiyle bağlantı türü, tarihler ve güncel org/yönetici ilişkileri. Hangi kişinin iş izinden, hangisinin yalnız org bilgisinden geldiği korunur; restricted metin veya oradan türetilmiş kişi yoktur.
- **Teknoloji:** Adayı olan alan başına şemalı bir LLM çağrısı; alanlar paralel değerlendirilebilir. Hiç adayı olmayan alanda çağrı yapılmaz. İki aday yolu tek bir gizli sahiplik puanına indirgenmez. Model tek bir kazananla sınırlanmaz; **incelenen havuzdan birden çok dayanaklı kişiyi** gerekçeleriyle önerebilir. Aday havuzu gecikme ve bağlam bütçesi için sınırlıdır; modelin bu havuzdaki her uygun kişiyi bulduğu iddia edilmez.
- **Model çıktısı:** Sırasız `people` listesi; her öğede havuzdaki kişi ID'si, **doğrudan temas / danışılacak kişi / yalnız yönlendirme teması** rolü, güven, dayanak türü, görünür kaynak ID'leri, görüşme sorusu ve doğrulanmamış olgular. Liste boş olabilir; aynı kişi aynı alanda tek kez bulunur. Her önerinin gerekçesi **“Bu kişi hakkında ne biliyoruz?”** ve **“Maya ona hangi soruyu soracak?”** sorularını cevaplar. İş izi varsa model, çalışmanın alana ilgisini (**doğrudan / komşu-bağımlı / ilgisiz**), kişinin çalışmayla bağlantısını ve güncel göreve uygunluğunu karıştırmadan değerlendirir; bunlardan birleşik bir sahiplik skoru üretmez. Yalnız org bilgisi olan aday geçmiş çalışma varmış gibi gösterilmez; yönetici yönlendirmesi modelin açık önerisini gerektirir.
- **Kişi başına kod kontrolü:** Her ID çağrının aday havuzunda ve dizinde mi; olgusal iddialar için verilen kaynaklar Maya'ya görünür mü; kişi şirket içinde hâlâ aktif mi; güncel görev ve yönetici ilişkisi doğrulanıyor mu; dizin kaydı geçmiş iş iddiası olarak mı kullanılmış; olgusal gerekçeler uygun kaynak ID'leriyle destekleniyor mu? Görüşme sorusu ve doğrulanmamış iddia, kanıtlanmış olgu gibi kaynaklandırılmaz. Doğrudan temasın görünür izi veya ayrıca doğrulanmış güncel görev bağı, yönlendirme temasının güncel yöneticilik bağı var mı? **Şirketten ayrılmış kişi hiçbir rolde gösterilemez.** Takım değiştirmiş ama hâlâ aktif kişi, eski ve gerçekten ilgili bir izi varsa sınırlı danışman olabilir.
- **Yönlendirme kararı:** Önce modelin açıkça önerdiği kişiler ayrı ayrı denetlenir. Yönetici ancak model onu açıkça önermişse, geçerli çıktıda doğrudan temas önerilmemişse ve yönlendirme koşulları doğrulanmışsa gösterilir. Model timeout'u, geçersiz şema veya reddedilmiş doğrudan temas önerisi kodun kendiliğinden yönetici eklemesine ya da göstermesine izin vermez.
- **Tekil ret ve başarısızlık:** Geçersiz kişi/kaynak elenir; şema bütünüyle geçersizse alan tamamlanmamış kalır. Önerilmiş bir doğrudan temas denetimde elenir ve başka geçerli doğrudan temas yoksa bu ret tek başına “doğrudan temas bulunamadı” sonucu sayılmaz: varsa modelin önerdiği yönetici de gösterilmez, kalan rol koşullarını karşılayan kişiler korunur ve doğrudan temas incelemesinin tamamlanamadığı belirtilir. Böyle bir durumda gösterilebilir kişi kalmamışsa alan *inceleme tamamlanamadı* olur; *not-found* olmaz. İkinci bir model çağrısıyla sessizce “tamir” edilmez. Kod **yapısal dayanağı** doğrular; kaynağın projeyle ve kişinin rolle anlamsal uygunluğunu tek başına ispatlayamaz. Bunlar model kararında ve farklı cümlelerle değerlendirmede ölçülür.
- **Çıktı:** Önerilmiş ve kişi başına denetimden geçmiş herkesin rolü ayrılmış, sırasız listesi; ya da neden güvenle kişi gösterilemediği. Danışman tek başına bulunabilir: bu, eksik doğrudan teması gizlemez. “İlgili erişilebilir iş izi bulunamadı” **arama bulgusudur**; dizin yolundan kişi gösterilmesiyle birlikte de bulunabilir ve bütün şirkette böyle bir iş yapılmadığını kanıtlamaz. *Gösterilecek kişi yok* yalnız tamamlanmış incelemenin sonucudur; timeout, geçersiz çıktı veya incelenecek havuzun bağlam bütçesine sığmaması ise *inceleme tamamlanamadı* sonucudur. Tekil ret yüzünden doğrudan temas incelemesi tamamlanamadığında kalan güvenli kişiler gösterilse de bu belirsizlik gizlenmez. Retrieval havuz sınırının veya modelin kaçırdığı uygun kişiler, retrieval → havuz → model → kart aşamalarında ayrı geri çağırma ölçümüdür. Havuz bağlam bütçesine sığmaz veya model çıktısı kesilirse kısmi listeyi eksiksizmiş gibi sunmak yerine inceleme tamamlanamadı denir. Model çağrısı başarısızsa kod onun yerine kişi seçmez; alan yeniden denenebilir.

Gerçek model çıktısı **şemalı JSON** olmalıdır; çoklu kişi listesinde kimlik, rol, kaynak, dayanak türü, güven, doğrulanmamış iddia ve görüşme sorusu gibi alanlar kodca kişi başına doğrulanır. Aşağıdaki okunabilir metin örneği JSON şemasının kendisi değildir.

İstek düzeyindeki refusal hiçbir alan kartı üretmez. Etki analizinden geçmiş her alanın gösterilebilir sonucu aşağıdaki öncelikli biçimlerden biridir; “ilgili iş izi bulunamadı” bunlardan bağımsız bir arama bulgusudur:

| Durum | Maya'nın gördüğü |
| --- | --- |
| İnceleme bütçe, timeout veya geçersiz şema nedeniyle tamamlanamadı | *İnceleme tamamlanamadı*; kısmi liste veya otomatik yönetici yönlendirmesi yok. |
| Önerilen doğrudan temas denetimde elendi; geçerli başka doğrudan temas yok | Kalan denetlenmiş kişiler varsa görünür ve doğrudan temas incelemesinin tamamlanamadığı belirtilir; yoksa *inceleme tamamlanamadı*. Yönetici bu ret yüzünden eklenmez veya gösterilmez. |
| Denetlenmiş doğrudan temas var | Dayanağı, rolü ve sorusuyla tüm denetlenmiş doğrudan temaslar ve varsa danışılacak kişiler görünür; yönetici yalnız yönlendirme diye eklenmez. |
| Başarılı model değerlendirmesi doğrudan temas önermedi; geçerli yönetici yönlendirmesi önerdi | **Yönlendirme teması** ve varsa danışılacak kişiler görünür; geçmiş sahiplik/uzmanlık iddiası yok. |
| Yalnız danışılacak kişi gösterilebilir | Danışman dayanağıyla görünür; doğrudan temas bulunmuş gibi sunulmaz. |
| İki aday yolundan da gösterilecek kişi çıkmadı ve inceleme tamamlandı | *Not-found*; isim yok. Buna geçerli boş model seçimi veya adaysız alan dahildir. |

#### Hayalî kampanya alanı: LLM'nin gördüğü ve önerdiği kişiler

Maya, kampanyanın **retail marketing** olduğunu ve AI'ın öneri hazırlayıp insanın lansmanı onaylayacağını söylemiş olsun. Aşağıdaki kişi ve kaynaklar yalnız bu örnek için uydurulmuştur. Nina ve Elena, Growth Marketing'e bağlı **aktif kişiler** arasından ünvan/görev–alan anahtar kelime eşleşmesiyle; Marcus yöneticiye ayrılan yer sayesinde org havuzuna girer. Priya ve Owen ise izinli iş izi aramasından gelir; hazır konu temasları değildir. Model şirketteki herkesi değil, bu alanın sınırlı, tekilleştirilmiş havuzunu görür:

```text
Area: Growth Marketing
Need: Find who can explain the current campaign planning and launch review.
Project: AI prepares retail audiences, copy, budgets and schedules;
         a person approves launch. Ownership of this new idea is unknown.

Nina — current Growth Marketing member; Campaign Operations Specialist
  jira:MKT-482 | 2026 | assignee | "Finalize audience approval checklist."
  slack:retail-814 | 2026 | message author |
    "I will coordinate launch review with the channel owners."
Elena — current Growth Marketing member; Campaign Analyst
  jira:MKT-482 | 2026 | reporter, not assignee
  slack:retail-815 | 2026 | message author |
    "I prepared the campaign performance report."
Marcus — current Growth Marketing manager
  directory:growth-manager | current | manager relationship;
    no relevant accessible work trace found in this search
Priya — formerly Growth Marketing, now Brand Review
  docs:campaign-review-2023 | 2023 | author |
    "Retail campaign review and approval process."
  directory:priya-current | current | active in Brand Review
Owen — current Campaign Platform member
  github:campaign-scheduler-pr-76 | 2026 | change author |
    "Update campaign scheduler integration."
```

GitHub kaydı Owen'ı **platform** için güçlü bir aday yapabilir; bu kayıt onu pazarlama lansman onayının sahibi yapmaz. Jira reporter olmak da assignee olmakla eşit değildir. Bu alandaki örnek, sırasız çoklu kişi değerlendirmesi:

```text
Direct contact: Nina
  Why: Assigned the audience approval checklist [jira:MKT-482].
       Coordinated a launch review [slack:retail-814].
  Ask: "Who should review AI-prepared campaigns before launch?"
  Unverified: Ownership of this new AI initiative and AI expertise.
Advisor: Priya
  Why: Authored an earlier review process [docs:campaign-review-2023].
  Ask: "Which prior review steps could be relevant?"
  Caution: The record is old; Priya is now in Brand Review
            [directory:priya-current].
  Unverified: Current Growth Marketing ownership and applicability of
              the old process.
Not shown in this area: Elena's visible contribution concerns reporting;
                        Marcus has only the management link while Nina is a
                        suitable direct contact; Owen's trace concerns
                        platform integration.
```

Bu, modelin serbestçe isim icat etmesi değildir. Kod gösterilen kişi ve kaynakların havuzda, Maya'ya açık ve belirtilen bağlantı türünde olduğunu kontrol eder. Bu örnekte **Nina doğrudan temas, Priya danışılacak kişi** olarak görünür; Marcus, Nina varken sırf yönetici diye yönlendirme teması eklenmez. Nina'nın bu alana uygun, Elena'nın ise bu soruya dayanağının yetersiz olduğu modelin bağlamsal değerlendirmesidir; kod bu anlamsal hükmü tek başına ispatlayamaz. İş izi eskiyse, ayrışıyorsa veya yalnız ismi anıyorsa model ihtiyatlı davranabilir ya da boş liste döndürebilir.

Aynı alan için başarılı model değerlendirmesi **güvenli bir doğrudan temas önermeseydi** — örneğin ilgili erişilebilir iz bulunmasa veya iz yalnız ayrılmış bir kişiye işaret etse — güçlü Growth Marketing eşlemesiyle güncel yönetici Marcus yine aday olabilirdi. Model onu açıkça önerir ve koşullar denetimden geçerse yalnız şu amaçla gösterilebilir: “Currently manages Growth Marketing [directory:growth-manager]. Ask who should review this proposal; ownership and expertise are unverified.” Düşük sahiplik güveni, bu **yönlendirme temasını** göstermeye engel değildir; aynı amaç ve belirsizlik kartta korunur. Model timeout olursa veya önerdiği tek doğrudan temas denetimde elenirse kod Marcus'u kendiliğinden seçmez; doğrudan temas incelemesi tamamlanmış sayılmaz.

APP2 için de aynı ayrım geçerlidir: İlgili eski ödeme işini bilen kişi artık başka takımdaysa bir danışman olabilir; güncel takımdan uygun kişiler desteklenen iddialarıyla doğrudan temas, gerektiğinde yönetici yalnız yönlendirme teması olabilir. Restricted içerikte geçen ama başka görünür dayanağı olmayan biri karta girmez. Örnekteki fraud/risk alanı, az sayıdaki erişilebilir izi rastgele bir kişiyle doldurmaz; inceleme tamamlandığında güvenli bir aday yoksa not-found olarak kalır.

### 7. Kartı oluştur ve alanların önceliğini değerlendir

- **Girdi:** Etki analizinden geçmiş alanlar; her alanın sırasız, rolü doğrulanmış kişi listesi, boş veya tamamlanamamış sonucu ve doğrulanamayan olguları. Kart-geneli modele yalnız güvenli alan gerekçeleri, sonuç durumları ve gösterilebilir kişi bilgileri verilir; elenmiş kişiler ve restricted ayrıntılar verilmez.
- **Model görevi:** Etki analizinden geçen alanlar varsa bir şemalı LLM çağrısı yalnız **mevcut alan ID'lerinin dikkat sırasını** ve varsa **alanlar arasında henüz cevaplanmamış tek bir ortak soruyu** önerir. Anlamlı bir ortak soru yoksa soru boş kalır; mevcut dayanakların söylemediği yeni bir olgu eklenmez. Kişileri seçmez, azaltmaz veya sıralamaz; boş ama kritik alanları görünmez kılmaz. Temsili APP2 örneğinde ödeme operasyonları ile hukuk/uyum arasındaki açık ortak soruyu gösterebilir; bu alan sırası veya görüşülecek kişiler sabit kural değildir.
- **Kod kontrolü ve çıktı:** Sıra, doğrulanmış mevcut alan ID'lerinin **tamamını birer kez** içermelidir; hiçbir alan karttan çıkmaz. Ortak soruda yeni kişi, kaynak ID'si veya kısıtlı ayrıntı var mı? Kod yapısal sınırı denetler; sorunun mevcut olgulardan anlamsal olarak çıkıp çıkmadığı farklı cümlelerde ayrıca ölçülür. Geçersiz veya zaman aşımına uğrayan çıktı kartı değiştirmez: alanlar etki analizinden gelen deterministik sırada kalır, modelden öncelik iddiası veya ortak soru gösterilmez. Kişiler her alanda role göre gruplanır; aynı roldekiler için sabit, **öncelik ima etmeyen** bir görüntü sırası kullanılır. Ortak soru ve kişi başına görüşme soruları eylem adımları veya gönderim taslakları değildir. Kart gösterimi dış iletişim veya koordinasyon kaydı başlatmaz. Yönlendirme amacı ve belirsizlik kartta değişmeden kalır. Kartta her kişi için dayanak ve görüşme amacı ile *not-found* / tamamlanamamış alanlar görünür; restricted kaynağın varlığına ilişkin not gösterilmez.

Kart kişi başına üç ayrı soruyu kolay okunur biçimde yanıtlar: **Why this person?** (görünür dayanak, kaynak türü, kişinin o kaynakla bağı ve tarih), **Ask them?** (görüşmenin somut sorusu), **Not established?** (proje sahipliği veya uzmanlık gibi doğrulanmamış iddia). Kampanya örneğinde iki farklı dayanağın kullanıcıya görünen biçimi:

| Kişi | Why this person? | Ask them? | Not established? |
| --- | --- | --- | --- |
| Nina (direct contact) | Assigned the audience approval checklist in 2026 `[jira:MKT-482]`; wrote the launch review message in 2026 `[slack:retail-814]`. | “Who should review AI-prepared campaigns before launch?” | Ownership of this AI initiative and AI expertise. |
| Priya (advisor) | Authored a review process in 2023 `[docs:campaign-review-2023]`; now in Brand Review `[directory:priya-current]`. | “Which prior review steps could be relevant?” | Current Growth Marketing ownership and applicability of the old process. |
| Marcus (alternative without a relevant work trace found) | Currently manages Growth Marketing `[directory:growth-manager]`; no sufficient relevant accessible work trace was found in this search. | “Who should route this proposal to the right practitioner?” | Prior campaign work, ownership of this initiative and subject expertise. |

Tablo bu Türkçe belgenin açıklamasıdır; ürün metni İngilizcedir. Kullanıcıya görünen örnekte kaynak kimliği ile tarih, kişinin neden aday olduğunu anlamaya yarar; rastgele bir citation semantik iddiayı kanıtlamış sayılmaz. Tam kaynak ayrıntıları kartı boğmadan açılabilir.

Kısıtlı başlık, içerik, kayıt ID'si ve yalnız orada geçen isimler model girdisine, karta, kullanıcıya görünen kaynak ayrıntılarına veya loglara girmez.

### 8. Kartın gösterimi ve oturumun korunması

- **Girdi:** Alan kartı, rolü ayrılmış tüm gösterilebilir kişiler, boş veya tamamlanamamış alan durumları, varsa alan önceliği ve alanlar arası ortak soru. Bu Workbot'un nihai önerisidir; Maya arayüzde temas seçmez, çıkarmaz veya sıralamaz. Kart-geneli önceliklendirme başarısızsa güvenli kişilerin hiçbiri kaybolmaz. Workbot Maya adına mesaj, arama veya davet başlatmaz; Maya gösterilen kişiye isterse kendisi yazar veya onu arar.
- **Çıktı:** Gösterilen alan kartı, **tüm kişi/rol/dayanakları, varsa alan önceliği ve ortak sorusuyla** çalışma oturumunda korunur. Tekrar yükleme aynı oturum kartını getirir; yeniden modele sorup farklı kişilere dönüşmez. Aynı oturumda yeni bir açıklama cevabı verilirse önceki kart geçersizleşir; yeni sonuç tamamlanmadan eski kart güncelmiş gibi gösterilmez. Farklı bir proje cümlesi yeni bir oturum açar. Oturum durumu onaylı koordinasyon kaydı değildir; kartın gösterimi böyle bir kayıt veya dış iletişim oluşturmaz.
- **Yeniden görüntüleme sınırı:** Oturumun Maya'nın kimliğine ve workspace'ine bağlılığı, karta bağlı kaynakların görünürlüğü ve sürümü/içerik özeti ile gösterilen kişilerin aktifliği ve dayanak olarak kullanılan güncel dizin ilişkileri yeniden yüklemede de doğrulanır. Erişim, kaynak içeriği veya bu güncel ilişkiler sonradan değişmişse eski kart veya kaynak ayrıntıları gösterilmez ve aynı kartı yeniden modelden üretmiş gibi davranılmaz; yeni bir istek gerekir. Bunlar değişmemişse oturum kartı aynen korunur.
- **Güvenlik:** Refusal gösterilebilir kişi kartı üretmez. Serbest metinden veya restricted kaynaktan yeni bir kişiyi karta geçirmek yasaktır. Maya'nın kişi önerisiyle kartı değiştirme veya yeniden değerlendirme döngüsü hedef sürümün kapsamında değildir.

## Yarışma simülasyonunun ölçüsü

Simülasyon iki ayrı katmandır:

- **Arka plan:** Hedeflenen darboğaz, binlerce çalışanın bulunduğu çok takımlı bir şirkette doğru kişiyi keşfetmektir; yarışma sürümü gerçek şirket verisi veya canlı bağlayıcı kullanmaz. İlk sınama için örneğin **2.000–5.000 sentetik kişilik yapılandırılmış dizin** düşünülebilir; bu bir ürün limiti veya gerçekleşmiş performans sonucu değil, ölçümle doğrulanacak başlangıç varsayımıdır. Takım, güncel/geçmiş görev, yönetici ve aktiflik ilişkileri ucuzca temsil edilebilir; herkese zengin biyografi, hazır konu teması veya ayrıntılı iş izi verilmez. İş izleri dizinden daha seyrektir: birkaç tutarlı ana vaka çevresindeki çok kaynaklı ilgili kayıtlar, eski ve zayıf bağlar, çelişkiler, erişilemeyen kayıtlar ve konu bakımından yakın **zor negatifler** dikkatle tasarlanır. Programatik arka plan kayıtları aynı şablonun binlerce kopyası olmamalıdır. İş izi sayısı ve yoğunluğu, yanlış pozitif üretmeden doğru kişiyi geri çağırma ve gereksiz yönetici yönlendirmesinden kaçınma sonuçlarına göre ayarlanır; bütün şirketteki her çalışanın geçmişini temsil ettiği iddia edilmez.
- **Sunum:** Hakemin birkaç saniyede takip edebileceği tek fikir, birkaç zengin kişi ve 2–3 belirgin kaynak ekranda kolay okunur. Alanlar ve roller gruplanabilir veya ayrıntıları açılabilir; bu, doğrulanmış kişileri ya da boş alanları gizleyen bir “ilk iki” vitrini değildir. Arka plandaki aday keşfi 10–12 hazır kişiye veya sabit senaryo cevaplarına indirgenmez.

İstek sırasında bütün dizin veya korpus LLM'e gönderilmez. Hazır indekslerde grant-filtreli arama ve ilgili org-unit filtrelemesi **sınırlı aday havuzu** oluşturur; model yalnız o alanın dayanaklarını görür. Bu yapı binlerce kişilik dizinden aday daraltmayı sentetik veride sınar; gerçek kurumsal veride kişi bulma başarısını, yetkilendirmeyi veya üretim ölçeğini doğrulamaz. Sentetik kaydın türü ve kişi bağlantısının gücü gerçekte farklı olduğu gibi korunur.

Korpus ve değerlendirme bütününde aşağıdaki zor vakalar temsil edilir; her birini her ana senaryoya eklemek gerekmez. Son satır bir korpus kaydı değil, ayrı bir giriş cümlesiyle yapılacak keşif sınamasıdır:

| Vaka türü | Amaç |
| --- | --- |
| Doğrudan iş izi | Assignee/yazar gibi güçlü bağdan doğru kişiyi bulmak |
| Anılma ve zayıf bağ | Yalnız adı geçen kişiyi dayanağı olmadan doğrudan temas yapmamak |
| Eski iz | Takım değiştirmiş kişiyi yanlış güncel sahip gibi göstermemek |
| Ayrılmış çalışan | Aktif olmayan kişiyi temas veya danışman yapmamak |
| Komşu alan | Ödeme işini yalnız “wallet” kelimesiyle karıştırmamak |
| Çelişkili kaynak | Farklı kişileri işaret eden izlerde belirsizliği taşımak |
| Restricted ince alan | Erişilemeyen kayıttan kişi veya varlık ipucu üretmemek; iki aday yolundan da güvenle gösterilecek kişi çıkmazsa not-found göstermek |
| Doğrudan iz olmayan yeni fikir | Model açıkça önerirse ve koşullar denetlenirse güncel yöneticiyi yalnız yönlendirme teması olarak sunmak |
| Hazır olmayan cümle | Sonucun demo cümlesine sabitlenmediğini kanıtlamak |

Ürün gerekliyse iki soruyu sırayla sorabilir; her istek veya kısa sunum iki soru sormak zorunda değildir. Üç dakikalık bir gösterimde tek açıklayıcı soru genellikle yeterlidir; ikinci soru yalnız cevabı alanı veya kişi rollerini gerçekten değiştirecekse sorulur. Hedef demo akışı: hazır olmayan bir cümle ver → gerekirse tek açıklama sorusunu cevapla → arama, aday havuzu ve çoklu kişi değerlendirmesini izlenebilir göster → kaynaklı alan kartındaki rolleri, görüşme sorularını, varsa alan önceliği ve alanlar arası ortak soruyu göster → reload'da aynı oturum kartının döndüğünü kanıtla. Demo kolaylığı için soru sayısı, kişiler veya sonuçlar cümleye özel sabitlenmez; simülasyon etiketi korunur.

## Nasıl değerlendirilir?

İsim sayısını veya tek birleşik bir kalite puanını hedeflemeyiz. Ayrı raporlanacak sonuçlar:

1. **Alan kapsamı:** Gerçekten görüşülmesi gereken alanlar bulunuyor mu; ilgisiz alanlarla kart şişiyor mu? APP2 ve kampanya dışındaki farklı proje cümlelerinde kaçırılan kritik alanlar ayrıca kaydedilir. Tekrarlayan kaçırmalar görülürse sınırlı bir yeniden değerlendirme düşünülür; bu, şimdiki varsayılan istek akışının parçası değildir.
2. **İş izi geri çağırma ve alan değerlendirmesi:** Erişilebilir kuvvetli iş izi taşıyan kişi retrieval → modele gönderilen havuz → alan değerlendirmesi → kart aşamalarının hangisinde kayboluyor? İncelenen havuzdaki uygun kişilerden model kaçı önerdi; önerilenlerin kaçı denetimden geçip doğru rolle gösterildi? Jira assignee'si yerine yalnız anılan veya ilgisiz GitHub katkıcısı mı yükseltiliyor? Olgusal iddiaların kaynakları gerçekten dayanak mı; görüşme sorusu ve belirsizlik kanıtlanmış olgu gibi mi sunuluyor? Kişi sayısı tek başına başarı ölçütü değildir; geri çağırma ve yanlış pozitifler ayrı raporlanır.
3. **Org havuzu ve yönlendirme yararı:** İlgili aktif kişi org filtresinde mi yoksa LLM değerlendirmesinde mi kayboluyor? Ünvan eşleşmesi eksik kişiyi kaçırıyor veya tek başına doğrudan temas gibi mi sunuluyor? Görünür iş izi ya da ayrıca doğrulanmış güçlü güncel görev bağıyla uygun aktif doğrudan temas çıkmadığında güçlü alan–takım eşleşmesi ve güncel yöneticiyle yararlı bir yönlendirme yapılıyor mu? Uygun doğrudan temas varken, model çağrısı hata verdiğinde veya önerilen doğrudan temas denetimde elendiğinde yönetici gereksiz yere mi gösterildi? Tekil ret sonrası güvenli danışmanlar korunup inceleme belirsizliği açıkça belirtiliyor mu; ayrılmış kişi önerildi mi?
4. **Soru yükü, iddia ve alan önceliği:** Sorular cevabın sonucu değiştirdiği durumlarda mı soruluyor, Maya gereksiz iki soruyla yoruluyor mu? Kişi kartındaki dayanak–soru–doğrulanmamış iddia ayrımı okunuyor mu? Yönetici geçmiş sahip veya uzman diye; komşu iş izi doğrudan deneyim diye sunuluyor mu? Üçüncü görev alanlar arasında gerçekten açık kalan tek bir ortak soru buluyor mu, yoksa kişi başına soruları tekrarlayıp yeni olgular mı uyduruyor? Kritik boş alanı veya güvenli kişileri gizliyor mu; deterministik alan sırasına göre ölçülebilir katkısı var mı?
5. **Güvenlik ve oturum durumu:** Erişilebilir verisi aynı iki korpustan birine restricted kayıt eklendiğinde BM25 skorları veya sıralama ve kullanıcıya görünen kişi, kaynak ya da restricted varlığına ilişkin sinyal değişiyor mu? Kısıtlı başlık, içerik, kayıt ID'si veya yalnız orada geçen kişi sızıyor mu? Cevapsız soru ve eksik olgu uyduruluyor mu; yanıtlanan her soru etki analizini yeniliyor mu? Eşlenemeyen birincil org unit tüm isteği güvenle durduruyor mu; tamamlanamayan kişi incelemesi “kimse yok” diye mi anlatılıyor? Kart gösterildikten sonra otomatik mesaj, davet veya koordinasyon kaydı oluşturuluyor mu? Cevaplar ile oturum kartındaki tüm kişi/rol/dayanaklar ve varsa alan önceliği/ortak soru aynı kimlik/workspace, erişim, kaynak sürümü ve güncel dizin ilişkileriyle yeniden yüklemede korunuyor mu; yeni cevap veya bunlardan birinin değişmesi eski kartı görünür bırakıyor mu?
6. **Performans ve ölçek sınaması:** Cevaplarla tekrarlanan etki analizi, hazır indekslerden izinli arama, alan değerlendirmesi ve kart-geneli öncelik süreleri ayrı; yapılan ve atlanan model çağrısı, alan sayısı, paralel fan-out ve toplam süre farklı cümle ve tekrarlarda görünür. Aynı ilgili kişileri ve dayanakları koruyarak küçük ve genişletilmiş sentetik dizinlerde retrieval → havuz → kart kayıpları, konuya yakın yanlış pozitifler, gereksiz yönetici yönlendirmesi, izin filtresi ve aşama süreleri karşılaştırılır. Tamamen alakasız dolgu kayıtları ekleyip değişmeyen kart almak, tek başına ölçek veya kalite kanıtı sayılmaz.

**Gerçek keşif mi, hazır cevap mı?** Gösterimde kullanılan cümlenin yanında önceden hazırlanmamış bir cümle ve doğrudan iş izi olmayan bir fikir çalıştırılır. Karttaki her adayın izinli BM25/Qdrant aramasından veya güncel dizin filtresinden geldiği izlenir. Bir kişinin iş izi bağlantısı değiştirildiğinde veya görünür kaynak erişimi kaldırıldığında aday havuzunun ve uygun durumda model çıktısının değişip değişmediği ölçülür; sonuçlar her durumda aynı kalıyorsa keşif iddiası doğrulanmamıştır. Bu deney yalnız ağsız regresyon veya yalnız güzel bir demo kartı değildir: model kararının niteliği ayrı, opt-in canlı koşularda ölçülür. Çok kaynaklı değerlendirme ayrıca yalnız takım yöneticisini göstermeye dayalı basit yönlendirmeyle karşılaştırılır; fark yaratmıyorsa karmaşıklık gerekçesizdir.

Ağsız testler şema, güvenlik ve akış regresyonunu; açık seçimli canlı koşular model davranışını ölçer. Ana senaryo, yeni fikir ve restricted ince alan ayrı değerlendirilir. Güzel görünen tek kart veya tek hızlı koşu tasarımı doğrulamaz.

## Uygulamadan önce açık bırakılan kararlar

- Güncel takım yöneticisini yönlendirme teması seçmek için alan–takım eşleşmesi ne kadar güçlü olmalı? Yöneticilik doğrulanır; sırf departman üyeliği yeterli değildir. Hangi yapılandırılmış güncel görev bağı, salt ünvan kelimesini aşarak doğrudan temas için yeterince güçlü sayılır?
- Org-aday havuzunun kesin üst sınırı, yöneticiye ayrılan yer, deterministik sıralama ve ünvan/görev eşlemesinde kullanılacak yapılandırılmış dizin alanları ne olmalı? Bunlar farklı cümlelerde geri çağırma ve gecikmeyle ölçülmeli.
- İş izi **doğrudan** ve **komşu** olarak hangi örneklerde ayrılacak? Eşikler çeşitli cümlelerde sınanmalı.
- Ölçümler kritik alanların tekrar tekrar kaçırıldığını gösterirse, sınırlı yeniden değerlendirmeyi hangi güvenli sinyal tetiklemeli? Her arama hit'i otomatik alan açmamalı.
- Korpusun zor vaka türleri hangi ana vakaların çevresinde, kaç örnekle kurulmalı; dizin büyüklüğü ve iş izi yoğunluğu arttığında ilgili kişilerin geri çağırması ile yanlış pozitifler nasıl değişiyor? Restricted kayıtlar erişilebilir arama indeksine girmeden ve kullanıcıya varlık ipucu üretmeden izin kontrolleri nasıl sınanmalı?
- Binlerce kişilik dizindeki org-unit sayısı artarsa etki analizine verilen gerçek ID/ad listesinin bağlam bütçesi ve alan kapsamı nasıl sınanmalı? Birincil eşleme başarısızlığının tüm isteği ne sıklıkla durdurduğu ölçülmeli. Listenin tamamının her ölçekte modele sığacağı varsayılmaz; güvenli bir daraltma gerekip gerekmediği değerlendirmeyle kararlaştırılır.
- Kart-geneli alan önceliklendirmesi ve tek ortak soru hangi cümlelerde deterministik alan sırasına karşı gerçek fark yaratıyor? Üçüncü görev hedef sürümde kalır; ölçüm yararını ve gecikme maliyetini ayrıca göstermeli.
- Alan-başı modelin **zorunlu şemalı JSON** çıktısında sırasız kişi listesi, roller, kaynak, dayanak türü, güven, belirsizlik ve görüşme sorusu nasıl temsil edilmeli? Restricted kaydın varlığı kullanıcıya veya modele aktarılmaz.
- İki açıklama sorusu, alan/aday havuzu sınırları ve alan-başı çağrı fan-out'u gerçek kalite, kullanıcı yükü, gecikme ve gösterim sonuçlarına göre nasıl ayarlanacak? Çıktıda keyfî kişi sayısı hedefi yok; bütçe yüzünden tamamlanamayan inceleme nasıl açıkça işaretlenecek?

Bu sorular netleşmeden embedding modelini veya prompt cümlelerini seçmek tasarımı erken kilitler. Qdrant'ta önceden indeksleme varsayımı, bu seçimlerin ve üretim dağıtım biçiminin yapıldığı anlamına gelmez.
