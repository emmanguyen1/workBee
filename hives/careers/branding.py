"""Known company domains only; unknown brands receive a monogram in the UI."""
import re
from pathlib import Path
from urllib.parse import urlencode

DOMAINS = {
    "virtu financial":"virtu.com", "verkada":"verkada.com", "toyota research institute":"tri.global",
    "akuna capital":"akunacapital.com", "cesiumastro":"cesiumastro.com", "muon space":"muonspace.com", "sigma computing":"sigmacomputing.com",
    "american public health association":"apha.org", "aclu":"aclu.org", "human rights watch":"hrw.org",
    "vera institute of justice":"vera.org", "achievement first":"achievementfirst.org", "alphasights":"alphasights.com",
    "chan zuckerberg initiative":"chanzuckerberg.com", "lila sciences":"lila.ai",
    "rocket lab":"rocketlabcorp.com",
    "oscar health":"oscarhealth.com", "commure":"commure.com", "included health":"includedhealth.com",
    "carta":"carta.com", "gusto":"gusto.com", "brex":"brex.com", "flexport":"flexport.com",
    "intercontinental exchange": "ice.com", "royal bank of canada": "rbc.com",
    "highmark health": "highmarkhealth.org", "jm family": "jmfamily.com", "peraton": "peraton.com",
    "hp": "hp.com", "graphcore": "graphcore.ai", "constellation energy": "constellationenergy.com",
    "applied materials": "appliedmaterials.com", "zebra technologies": "zebra.com",
    "great american insurance company": "gaig.com", "dow jones": "dowjones.com",
    "ernst young": "ey.com", "paccar": "paccar.com", "northrop grumman": "northropgrumman.com",
    "skydio": "skydio.com", "caci": "caci.com", "the federal reserve system": "federalreserve.gov",
    "blackhawk network holdings": "blackhawknetwork.com", "imc trading": "imc.com",
    "t mobile": "t-mobile.com", "costco": "costco.com", "barclays": "barclays.com",
    "visa": "visa.com", "cvs health": "cvshealth.com",
    "office of naval research": "onr.navy.mil", "u s department of energy": "energy.gov",
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
    domain = DOMAINS.get(normalized) or DOMAINS.get(re.sub(r" (?:inc|llc|ltd|corporation|corp|limited)$", "", normalized))
    words = company.split()
    initials = "".join(word[0] for word in words[:2]).upper() if words else "?"
    local = Path(__file__).with_name('static') / 'logos' / f'{domain}.png' if domain else None
    logo_url = f'/careers/logos/{domain}.png' if local and local.is_file() else "https://www.google.com/s2/favicons?" + urlencode({"domain": domain, "sz": 128}) if domain else None
    return {"company_domain": domain, "company_initials": initials,
            "company_logo_url": logo_url}
