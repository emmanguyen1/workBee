"""Known company domains only; unknown brands receive a monogram in the UI."""
import re
from urllib.parse import urlencode

DOMAINS = {
    "anthropic": "anthropic.com", "ai2 allen institute for ai": "allenai.org",
    "recursion": "recursion.com", "klaviyo": "klaviyo.com",
    "tiktok": "tiktok.com", "waymo": "waymo.com", "marvell": "marvell.com",
    "bytedance": "bytedance.com", "american express": "americanexpress.com",
    "booz allen": "boozallen.com", "general motors": "gm.com", "shure": "shure.com",
    "navy federal": "navyfederal.org", "vertiv": "vertiv.com", "rtx": "rtx.com",
    "electronic arts": "ea.com", "ge vernova": "gevernova.com",
    "susquehanna international group sig": "sig.com", "bny": "bny.com",
    "nissan global": "nissan-global.com", "expedia group": "expediagroup.com",
    "motorola": "motorola.com", "rockwell automation": "rockwellautomation.com",
    "onsemi": "onsemi.com", "dv trading": "dvtrading.com", "epic games": "epicgames.com",
    "johns hopkins applied physics laboratory": "jhuapl.edu", "bedrock robotics": "bedrockrobotics.com",
    "gordon food service": "gfs.com", "procter gamble": "pg.com", "lseg": "lseg.com",
    "optiver": "optiver.com", "globalfoundries": "gf.com", "the toro company": "thetorocompany.com",
    "astranis": "astranis.com", "pimco": "pimco.com", "honeywell": "honeywell.com",
    "westinghouse electric company": "westinghousenuclear.com", "zipline": "flyzipline.com",
    "draftkings": "draftkings.com", "johnson johnson": "jnj.com", "semtech": "semtech.com",
    "jp morgan chase": "jpmorganchase.com", "vanguard": "vanguard.com", "intuit": "intuit.com",
    "amgen": "amgen.com", "veeam software": "veeam.com",
    "figma": "figma.com", "palantir": "palantir.com", "palantir technologies": "palantir.com",
    "notion": "notion.so", "spacex": "spacex.com", "stripe": "stripe.com",
    "databricks": "databricks.com", "duolingo": "duolingo.com", "robinhood": "robinhood.com",
    "sofi": "sofi.com", "cloudflare": "cloudflare.com", "mongodb": "mongodb.com",
    "toast": "toasttab.com", "reddit": "reddit.com", "discord": "discord.com",
    "givewell": "givewell.org", "flatiron health": "flatiron.com", "zoox": "zoox.com", "ramp": "ramp.com",
    "google": "google.com", "microsoft": "microsoft.com", "amazon": "amazon.com", "apple": "apple.com",
    "meta": "meta.com", "nvidia": "nvidia.com", "adobe": "adobe.com", "salesforce": "salesforce.com",
    "bloomberg": "bloomberg.com", "bloomberg lp": "bloomberg.com", "capital one": "capitalone.com",
    "jpmorgan chase": "jpmorganchase.com", "goldman sachs": "goldmansachs.com", "morgan stanley": "morganstanley.com",
    "asml": "asml.com", "amd": "amd.com", "intel": "intel.com", "qualcomm": "qualcomm.com",
    "tesla": "tesla.com", "rivian": "rivian.com", "anduril": "anduril.com", "anduril industries": "anduril.com",
    "airbnb": "airbnb.com", "uber": "uber.com", "lyft": "lyft.com", "doordash": "doordash.com",
    "pinterest": "pinterest.com", "snap": "snap.com", "spotify": "spotify.com", "netflix": "netflix.com",
    "akuna capital": "akunacapital.com", "akuna capital university": "akunacapital.com",
    "jane street": "janestreet.com", "citadel": "citadel.com", "citadel securities": "citadelsecurities.com",
}


def company_brand(company):
    normalized = re.sub(r"[^a-z0-9]+", " ", company.casefold()).strip()
    domain = DOMAINS.get(normalized)
    words = company.split()
    initials = "".join(word[0] for word in words[:2]).upper() if words else "?"
    return {"company_domain": domain, "company_initials": initials,
            "company_logo_url": "https://www.google.com/s2/favicons?" + urlencode({"domain": domain, "sz": 128}) if domain else None}
