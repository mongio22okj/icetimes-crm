"""Seed iniziale dei principali bookmaker ADM italiani.

Bonus e dettagli sono PLACEHOLDER editoriali: verranno aggiornati a mano
o dallo scraper automatico. Link affiliato vuoto = si usa l'official_url.
"""
from django.db import migrations


BOOKMAKERS = [
    {
        "name": "Sisal",
        "slug": "sisal",
        "category": "both",
        "license_type": "adm",
        "license_number": "15228",
        "official_url": "https://www.sisal.it/",
        "rating": "4.5",
        "short_description": "Storico operatore italiano, palinsesto ampio scommesse + casinò.",
        "pros": "Marchio storico italiano\nPalinsesto scommesse completo\nCasinò ricco di slot e live\nApp mobile solida",
        "cons": "Quote a volte non competitive\nBonus benvenuto con requisiti rigidi",
        "order": 10,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse fino a 100€",
                "amount_text": "fino a 100€",
                "terms_summary": "Requisito di puntata multiplo, deposito minimo 10€. Verifica T&C aggiornati.",
                "is_featured": True,
            },
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus casinò di benvenuto",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "Snai",
        "slug": "snai",
        "category": "both",
        "license_type": "adm",
        "license_number": "15215",
        "official_url": "https://www.snai.it/",
        "rating": "4.4",
        "short_description": "Quote competitive, ottimo per il calcio e i tornei italiani.",
        "pros": "Quote calcio competitive\nLive streaming eventi\nApp veloce\nRete punti fisici",
        "cons": "Casinò meno ricco di altri\nInterfaccia desktop datata",
        "order": 20,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Eurobet",
        "slug": "eurobet",
        "category": "both",
        "license_type": "adm",
        "license_number": "15211",
        "official_url": "https://www.eurobet.it/",
        "rating": "4.3",
        "short_description": "Quote alte sulle scommesse calcio, piattaforma chiara.",
        "pros": "Quote spesso tra le migliori sul calcio\nMolti mercati live\nPromozioni ricarica frequenti",
        "cons": "Casinò più limitato\nNon tutti i mercati esotici disponibili",
        "order": 30,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto fino a 105€",
                "amount_text": "fino a 105€",
                "terms_summary": "Bonus su prima giocata + bonus su primo deposito. Verifica T&C aggiornati.",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Goldbet",
        "slug": "goldbet",
        "category": "both",
        "license_type": "adm",
        "license_number": "15215",
        "official_url": "https://www.goldbet.it/",
        "rating": "4.4",
        "short_description": "Bookmaker italiano popolare, palinsesto ampio e quote sul calcio.",
        "pros": "Quote competitive\nMercati live numerosi\nCash out\nCasinò ricco",
        "cons": "App a volte instabile su Android",
        "order": 40,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus benvenuto casinò",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "Lottomatica",
        "slug": "lottomatica",
        "category": "both",
        "license_type": "adm",
        "license_number": "15016",
        "official_url": "https://www.lottomatica.it/",
        "rating": "4.3",
        "short_description": "Sport, casinò, poker e lotterie sotto un unico marchio italiano.",
        "pros": "Tutti i giochi ADM in un'unica piattaforma\nCasinò completo\nLive betting",
        "cons": "Bonus benvenuto non sempre tra i più alti",
        "order": 50,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Betflag",
        "slug": "betflag",
        "category": "both",
        "license_type": "adm",
        "license_number": "15068",
        "official_url": "https://www.betflag.it/",
        "rating": "4.2",
        "short_description": "Operatore italiano focalizzato su scommesse sportive e quote elevate.",
        "pros": "Quote spesso alte sui big match\nPromozioni multiple frequenti\nLive betting",
        "cons": "Sezione casinò più piccola dei big",
        "order": 60,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse fino a 1.025€",
                "amount_text": "fino a 1.025€",
                "terms_summary": "Pacchetto benvenuto multi-step. Verifica T&C aggiornati.",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Bet365",
        "slug": "bet365",
        "category": "both",
        "license_type": "adm",
        "license_number": "15229",
        "official_url": "https://www.bet365.it/",
        "rating": "4.6",
        "short_description": "Leader mondiale: palinsesto enorme, live streaming, app eccellente.",
        "pros": "Palinsesto smisurato\nLive streaming ricco\nApp tra le migliori\nCash out su quasi tutto",
        "cons": "Bonus benvenuto in Italia più contenuto che all'estero",
        "order": 70,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Planetwin365",
        "slug": "planetwin365",
        "category": "both",
        "license_type": "adm",
        "license_number": "15068",
        "official_url": "https://www.planetwin365.it/",
        "rating": "4.1",
        "short_description": "Storico operatore con palinsesto ampio e rete agenzie territoriali.",
        "pros": "Buona offerta scommesse\nCasinò discreto\nPromozioni ricorrenti",
        "cons": "Interfaccia non moderna",
        "order": 80,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "NetBet",
        "slug": "netbet",
        "category": "both",
        "license_type": "adm",
        "license_number": "15016",
        "official_url": "https://www.netbet.it/",
        "rating": "4.1",
        "short_description": "Bookmaker internazionale presente in Italia con casinò ricco di slot.",
        "pros": "Slot e giochi casinò abbondanti\nQuote competitive\nApp curata",
        "cons": "Customer care a volte lento",
        "order": 90,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus benvenuto casinò",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "LeoVegas",
        "slug": "leovegas",
        "category": "both",
        "license_type": "adm",
        "license_number": "15225",
        "official_url": "https://www.leovegas.it/",
        "rating": "4.4",
        "short_description": "Mobile-first, casinò premiato, ampia scelta di slot e live casino.",
        "pros": "App tra le migliori\nCasinò vasto e curato\nLive casino di qualità",
        "cons": "Sezione scommesse più piccola dei big",
        "order": 100,
        "bonuses": [
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus benvenuto casinò + free spin",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "888sport",
        "slug": "888sport",
        "category": "both",
        "license_type": "adm",
        "license_number": "15208",
        "official_url": "https://www.888sport.it/",
        "rating": "4.0",
        "short_description": "Marchio internazionale con scommesse e casinò online.",
        "pros": "Marchio internazionale affidabile\nCasinò ricco\nPromozioni ricorrenti",
        "cons": "Quote talvolta non competitive",
        "order": 110,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "Bwin",
        "slug": "bwin",
        "category": "both",
        "license_type": "adm",
        "license_number": "15014",
        "official_url": "https://sports.bwin.it/",
        "rating": "4.2",
        "short_description": "Storico operatore austriaco, sponsor di squadre Serie A.",
        "pros": "Marchio internazionale solido\nApp ben fatta\nCash out\nLive ricco",
        "cons": "Bonus a volte inferiore alla concorrenza",
        "order": 120,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "AdmiralBet",
        "slug": "admiralbet",
        "category": "both",
        "license_type": "adm",
        "license_number": "15022",
        "official_url": "https://www.admiralbet.it/",
        "rating": "4.1",
        "short_description": "Brand internazionale con offerta scommesse + casinò + live in Italia.",
        "pros": "Palinsesto ampio\nLive ricco\nCasinò curato",
        "cons": "App un po' meno fluida dei top",
        "order": 130,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "Better (Lottomatica)",
        "slug": "better",
        "category": "sport",
        "license_type": "adm",
        "license_number": "15016",
        "official_url": "https://www.better.it/",
        "rating": "4.1",
        "short_description": "Brand scommesse del gruppo Lottomatica, focus sportivo.",
        "pros": "Focus sportivo chiaro\nQuote spesso buone\nIntegrazione con sistema Lottomatica",
        "cons": "Niente casinò sul brand",
        "order": 140,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "StarCasinò",
        "slug": "starcasino",
        "category": "casino",
        "license_type": "adm",
        "license_number": "15238",
        "official_url": "https://www.starcasino.it/",
        "rating": "4.3",
        "short_description": "Casinò online molto popolare in Italia, focus su slot e live.",
        "pros": "Catalogo slot enorme\nLive casino di qualità\nPromozioni continue",
        "cons": "Niente sezione scommesse",
        "order": 150,
        "bonuses": [
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus benvenuto casinò + free spin",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "StarVegas",
        "slug": "starvegas",
        "category": "casino",
        "license_type": "adm",
        "license_number": "15014",
        "official_url": "https://www.starvegas.it/",
        "rating": "4.2",
        "short_description": "Storico casinò online italiano, brand di Entain.",
        "pros": "Slot e jackpot in evidenza\nApp ben fatta\nTavoli live",
        "cons": "Niente scommesse",
        "order": 160,
        "bonuses": [
            {
                "bonus_type": "welcome_casino",
                "title": "Bonus benvenuto casinò + free spin",
                "amount_text": "dettaglio da verificare",
                "is_featured": True,
            },
        ],
    },
    {
        "name": "Unibet",
        "slug": "unibet",
        "category": "both",
        "license_type": "adm",
        "license_number": "15214",
        "official_url": "https://www.unibet.it/",
        "rating": "4.1",
        "short_description": "Operatore internazionale con palinsesto scommesse e casinò.",
        "pros": "Palinsesto sportivo ricco\nCasinò curato\nApp solida",
        "cons": "Bonus benvenuto contenuto",
        "order": 170,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
    {
        "name": "Quigioco",
        "slug": "quigioco",
        "category": "both",
        "license_type": "adm",
        "license_number": "15239",
        "official_url": "https://www.quigioco.it/",
        "rating": "3.9",
        "short_description": "Operatore italiano con scommesse, casinò e lotterie.",
        "pros": "Offerta completa scommesse + casinò\nPromozioni frequenti",
        "cons": "Meno noto dei top brand\nVolumi live più contenuti",
        "order": 180,
        "bonuses": [
            {
                "bonus_type": "welcome_sport",
                "title": "Bonus benvenuto scommesse",
                "amount_text": "dettaglio da verificare",
            },
        ],
    },
]


def seed(apps, schema_editor):
    Bookmaker = apps.get_model("bonus_comparatore", "Bookmaker")
    Bonus = apps.get_model("bonus_comparatore", "Bonus")

    for entry in BOOKMAKERS:
        bonuses = entry.pop("bonuses", [])
        bm, _ = Bookmaker.objects.update_or_create(
            slug=entry["slug"],
            defaults=entry,
        )
        for idx, b in enumerate(bonuses):
            Bonus.objects.update_or_create(
                bookmaker=bm,
                bonus_type=b["bonus_type"],
                defaults={
                    "title": b["title"],
                    "amount_text": b.get("amount_text", ""),
                    "terms_summary": b.get("terms_summary", ""),
                    "is_featured": b.get("is_featured", False),
                    "order": idx * 10,
                },
            )


def unseed(apps, schema_editor):
    Bookmaker = apps.get_model("bonus_comparatore", "Bookmaker")
    slugs = [b["slug"] for b in BOOKMAKERS]
    Bookmaker.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bonus_comparatore", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
