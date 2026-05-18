#!/usr/bin/env python3
"""Morning Brief v4"""
import calendar as _cal
import feedparser
import html as html_lib
import imaplib
import email
from email.header import decode_header
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
OUTPUT_DIR   = Path(__file__).parent
OUTPUT_FILE  = OUTPUT_DIR / "index.html"
CONFIG_FILE  = OUTPUT_DIR / "telegram_config.json"
SESSION_FILE = OUTPUT_DIR / "telegram_session"
MAX_PER_SOURCE = 10

# ── Email newsletters ─────────────────────────────────────────────────────────
EMAIL_ADDRESS  = "ton.adresse@gmail.com"      # ← à remplir
EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"        # ← App Password Gmail (pas ton mdp normal)
EMAIL_SUBJECTS = ["French Tech Updates"]      # ← ajouter d'autres sujets si besoin
EMAIL_LIMIT    = 10                           # nb de mails max par sujet

# ── Kalshi prediction markets ─────────────────────────────────────────────────
# Public API — aucune auth requise pour lire les marchés
KALSHI_API   = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_LIMIT = 200  # marchés fetchés par catégorie, on garde les top N après tri
KALSHI_CATS  = [
    ("Economics",  "macro", 8),   # (categorie Kalshi, cle interne, nb a afficher)
    ("Technology", "tech",  8),
]
# Mots-cles a bloquer — on exclut le politique et le sport
KALSHI_BLOCK = [
    "trump","biden","harris","democrat","republican","election","senate","house",
    "congress","president","governor","nfl","nba","mlb","nhl","fifa","super bowl",
    "oscar","emmy","grammy","celebrity","kardashian",
]

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = "YOUR_GOOGLE_AI_STUDIO_KEY"   # ← remplir sur aistudio.google.com
GEMINI_MODEL   = "gemini-1.5-flash"

TELEGRAM_CHANNELS = [
    ("AFP", "https://t.me/+5VtjHHeuarNjYTBk"),
]
TELEGRAM_LIMIT = 30
# ── AFP routing keywords ──────────────────────────────────────────────────────
TECH_KEYWORDS = [
    "ai ", "startup", "ipo", "fundrais", "venture capital", "silicon", "tech",
    "software", "openai", "anthropic", "apple", "google", "microsoft", "amazon",
    "meta ", "nvidia", "semiconductor", "chip", "robot", "crypto", "bitcoin",
    "intelligence artificielle", "numérique", "levée de fonds",
]
MACRO_KEYWORDS = [
    "economy", "inflation", "fed ", "ecb ", "interest rate", "gdp", "recession",
    "market", "stock", "bond ", "currency", "euro ", "dollar", "oil ", "commodities",
    "bce ", "taux ", "économie", "bourse", "croissance", "banque centrale",
    "trade", "tariff", "budget", "fiscal", "deficit", "debt ",
]
# ══════════════════════════════════════════════════════════════════════════════
#  CONFLICTS
# ══════════════════════════════════════════════════════════════════════════════
CONFLICTS = [
    {"id":"ukraine",  "name":"Ukraine — Russia",          "type":"conflict","lat":49.0, "lon":31.5,
     "started":"February 2022",
     "summary":"Russia launched a full-scale invasion of Ukraine in February 2022, triggering the largest armed conflict in Europe since World War II. Fighting continues along an approximately 1,000 km eastern front across Donbas, Zaporizhzhia, and Kharkiv oblasts, with Russian forces making slow incremental gains. Ukraine has responded with long-range drone strikes deep into Russian territory, hitting oil refineries, airfields, and Moscow itself. NATO allies have committed over $100B in military and financial aid, including F-16s, ATACMS, and Patriot systems. Casualty figures on both sides are estimated in the hundreds of thousands. Diplomatic efforts remain deadlocked; no credible peace framework has emerged and the war shows no sign of ending.",
     "keywords":["ukraine","russia","kyiv","zelenskyy","zelensky","donbas","kharkiv","kremlin","zaporizhzhia","donetsk","luhansk"]},
    {"id":"gaza",     "name":"Gaza — Israel",             "type":"conflict","lat":31.5, "lon":34.5,
     "started":"October 2023",
     "summary":"Hamas's mass attack on Israel on 7 October 2023 killed approximately 1,200 Israelis and took 250 hostages, triggering Israel's most intense military campaign in decades. The Gaza Strip has been subjected to sustained bombardment and ground operations, with Palestinian death tolls exceeding 45,000 according to Gaza health authorities, the majority civilians. A brief ceasefire in late 2023 allowed some hostage releases but fighting quickly resumed. The UN has declared famine conditions in northern Gaza; virtually all civilian infrastructure has been destroyed. International pressure for a permanent ceasefire has intensified but negotiations between Hamas and Israel, mediated by Qatar and Egypt, have repeatedly collapsed. The West Bank has simultaneously seen rising settler violence and military raids.",
     "keywords":["gaza","israel","hamas","netanyahu","rafah","west bank","idf","ceasefire","hostage","palestin"]},
    {"id":"sudan",    "name":"Sudan Civil War",            "type":"conflict","lat":15.5, "lon":32.5,
     "started":"April 2023",
     "summary":"War between the Sudanese Armed Forces (SAF) and the paramilitary Rapid Support Forces (RSF) erupted in April 2023, rapidly engulfing Khartoum and spreading to Darfur and Kordofan. Over 12 million people have been displaced — one of the world's worst humanitarian crises — with famine declared in several regions. RSF forces have committed widespread atrocities in Darfur that international investigators have characterised as genocide, echoing the 2003 massacres. Khartoum has been devastated by sustained urban combat, its infrastructure reduced to rubble. International attention and humanitarian access remain grossly insufficient; no meaningful peace process is underway.",
     "keywords":["sudan","rsf","darfur","khartoum","sudanese armed"]},
    {"id":"yemen",    "name":"Yemen",                     "type":"conflict","lat":15.5, "lon":47.5,
     "started":"2014",
     "summary":"The Houthi movement (Ansar Allah), backed by Iran, controls northern Yemen including Sanaa. Since October 2023, Houthis have launched hundreds of drone and missile strikes on commercial and military shipping in the Red Sea and Gulf of Aden, forcing major container lines to reroute around Africa and driving up global freight costs. The US, UK, and allied forces have conducted extensive retaliatory strikes on Houthi weapons infrastructure, with limited lasting effect. Separately, a fragile UN-brokered truce between Houthis and the Saudi-backed government has reduced large-scale ground combat in much of the country, though no political settlement is in sight and Yemen remains one of the world's worst humanitarian disasters.",
     "keywords":["yemen","houthi","houthis","red sea attack","aden","sanaa"]},
    {"id":"myanmar",  "name":"Myanmar",                   "type":"conflict","lat":19.0, "lon":96.5,
     "started":"February 2021",
     "summary":"A broad resistance coalition — including the People's Defence Force (PDF) and ethnic armed organisations (EAOs) such as the Arakan Army, TNLA, and MNDAA — has made dramatic territorial gains against the military junta since a coordinated offensive launched in late 2023. Key border towns including Laukkai, Myawaddy, and significant stretches of Shan State have fallen to resistance forces, severing junta control of major trade routes to China and Thailand. The military has lost over a third of its territory and introduced conscription as manpower dwindles. China has mediated fragile ceasefires in border areas to protect its Belt and Road investments, while the US and EU have tightened sanctions on the regime.",
     "keywords":["myanmar","burma","junta","arakan army","tatmadaw","shan state","mandalay"]},
    {"id":"sahel",    "name":"Sahel — Mali / Burkina / Niger","type":"conflict","lat":14.0,"lon":-2.0,
     "started":"2012",
     "summary":"A belt of jihadist insurgency linked to Islamic State Sahel Province (ISSP) and JNIM (al-Qaeda affiliate) continues to expand across Mali, Burkina Faso, and Niger, displacing millions and collapsing state authority across vast rural areas. Military juntas ruling all three countries have expelled French and other Western forces and invited Russia's Africa Corps (formerly Wagner Group) as security partners — a shift that has not improved security outcomes. Burkina Faso's junta has lost control of an estimated 40–60% of national territory. ECOWAS sanctions have proved ineffective. The region faces acute food insecurity and has become a launchpad for attacks reaching coastal West African states including Benin, Togo, and Ghana.",
     "keywords":["sahel","mali","burkina faso","niger junta","aqim","jnim","africa corps","bamako","ouagadougou"]},
    {"id":"drc",      "name":"DR Congo",                  "type":"conflict","lat":-2.5, "lon":28.5,
     "started":"1990s",
     "summary":"M23 rebels, armed and directed by Rwanda according to UN experts, have seized substantial territory in eastern DRC including key parts of Goma, the commercial capital of North Kivu with a population of over one million. The offensive is the most significant territorial shift in the Congo's decades-long conflict and has displaced over six million people in the east alone. Direct DRC-Rwanda confrontation risk is high, with both governments exchanging artillery fire across the border. MONUSCO, the UN peacekeeping mission, is drawing down amid widespread hostility. The Nairobi and Luanda peace processes have produced repeated ceasefires that collapse within days. Coltan and gold mines remain central to the conflict economy.",
     "keywords":["drc","congo","m23","goma","kivu","rwanda drc","kinshasa","afd congo"]},
    {"id":"somalia",  "name":"Somalia",                   "type":"conflict","lat":5.0,  "lon":46.0,
     "started":"2006",
     "summary":"Al-Shabaab controls large swathes of south-central Somalia and continues to mount sophisticated attacks in Mogadishu and increasingly in Kenya and Ethiopia. Despite losing some territory to Somali National Army offensives in 2022–23, the group has rebounded and continues to raise funds through taxation and extortion across its territory. The AU Transition Mission (ATMIS) is drawing down on schedule, creating security vacuums that al-Shabaab is actively exploiting. The federal government in Mogadishu is beset by clan disputes and fiscal crisis. Drought and recurrent flooding have driven acute food insecurity, making Somalia one of the world's most complex humanitarian emergencies.",
     "keywords":["somalia","al-shabaab","mogadishu","atmis","al shabaab"]},
    {"id":"haiti",    "name":"Haiti",                     "type":"conflict","lat":18.9, "lon":-72.3,
     "started":"2021",
     "summary":"Armed gang coalitions led by the G9 federation and the Viv Ansanm alliance have seized control of much of Port-au-Prince and key provincial towns, triggering a full humanitarian and governance collapse. Hospitals, schools, and government offices have been overwhelmed or shut entirely. A Kenyan-led Multinational Security Support Mission (MSS) deployed in mid-2024 but is severely under-resourced and has struggled to make security gains. Over 700,000 people are internally displaced; famine conditions have been declared. Kidnapping for ransom is endemic across the country. A transitional presidential council is attempting to stabilise governance ahead of planned elections, but the political roadmap remains contested.",
     "keywords":["haiti","gang haiti","port-au-prince","kenyan mission"]},
    {"id":"colombia", "name":"Colombia",                  "type":"conflict","lat":4.0,  "lon":-72.0,
     "started":"ongoing",
     "summary":"Dissident FARC factions (Estado Mayor Central and Segunda Marquetalia) and the ELN guerrillas continue active operations across border regions with Venezuela and Ecuador, the Pacific coast, and the Catatumbo region. President Petro's flagship 'total peace' policy led to multiple negotiated ceasefires, virtually all of which have collapsed. The Catatumbo conflict in early 2024 saw intense fighting between the ELN and FARC dissidents, displacing over 30,000 civilians. Coca production and cocaine trafficking continue at record levels, funding all armed groups. Violence against social leaders, indigenous communities, and former FARC combatants who demobilised under the 2016 peace deal remains a persistent and largely unpunished problem.",
     "keywords":["colombia","eln","farc","catatumbo","petro colombia"]},
    {"id":"mozambique","name":"Mozambique",               "type":"conflict","lat":-13.0,"lon":39.5,
     "started":"2017",
     "summary":"An Islamist insurgency (Ansar al-Sunna Muhammadiyah, known locally as Al-Shabaab) has persisted in Cabo Delgado province despite Rwandan and SADC military deployments since 2021, displacing nearly a million people and keeping major LNG projects including TotalEnergies' $20B Afungi facility on indefinite suspension. Post-election unrest following the contested October 2024 presidential election resulted in over 300 deaths, with opposition leader Venâncio Mondlane disputing results from exile and calling for sustained protests. The combination of insurgency and political crisis has left Mozambique facing serious instability on multiple fronts simultaneously.",
     "keywords":["mozambique","cabo delgado","ansar al-sunna"]},
    {"id":"taiwan",   "name":"Taiwan Strait",             "type":"tension", "lat":23.5, "lon":120.5,
     "started":"ongoing",
     "summary":"The PLA conducts increasingly frequent and sophisticated military exercises around Taiwan, including multi-day air and sea encirclement drills that simulate a blockade. China's grey-zone operations — using coast guard vessels, maritime militia, and daily incursions into Taiwan's air defence identification zone — have intensified under Xi Jinping. US arms sales, Congressional visits, and Taiwan's own defence budget increases have further heightened cross-strait tensions. Taiwan's president Lai Ching-te, elected in January 2024, maintains a firm stance while avoiding direct provocation. TSMC's dominance of advanced semiconductor manufacturing gives Taiwan extraordinary global strategic weight, making a Chinese move against the island a direct threat to global supply chains.",
     "keywords":["taiwan","pla taiwan","beijing taiwan","taiwan strait","tsmc"]},
    {"id":"southchinasea","name":"South China Sea",       "type":"tension", "lat":12.0, "lon":115.0,
     "started":"ongoing",
     "summary":"China and the Philippines are engaged in near-daily confrontations at Second Thomas Shoal (Ayungin Shoal), where Manila maintains a deliberate military outpost on the deliberately grounded vessel BRP Sierra Madre. Chinese coast guard vessels have used water cannons, military-grade lasers, and physical obstruction against Philippine resupply missions, injuring Filipino sailors and seizing supplies. The Philippines has invoked its mutual defence treaty with the US, which has reinforced its alliance posture and stationed additional forces at new Philippine bases. ASEAN negotiations for a Code of Conduct in the South China Sea have stalled. Vietnam, Malaysia, and Brunei also have contested overlapping claims.",
     "keywords":["south china sea","spratlys","second thomas shoal","philippines china sea","paracel"]},
    {"id":"northkorea","name":"North Korea",              "type":"tension", "lat":40.0, "lon":127.0,
     "started":"ongoing",
     "summary":"North Korea has deployed an estimated 10,000–12,000 troops to Russia to support operations in Ukraine, representing a significant and unprecedented internationalisation of Pyongyang's military posture. In exchange, North Korea is believed to be receiving advanced missile and satellite technology, conventional weapons, and economic relief. Kim Jong-un has conducted multiple ICBM tests demonstrating the capability to strike the US mainland. Pyongyang has formally declared South Korea a hostile foreign state, dismantled inter-Korean liaison infrastructure, and launched balloons carrying trash and propaganda into the South. North-South relations are at their lowest point in three decades.",
     "keywords":["north korea","pyongyang","kim jong","dprk","north korean troops"]},
    {"id":"iran",     "name":"Iran",                      "type":"tension", "lat":32.0, "lon":53.0,
     "started":"ongoing",
     "summary":"Iran's uranium enrichment has reached 60% purity — close to the 90% weapons-grade threshold — at facilities where IAEA inspectors have significantly reduced access. Tehran's 'Axis of Resistance' proxy network — Hezbollah, Hamas, Houthis, and various Iraqi Shia militias — has been severely weakened but not dismantled following Israel's 2024 campaign. A direct Iran-Israel exchange of fire in April 2024 (300+ Iranian drones and missiles followed by an Israeli retaliatory strike) marked a historic first direct confrontation between the two countries. Intermittent US-Iran nuclear negotiations continue but have not produced a successor agreement to the 2015 JCPOA. Iran's path to nuclear weapons capability is the central strategic concern animating Middle Eastern security.",
     "keywords":["iran","tehran","iranian","irgc","nuclear iran","khamenei"]},
    {"id":"venezuela","name":"Venezuela",                 "type":"tension", "lat":8.0,  "lon":-66.0,
     "started":"2019",
     "summary":"Nicolás Maduro claimed victory in the July 2024 presidential election despite opposition candidate Edmundo González demonstrably winning according to independently verified voting tallies from over 80% of polling stations. The regime deployed massive repression against post-election protests, with over 2,400 arrested and more than two dozen killed. González went into exile while opposition leader María Corina Machado remains in Venezuela under constant threat of arrest, continuing to organise from hiding. The US, EU, and most Latin American democracies have refused to recognise Maduro's claimed mandate. Venezuela's migrant diaspora now exceeds 7.7 million — one of the world's largest displacement crises — driven by economic collapse and political persecution.",
     "keywords":["venezuela","maduro","caracas","edmundo gonzalez"]},
    {"id":"syria",    "name":"Syria",                     "type":"tension", "lat":35.0, "lon":38.0,
     "started":"2011",
     "summary":"HTS (Hayat Tahrir al-Sham) led a lightning offensive in late November 2024 that toppled Bashar al-Assad's government in just eleven days, ending 54 years of Assad family rule. A transitional government led by Ahmed al-Sharaa (formerly Abu Mohammad al-Jolani) is consolidating control in major cities while navigating competing factions, IS sleeper cell attacks, and a contested periphery. Turkish forces and Turkey-backed groups hold the north, US-backed Kurdish SDF forces control the northeast, and Israel has conducted hundreds of airstrikes destroying Syrian military infrastructure. International sanctions relief is conditional on transition governance credibility. Syria faces one of the world's most acute reconstruction challenges with an estimated $400B in war damage.",
     "keywords":["syria","damascus","hts","hayat tahrir","post-assad","syrian"]},
    {"id":"kosovo",   "name":"Kosovo / Balkans",          "type":"tension", "lat":42.5, "lon":21.0,
     "started":"ongoing",
     "summary":"Serbia refuses to recognise Kosovo's 2008 declaration of independence, backed internationally by Russia and China. The ethnic Serb-majority north of Kosovo operates parallel institutions funded by Belgrade, creating persistent governance friction. Periodic flashpoints — including armed incidents at the Jarinje border crossing and clashes over Kosovo's attempts to assert authority in the north — have kept NATO's KFOR peacekeeping force on heightened alert. The EU-brokered Brussels Agreement to normalise relations has not been implemented by either side. Serbia's President Vučić navigates between EU accession aspirations and traditional Moscow alignment, complicating Western leverage.",
     "keywords":["kosovo","serbia kosovo","pristina","vucic"]},
    {"id":"ethiopia", "name":"Ethiopia",                  "type":"tension", "lat":13.0, "lon":39.0,
     "started":"ongoing",
     "summary":"The November 2022 Tigray ceasefire has held but its implementation — including Tigray People's Liberation Front disarmament, accountability for atrocities, and Eritrean troop withdrawal — is severely incomplete. A simultaneous Amhara insurgency (the Fano militia) has opened a second front, with fighting in and around Gondar, Bahir Dar, and the Amhara highlands. The Oromo Liberation Army continues operations in Oromia. Prime Minister Abiy Ahmed's government faces simultaneous insurgencies it cannot fully suppress while also pursuing an assertive foreign policy, including a push for Red Sea access that is straining relations with Somalia, Eritrea, and Djibouti. Ethiopia hosts Africa's largest refugee population while generating new displacement internally.",
     "keywords":["ethiopia","tigray","amhara","oromia","addis ababa conflict"]},
    {"id":"lebanon",  "name":"Lebanon",                   "type":"tension", "lat":33.9, "lon":35.5,
     "started":"ongoing",
     "summary":"A ceasefire between Israel and Hezbollah went into effect in November 2024 following Hezbollah's most severe setbacks in decades — including the assassination of Secretary-General Hassan Nasrallah, the killing of most of its senior military command, and the destruction of its missile arsenal. Lebanon elected a new president and formed a functioning government for the first time in years, signalling a fragile political opening. However, Hezbollah remains armed, politically entrenched, and backed by Iran. Reconstruction of southern Lebanon will cost an estimated $10B. The Lebanese economy — already in freefall since the 2019 financial collapse — is struggling to attract the international support needed for stabilisation and recovery.",
     "keywords":["lebanon","hezbollah","beirut","lebanese"]},
]
# ══════════════════════════════════════════════════════════════════════════════
#  NEWS SOURCES
# ══════════════════════════════════════════════════════════════════════════════
TECH_SOURCES = [
    ("Silicon Carne",       "https://siliconcarne.substack.com/feed"),
    ("Not Boring",          "https://www.notboring.co/feed"),
    ("TBPN",                "https://tbpn.substack.com/feed"),
    # FT Tech: direct section feed works with browser-like headers (25 articles)
    ("FT Tech",             "https://www.ft.com/technology?format=rss"),
    # FT Companies/Tech: slightly different selection, good overlap coverage
    ("FT Companies Tech",   "https://www.ft.com/companies/technology?format=rss"),
    ("The NBS",             "https://news.google.com/rss/search?q=site:the-nbs.fr&hl=fr&gl=FR&ceid=FR:fr"),
    ("Les Echos Start",     "https://news.google.com/rss/search?q=site:lesechos.fr/start-up&hl=fr&gl=FR&ceid=FR:fr"),
    ("SiliconMania",        "https://news.google.com/rss/search?q=site:siliconmania.tv&hl=fr&gl=FR&ceid=FR:fr"),
    ("Les Echos Deals",     "https://news.google.com/rss/search?q=site:lesechos.fr/start-up/deals&hl=fr&gl=FR&ceid=FR:fr"),
    ("Les Echos Portraits", "https://news.google.com/rss/search?q=site:lesechos.fr/start-up/portraits&hl=fr&gl=FR&ceid=FR:fr"),
]
MACRO_SOURCES = [
    # GN site:ft.com returns ~100 articles vs homepage RSS's 10
    ("FT",            "https://news.google.com/rss/search?q=site:ft.com&hl=en&gl=US&ceid=US:en"),
    ("The Economist", "https://www.economist.com/the-world-this-week/rss.xml"),
    ("Les Echos",     "https://news.google.com/rss/search?q=site:lesechos.fr&hl=fr&gl=FR&ceid=FR:fr"),
]
CULTURE_SOURCES = [
    ("NSS Magazine",      "https://news.google.com/rss/search?q=site:nssmag.com&hl=en&gl=US&ceid=US:en"),
    ("The Art Newspaper", "https://news.google.com/rss/search?q=site:theartnewspaper.com&hl=en&gl=US&ceid=US:en"),
    ("Télérama",          "https://news.google.com/rss/search?q=site:telerama.fr&hl=fr&gl=FR&ceid=FR:fr"),
    ("NYT Arts",          "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml"),
]
SPORTS_SOURCES_FR = [
    ("L'Équipe", "https://news.google.com/rss/search?q=site:lequipe.fr&hl=fr&gl=FR&ceid=FR:fr"),
]
SPORTS_SOURCES_INT = [
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
]
CONFLICT_NEWS_SOURCES = [
    # ── Broad wire / world feeds ──────────────────────────────────────────────
    ("Reuters World",  "https://feeds.reuters.com/reuters/worldNews"),
    ("Reuters Top",    "https://feeds.reuters.com/reuters/topNews"),
    ("BBC World",      "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera",     "https://www.aljazeera.com/xml/rss/all.xml"),
    # ── Quality press ─────────────────────────────────────────────────────────
    ("FT",             "https://news.google.com/rss/search?q=site:ft.com&hl=en&gl=US&ceid=US:en"),
    ("Le Monde Int",   "https://news.google.com/rss/search?q=site:lemonde.fr/international&hl=fr&gl=FR&ceid=FR:fr"),
    ("Les Echos",      "https://news.google.com/rss/search?q=site:lesechos.fr&hl=fr&gl=FR&ceid=FR:fr"),
    ("Defense News",   "https://news.google.com/rss/search?q=site:defensenews.com&hl=en&gl=US&ceid=US:en"),
    # ── Conflict-specific keyword searches (ensure coverage of niche zones) ──
    ("GN Sudan",       "https://news.google.com/rss/search?q=sudan+war+rsf+darfur&hl=en&gl=US&ceid=US:en"),
    ("GN Myanmar",     "https://news.google.com/rss/search?q=myanmar+junta+arakan+resistance&hl=en&gl=US&ceid=US:en"),
    ("GN DRC",         "https://news.google.com/rss/search?q=drc+congo+m23+goma+kivu&hl=en&gl=US&ceid=US:en"),
    ("GN Sahel",       "https://news.google.com/rss/search?q=sahel+mali+burkina+niger+jihadist&hl=en&gl=US&ceid=US:en"),
    ("GN Somalia",     "https://news.google.com/rss/search?q=somalia+al-shabaab+mogadishu&hl=en&gl=US&ceid=US:en"),
    ("GN Haiti",       "https://news.google.com/rss/search?q=haiti+gang+violence+port-au-prince&hl=en&gl=US&ceid=US:en"),
    ("GN Colombia",    "https://news.google.com/rss/search?q=colombia+eln+farc+conflict+catatumbo&hl=en&gl=US&ceid=US:en"),
    ("GN Mozambique",  "https://news.google.com/rss/search?q=mozambique+cabo+delgado+insurgency&hl=en&gl=US&ceid=US:en"),
    ("GN Ethiopia",    "https://news.google.com/rss/search?q=ethiopia+tigray+amhara+conflict&hl=en&gl=US&ceid=US:en"),
    ("GN Venezuela",   "https://news.google.com/rss/search?q=venezuela+maduro+opposition+crisis&hl=en&gl=US&ceid=US:en"),
    ("GN Kosovo",      "https://news.google.com/rss/search?q=kosovo+serbia+tension+balkans&hl=en&gl=US&ceid=US:en"),
    # ── Conflicts relying on broad feeds — dedicated fallback searches ─────
    ("GN Ukraine",     "https://news.google.com/rss/search?q=ukraine+russia+war+frontline+zelenskyy&hl=en&gl=US&ceid=US:en"),
    ("GN Gaza",        "https://news.google.com/rss/search?q=gaza+israel+hamas+ceasefire+rafah&hl=en&gl=US&ceid=US:en"),
    ("GN Yemen",       "https://news.google.com/rss/search?q=houthi+yemen+red+sea+attack+shipping&hl=en&gl=US&ceid=US:en"),
    ("GN Taiwan",      "https://news.google.com/rss/search?q=taiwan+china+pla+military+strait&hl=en&gl=US&ceid=US:en"),
    ("GN SCS",         "https://news.google.com/rss/search?q=south+china+sea+philippines+shoal+coast+guard&hl=en&gl=US&ceid=US:en"),
    ("GN NKorea",      "https://news.google.com/rss/search?q=north+korea+kim+missile+pyongyang+troops&hl=en&gl=US&ceid=US:en"),
    ("GN Iran",        "https://news.google.com/rss/search?q=iran+nuclear+iaea+sanctions+enrichment&hl=en&gl=US&ceid=US:en"),
    ("GN Syria",       "https://news.google.com/rss/search?q=syria+hts+damascus+transition+reconstruction&hl=en&gl=US&ceid=US:en"),
    ("GN Lebanon",     "https://news.google.com/rss/search?q=lebanon+hezbollah+ceasefire+reconstruction&hl=en&gl=US&ceid=US:en"),
    # Note: AFP (Telegram) is fetched separately via _fetch_telegram() and merged in main()
]
PARIS_SOURCES = [
    ("Sortir à Paris", "https://www.sortiraparis.com/rss/"),
    ("Timeout Paris",  "https://www.timeout.com/paris/rss"),
    ("Télérama",       "https://news.google.com/rss/search?q=site:telerama.fr&hl=fr&gl=FR&ceid=FR:fr"),
]
CITIES_SOURCES = [
    # Marseille
    ("Les Echos PACA",    "https://news.google.com/rss/search?q=marseille+site:lesechos.fr&hl=fr&gl=FR&ceid=FR:fr"),
    ("Le Monde Marseille","https://news.google.com/rss/search?q=marseille+site:lemonde.fr&hl=fr&gl=FR&ceid=FR:fr"),
    # Paris
    ("Le Monde Paris",    "https://news.google.com/rss/search?q=paris+actualit%C3%A9+site:lemonde.fr&hl=fr&gl=FR&ceid=FR:fr"),
    ("Le Parisien",       "https://news.google.com/rss/search?q=site:leparisien.fr&hl=fr&gl=FR&ceid=FR:fr"),
]
# ══════════════════════════════════════════════════════════════════════════════
#  CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
CALENDAR_EVENTS = [
    # ══ 2026 ══════════════════════════════════════════════════════════════════
    # January
    {"name":"CES Las Vegas",                "start":"2026-01-06","end":"2026-01-09","cat":"tech"},
    {"name":"Davos / WEF",                  "start":"2026-01-19","end":"2026-01-23","cat":"finance"},
    {"name":"Australian Open",              "start":"2026-01-19","end":"2026-02-01","cat":"tennis"},
    {"name":"Haute Couture SS",             "start":"2026-01-26","end":"2026-01-30","cat":"fashion"},
    # February
    {"name":"Super Bowl LX",                "start":"2026-02-01","end":"2026-02-01","cat":"football"},
    {"name":"Six Nations Rugby",            "start":"2026-02-07","end":"2026-03-21","cat":"rugby"},
    {"name":"NY Fashion Week FW",           "start":"2026-02-06","end":"2026-02-11","cat":"fashion"},
    {"name":"London Fashion Week FW",       "start":"2026-02-13","end":"2026-02-17","cat":"fashion"},
    {"name":"Berlinale",                    "start":"2026-02-12","end":"2026-02-22","cat":"culture"},
    {"name":"Milan Fashion Week FW",        "start":"2026-02-17","end":"2026-02-23","cat":"fashion"},
    {"name":"MWC Barcelona",               "start":"2026-02-23","end":"2026-02-26","cat":"tech"},
    # March
    {"name":"Paris Fashion Week FW",        "start":"2026-02-24","end":"2026-03-03","cat":"fashion"},
    {"name":"F1 Season 2026",               "start":"2026-03-15","end":"2026-11-29","cat":"f1"},
    # April
    {"name":"Art Paris",                    "start":"2026-04-02","end":"2026-04-05","cat":"culture"},
    {"name":"Grand National",               "start":"2026-04-04","end":"2026-04-04","cat":"horses"},
    {"name":"The Masters",                  "start":"2026-04-09","end":"2026-04-12","cat":"golf"},
    {"name":"Coachella",                    "start":"2026-04-10","end":"2026-04-19","cat":"music"},
    {"name":"Venice Biennale",              "start":"2026-04-18","end":"2026-11-22","cat":"culture"},
    # May
    {"name":"Met Gala",                     "start":"2026-05-04","end":"2026-05-04","cat":"fashion"},
    {"name":"Frieze New York",              "start":"2026-05-07","end":"2026-05-11","cat":"culture"},
    {"name":"European Aquatics Champs",     "start":"2026-05-11","end":"2026-05-17","cat":"swimming"},
    {"name":"Cannes Film Festival",         "start":"2026-05-12","end":"2026-05-23","cat":"culture"},
    {"name":"UEFA Europa League Final",     "start":"2026-05-20","end":"2026-05-20","cat":"football"},
    {"name":"F1 Monaco GP",                 "start":"2026-05-24","end":"2026-05-24","cat":"f1"},
    {"name":"Roland Garros",                "start":"2026-05-25","end":"2026-06-07","cat":"tennis"},
    {"name":"UEFA Champions League Final",  "start":"2026-05-30","end":"2026-05-30","cat":"football"},
    # June
    {"name":"Epsom Derby",                  "start":"2026-06-06","end":"2026-06-06","cat":"horses"},
    {"name":"Prix du Jockey Club",          "start":"2026-06-07","end":"2026-06-07","cat":"horses"},
    {"name":"FIFA World Cup 2026",          "start":"2026-06-11","end":"2026-07-19","cat":"football"},
    {"name":"Vivatech Paris",               "start":"2026-06-11","end":"2026-06-14","cat":"tech"},
    {"name":"G7 Summit",                    "start":"2026-06-13","end":"2026-06-15","cat":"finance"},
    {"name":"Royal Ascot",                  "start":"2026-06-16","end":"2026-06-20","cat":"horses"},
    {"name":"Art Basel Basel",              "start":"2026-06-17","end":"2026-06-21","cat":"culture"},
    {"name":"US Open Golf",                 "start":"2026-06-18","end":"2026-06-21","cat":"golf"},
    {"name":"Paris Men's Fashion Week",     "start":"2026-06-23","end":"2026-06-28","cat":"fashion"},
    {"name":"Glastonbury",                  "start":"2026-06-24","end":"2026-06-28","cat":"music"},
    {"name":"Wimbledon",                    "start":"2026-06-29","end":"2026-07-12","cat":"tennis"},
    {"name":"Henley Royal Regatta",         "start":"2026-06-30","end":"2026-07-04","cat":"rowing"},
    # July
    {"name":"Tour de France",               "start":"2026-07-04","end":"2026-07-26","cat":"cycling"},
    {"name":"F1 British GP (Silverstone)",  "start":"2026-07-05","end":"2026-07-05","cat":"f1"},
    {"name":"Haute Couture FW",             "start":"2026-07-06","end":"2026-07-10","cat":"fashion"},
    {"name":"The Open Championship",        "start":"2026-07-16","end":"2026-07-19","cat":"golf"},
    {"name":"World Aquatics Champs",        "start":"2026-07-17","end":"2026-08-02","cat":"swimming"},
    # August
    {"name":"Rolex Fastnet Race",           "start":"2026-08-09","end":"2026-08-16","cat":"sailing"},
    {"name":"US Open Tennis",               "start":"2026-08-31","end":"2026-09-13","cat":"tennis"},
    {"name":"Venice Film Festival",         "start":"2026-08-26","end":"2026-09-05","cat":"culture"},
    # September
    {"name":"F1 Italian GP (Monza)",        "start":"2026-09-06","end":"2026-09-06","cat":"f1"},
    {"name":"World Rowing Champs",          "start":"2026-09-06","end":"2026-09-13","cat":"rowing"},
    {"name":"TIFF Toronto",                 "start":"2026-09-10","end":"2026-09-20","cat":"culture"},
    {"name":"NY Fashion Week SS",           "start":"2026-09-05","end":"2026-09-11","cat":"fashion"},
    {"name":"London Fashion Week SS",       "start":"2026-09-12","end":"2026-09-16","cat":"fashion"},
    {"name":"UN General Assembly",          "start":"2026-09-15","end":"2026-09-25","cat":"finance"},
    {"name":"Milan Fashion Week SS",        "start":"2026-09-16","end":"2026-09-22","cat":"fashion"},
    # October
    {"name":"Paris Fashion Week SS",        "start":"2026-09-28","end":"2026-10-06","cat":"fashion"},
    {"name":"Prix de l'Arc de Triomphe",    "start":"2026-10-04","end":"2026-10-04","cat":"horses"},
    {"name":"Frieze London",                "start":"2026-10-14","end":"2026-10-18","cat":"culture"},
    # November
    {"name":"Web Summit",                   "start":"2026-11-02","end":"2026-11-05","cat":"tech"},
    {"name":"Paris Photo",                  "start":"2026-11-12","end":"2026-11-15","cat":"culture"},
    {"name":"G20 Summit",                   "start":"2026-11-18","end":"2026-11-19","cat":"finance"},
    {"name":"F1 Abu Dhabi GP",              "start":"2026-11-29","end":"2026-11-29","cat":"f1"},
    # December
    {"name":"Art Basel Miami",              "start":"2026-12-04","end":"2026-12-06","cat":"culture"},

    # ══ 2027 ══════════════════════════════════════════════════════════════════
    # January
    {"name":"CES Las Vegas 2027",           "start":"2027-01-05","end":"2027-01-08","cat":"tech"},
    {"name":"Davos / WEF 2027",             "start":"2027-01-18","end":"2027-01-22","cat":"finance"},
    {"name":"Australian Open 2027",         "start":"2027-01-18","end":"2027-02-01","cat":"tennis"},
    {"name":"Haute Couture SS 2027",        "start":"2027-01-25","end":"2027-01-29","cat":"fashion"},
    # February
    {"name":"Six Nations Rugby 2027",       "start":"2027-02-06","end":"2027-03-20","cat":"rugby"},
    {"name":"NY Fashion Week FW 2027",      "start":"2027-02-05","end":"2027-02-10","cat":"fashion"},
    {"name":"Berlinale 2027",               "start":"2027-02-11","end":"2027-02-21","cat":"culture"},
    {"name":"London Fashion Week FW 2027",  "start":"2027-02-12","end":"2027-02-16","cat":"fashion"},
    {"name":"Milan Fashion Week FW 2027",   "start":"2027-02-16","end":"2027-02-22","cat":"fashion"},
    {"name":"MWC Barcelona 2027",           "start":"2027-02-22","end":"2027-02-25","cat":"tech"},
    # March
    {"name":"Paris Fashion Week FW 2027",   "start":"2027-02-23","end":"2027-03-02","cat":"fashion"},
    # April
    {"name":"Art Paris 2027",               "start":"2027-04-01","end":"2027-04-04","cat":"culture"},
    {"name":"Grand National 2027",          "start":"2027-04-03","end":"2027-04-03","cat":"horses"},
    {"name":"The Masters 2027",             "start":"2027-04-08","end":"2027-04-11","cat":"golf"},
    {"name":"Coachella 2027",               "start":"2027-04-09","end":"2027-04-18","cat":"music"},
    # May
    {"name":"Met Gala 2027",                "start":"2027-05-03","end":"2027-05-03","cat":"fashion"},
    {"name":"Cannes Film Festival 2027",    "start":"2027-05-11","end":"2027-05-22","cat":"culture"},
    {"name":"F1 Monaco GP 2027",            "start":"2027-05-23","end":"2027-05-23","cat":"f1"},
    {"name":"Roland Garros 2027",           "start":"2027-05-24","end":"2027-06-06","cat":"tennis"},
    # June
    {"name":"Art Basel Basel 2027",         "start":"2027-06-16","end":"2027-06-20","cat":"culture"},
    {"name":"Glastonbury 2027",             "start":"2027-06-23","end":"2027-06-27","cat":"music"},
    {"name":"Wimbledon 2027",               "start":"2027-06-28","end":"2027-07-11","cat":"tennis"},
    # July
    {"name":"Tour de France 2027",          "start":"2027-07-03","end":"2027-07-25","cat":"cycling"},
    {"name":"Haute Couture FW 2027",        "start":"2027-07-05","end":"2027-07-09","cat":"fashion"},
    # August
    {"name":"Venice Film Festival 2027",    "start":"2027-08-25","end":"2027-09-04","cat":"culture"},
    # September
    {"name":"Rugby World Cup 2027",         "start":"2027-09-06","end":"2027-10-23","cat":"rugby"},
    {"name":"TIFF 2027",                    "start":"2027-09-09","end":"2027-09-19","cat":"culture"},
    {"name":"Ryder Cup 2027",               "start":"2027-09-24","end":"2027-09-26","cat":"golf"},
    # October
    {"name":"Prix de l'Arc 2027",           "start":"2027-10-03","end":"2027-10-03","cat":"horses"},
    {"name":"Frieze London 2027",           "start":"2027-10-13","end":"2027-10-17","cat":"culture"},
    # November
    {"name":"Paris Photo 2027",             "start":"2027-11-11","end":"2027-11-14","cat":"culture"},
    # December
    {"name":"Art Basel Miami 2027",         "start":"2027-12-03","end":"2027-12-05","cat":"culture"},
]
# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _s(t):
    return html_lib.escape(str(t or ""), quote=True)
def _parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None
def _ts(dt):
    return int(dt.timestamp()) if dt else 0
def _ago(dt):
    if not dt:
        return ""
    diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    if diff < 3600:  return f"{diff//60}m"
    if diff < 86400: return f"{diff//3600}h"
    return f"{diff//86400}d"
def _img(entry):
    mt = getattr(entry, "media_thumbnail", None)
    if mt and isinstance(mt, list) and mt[0].get("url"):
        return mt[0]["url"]
    for mc in getattr(entry, "media_content", []):
        url = mc.get("url", "")
        if url and ("image" in mc.get("type","") or
                    url.lower().endswith((".jpg",".jpeg",".png",".webp"))):
            return url
    for enc in getattr(entry, "enclosures", []):
        if "image" in enc.get("type","") and enc.get("href"):
            return enc["href"]
    for field in [entry.get("summary",""),
                  (entry.get("content") or [{}])[0].get("value","")]:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', field or "")
        if m and m.group(1).startswith("http"):
            return m.group(1)
    return ""
def _filter_recent(arts, days=7):
    """Drop articles older than `days` days. Articles with no date are kept."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    return [a for a in arts if not a["ts"] or a["ts"] >= cutoff]
def _snip(entry):
    raw = entry.get("summary","") or ""
    txt = re.sub(r"<[^>]+>"," ", raw)
    txt = re.sub(r"\s+"," ", txt).strip()
    return txt[:280] + "…" if len(txt) > 280 else txt
def _fetch(sources):
    arts = []
    for name, url in sources:
        try:
            feed = feedparser.parse(url,
                agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                request_headers={"Accept":"application/rss+xml,application/xml,text/xml,*/*"})
            for e in feed.entries[:MAX_PER_SOURCE]:
                arts.append({
                    "source":  name,
                    "title":   e.get("title","—"),
                    "link":    e.get("link","#"),
                    "date":    _parse_date(e),
                    "ts":      _ts(_parse_date(e)),
                    "img":     _img(e),
                    "snip":    _snip(e),
                })
        except Exception as ex:
            print(f"  ⚠  {name}: {ex}")
    arts.sort(key=lambda a: a["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return arts
def _dedup(arts):
    STOP = {"the","a","an","in","of","to","and","for","on","at","is","are","was",
            "with","by","that","this","as","it","its","from","be","or","has","have",
            "had","will","than","after","but","not","about","new","de","la","le",
            "les","du","un","une","en","et","des","sur","pour","par","dans","est"}
    def words(t):
        return {w for w in re.sub(r"[^a-z0-9àâéèêëîïôùûü ]","",t.lower()).split()
                if w not in STOP and len(w)>2}
    groups, used = [], set()
    for i, a in enumerate(arts):
        if i in used: continue
        wi = words(a["title"])
        grp = [a]
        for j, b in enumerate(arts):
            if j<=i or j in used: continue
            wj = words(b["title"])
            u = wi | wj
            if u and len(wi & wj)/len(u) >= 0.35:
                grp.append(b); used.add(j)
        used.add(i); groups.append(grp)
    return groups
def _match_conflicts(arts):
    """Return {conflict_id: [article_dict, ...]}"""
    out = {c["id"]: [] for c in CONFLICTS}
    for a in arts:
        txt = (a["title"]+" "+a.get("snip","")).lower()
        for c in CONFLICTS:
            if any(kw in txt for kw in c["keywords"]) and len(out[c["id"]]) < 10:
                out[c["id"]].append(a)
    return out
def _route_afp(msgs):
    """Sort AFP messages into tech, macro, conflict pools, and a ticker remainder."""
    tech, macro, ticker = [], [], []
    conflict_pool = []
    for m in msgs:
        txt = (m["title"]+" "+m.get("snip","")).lower()
        matched_conflict = any(
            any(kw in txt for kw in c["keywords"])
            for c in CONFLICTS
        )
        if matched_conflict:
            conflict_pool.append(m)
        elif any(kw in txt for kw in TECH_KEYWORDS):
            tech.append(m)
        elif any(kw in txt for kw in MACRO_KEYWORDS):
            macro.append(m)
        else:
            ticker.append(m)
    return {"conflict": conflict_pool, "tech": tech,
            "macro": macro, "ticker": ticker}
def _fetch_telegram():
    if not CONFIG_FILE.exists() or not SESSION_FILE.with_suffix(".session").exists():
        print("  ⚠  Telegram: no session — skipping (run telegram_auth.py)")
        return []
    try:
        from telethon.sync import TelegramClient
    except ImportError:
        print("  ⚠  Telegram: telethon not installed — skipping")
        return []
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except Exception as e:
        print(f"  ⚠  Telegram config: {e}")
        return []
    arts = []
    try:
        with TelegramClient(str(SESSION_FILE), cfg["api_id"], cfg["api_hash"]) as client:
            for label, channel in TELEGRAM_CHANNELS:
                try:
                    entity = client.get_entity(channel)
                    msgs   = client.get_messages(entity, limit=TELEGRAM_LIMIT)
                    is_inv = channel.startswith("https://t.me/+")
                    for msg in msgs:
                        txt = (msg.text or "").strip()
                        if not txt or len(txt) < 20: continue
                        lines = txt.split("\n")
                        title = lines[0][:160]
                        snip  = " ".join(lines[1:])[:280] if len(lines)>1 else ""
                        link  = channel if is_inv else f"https://t.me/{channel}/{msg.id}"
                        dt    = msg.date.replace(tzinfo=timezone.utc) if msg.date else None
                        arts.append({"source":label,"title":title,"link":link,
                                     "date":dt,"ts":_ts(dt),"img":"","snip":snip})
                except Exception as e:
                    print(f"  ⚠  Telegram {channel}: {e}")
    except Exception as e:
        print(f"  ⚠  Telegram client: {e}")
    arts.sort(key=lambda a: a["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    print(f"    → {len(arts)} AFP messages")
    return arts

def _fetch_emails():
    """Fetch newsletters from Gmail matching EMAIL_SUBJECTS via IMAP."""
    arts = []
    if not EMAIL_ADDRESS or EMAIL_ADDRESS == "ton.adresse@gmail.com":
        print("  ⚠  Email: adresse non configurée — skipping")
        return arts
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")
        for subj_filter in EMAIL_SUBJECTS:
            _, data = mail.search(None, f'(SUBJECT "{subj_filter}")')
            ids = data[0].split()
            if not ids:
                print(f"  ⚠  Email: aucun mail trouvé pour '{subj_filter}'")
                continue
            for num in ids[-EMAIL_LIMIT:]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                # Decode subject
                raw_subj, enc = decode_header(msg["Subject"])[0]
                title = (raw_subj.decode(enc or "utf-8", errors="ignore")
                         if isinstance(raw_subj, bytes) else raw_subj)
                # Parse date
                from email.utils import parsedate_to_datetime
                try:
                    dt = parsedate_to_datetime(msg["Date"]).astimezone(timezone.utc)
                except Exception:
                    dt = None
                # Extract body — prefer plain text, fall back to HTML stripped of tags
                snip = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                snip = payload.decode(
                                    part.get_content_charset() or "utf-8", errors="ignore")
                                break
                        elif ct == "text/html" and not snip:
                            payload = part.get_payload(decode=True)
                            if payload:
                                raw = payload.decode(
                                    part.get_content_charset() or "utf-8", errors="ignore")
                                snip = re.sub(r"<[^>]+>", " ", raw)
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        raw = payload.decode(
                            msg.get_content_charset() or "utf-8", errors="ignore")
                        ct = msg.get_content_type()
                        if ct == "text/html":
                            snip = re.sub(r"<[^>]+>", " ", raw)
                        else:
                            snip = raw
                snip = re.sub(r"\s+", " ", snip).strip()
                if len(snip) > 280:
                    snip = snip[:280] + "…"
                arts.append({
                    "source": subj_filter,
                    "title":  title,
                    "link":   "#",
                    "date":   dt,
                    "ts":     _ts(dt),
                    "img":    "",
                    "snip":   snip,
                })
        mail.logout()
    except Exception as ex:
        print(f"  ⚠  Email fetch: {ex}")
    arts.sort(key=lambda a: a["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    print(f"    → {len(arts)} newsletter emails")
    return arts

def _gemini_executive_summary(tech_groups, macro_arts, conflict_pool):
    """
    Call Gemini Flash to generate:
    - 3 bullets "what to know this morning"
    - Editorial headline rewrites for top 5 tech + top 5 macro stories
    Returns dict or None on failure.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GOOGLE_AI_STUDIO_KEY":
        print("  ⚠  Gemini: API key not configured — skipping")
        return None
    try:
        tech_titles  = [g[0]["title"] for g in tech_groups[:10]]
        macro_titles = [a["title"] for a in macro_arts[:10]]
        conflict_titles = [a["title"] for a in conflict_pool[:8]]
        today = datetime.now().strftime("%A %d %B %Y")
        prompt = f"""Today is {today}.

You are a senior editor writing for Bloomberg/FT readers — financially literate, international, time-pressed.

Here are today's top headlines across three feeds:

TECH & VC:
{chr(10).join(f"- {t}" for t in tech_titles)}

MACRO & MARKETS:
{chr(10).join(f"- {t}" for t in macro_titles)}

GEOPOLITICS:
{chr(10).join(f"- {t}" for t in conflict_titles)}

Your job:

1. Write exactly 3 "what to know this morning" bullets. Each bullet: one bold signal or development that actually matters. Max 2 sentences each. No filler. No "In a sign of..." openings. Direct, precise, analytical tone.

2. Rewrite the top 5 TECH headlines and top 5 MACRO headlines as editorial titles — sharp, specific, no clickbait. Keep under 12 words each.

Return ONLY valid JSON, no markdown, no backticks:
{{
  "bullets": [
    {{"emoji": "📈", "text": "..."}},
    {{"emoji": "💡", "text": "..."}},
    {{"emoji": "⚡", "text": "..."}}
  ],
  "tech_titles": ["rewritten title 1", "rewritten title 2", "rewritten title 3", "rewritten title 4", "rewritten title 5"],
  "macro_titles": ["rewritten title 1", "rewritten title 2", "rewritten title 3", "rewritten title 4", "rewritten title 5"]
}}"""
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
        }).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        result = json.loads(raw)
        print(f"    → Gemini: {len(result.get('bullets',[]))} bullets, "
              f"{len(result.get('tech_titles',[]))} tech titles, "
              f"{len(result.get('macro_titles',[]))} macro titles")
        return result
    except Exception as ex:
        print(f"  ⚠  Gemini: {ex}")
        return None

def _fetch_kalshi():
    """
    Fetch hottest open markets from Kalshi public API (no auth needed).
    Returns dict: {"macro": [...], "tech": [...]}
    Each item: {title, yes_pct, volume, open_interest, url}
    Sorted by open_interest desc (most money at stake = hottest).
    """
    result = {"macro": [], "tech": []}
    for kalshi_cat, brief_key, max_show in KALSHI_CATS:
        try:
            url = (
                f"{KALSHI_API}/markets"
                f"?limit={KALSHI_LIMIT}"
                f"&status=open"
                f"&category={urllib.parse.quote(kalshi_cat)}"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "Accept":     "application/json",
                    "User-Agent": "Mozilla/5.0 MorningBrief/4.0",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())
            markets = data.get("markets", [])
            filtered = []
            for m in markets:
                title_lower = (m.get("title") or "").lower()
                if any(kw in title_lower for kw in KALSHI_BLOCK):
                    continue
                filtered.append(m)
            # Sort by open_interest desc
            filtered.sort(key=lambda m: m.get("open_interest", 0), reverse=True)
            for m in filtered[:max_show]:
                ticker  = m.get("ticker", "")
                # yes_ask is in cents 0-100 on Kalshi
                yes_raw = m.get("yes_ask") or m.get("last_price") or 0
                yes_pct = round(yes_raw)
                result[brief_key].append({
                    "title":         m.get("title", "—"),
                    "yes_pct":       yes_pct,
                    "volume":        m.get("volume", 0),
                    "open_interest": m.get("open_interest", 0),
                    "url":           f"https://kalshi.com/markets/{ticker}",
                })
            print(f"    → Kalshi {kalshi_cat}: {len(result[brief_key])} markets")
        except Exception as ex:
            print(f"  ⚠  Kalshi {kalshi_cat}: {ex}")
    return result


def _fetch_event_news(name, max_items=8):
    """Fetch latest news for a calendar event by name via Google News RSS."""
    q = name.replace(" ", "+").replace("'", "").replace("&", "")
    url = (f"https://news.google.com/rss/search?q=%22{q}%22"
           f"&hl=en&gl=US&ceid=US:en")
    try:
        feed = feedparser.parse(
            url,
            agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            request_headers={"Accept": "application/rss+xml,application/xml,text/xml,*/*"},
        )
        arts = []
        for e in feed.entries[:max_items]:
            dt  = _parse_date(e)
            src = getattr(getattr(e, "source", None), "title", "") or ""
            arts.append({
                "title": e.get("title", "—"),
                "link":  e.get("link", "#"),
                "source": src,
                "ago":   _ago(dt),
            })
        return arts
    except Exception as ex:
        print(f"  ⚠  event news ({name}): {ex}")
        return []

def _fetch_calendar_event_news():
    """Fetch news for calendar events active within a +-30/+90 day window."""
    from datetime import timedelta
    today   = datetime.now()
    w_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    w_end   = (today + timedelta(days=90)).strftime("%Y-%m-%d")
    relevant = [e for e in CALENDAR_EVENTS
                if e["start"] <= w_end and e["end"] >= w_start]
    out = {}
    for e in relevant:
        print(f"    → event news: {e['name']}")
        arts = _fetch_event_news(e["name"])
        if arts:
            out[e["name"]] = arts
    return out

# ══════════════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#FFFFFF;--bg2:#F8F7F4;--bg3:#F0EEE9;
  --border:#E5E2D8;--text:#0A0A0A;--muted:#6B6860;--dim:#B8B5AC;
  --accent:#C41E1E;--r:3px;
  --display:'Playfair Display',Georgia,serif;
  --sans:'DM Sans',-apple-system,BlinkMacSystemFont,sans-serif;
  --mono:'IBM Plex Mono',monospace;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#0C0C0A;--bg2:#131310;--bg3:#1A1A16;
    --border:#252520;--text:#E8E5DC;--muted:#555250;--dim:#302E28;--accent:#E03030
  }
  header{background:rgba(12,12,10,.97)}
  .sg-title,.mi-title,.pi-title{color:#4A4840}
  .sg-title:hover,.mi:hover .mi-title,.pi-title:hover{color:var(--text)}
  .ct{color:#4A4840}
  .card:hover .ct,.mi.open .mi-title{color:var(--text)}
  .cp-sum{color:#3A3830}
  .cp-art{color:#3A3830}
  .cp-art:hover{color:#aaa}
  .km-bar-bg{background:#1e1e18}
  .km-item:hover{background:#111}
  .exec-bullet{border-left-color:#302E28}
}
body{font-family:var(--sans);background:var(--bg);color:var(--text);
  font-size:13px;line-height:1.6;-webkit-font-smoothing:antialiased}

/* ── Header ───────────────────────────────────────────────────── */
header{
  display:flex;justify-content:space-between;align-items:center;
  padding:20px 48px;border-bottom:1px solid var(--border);
  position:sticky;top:0;
  background:rgba(255,255,255,.97);
  backdrop-filter:blur(20px);z-index:200
}
@media(prefers-color-scheme:dark){header{background:rgba(12,12,10,.97)}}
.logo{
  font-family:var(--display);font-size:26px;font-weight:700;
  color:var(--text);letter-spacing:-.5px;font-style:italic;
  display:flex;align-items:baseline;gap:10px
}
.logo-dot{
  width:8px;height:8px;border-radius:50%;
  background:var(--accent);flex-shrink:0;margin-bottom:3px
}
.ts{
  font-family:var(--mono);font-size:9px;color:var(--muted);
  letter-spacing:.5px;text-transform:uppercase
}
.btn{
  background:var(--text);color:var(--bg);border:none;
  font-size:9px;padding:7px 18px;border-radius:2px;cursor:pointer;
  font-family:var(--sans);font-weight:700;letter-spacing:1.5px;
  text-transform:uppercase;transition:background .15s;margin-left:14px
}
.btn:hover{background:var(--accent)}

/* ── Executive Summary ─────────────────────────────────────────── */
.exec-wrap{
  padding:36px 48px 32px;
  border-bottom:1px solid var(--border);
  background:var(--bg)
}
.exec-date{
  font-family:var(--mono);font-size:9px;color:var(--muted);
  letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px
}
.exec-title{
  font-family:var(--display);font-size:13px;font-weight:400;
  color:var(--muted);letter-spacing:2px;text-transform:uppercase;
  margin-bottom:20px
}
.exec-bullets{display:flex;flex-direction:column;gap:0}
.exec-bullet{
  display:flex;gap:16px;align-items:baseline;
  padding:13px 0;border-bottom:1px solid var(--border)
}
.exec-bullet:last-child{border-bottom:none}
.exec-emoji{font-size:14px;flex-shrink:0;line-height:1}
.exec-text{font-size:14px;line-height:1.65;color:var(--text);font-weight:300}
.exec-text strong{font-weight:500}

/* ── AFP Ticker ───────────────────────────────────────────────── */
.ticker{
  display:flex;align-items:stretch;
  border-bottom:1px solid var(--border);
  overflow:hidden;min-height:34px
}
.ticker-label{
  font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:2px;
  text-transform:uppercase;color:#fff;background:var(--accent);
  padding:0 20px;display:flex;align-items:center;flex-shrink:0;z-index:2
}
.ticker-track{flex:1;overflow:hidden;position:relative}
.ticker-items{
  display:flex;width:max-content;
  animation:ticker-scroll 60s linear infinite
}
.ticker:hover .ticker-items{animation-play-state:paused}
@keyframes ticker-scroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.t-item{
  font-size:11px;color:var(--muted);text-decoration:none;
  padding:0 28px;border-right:1px solid var(--border);
  white-space:nowrap;transition:color .12s;
  display:flex;align-items:center;height:34px;flex-shrink:0;
  font-family:var(--sans)
}
.t-item:hover{color:var(--text)}

/* ── Filter buttons ────────────────────────────────────────────── */
.fb{
  background:none;border:1px solid var(--border);color:var(--muted);
  font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
  padding:4px 12px;border-radius:2px;cursor:pointer;
  font-family:var(--mono);transition:all .15s;flex-shrink:0
}
.fb.on{background:var(--text);color:var(--bg);border-color:var(--text)}
.fb:hover:not(.on){color:var(--text);border-color:var(--text)}

/* ── Section header ────────────────────────────────────────────── */
.section{border-bottom:1px solid var(--border)}
.sec-hd{
  padding:0 48px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between
}
.dot{display:none}
.cp-item .dot{
  display:inline-block;width:7px;height:7px;
  border-radius:50%;flex-shrink:0
}
.sec-hd-text{
  font-family:var(--display);font-size:17px;font-style:italic;
  font-weight:700;color:var(--text);
  padding:18px 0 14px;letter-spacing:-.3px
}
.sec-hd-meta{
  font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:.3px
}

/* ── Layouts ───────────────────────────────────────────────────── */
.two-col{
  display:grid;grid-template-columns:1fr 1fr;
  border-bottom:1px solid var(--border)
}
.two-col>.section{border-bottom:none;border-right:1px solid var(--border)}
.two-col>.section:last-child{border-right:none}
.three-col{
  display:grid;grid-template-columns:1fr 1fr 1fr;
  border-bottom:1px solid var(--border)
}
.three-col>.section{
  border-bottom:none;border-right:1px solid var(--border);
  height:400px;display:flex;flex-direction:column;overflow:hidden
}
.three-col>.section:last-child{border-right:none}
.three-col .story-list,.three-col .paris-list{flex:1;overflow-y:auto;max-height:none}

/* ── Map ───────────────────────────────────────────────────────── */
.map-wrap{display:flex;height:460px}
#map{flex:0 0 62%;height:100%}
.cp{
  flex:1;display:flex;flex-direction:column;
  border-left:1px solid var(--border);background:var(--bg2);overflow:hidden
}
.cp-hd{
  padding:10px 16px;font-family:var(--mono);font-size:9px;
  font-weight:500;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--border);flex-shrink:0
}
.cp-list{flex:1;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.cp-list::-webkit-scrollbar{width:2px}
.cp-item{
  display:flex;align-items:center;gap:9px;padding:9px 16px;
  border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s
}
.cp-item:hover,.cp-item.active{background:var(--bg3)}
.cp-item-name{font-size:12px;color:var(--muted);flex:1;font-weight:300}
.new-badge{
  font-family:var(--mono);font-size:8px;font-weight:500;color:#D97706;
  background:#D9770612;padding:2px 7px;border-radius:2px;flex-shrink:0;letter-spacing:.4px
}
.cp-det{display:none;flex-direction:column;height:100%}
.cp-det.on{display:flex}
.cp-back{
  padding:9px 16px;font-size:11px;color:var(--muted);cursor:pointer;
  border-bottom:1px solid var(--border);flex-shrink:0;transition:color .12s
}
.cp-back:hover{color:var(--text)}
.cp-body{
  flex:1;overflow-y:auto;padding:14px 16px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent
}
.cp-name{
  font-family:var(--display);font-size:15px;font-style:italic;
  font-weight:700;color:var(--text);margin-bottom:3px
}
.cp-meta{
  font-family:var(--mono);font-size:9px;color:var(--muted);
  margin-bottom:10px;letter-spacing:.2px
}
.cp-sum{
  font-size:12px;color:var(--muted);line-height:1.7;margin-bottom:13px;
  padding-left:10px;border-left:2px solid var(--border);font-weight:300
}
.cp-arts-hd{
  font-family:var(--mono);font-size:9px;font-weight:500;letter-spacing:1.2px;
  text-transform:uppercase;color:var(--dim);margin-bottom:7px
}
.cp-art{
  display:block;padding:7px 0;border-bottom:1px solid var(--border);
  text-decoration:none;color:var(--muted);font-size:11px;line-height:1.5;
  transition:color .12s;font-weight:300
}
.cp-art:last-child{border-bottom:none}
.cp-art:hover{color:var(--text)}
.cp-art small{color:var(--dim);font-size:9px;font-family:var(--mono)}
.cp-no{font-size:11px;color:var(--dim);padding:8px 0}
@keyframes pulse-ring{
  0%{box-shadow:0 0 0 0 rgba(212,151,17,.65)}
  70%{box-shadow:0 0 0 10px rgba(212,151,17,0)}
  100%{box-shadow:0 0 0 0 rgba(212,151,17,0)}
}
.pulse-icon div{animation:pulse-ring 1.8s infinite;border-radius:50%}
.dark-popup .leaflet-popup-content-wrapper{
  background:#141412;color:#d8d5cc;border:1px solid #252520;border-radius:4px
}
.dark-popup .leaflet-popup-tip{background:#141412}

/* ── Story list ─────────────────────────────────────────────────── */
.story-list{
  padding:0 48px 30px;max-height:560px;overflow-y:auto;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent
}
.story-list::-webkit-scrollbar{width:2px}
.sg{
  padding:12px 0;border-bottom:1px solid var(--border);
  display:flex;align-items:baseline;gap:12px
}
.sg:last-child{border-bottom:none}
.sg-title{
  font-size:13px;color:var(--muted);text-decoration:none;
  flex:1;line-height:1.6;transition:color .12s;font-weight:300
}
.sg-title.editorial{
  font-family:var(--display);font-size:14px;font-style:italic;
  font-weight:600;color:var(--text)
}
.sg-title:hover{color:var(--text)}
.badges{display:flex;flex-wrap:wrap;gap:3px;flex-shrink:0}
.badge{
  font-family:var(--mono);font-size:8px;font-weight:500;color:var(--dim);
  border:1px solid var(--border);padding:2px 7px;
  border-radius:2px;white-space:nowrap;letter-spacing:.5px;text-transform:uppercase
}
.sg-time{
  font-family:var(--mono);font-size:9px;color:var(--dim);flex-shrink:0
}

/* ── Macro list ─────────────────────────────────────────────────── */
.macro-list{
  padding:0 48px 30px;max-height:560px;overflow-y:auto;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent
}
.macro-list::-webkit-scrollbar{width:2px}
.mi{
  padding:11px 0;border-bottom:1px solid var(--border);cursor:pointer
}
.mi:last-child{border-bottom:none}
.mi-row{display:flex;gap:12px;align-items:baseline}
.mi-src{
  font-family:var(--mono);font-size:8px;color:var(--dim);width:64px;flex-shrink:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  letter-spacing:.7px;text-transform:uppercase;font-weight:500
}
.mi-title{
  font-size:13px;color:var(--muted);flex:1;line-height:1.6;
  transition:color .12s;font-weight:300
}
.mi-title.editorial{
  font-family:var(--display);font-size:14px;font-style:italic;
  font-weight:600;color:var(--text)
}
.mi:hover .mi-title{color:var(--text)}
.mi-time{font-family:var(--mono);font-size:9px;color:var(--dim);flex-shrink:0}
.mi-expand{
  display:none;padding:8px 0 4px 76px;font-size:11.5px;
  color:var(--muted);line-height:1.65;font-weight:300
}
.mi-expand a{
  color:var(--accent);text-decoration:none;font-size:11px;
  display:inline-block;margin-top:6px
}
.mi-expand a:hover{text-decoration:underline}
.mi.open .mi-expand{display:block}
.mi.open .mi-title{color:var(--text)}

/* ── Kalshi ─────────────────────────────────────────────────────── */
.kalshi-wrap{
  display:grid;grid-template-columns:1fr 1fr;
  border-top:1px solid var(--border)
}
.kalshi-col{padding:0 48px 28px}
.kalshi-col:first-child{border-right:1px solid var(--border)}
.kalshi-sub{
  font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:1.4px;
  text-transform:uppercase;color:var(--muted);
  padding:14px 0 10px;border-bottom:1px solid var(--border);margin-bottom:4px
}
.km-item{
  display:flex;align-items:center;gap:12px;
  padding:9px 0;border-bottom:1px solid var(--border);
  text-decoration:none;color:inherit;transition:background .1s;border-radius:0
}
.km-item:last-child{border-bottom:none}
.km-item:hover{
  background:var(--bg3);margin:0 -8px;
  padding:9px 8px;border-radius:2px
}
.km-title{
  font-size:12px;color:var(--muted);flex:1;line-height:1.5;font-weight:300
}
.km-prob{
  font-family:var(--mono);font-size:13px;font-weight:600;
  flex-shrink:0;min-width:38px;text-align:right
}
.km-bar-wrap{width:44px;flex-shrink:0}
.km-bar-bg{height:3px;background:var(--bg3);border-radius:0;overflow:hidden}
.km-bar-fill{height:100%;border-radius:0}
.km-vol{
  font-family:var(--mono);font-size:9px;color:var(--dim);
  flex-shrink:0;white-space:nowrap
}
.kalshi-empty{font-size:11px;color:var(--dim);padding:14px 0;font-style:italic}

/* ── Culture cards ──────────────────────────────────────────────── */
.cards{
  display:flex;gap:14px;overflow-x:auto;padding:0 48px 24px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent
}
.cards::-webkit-scrollbar{height:2px}
.cards::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.card{
  flex:0 0 196px;background:var(--bg2);border:1px solid var(--border);
  border-radius:2px;text-decoration:none;color:inherit;overflow:hidden;
  display:flex;flex-direction:column;transition:border-color .18s,transform .2s
}
.card:hover{transform:translateY(-4px);border-color:var(--text)}
.card:hover .ct{color:var(--text)}
.ci{
  height:118px;background-size:cover;background-position:center;
  position:relative;flex-shrink:0
}
.ci::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(to top,rgba(0,0,0,.5) 0%,transparent 60%)
}
.cs{
  position:absolute;bottom:8px;left:9px;z-index:1;
  font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:1px;
  text-transform:uppercase;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);
  padding:2px 8px;border-radius:2px;color:#e0e0e0
}
.cb{
  padding:10px 12px 12px;flex:1;display:flex;flex-direction:column;
  justify-content:space-between
}
.ct{
  font-size:11.5px;line-height:1.55;color:var(--muted);transition:color .15s;
  flex:1;margin-bottom:6px;font-weight:300
}
.ctime{font-family:var(--mono);font-size:9px;color:var(--dim)}

/* ── Paris list ─────────────────────────────────────────────────── */
.paris-list{
  padding:0 48px 30px;max-height:560px;overflow-y:auto;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent
}
.paris-list::-webkit-scrollbar{width:2px}
.pi{
  display:flex;gap:12px;align-items:baseline;
  padding:10px 0;border-bottom:1px solid var(--border)
}
.pi:last-child{border-bottom:none}
.pi-src{
  font-family:var(--mono);font-size:8px;color:var(--dim);width:74px;flex-shrink:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  letter-spacing:.7px;text-transform:uppercase;font-weight:500
}
.pi-title{
  font-size:13px;color:var(--muted);text-decoration:none;
  flex:1;line-height:1.55;transition:color .12s;font-weight:300
}
.pi-title:hover{color:var(--text)}
.pi-t{font-family:var(--mono);font-size:9px;color:var(--dim);flex-shrink:0}

/* ── Calendar ───────────────────────────────────────────────────── */
.cal-btn{
  background:none;border:1px solid var(--border);color:var(--text);
  font-family:var(--mono);font-size:12px;width:28px;height:28px;
  border-radius:2px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:all .15s
}
.cal-btn:hover{background:var(--text);color:var(--bg);border-color:var(--text)}
.cal-btn:disabled{opacity:.25;cursor:default;pointer-events:none}
.cal-nav-label{
  font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted)
}
.cal-legend{display:flex;flex-wrap:wrap;gap:6px 16px;flex:1}
.cal-leg-i{
  display:flex;align-items:center;gap:5px;
  font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:.7px;
  text-transform:uppercase;color:var(--muted)
}
.cal-leg-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.cal-months{
  display:grid;grid-template-columns:repeat(3,1fr);
  padding:28px 48px 44px;gap:0 52px;align-items:start
}
.cal-month{min-width:0}
.cal-mhd{
  font-family:var(--display);font-size:17px;font-style:italic;
  font-weight:700;color:var(--text);margin-bottom:12px;
  padding-bottom:9px;border-bottom:2px solid var(--border)
}
.cal-elist{display:flex;flex-direction:column}
.cal-erow{
  display:grid;grid-template-columns:8px 1fr auto;
  align-items:start;gap:8px;padding:5px 0;border-bottom:1px solid var(--border)
}
.cal-erow:last-child{border-bottom:none}
.cal-erow.ev-past{opacity:.3}
.cal-erow.ev-live{
  background:var(--bg3);border-radius:2px;
  padding:5px 7px;margin:0 -7px 1px -7px;border-bottom:none
}
.cal-edot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:3px}
.cal-ename{font-size:11.5px;color:var(--text);font-weight:300;line-height:1.4}
.cal-erange{
  font-family:var(--mono);font-size:9px;color:var(--muted);
  white-space:nowrap;text-align:right;padding-top:1px
}
.cal-empty-msg{
  font-size:11px;color:var(--dim);padding:10px 0;font-style:italic
}
.cal-det{
  border-top:1px solid var(--border);padding:28px 48px 36px;
  background:var(--bg2)
}
.cal-det-hd{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:18px
}
.cal-det-title{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.cal-det-name{
  font-family:var(--display);font-size:18px;font-style:italic;
  font-weight:700;color:var(--text)
}
.cal-det-range{
  font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:.3px
}
.cal-det-close{
  background:none;border:1px solid var(--border);color:var(--muted);
  font-size:15px;width:28px;height:28px;border-radius:2px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  transition:all .15s
}
.cal-det-close:hover{background:var(--text);color:var(--bg);border-color:var(--text)}
.cal-det-arts{
  display:grid;grid-template-columns:repeat(2,1fr);
  border-top:1px solid var(--border)
}
.cal-det-art{
  padding:9px 16px 9px 0;border-bottom:1px solid var(--border);
  text-decoration:none;color:var(--text);display:block;font-size:12px;
  line-height:1.55;font-weight:300;transition:color .12s
}
.cal-det-art:hover{color:var(--accent)}
.cal-det-art small{
  display:block;font-family:var(--mono);font-size:9px;
  color:var(--dim);margin-top:2px
}
.cal-det-none{
  font-size:11px;color:var(--dim);padding:12px 0;font-style:italic;
  border-top:1px solid var(--border)
}
.cal-erow[data-ev]{cursor:pointer}
.cal-erow[data-ev]:hover .cal-ename{color:var(--accent)}
.cal-erow.ev-sel .cal-ename{color:var(--accent)}
.cal-erow.ev-sel{
  background:var(--bg3);border-radius:2px;
  padding:5px 7px;margin:0 -7px 1px -7px;border-bottom:none
}

/* ── Tablet ─────────────────────────────────────────────────────── */
@media(max-width:1100px){
  .cal-months{grid-template-columns:repeat(2,1fr);gap:0 36px}
}

/* ── Mobile ─────────────────────────────────────────────────────── */
@media(max-width:768px){
  header{padding:14px 20px;flex-wrap:wrap;gap:8px}
  .logo{font-size:21px}
  .ts{font-size:8px}
  .btn{padding:6px 12px;font-size:8px;margin-left:0}
  .exec-wrap{padding:24px 20px 20px}
  .sec-hd{padding:0 20px}
  .story-list,.macro-list,.paris-list{padding:0 20px 20px}
  .cards{padding:0 20px 16px}
  .two-col{grid-template-columns:1fr}
  .two-col>.section{border-right:none;border-bottom:1px solid var(--border)}
  .two-col>.section:last-child{border-bottom:none}
  .three-col{grid-template-columns:1fr}
  .three-col>.section{
    height:auto;border-right:none;border-bottom:1px solid var(--border)
  }
  .three-col>.section:last-child{border-bottom:none}
  .three-col .story-list,.three-col .paris-list{max-height:280px}
  .map-wrap{flex-direction:column;height:auto}
  #map{flex:none;height:240px;width:100%}
  .cp{border-left:none;border-top:1px solid var(--border);height:280px}
  .kalshi-wrap{grid-template-columns:1fr}
  .kalshi-col{padding:0 20px 20px}
  .kalshi-col:first-child{border-right:none;border-bottom:1px solid var(--border)}
  .cal-months{grid-template-columns:1fr;padding:20px 20px 28px;gap:28px 0}
  .cal-det{padding:20px 20px 28px}
  .cal-det-arts{grid-template-columns:1fr}
}
"""
# ══════════════════════════════════════════════════════════════════════════════
#  HTML BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def _sec(color, label, body, extra_style=""):
    style = f"style='{extra_style}'" if extra_style else ""
    return (
        f'<div class="section" {style}>'
        f'<div class="sec-hd" style="border-left:3px solid {color}">'
        f'<span class="sec-hd-text">{label}</span>'
        f'</div>'
        f'{body}</div>\n'
    )

def build_executive_summary(gemini_data, now_str):
    if not gemini_data or not gemini_data.get("bullets"):
        return ""
    bullets_html = "".join(
        f'<div class="exec-bullet">'
        f'<span class="exec-emoji">{b.get("emoji","•")}</span>'
        f'<span class="exec-text">{_s(b.get("text",""))}</span>'
        f'</div>'
        for b in gemini_data["bullets"]
    )
    return (
        f'<div class="exec-wrap">'
        f'<div class="exec-date">{now_str}</div>'
        f'<div class="exec-title">Three things to know this morning</div>'
        f'<div class="exec-bullets">{bullets_html}</div>'
        f'</div>\n'
    )
def build_ticker(items):
    if not items:
        return ""
    once = "".join(
        f'<a href="{_s(a["link"])}" target="_blank" rel="noopener" class="t-item">'
        f'{_s(a["title"])}</a>'
        for a in items[:12]
    )
    # Duplicate for seamless infinite scroll (translateX(-50%) loops back to start)
    links = once + once
    return (
        f'<div class="ticker">'
        f'<span class="ticker-label">AFP</span>'
        f'<div class="ticker-track"><div class="ticker-items">{links}</div></div>'
        f'</div>\n'
    )
def build_map(conflicts_json, articles_json):
    return f"""
<div class="section">
  <div class="sec-hd" style="border-top:2px solid #D42B17">
    <span class="sec-hd-text">Geopolitical Flashpoints</span>
    <span class="sec-hd-meta">● conflict &nbsp;● tension &nbsp;⚡ new</span>
  </div>
  <div class="map-wrap">
    <div id="map"></div>
    <div class="cp">
      <div class="cp-hd">Conflicts &amp; Tensions</div>
      <div id="cp-list" class="cp-list"></div>
      <div id="cp-det" class="cp-det">
        <div class="cp-back" id="cp-back">← All conflicts</div>
        <div class="cp-body" id="cp-body"></div>
      </div>
    </div>
  </div>
</div>
<script>
(function(){{
  var C = {conflicts_json};
  var A = {articles_json};
  var TC = {{ conflict:'#EF4444', tension:'#F97316' }};
  var listEl = document.getElementById('cp-list');
  var detEl  = document.getElementById('cp-det');
  var bodyEl = document.getElementById('cp-body');
  var markers = {{}};
  var map = L.map('map',{{center:[20,10],zoom:2,minZoom:1,
    zoomControl:true,attributionControl:false}});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',
    {{subdomains:'abcd',maxZoom:19}}).addTo(map);
  function isNew(id) {{
    var arts = A[id] || [];
    if (!arts.length) return false;
    var seen = parseInt(localStorage.getItem('seen_'+id)||'0');
    return arts.some(function(a){{ return (a.ts||0)*1000 > seen; }});
  }}
  function markSeen(id) {{
    localStorage.setItem('seen_'+id, Date.now());
  }}
  function showDetail(id) {{
    var c = C.find(function(x){{return x.id===id;}});
    if (!c) return;
    markSeen(id);
    var li = listEl.querySelector('[data-id="'+id+'"]');
    if (li) {{ li.querySelector('.new-badge') && (li.querySelector('.new-badge').style.display='none'); }}
    if (markers[id] && markers[id]._isPulse) {{
      markers[id].remove();
      var col = TC[c.type]||'#888';
      var m = L.circleMarker([c.lat,c.lon],{{
        radius:c.type==='conflict'?7:5,color:col,fillColor:col,fillOpacity:.75,weight:1.5
      }}).addTo(map);
      m.bindTooltip(c.name,{{direction:'top',opacity:.9}});
      m.on('click',function(){{showDetail(c.id);}});
      markers[id]=m;
    }}
    var arts = A[id]||[];
    var artsHtml = arts.length
      ? arts.map(function(a){{
          return '<a href="'+a.link+'" target="_blank" rel="noopener" class="cp-art">'
            +_esc(a.title)+'<br><small>'+_esc(a.source)+(a.ago?' · '+a.ago:'')+'</small></a>';
        }}).join('')
      : '<p class="cp-no">No recent articles matched.</p>';
    bodyEl.innerHTML =
      '<div class="cp-name">'+_esc(c.name)+'</div>'
      +'<div class="cp-meta">Since '+_esc(c.started)
        +' &nbsp;·&nbsp; <span style="color:'+(TC[c.type]||'#888')+'">'+c.type+'</span></div>'
      +'<div class="cp-sum">'+_esc(c.summary)+'</div>'
      +'<div class="cp-arts-hd">Recent Coverage</div>'
      +artsHtml;
    listEl.style.display='none';
    detEl.classList.add('on');
    document.querySelectorAll('.cp-item').forEach(function(el){{
      el.classList.toggle('active', el.dataset.id===id);
    }});
  }}
  function _esc(t) {{
    return String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }}
  document.getElementById('cp-back').addEventListener('click',function(){{
    detEl.classList.remove('on');
    listEl.style.display='';
    document.querySelectorAll('.cp-item').forEach(function(el){{el.classList.remove('active');}});
  }});
  C.forEach(function(c){{
    var col = TC[c.type]||'#888';
    var hasNew = isNew(c.id);
    var item = document.createElement('div');
    item.className='cp-item'; item.dataset.id=c.id;
    item.innerHTML='<span class="dot" style="background:'+col+'"></span>'
      +'<span class="cp-item-name">'+_esc(c.name)+'</span>'
      +(hasNew?'<span class="new-badge">⚡ new</span>':'');
    item.addEventListener('click',function(){{showDetail(c.id);}});
    listEl.appendChild(item);
    var m;
    if (hasNew) {{
      var icon = L.divIcon({{
        className:'pulse-icon',
        html:'<div style="width:14px;height:14px;background:'+col+';border-radius:50%"></div>',
        iconSize:[14,14],iconAnchor:[7,7]
      }});
      m = L.marker([c.lat,c.lon],{{icon:icon}}).addTo(map);
      m._isPulse = true;
    }} else {{
      m = L.circleMarker([c.lat,c.lon],{{
        radius:c.type==='conflict'?7:5,color:col,fillColor:col,fillOpacity:.75,weight:1.5
      }}).addTo(map);
    }}
    m.bindTooltip(c.name,{{direction:'top',opacity:.9}});
    m.on('click',function(){{showDetail(c.id);}});
    markers[c.id]=m;
  }});
}})();
</script>
"""
def build_tech(groups):
    rows = ""
    for g in groups[:40]:
        primary = g[0]
        sources = list(dict.fromkeys(a["source"] for a in g))
        badges  = "".join(f'<span class="badge">{_s(s)}</span>' for s in sources)
        ed_title = primary.get("editorial_title")
        title_html = _s(ed_title) if ed_title else _s(primary["title"])
        title_cls  = "sg-title editorial" if ed_title else "sg-title"
        rows += (
            f'<div class="sg">'
            f'<a href="{_s(primary["link"])}" target="_blank" rel="noopener" class="{title_cls}">'
            f'{title_html}</a>'
            f'<div class="badges">{badges}</div>'
            f'<span class="sg-time">{_ago(primary["date"])}</span>'
            f'</div>\n'
        )
    return _sec("#0A0A0A","Tech — Startups — VC",
                f'<div class="story-list">{rows}</div>')
def build_macro(arts):
    rows = ""
    for a in arts[:35]:
        snip     = _s(a["snip"]) if a.get("snip") else ""
        ed_title = a.get("editorial_title")
        title_html = _s(ed_title) if ed_title else _s(a["title"])
        title_cls  = "mi-title editorial" if ed_title else "mi-title"
        rows += (
            f'<div class="mi" onclick="this.classList.toggle(\'open\')">'
            f'<div class="mi-row">'
            f'<span class="mi-src">{_s(a["source"])}</span>'
            f'<span class="{title_cls}">{title_html}</span>'
            f'<span class="mi-time">{_ago(a["date"])}</span>'
            f'</div>'
            f'<div class="mi-expand">{snip}'
            f'<br><a href="{_s(a["link"])}" target="_blank" rel="noopener">'
            f'→ Read on {_s(a["source"])}</a></div>'
            f'</div>\n'
        )
    return _sec("#0A0A0A","Macro — Finance — Markets",
                f'<div class="macro-list">{rows}</div>')
def build_kalshi(kalshi_data):
    """Build the Kalshi prediction markets section (Economics + Technology)."""
    def _fmt_oi(v):
        if not v: return ""
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000:     return f"${v/1_000:.0f}K"
        return f"${v}"
    def _col(pct):
        if pct >= 65: return "#16a34a"
        if pct <= 35: return "#dc2626"
        return "#888"
    def _render_col(items, sublabel):
        if not items:
            return (f'<div class="kalshi-sub">{sublabel}</div>'
                    f'<p class="kalshi-empty">No markets available — check API or try later.</p>')
        rows = f'<div class="kalshi-sub">{sublabel}</div>'
        for m in items:
            pct = m["yes_pct"]
            col = _col(pct)
            oi  = _fmt_oi(m.get("open_interest") or m.get("volume") or 0)
            rows += (
                f'<a href="{_s(m["url"])}" target="_blank" rel="noopener" class="km-item">'
                f'<span class="km-title">{_s(m["title"])}</span>'
                f'<span class="km-bar-wrap"><div class="km-bar-bg">'
                f'<div class="km-bar-fill" style="width:{pct}%;background:{col}"></div>'
                f'</div></span>'
                f'<span class="km-prob" style="color:{col}">{pct}%</span>'
                f'<span class="km-vol">{oi}</span>'
                f'</a>\n'
            )
        return rows
    macro_html = _render_col(kalshi_data.get("macro", []), "Economics")
    tech_html  = _render_col(kalshi_data.get("tech",  []), "Technology")
    body = (
        f'<div class="kalshi-wrap">'
        f'<div class="kalshi-col">{macro_html}</div>'
        f'<div class="kalshi-col">{tech_html}</div>'
        f'</div>'
    )
    label = ('Kalshi — Prediction Markets &nbsp;'
             '<span style="font-size:8px;font-weight:400;color:var(--muted);'
             'letter-spacing:.5px;text-transform:none">'
             'ranked by open interest · click to view on kalshi.com</span>')
    return _sec("#F59E0B", label, body)

def build_culture(arts):
    cards = ""
    for a in arts[:24]:
        img = a.get("img","")
        bg  = (f"background-image:url({_s(img)});background-size:cover;background-position:center;"
               if img else "background:linear-gradient(135deg,#E879F922,#FB923C11);")
        cards += (
            f'<a href="{_s(a["link"])}" target="_blank" rel="noopener" class="card">'
            f'<div class="ci" style="{bg}"><span class="cs">{_s(a["source"])}</span></div>'
            f'<div class="cb"><p class="ct">{_s(a["title"])}</p>'
            f'<span class="ctime">{_ago(a["date"])}</span></div></a>\n'
        )
    return _sec("#D42B17","Fashion &amp; Culture",
                f'<div class="cards">{cards}</div>')
def build_sports(fr_arts, int_arts):
    all_arts = sorted(fr_arts + int_arts,
                      key=lambda a: a["date"] or datetime.min.replace(tzinfo=timezone.utc),
                      reverse=True)
    rows = "".join(
        f'<div class="sg">'
        f'<a href="{_s(a["link"])}" target="_blank" rel="noopener" class="sg-title">'
        f'{_s(a["title"])}</a>'
        f'<div class="badges"><span class="badge">{_s(a["source"])}</span></div>'
        f'<span class="sg-time">{_ago(a["date"])}</span>'
        f'</div>\n'
        for a in all_arts[:20]
    )
    if not rows:
        rows = '<p style="font-size:11px;color:var(--dim)">No articles fetched.</p>'
    return _sec("#0C0C0C","Sports", f'<div class="story-list">{rows}</div>')
def build_cities(arts):
    MARSEILLE_SOURCES = {"Les Echos PACA", "Le Monde Marseille"}
    rows = ""
    for a in arts[:30]:
        city = "marseille" if a["source"] in MARSEILLE_SOURCES else "paris"
        rows += (
            f'<div class="sg city-item" data-city="{city}">'
            f'<a href="{_s(a["link"])}" target="_blank" rel="noopener" class="sg-title">'
            f'{_s(a["title"])}</a>'
            f'<div class="badges"><span class="badge">{_s(a["source"])}</span></div>'
            f'<span class="sg-time">{_ago(a["date"])}</span>'
            f'</div>\n'
        )
    if not rows:
        rows = '<p style="font-size:11px;color:var(--dim)">No articles fetched.</p>'
    body = f"""<div style="padding:0 40px 10px;display:flex;gap:6px;flex-shrink:0">
  <button class="fb on" id="city-all" onclick="filterCity('all')">All</button>
  <button class="fb" id="city-marseille" onclick="filterCity('marseille')">Marseille</button>
  <button class="fb" id="city-paris" onclick="filterCity('paris')">Paris</button>
</div>
<div class="story-list" id="city-list">{rows}</div>
<script>
function filterCity(v){{
  document.querySelectorAll('.fb[id^="city-"]').forEach(function(b){{
    b.classList.toggle('on', b.id==='city-'+v||(v==='all'&&b.id==='city-all'));
  }});
  document.querySelectorAll('.city-item').forEach(function(el){{
    el.style.display=(v==='all'||el.dataset.city===v)?'':'none';
  }});
}}
</script>"""
    return _sec("#0C0C0C","Marseille &amp; Paris", body)
def build_paris(arts):
    rows = ""
    for a in arts[:20]:
        rows += (
            f'<div class="pi">'
            f'<span class="pi-src">{_s(a["source"])}</span>'
            f'<a href="{_s(a["link"])}" target="_blank" rel="noopener" class="pi-title">'
            f'{_s(a["title"])}</a>'
            f'<span class="pi-t">{_ago(a["date"])}</span>'
            f'</div>\n'
        )
    if not rows:
        rows = '<p style="font-size:11px;color:var(--dim);padding:14px 0">No Paris events fetched — feeds may be unavailable.</p>'
    return _sec("#0C0C0C","Paris — What\'s On",
                f'<div class="paris-list">{rows}</div>')
def build_calendar(event_news={}):
    today     = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    cat_col = {
        "culture":"#7C3AED","fashion":"#EA580C","football":"#15803D",
        "f1":"#DC2626","horses":"#B45309","swimming":"#1D4ED8",
        "rowing":"#0E7490","sailing":"#0F766E","tennis":"#0284C7",
        "golf":"#166534","cycling":"#D97706","rugby":"#7E22CE",
        "music":"#DB2777","tech":"#0369A1","finance":"#374151",
    }
    cat_lbl = {
        "culture":"Culture","fashion":"Fashion","football":"Football",
        "f1":"F1","horses":"Horses","swimming":"Swimming",
        "rowing":"Rowing","sailing":"Sailing","tennis":"Tennis",
        "golf":"Golf","cycling":"Cycling","rugby":"Rugby",
        "music":"Music","tech":"Tech","finance":"Finance",
    }
    month_names = ["","January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    mon_abbr    = ["","Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

    def fmt_range(s_str, e_str):
        from datetime import datetime as _dt
        s = _dt.strptime(s_str, "%Y-%m-%d")
        e = _dt.strptime(e_str, "%Y-%m-%d")
        if s_str == e_str:
            return f"{s.day} {mon_abbr[s.month]}"
        if s.year == e.year and s.month == e.month:
            return f"{s.day}-{e.day} {mon_abbr[s.month]}"
        span = (e - s).days
        if s.year != e.year:
            return f"{s.day} {mon_abbr[s.month]} - {e.day} {mon_abbr[e.month]} {e.year}"
        if span > 60:
            return f"{mon_abbr[s.month]} - {mon_abbr[e.month]} {s.year}"
        return f"{s.day} {mon_abbr[s.month]} - {e.day} {mon_abbr[e.month]}"

    # Jan 2026 → Dec 2027 = 24 months
    start_y, start_m = 2026, 1
    total = 24
    cur_idx = (today.year - start_y) * 12 + (today.month - start_m)
    cur_idx = max(0, min(cur_idx, total - 3))

    # Build a dict: (year, month) → sorted list of events starting that month
    monthly = {}
    for e in CALENDAR_EVENTS:
        sy = int(e["start"][:4]); sm = int(e["start"][5:7])
        monthly.setdefault((sy, sm), []).append(e)
    for k in monthly:
        monthly[k].sort(key=lambda e: e["start"])

    all_months = []
    cy, cm = start_y, start_m
    for idx in range(total):
        events = monthly.get((cy, cm), [])
        if events:
            rows = ""
            for e in events:
                col = cat_col.get(e["cat"], "#555")
                rng = fmt_range(e["start"], e["end"])
                if e["end"] < today_str:
                    cls = " ev-past"
                elif e["start"] <= today_str <= e["end"]:
                    cls = " ev-live"
                else:
                    cls = ""
                has_news = e["name"] in event_news
                ev_attr  = f' data-ev="{_s(e["name"])}" data-range="{_s(rng)}"' if has_news else ""
                rows += (
                    f'<div class="cal-erow{cls}"{ev_attr}>'
                    f'<span class="cal-edot" style="background:{col}"></span>'
                    f'<span class="cal-ename">{_s(e["name"])}</span>'
                    f'<span class="cal-erange">{rng}</span>'
                    f'</div>\n'
                )
        else:
            rows = '<div class="cal-empty-msg">No events this month</div>'

        vis = "" if cur_idx <= idx < cur_idx + 3 else "display:none"
        all_months.append(
            f'<div class="cal-month" data-ci="{idx}" style="{vis}">'
            f'<div class="cal-mhd">{month_names[cm]} {cy}</div>'
            f'<div class="cal-elist">{rows}</div>'
            f'</div>'
        )
        cm += 1
        if cm > 12:
            cm = 1; cy += 1

    months_html = "".join(all_months)
    legend = "".join(
        f'<span class="cal-leg-i">'
        f'<span class="cal-leg-dot" style="background:{col}"></span>'
        f'{cat_lbl[cat]}</span>'
        for cat, col in cat_col.items()
    )

    event_news_js = json.dumps(event_news, ensure_ascii=False)

    body = f"""
<div style="display:flex;align-items:center;justify-content:space-between;
  padding:16px 40px 20px;border-bottom:1px solid var(--border);flex-wrap:wrap;gap:12px">
  <div class="cal-legend">{legend}</div>
  <div style="display:flex;align-items:center;gap:10px;flex-shrink:0">
    <button class="cal-btn" id="cal-prev">&#8592;</button>
    <span class="cal-nav-label" id="cal-range"></span>
    <button class="cal-btn" id="cal-next">&#8594;</button>
  </div>
</div>
<div class="cal-months" id="cal-months-wrap">{months_html}</div>
<div id="cal-det" style="display:none">
  <div class="cal-det-hd">
    <div class="cal-det-title">
      <span class="cal-det-name" id="cal-det-name"></span>
      <span class="cal-det-range" id="cal-det-range"></span>
    </div>
    <button class="cal-det-close" id="cal-det-close">&#x2715;</button>
  </div>
  <div id="cal-det-body"></div>
</div>
<script>
(function(){{
  var cur={cur_idx},total={total};
  var names={json.dumps(month_names)};
  var sy={start_y},sm={start_m};
  var EN={event_news_js};
  var activeEv=null;
  function _esc(t){{return String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}}
  function getShow(){{return window.innerWidth<=768?1:window.innerWidth<=1100?2:3;}}
  function mname(idx){{
    var y=sy+Math.floor((sm-1+idx)/12),m=(sm-1+idx)%12;
    return names[m+1]+' '+y;
  }}
  function show(s){{
    var SHOW=getShow();
    document.querySelectorAll('.cal-month').forEach(function(el){{
      var i=parseInt(el.dataset.ci);
      el.style.display=(i>=s&&i<s+SHOW)?'':'none';
    }});
    document.getElementById('cal-prev').disabled=s<=0;
    document.getElementById('cal-next').disabled=s+SHOW>=total;
    document.getElementById('cal-range').textContent=mname(s)+' – '+mname(s+SHOW-1);
  }}
  function openDetail(name, range){{
    activeEv=name;
    document.getElementById('cal-det-name').textContent=name;
    document.getElementById('cal-det-range').textContent=range;
    var arts=EN[name]||[];
    var bodyEl=document.getElementById('cal-det-body');
    if(arts.length){{
      var html='<div class="cal-det-arts">';
      arts.forEach(function(a){{
        html+='<a href="'+_esc(a.link)+'" target="_blank" rel="noopener" class="cal-det-art">'
          +_esc(a.title)
          +'<small>'+_esc(a.source)+(a.ago?' · '+a.ago:'')+'</small>'
          +'</a>';
      }});
      html+='</div>';
      bodyEl.innerHTML=html;
    }} else {{
      bodyEl.innerHTML='<p class="cal-det-none">No recent coverage found.</p>';
    }}
    document.getElementById('cal-det').style.display='';
    document.querySelectorAll('.cal-erow.ev-sel').forEach(function(el){{el.classList.remove('ev-sel');}});
    document.querySelectorAll('.cal-erow[data-ev="'+CSS.escape(name)+'"]').forEach(function(el){{
      el.classList.add('ev-sel');
    }});
  }}
  function closeDetail(){{
    activeEv=null;
    document.getElementById('cal-det').style.display='none';
    document.querySelectorAll('.cal-erow.ev-sel').forEach(function(el){{el.classList.remove('ev-sel');}});
  }}
  document.addEventListener('click',function(ev){{
    var row=ev.target.closest('.cal-erow[data-ev]');
    if(row){{
      var name=row.dataset.ev, range=row.dataset.range;
      if(activeEv===name){{closeDetail();}} else {{openDetail(name,range);}}
      return;
    }}
    if(ev.target.closest('#cal-det-close')){{closeDetail();}}
  }});
  document.getElementById('cal-prev').onclick=function(){{if(cur>0){{cur--;show(cur);}}}};
  document.getElementById('cal-next').onclick=function(){{if(cur+getShow()<total){{cur++;show(cur);}}}};
  window.addEventListener('resize',function(){{show(cur);}});
  show(cur);
}})();
</script>"""
    return _sec("#0C0C0C","Competitions &amp; Festivals 2026–27", body)
# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Morning Brief v4 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("-"*54)
    print("  Fetching AFP (Telegram)…")
    tg_arts  = _fetch_telegram()
    afp      = _route_afp(tg_arts)
    print("  Fetching emails (newsletters)…")
    email_arts = _fetch_emails()
    print("  Fetching Tech/VC…")
    tech_raw = _filter_recent(_fetch(TECH_SOURCES) + afp["tech"] + email_arts)
    tech_grp = _dedup(tech_raw)
    print(f"    → {len(tech_raw)} articles → {len(tech_grp)} stories")
    print("  Fetching Macro…")
    macro_arts = _filter_recent(_fetch(MACRO_SOURCES) + afp["macro"])
    print(f"    → {len(macro_arts)} articles")
    print("  Fetching Culture/Fashion…")
    culture_arts = _filter_recent(_fetch(CULTURE_SOURCES))
    print(f"    → {len(culture_arts)} articles")
    print("  Fetching Sports…")
    fr_arts  = _filter_recent(_fetch(SPORTS_SOURCES_FR))
    int_arts = _filter_recent(_fetch(SPORTS_SOURCES_INT))
    print(f"    → L'Equipe: {len(fr_arts)}, BBC Sport: {len(int_arts)}")
    print("  Fetching conflict news…")
    conflict_pool = _filter_recent(_fetch(CONFLICT_NEWS_SOURCES) + afp["conflict"])
    print(f"    → {len(conflict_pool)} articles for conflict matching")
    print("  Fetching Paris…")
    paris_arts = _filter_recent(_fetch(PARIS_SOURCES))
    print(f"    → {len(paris_arts)} Paris articles")
    print("  Fetching Cities (Marseille & Paris)…")
    cities_arts = _filter_recent(_fetch(CITIES_SOURCES))
    print(f"    → {len(cities_arts)} city articles")
    print("  Fetching calendar event news…")
    event_news = _fetch_calendar_event_news()
    print(f"    → {len(event_news)} events with coverage")
    print("  Fetching Kalshi prediction markets…")
    kalshi_data = _fetch_kalshi()
    print("  Generating executive summary with Gemini…")
    gemini_data = _gemini_executive_summary(tech_grp, macro_arts, conflict_pool)
    # Apply Gemini editorial titles to top stories
    if gemini_data:
        for i, title in enumerate(gemini_data.get("tech_titles", [])):
            if i < len(tech_grp):
                tech_grp[i][0]["editorial_title"] = title
        for i, title in enumerate(gemini_data.get("macro_titles", [])):
            if i < len(macro_arts):
                macro_arts[i]["editorial_title"] = title
    raw_match = _match_conflicts(conflict_pool)
    conf_arts_js = {
        cid: [{"title":a["title"],"link":a["link"],
               "source":a["source"],"ago":_ago(a["date"]),"ts":a["ts"]}
              for a in arts]
        for cid, arts in raw_match.items()
    }
    conf_js = [{k:v for k,v in c.items() if k!="keywords"} for c in CONFLICTS]
    now_str = datetime.now().strftime("%A %d %B %Y — %H:%M")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morning Brief</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,400;1,600;1,700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="logo"><span class="logo-dot"></span>Morning Brief</div>
  <div style="display:flex;align-items:center">
    <span class="ts">{now_str}</span>
    <button class="btn" onclick="location.reload()">↻ Refresh</button>
  </div>
</header>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
{build_executive_summary(gemini_data, now_str)}
{build_ticker(afp["ticker"])}
{build_map(json.dumps(conf_js, ensure_ascii=False),
           json.dumps(conf_arts_js, ensure_ascii=False))}
<div class="two-col">
{build_tech(tech_grp)}
{build_macro(macro_arts)}
</div>
{build_kalshi(kalshi_data)}
{build_culture(culture_arts)}
<div class="three-col">
{build_sports(fr_arts, int_arts)}
{build_cities(cities_arts)}
{build_paris(paris_arts)}
</div>
{build_calendar(event_news)}
</body>
</html>"""
    OUTPUT_FILE.write_text(page, encoding="utf-8")
    print("-"*54)
    print(f"✓  Saved → {OUTPUT_FILE}")
if __name__ == "__main__":
    main()
