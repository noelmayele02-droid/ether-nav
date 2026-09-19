"""
ÉTHER//NAV — un vrai navigateur web dans Streamlit, qui fonctionne… à sa manière.

Lancer :  pip install -r requirements.txt  &&  python -m streamlit run app.py
"""

import hashlib
import html
import ipaddress
import math
import random
import re
import socket
import time
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote, urljoin, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="ÉTHER//NAV",
    page_icon="🧿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────

ACCUEIL = "about:accueil"
ENTETES = {
    "User-Agent": "Mozilla/5.0 (compatible; ETHER-NAV/1.0; +https://streamlit.io)",
    "Accept-Language": "fr,en;q=0.8",
}
TAILLE_MAX = 2_000_000
DELAI = 10
BALISES_INTERDITES = [
    "head", "title", "script", "style", "iframe", "object", "embed", "noscript", "form",
    "link", "meta", "svg", "canvas", "video", "audio", "input", "button", "select",
    "textarea", "template", "dialog",
]
ATTRIBUTS_OK = {"alt", "title", "colspan", "rowspan"}
MODES = ["Lecture", "Rêve", "Miroir", "Fantôme", "Rayons X"]

PORTAILS = [
    ("📚 Wikipédia", "https://fr.wikipedia.org/"),
    ("🎲 Page au hasard", "https://fr.wikipedia.org/wiki/Sp%C3%A9cial:Page_au_hasard"),
    ("🧑‍💻 Hacker News", "https://news.ycombinator.com/"),
    ("🏺 Le tout premier site web", "http://info.cern.ch/"),
    ("📰 CNN Lite", "https://lite.cnn.com/"),
    ("🗞️ NPR en texte", "https://text.npr.org/"),
]

HUMEURS = [
    "convaincu d'être un grille-pain",
    "vexé par le mardi",
    "nostalgique d'un futur qui n'a pas eu lieu",
    "allergique aux pop-ups",
    "étrangement confiant",
    "en pleine crise d'identité",
]
HUMEURS_SITES = [
    "sereine", "méfiante", "nostalgique", "affamée de données",
    "légèrement hantée", "très sûre d'elle", "en retard sur tout", "bavarde",
]
SOUS_TITRES = [
    "Le web, mais il a un avis sur toi.",
    "Chaque page arrive un peu différente de ce qu'elle était.",
    "Les liens sont confisqués à l'entrée. Ils sont dans la soute.",
    "Navigation garantie sans garantie.",
    "Le bouton Retour fait ce qu'il peut.",
]
MESSAGES_CHARGEMENT = [
    "Négociation avec les serveurs du passé…",
    "Réveil poli du serveur distant…",
    "Décodage d'un accent binaire…",
    "Traversée d'un couloir de paquets…",
    "Consultation du registre des adresses oubliées…",
]


# ─────────────────────────────────────────────────────────────
#  ÉTAT
# ─────────────────────────────────────────────────────────────

def initialiser():
    ss = st.session_state
    if "onglets" in ss:
        return
    ss.onglets = [{"id": 1, "pile": [ACCUEIL], "pos": 0, "jeton": 0}]
    ss.compteur_onglets = 1
    ss.onglet_actif = 1
    ss.historique = []
    ss.reliquaire = []
    ss.titres = {}
    ss.journal = []
    ss.humeur = random.choice(HUMEURS)
    ss.teinte = random.randint(0, 360)
    ss.chaos = 0.4
    ss.stabilite = 40
    ss.moteur = "Wikipédia"
    ss.taille_texte = 16
    ss.bloquer_images = False


def journaliser(message):
    ss = st.session_state
    ss.journal.append(f"[{datetime.now():%H:%M:%S}] {message}")
    ss.journal = ss.journal[-8:]


def trouver_onglet(id_onglet):
    return next(o for o in st.session_state.onglets if o["id"] == id_onglet)


def onglet_courant():
    return trouver_onglet(st.session_state.onglet_actif)


def url_courante(onglet):
    return onglet["pile"][onglet["pos"]]


def degrader(texte, proba):
    return "".join(
        random.choice("░▒▓█▚▞¿?#") if (c != " " and random.random() < proba) else c
        for c in texte
    )


# ─────────────────────────────────────────────────────────────
#  RÉSEAU : sécurité, téléchargement, analyse
# ─────────────────────────────────────────────────────────────

def url_est_publique(url):
    """Refuse tout ce qui n'est pas http(s) vers une adresse publique (protection SSRF)."""
    analyse = urlparse(url)
    if analyse.scheme not in ("http", "https") or not analyse.hostname:
        return False
    port = analyse.port or (443 if analyse.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(analyse.hostname, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


def analyser(url, octets):
    soupe = BeautifulSoup(octets, "html.parser")
    titre = soupe.title.get_text(" ", strip=True) if soupe.title else ""
    corps = soupe.body or soupe
    for balise in corps(BALISES_INTERDITES):
        balise.decompose()

    titres = [
        (int(b.name[1]), b.get_text(" ", strip=True)[:120])
        for b in corps.find_all(re.compile(r"^h[1-6]$"))
        if b.get_text(strip=True)
    ]
    stats = dict(Counter(b.name for b in corps.find_all(True)))

    liens, vus = [], set()
    for a in corps.find_all("a", href=True):
        cible = urljoin(url, a["href"]).split("#")[0]
        if urlparse(cible).scheme in ("http", "https") and cible not in vus and cible != url:
            vus.add(cible)
            texte = a.get_text(" ", strip=True)[:80]
            liens.append((texte or urlparse(cible).netloc, cible))
            if len(liens) >= 120:
                break

    nb_images = 0
    for b in corps.find_all(True):
        if b.name == "img":
            source = b.get("src") or b.get("data-src") or ""
            cible = urljoin(url, source) if source else ""
            if urlparse(cible).scheme in ("http", "https") and nb_images < 40:
                nb_images += 1
                b.attrs = {"src": cible, "alt": str(b.get("alt", ""))[:120], "loading": "lazy"}
            else:
                b.decompose()
        elif b.name == "a":
            b.attrs = {}
        else:
            b.attrs = {k: v for k, v in b.attrs.items() if k in ATTRIBUTS_OK}

    return {
        "titre": titre,
        "html": corps.decode_contents()[:500_000],
        "texte": corps.get_text("\n", strip=True)[:200_000],
        "liens": liens,
        "titres": titres,
        "stats": stats,
        "images": nb_images,
    }


@st.cache_data(ttl=600, show_spinner=False, max_entries=64)
def recuperer_page(url, jeton):
    courante = url
    reponse = None
    try:
        for _ in range(6):
            if not url_est_publique(courante):
                return {"ok": False, "erreur": "Adresse refusée : invalide, ou pointant vers un réseau privé."}
            reponse = requests.get(
                courante, headers=ENTETES, timeout=DELAI, stream=True, allow_redirects=False
            )
            if reponse.status_code in (301, 302, 303, 307, 308) and reponse.headers.get("Location"):
                courante = urljoin(courante, reponse.headers["Location"])
                reponse.close()
                reponse = None
                continue
            break
        else:
            return {"ok": False, "erreur": "Trop de redirections. Le site tourne en rond."}

        type_contenu = reponse.headers.get("Content-Type", "").lower()
        if not any(t in type_contenu for t in ("html", "text/plain", "xml")):
            return {"ok": False, "erreur": f"Type de contenu non pris en charge : {type_contenu or 'inconnu'}."}

        contenu = bytearray()
        for morceau in reponse.iter_content(65536):
            contenu.extend(morceau)
            if len(contenu) > TAILLE_MAX:
                break
        page = analyser(courante, bytes(contenu))
        page.update(ok=True, url=courante, code=reponse.status_code, octets=len(contenu))
        return page
    except requests.RequestException as erreur:
        return {
            "ok": False,
            "erreur": f"Le réseau a refusé de coopérer ({type(erreur).__name__}). Réessaie avec ⟳.",
        }
    finally:
        if reponse is not None:
            reponse.close()


@st.cache_data(ttl=600, show_spinner=False, max_entries=64)
def chercher(moteur, requete, jeton):
    resultats = []
    try:
        if moteur.startswith("DuckDuckGo"):
            reponse = requests.post(
                "https://html.duckduckgo.com/html/", data={"q": requete}, headers=ENTETES, timeout=DELAI
            )
            reponse.raise_for_status()
            soupe = BeautifulSoup(reponse.text, "html.parser")
            for bloc in soupe.select("div.result"):
                lien = bloc.select_one("a.result__a")
                if not lien:
                    continue
                href = lien.get("href", "")
                if "uddg=" in href:
                    href = parse_qs(urlparse(href).query).get("uddg", [""])[0]
                elif href.startswith("//"):
                    href = "https:" + href
                if not href.startswith("http"):
                    continue
                extrait = bloc.select_one(".result__snippet")
                resultats.append({
                    "titre": lien.get_text(" ", strip=True),
                    "url": href,
                    "extrait": extrait.get_text(" ", strip=True) if extrait else "",
                })
            if not resultats:
                raise ValueError("aucun résultat (DuckDuckGo a peut-être bloqué la requête)")
        else:
            reponse = requests.get(
                "https://fr.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": requete,
                        "format": "json", "srlimit": 12, "utf8": 1},
                headers=ENTETES, timeout=DELAI,
            )
            reponse.raise_for_status()
            for r in reponse.json()["query"]["search"]:
                resultats.append({
                    "titre": r["title"],
                    "url": "https://fr.wikipedia.org/wiki/" + quote(r["title"].replace(" ", "_")),
                    "extrait": BeautifulSoup(r["snippet"], "html.parser").get_text(),
                })
    except Exception as erreur:  # noqa: BLE001 - on veut afficher n'importe quel échec
        return {"ok": False, "erreur": f"{type(erreur).__name__} : {erreur}"}
    return {"ok": True, "resultats": resultats}


# ─────────────────────────────────────────────────────────────
#  NAVIGATION (callbacks)
# ─────────────────────────────────────────────────────────────

def interpreter_saisie(saisie, moteur):
    saisie = saisie.strip()
    if not saisie:
        return None
    if saisie.startswith("about:") or re.match(r"^https?://", saisie, re.I):
        return saisie
    if " " not in saisie and re.match(r"^[\w-]+(\.[\w-]+)+(:\d+)?(/.*)?$", saisie):
        return "https://" + saisie
    return f"recherche:{moteur}|{saisie}"


def texte_adresse(url):
    return url.split("|", 1)[1] if url.startswith("recherche:") else url


def cle_adresse():
    o = onglet_courant()
    return f"adresse_{o['id']}_{o['pos']}_{o['jeton']}"


def naviguer(url):
    ss = st.session_state
    o = onglet_courant()
    if "Page_au_hasard" in url:
        url += f"?anomalie={random.randint(0, 10**9)}"
    o["pile"] = o["pile"][: o["pos"] + 1] + [url]
    o["pos"] = len(o["pile"]) - 1
    if not url.startswith("about:"):
        ss.historique.append({"heure": datetime.now().strftime("%H:%M:%S"), "url": url})
        ss.historique = ss.historique[-200:]


def valider_adresse():
    saisie = st.session_state.get(cle_adresse(), "")
    cible = interpreter_saisie(saisie, st.session_state.moteur)
    if cible:
        naviguer(cible)


def reculer():
    ss = st.session_state
    o = onglet_courant()
    if o["pos"] <= 0:
        return
    if o["pos"] > 1 and random.random() < ss.chaos * 0.25:
        o["pos"] = random.randrange(0, o["pos"])
        journaliser("le bouton Retour a fait un détour")
    else:
        o["pos"] -= 1


def avancer():
    o = onglet_courant()
    if o["pos"] < len(o["pile"]) - 1:
        o["pos"] += 1


def actualiser():
    onglet_courant()["jeton"] += 1


def nouvel_onglet(url=ACCUEIL):
    ss = st.session_state
    ss.compteur_onglets += 1
    ss.onglets.append({"id": ss.compteur_onglets, "pile": [url], "pos": 0, "jeton": 0})
    ss.onglet_actif = ss.compteur_onglets


def fermer_onglet():
    ss = st.session_state
    if len(ss.onglets) == 1:
        o = ss.onglets[0]
        o.update(pile=[ACCUEIL], pos=0, jeton=o["jeton"] + 1)
        journaliser("dernier onglet : réinitialisé plutôt que fermé")
        return
    courant = onglet_courant()
    ss.onglets = [o for o in ss.onglets if o["id"] != courant["id"]]
    if random.random() < ss.chaos * 0.3:
        ss.compteur_onglets += 1
        zombie = {"id": ss.compteur_onglets, "pile": [url_courante(courant)], "pos": 0, "jeton": 0}
        ss.onglets.append(zombie)
        ss.onglet_actif = zombie["id"]
        journaliser("un onglet est revenu d'entre les morts")
    else:
        ss.onglet_actif = ss.onglets[-1]["id"]


def suivre_lien(cible, alternatives):
    if alternatives and random.random() < st.session_state.chaos * 0.15:
        journaliser("un lien a hésité et a choisi une autre destination")
        naviguer(random.choice(alternatives))
    else:
        naviguer(cible)


def ajouter_relique(titre, url):
    ss = st.session_state
    if all(r["url"] != url for r in ss.reliquaire):
        ss.reliquaire.append({"titre": titre or url, "url": url})
        ss.reliquaire = ss.reliquaire[-30:]
        st.toast("Relique ajoutée au Reliquaire.", icon="🏺")


def supprimer_relique(url):
    st.session_state.reliquaire = [r for r in st.session_state.reliquaire if r["url"] != url]


def purger_realite():
    st.session_state.clear()


# ─────────────────────────────────────────────────────────────
#  STYLE
# ─────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@600;800&family=VT323&display=swap');

:root { --t: __T__; --v: __V__s; --taille: __TAILLE__px; }

.stApp {
  background:
    radial-gradient(circle at 12% 8%, hsl(var(--t) 90% 20% / .9), transparent 55%),
    radial-gradient(circle at 88% 92%, hsl(calc(var(--t) + 150) 90% 18% / .9), transparent 55%),
    #06070f;
  background-attachment: fixed;
  color: #e8eaff;
  font-family: 'IBM Plex Sans', sans-serif;
}
.stApp::after {
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.03) 0 1px, transparent 1px 3px);
  mix-blend-mode: overlay;
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.4rem; max-width: 1200px; }
[data-testid="stSidebar"] {
  background: rgba(8, 10, 22, .8); backdrop-filter: blur(14px);
  border-right: 1px solid hsl(var(--t) 100% 60% / .4);
}

/* Titre glitch */
.glitch {
  font-family: 'VT323', monospace; font-size: clamp(2.4rem, 7vw, 4.6rem);
  position: relative; letter-spacing: .08em; margin: 0; line-height: 1; padding: 0;
  text-shadow: 0 0 24px hsl(var(--t) 100% 60% / .8);
  animation: tremble var(--v) infinite steps(2);
}
.glitch::before, .glitch::after {
  content: attr(data-text); position: absolute; left: 0; top: 0; width: 100%; overflow: hidden;
}
.glitch::before { color: #ff2bd6; transform: translate(-3px, 0); animation: coupe var(--v) infinite linear alternate-reverse; }
.glitch::after  { color: #20f0ff; transform: translate(3px, 0);  animation: coupe calc(var(--v) * 1.3) infinite linear alternate; }
@keyframes coupe {
  0% { clip-path: inset(8% 0 82% 0); } 20% { clip-path: inset(62% 0 8% 0); }
  40% { clip-path: inset(30% 0 50% 0); } 60% { clip-path: inset(80% 0 4% 0); }
  80% { clip-path: inset(12% 0 70% 0); } 100% { clip-path: inset(46% 0 30% 0); }
}
@keyframes tremble {
  0% { transform: translate(0); } 25% { transform: translate(-2px, 1px); }
  50% { transform: translate(2px, -1px); } 75% { transform: translate(-1px, -2px); }
  100% { transform: translate(1px, 2px); }
}
.sous-titre { font-family: 'VT323', monospace; font-size: 1.4rem; opacity: .75; margin: .2rem 0 1rem; }
.chrome { display: flex; gap: .45rem; align-items: center; margin: 0 0 .5rem; }
.chrome span { width: .8rem; height: .8rem; border-radius: 50%; display: inline-block; }
.chrome .p1 { background: #ff5f57; } .chrome .p2 { background: #febc2e; } .chrome .p3 { background: #28c840; }

/* Onglets = pilules */
div[role="radiogroup"] { gap: .4rem; flex-wrap: wrap; }
div[role="radiogroup"] > label {
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12);
  border-radius: 12px 12px 4px 4px; padding: .3rem .9rem; margin: 0;
}
div[role="radiogroup"] > label:has(input:checked) {
  background: hsl(var(--t) 90% 45% / .35); border-color: hsl(var(--t) 100% 65% / .8);
}
div[role="radiogroup"] > label > div:first-child { display: none; }

/* Barre d'adresse */
[data-testid="stTextInput"] input {
  background: rgba(255,255,255,.07); border: 1px solid hsl(var(--t) 100% 65% / .5);
  border-radius: 999px; padding-left: 1.1rem; color: #fff;
}
[data-testid="stForm"] { border: 0; padding: 0; }

/* Boutons */
.stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {
  background: linear-gradient(135deg, hsl(var(--t) 95% 48%), hsl(calc(var(--t) + 80) 95% 55%));
  color: #fff; border: 0; border-radius: 14px; font-weight: 600;
  box-shadow: 0 0 20px hsl(var(--t) 100% 55% / .45);
  transition: transform .25s cubic-bezier(.3, 1.9, .5, .8);
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, .stDownloadButton > button:hover {
  transform: translateX(6px) rotate(-1.5deg) scale(1.05); color: #fff; border: 0;
}
.stButton > button:active { transform: scale(.92) rotate(3deg); }
.stButton > button:disabled { opacity: .3; box-shadow: none; }

/* Cartes et pages */
.carte {
  border: 1px solid hsl(var(--t) 100% 65% / .5); border-radius: 18px; padding: .9rem 1.2rem;
  background: rgba(255,255,255,.04); backdrop-filter: blur(8px); margin: .4rem 0 .2rem;
}
.titre-page { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.5rem; line-height: 1.15; }
.petit-url { font-size: .82rem; opacity: .6; word-break: break-all; }
.aura { font-size: .9rem; margin-top: .35rem; }
.page-web {
  background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.1); border-radius: 18px;
  padding: 1.3rem 1.6rem; line-height: 1.65; font-size: var(--taille); overflow-x: auto; margin-top: .6rem;
}
.page-web img { max-width: 100%; height: auto; border-radius: 10px; }
.page-web a { color: hsl(calc(var(--t) + 60) 100% 74%); text-decoration: underline dotted; pointer-events: none; }
.page-web table { border-collapse: collapse; display: block; overflow-x: auto; }
.page-web td, .page-web th { border: 1px solid rgba(255,255,255,.15); padding: .25rem .5rem; }
.page-web pre { white-space: pre-wrap; overflow-x: auto; }
.miroir { transform: scaleX(-1); }
.reve p { margin: .5rem 0; }
.fantome p { opacity: .22; transition: opacity .8s; margin: .5rem 0; }
.fantome p.f2 { opacity: .4; } .fantome p.f3 { opacity: .6; } .fantome p.f4 { opacity: .8; }
.fantome p:hover { opacity: 1; }
@media (hover: none) { .fantome p { opacity: .8; } }
@media (prefers-reduced-motion: reduce) { .glitch, .glitch::before, .glitch::after { animation: none; } }
"""


def injecter_css(chaos):
    ss = st.session_state
    vitesse = round(4.0 - 3.5 * chaos, 2)
    teinte = (ss.teinte + int(chaos * 40 * math.sin(time.time() / 3))) % 360
    css = (
        CSS.replace("__T__", str(teinte))
        .replace("__V__", str(vitesse))
        .replace("__TAILLE__", str(int(ss.taille_texte)))
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  PAGES INTERNES
# ─────────────────────────────────────────────────────────────

def page_accueil():
    st.markdown("### Bienvenue dans l'éther")
    st.write(
        "Tape une adresse, un mot-clé ou choisis un portail. Les pages sont téléchargées par le "
        "serveur, nettoyées de tout script, puis servies dans le mode de perception de ton choix."
    )
    colonnes = st.columns(3)
    for i, (nom, url) in enumerate(PORTAILS):
        colonnes[i % 3].button(nom, key=f"portail_{i}", on_click=naviguer, args=(url,))
    st.caption("Astuce : `about:aide` explique ce que le navigateur fait de travers, et pourquoi.")


def page_historique():
    ss = st.session_state
    st.markdown("### 🕰 Historique (approximatif)")
    if not ss.historique:
        st.caption("Rien à signaler. Suspect.")
        return

    def decalage(entree):
        graine = int(hashlib.md5((entree["heure"] + entree["url"]).encode()).hexdigest(), 16)
        base = datetime.strptime(entree["heure"], "%H:%M:%S")
        return (base + timedelta(seconds=graine % 21600 - 10800)).strftime("%H:%M:%S")

    tableau = pd.DataFrame(
        [{"heure officielle": e["heure"], "heure ressentie": decalage(e), "adresse": e["url"]}
         for e in reversed(ss.historique)]
    )
    st.dataframe(tableau, hide_index=True)
    urls = list(dict.fromkeys(e["url"] for e in reversed(ss.historique)))
    choix = st.selectbox("Retourner quelque part", urls, key="choix_historique")
    st.button("Y retourner", key="btn_retour_histo", on_click=naviguer, args=(choix,))


def page_reliquaire():
    ss = st.session_state
    st.markdown("### 🏺 Le Reliquaire")
    if ss.chaos > 0.5 and len(ss.reliquaire) > 1 and random.random() < 0.5:
        random.shuffle(ss.reliquaire)
        journaliser("le Reliquaire a réarrangé ses reliques")
    if not ss.reliquaire:
        st.caption("Vide. Ajoute une page avec le bouton ★ quand tu en visites une.")
    for i, relique in enumerate(ss.reliquaire):
        c1, c2 = st.columns([8, 1])
        c1.button(relique["titre"][:70], key=f"rel_{i}", on_click=naviguer, args=(relique["url"],), help=relique["url"])
        c2.button("🗑", key=f"relsup_{i}", on_click=supprimer_relique, args=(relique["url"],))


def page_aide():
    st.markdown("### 📖 Ce que le navigateur fait de travers")
    st.markdown(
        """
**Ce qui marche vraiment** : onglets, historique par onglet, retour / avant / actualiser, marque-pages,
recherche (Wikipédia ou DuckDuckGo), téléchargement du texte d'une page, blocage des images, taille du texte.

**Ce qui est bizarre, exprès** (dosé par le curseur *Stabilité*) :
- le bouton **Retour** fait parfois un détour dans l'historique ;
- un **lien** peut hésiter et t'envoyer ailleurs ;
- un **onglet fermé** peut revenir d'entre les morts ;
- le **Reliquaire** réarrange ses reliques ;
- les pages ont une **aura**, et le mode **Rêve** mélange leurs mots ;
- l'historique affiche une **heure ressentie**.

**Limites** : pas de JavaScript ; certains sites refusent les requêtes de serveurs ; les liens d'une page sont
regroupés dans la *soute à liens* sous la page (ils ne sont pas cliquables dans le texte).
"""
    )


# ─────────────────────────────────────────────────────────────
#  RECHERCHE
# ─────────────────────────────────────────────────────────────

def page_recherche(url, chaos):
    o = onglet_courant()
    moteur, requete = url[len("recherche:"):].split("|", 1)
    with st.status(f"{moteur} consulte les oracles…", expanded=False) as statut:
        reponse = chercher(moteur, requete, o["jeton"])
        statut.update(
            label="Oracles consultés" if reponse["ok"] else "Les oracles se sont tus",
            state="complete" if reponse["ok"] else "error",
        )
    st.markdown(f"### 🔎 « {requete} »")
    if not reponse["ok"]:
        st.error(reponse["erreur"])
        if not moteur.startswith("Wikipédia"):
            st.button("Réessayer avec Wikipédia", key="btn_wiki", on_click=naviguer,
                      args=(f"recherche:Wikipédia|{requete}",))
        return
    resultats = reponse["resultats"]
    if not resultats:
        st.info("Aucun résultat. Le vide n'a rien à te dire sur ce sujet.")
        return

    minute = int(time.time() // 60)

    def mystere(r):
        return int(hashlib.sha256((r["titre"] + requete).encode()).hexdigest(), 16) % 100

    if chaos > 0.5:
        resultats = sorted(
            resultats,
            key=lambda r: hashlib.sha256((r["titre"] + str(minute)).encode()).hexdigest(),
        )
        st.caption("Les résultats sont classés par résonance, pas par pertinence. Ça change chaque minute.")
    for i, r in enumerate(resultats):
        domaine = urlparse(r["url"]).netloc
        st.html(
            f'<div class="carte"><div class="titre-page">{html.escape(r["titre"])}</div>'
            f'<div class="petit-url">{html.escape(domaine)}</div>'
            f'<p>{html.escape(r["extrait"])}</p>'
            f'<div class="aura">Score de mystère : {mystere(r)}/100</div></div>'
        )
        st.button("Ouvrir", key=f"res_{o['id']}_{o['pos']}_{i}", on_click=naviguer, args=(r["url"],))


# ─────────────────────────────────────────────────────────────
#  PAGE WEB
# ─────────────────────────────────────────────────────────────

def aura(domaine):
    h = int(hashlib.sha256(domaine.encode()).hexdigest(), 16)
    return {"score": h % 101, "teinte": h % 360, "humeur": HUMEURS_SITES[(h >> 8) % len(HUMEURS_SITES)]}


def paragraphes_texte(texte, maximum):
    lignes = [l.strip() for l in texte.split("\n") if len(l.strip()) > 35]
    if len(lignes) < 3:
        lignes = [l.strip() for l in texte.split("\n") if l.strip()]
    return lignes[:maximum]


def afficher_contenu(page, mode, chaos):
    ss = st.session_state
    rng = random.Random(f"{page['url']}{int(time.time() // 60)}")

    if mode in ("Lecture", "Miroir"):
        contenu = page["html"]
        if ss.bloquer_images:
            contenu = re.sub(r"<img\b[^>]*>", "", contenu, flags=re.I)
        classe = "page-web miroir" if mode == "Miroir" else "page-web"
        st.html(f'<div class="{classe}">{contenu}</div>')

    elif mode == "Rêve":
        sortie = []
        for paragraphe in paragraphes_texte(page["texte"], 70):
            mots = paragraphe.split()
            for _ in range(int(len(mots) * (0.15 + chaos * 0.5))):
                i, j = rng.randrange(len(mots)), rng.randrange(len(mots))
                mots[i], mots[j] = mots[j], mots[i]
            sortie.append(f"<p>{html.escape(' '.join(mots))}</p>")
        st.html(f'<div class="page-web reve">{"".join(sortie) or "<p>Rien à rêver.</p>"}</div>')
        st.caption("Les mots ont été redistribués pendant que tu ne regardais pas.")

    elif mode == "Fantôme":
        sortie = [
            f'<p class="f{rng.randint(1, 4)}">{html.escape(p)}</p>'
            for p in paragraphes_texte(page["texte"], 80)
        ]
        st.html(f'<div class="page-web fantome">{"".join(sortie) or "<p>Rien à voir ici.</p>"}</div>')
        st.caption("Survole un paragraphe pour le faire réapparaître.")

    else:  # Rayons X
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Balises", sum(page["stats"].values()))
        c2.metric("Liens", len(page["liens"]))
        c3.metric("Images", page["images"])
        c4.metric("Titres", len(page["titres"]))
        if page["stats"]:
            st.bar_chart(pd.Series(page["stats"]).sort_values(ascending=False).head(15))
        plan = "\n".join("  " * (n - 1) + f"h{n} · {t}" for n, t in page["titres"][:60])
        st.text(plan or "Aucun titre : cette page n'a pas de squelette apparent.")


def panneau_liens(page):
    o = onglet_courant()
    liens = page["liens"]
    with st.expander(f"🧺 Soute à liens ({len(liens)}) — les liens de la page y sont confisqués"):
        if not liens:
            st.caption("Aucun lien à confisquer.")
            return
        filtre = st.text_input(
            "Filtrer", key=f"filtre_{o['id']}_{o['pos']}", placeholder="mot du lien ou du domaine"
        ).lower()
        visibles = [l for l in liens if filtre in f"{l[0]} {l[1]}".lower()][:48]
        alternatives = [cible for _, cible in visibles]
        colonnes = st.columns(2)
        for i, (texte, cible) in enumerate(visibles):
            colonnes[i % 2].button(
                texte[:55], key=f"lien_{o['id']}_{o['pos']}_{i}", help=cible,
                on_click=suivre_lien, args=(cible, alternatives),
            )


def page_web(url, chaos):
    ss = st.session_state
    o = onglet_courant()

    with st.status(random.choice(MESSAGES_CHARGEMENT), expanded=False) as statut:
        time.sleep(random.uniform(0.1, 0.1 + 0.4 * chaos))
        page = recuperer_page(url, o["jeton"])
        if page["ok"]:
            statut.update(label=f"Reçu : {page['octets'] // 1024} Ko", state="complete")
        else:
            statut.update(label="Échec de la négociation", state="error")

    if not page["ok"]:
        st.error(page["erreur"])
        st.button("Chercher ce texte à la place", key="btn_chercher_plutot", on_click=naviguer,
                  args=(f"recherche:{ss.moteur}|{url}",))
        return

    if url not in ss.titres:
        ss.titres[url] = page["titre"] or urlparse(page["url"]).netloc
        st.rerun()

    domaine = urlparse(page["url"]).netloc
    a = aura(domaine)
    kilo = max(1, page["octets"] // 1024)
    st.html(
        f'<div class="carte" style="border-color:hsl({a["teinte"]} 100% 65% / .7)">'
        f'<div class="titre-page">{html.escape(page["titre"] or domaine)}</div>'
        f'<div class="petit-url">{html.escape(page["url"])}</div>'
        f'<div class="aura">Aura {a["score"]}/100 · humeur {a["humeur"]} · {kilo} Ko · HTTP {page["code"]}</div>'
        f"</div>"
    )
    if page["url"] != url:
        st.caption(f"Redirigé vers {page['url']}")

    colonne_mode, colonne_actions = st.columns([5, 3])
    mode = colonne_mode.radio("Mode de perception", MODES, horizontal=True, key=f"mode_{o['id']}")
    with colonne_actions:
        c1, c2 = st.columns(2)
        c1.button("★ Reliquaire", key="btn_relique", on_click=ajouter_relique,
                  args=(page["titre"] or domaine, url))
        c2.download_button("⬇ Texte", data=page["texte"], file_name=f"{domaine or 'page'}.txt",
                           key=f"dl_{o['id']}_{o['pos']}")

    afficher_contenu(page, mode, chaos)
    panneau_liens(page)


# ─────────────────────────────────────────────────────────────
#  INTERFACE
# ─────────────────────────────────────────────────────────────

def barre_laterale():
    ss = st.session_state
    st.sidebar.markdown("## 🧿 Cockpit")
    stabilite = st.sidebar.slider(
        "Stabilité (fiabilité douteuse)", 0, 100, key="stabilite",
        help="Moins il y a de stabilité, plus le navigateur est capricieux (avec un peu de bruit en plus).",
    )
    chaos = min(1.0, max(0.0, 1 - stabilite / 100 + random.uniform(-0.1, 0.1)))
    ss.chaos = chaos

    c1, c2 = st.sidebar.columns(2)
    c1.metric("Chaos", f"{chaos * 100:.0f} %")
    c2.metric("Onglets", len(ss.onglets))
    st.sidebar.caption(f"Humeur du navigateur : {ss.humeur}.")

    with st.sidebar.expander("Réglages", expanded=False):
        st.selectbox("Moteur de recherche", ["Wikipédia", "DuckDuckGo (capricieux)"], key="moteur")
        st.slider("Taille du texte des pages", 12, 24, key="taille_texte")
        st.checkbox("Bloquer les images", key="bloquer_images")

    with st.sidebar.expander("Journal des incidents"):
        if ss.journal:
            for ligne in reversed(ss.journal):
                st.text(ligne)
        else:
            st.text("Aucun incident. Pour l'instant.")
    st.sidebar.button("Purger la réalité", key="btn_purge", on_click=purger_realite)
    return chaos


def etiquette_onglet(id_onglet):
    ss = st.session_state
    o = trouver_onglet(id_onglet)
    url = url_courante(o)
    if url.startswith("about:"):
        base = url[6:].capitalize()
    elif url.startswith("recherche:"):
        base = "🔎 " + texte_adresse(url)
    else:
        base = ss.titres.get(url) or urlparse(url).netloc
    base = base[:22] + ("…" if len(base) > 22 else "")
    return degrader(base, ss.chaos * 0.4) if ss.chaos > 0.7 else base


def entete():
    st.html('<div class="chrome"><span class="p1"></span><span class="p2"></span><span class="p3"></span></div>')
    st.markdown('<h1 class="glitch" data-text="ÉTHER//NAV">ÉTHER//NAV</h1>', unsafe_allow_html=True)
    st.markdown(f'<div class="sous-titre">{random.choice(SOUS_TITRES)}</div>', unsafe_allow_html=True)


def barre_onglets():
    ss = st.session_state
    st.radio(
        "Onglets", [o["id"] for o in ss.onglets], format_func=etiquette_onglet,
        horizontal=True, key="onglet_actif", label_visibility="collapsed",
    )


def barre_outils(chaos):
    o = onglet_courant()
    url = url_courante(o)
    c = st.columns(6)
    c[0].button("◀", key="btn_retour", on_click=reculer, help="Retour (capricieux)", disabled=o["pos"] == 0)
    c[1].button("▶", key="btn_avant", on_click=avancer, help="Avancer", disabled=o["pos"] >= len(o["pile"]) - 1)
    c[2].button("⟳", key="btn_actualiser", on_click=actualiser, help="Actualiser")
    c[3].button("⌂", key="btn_accueil", on_click=naviguer, args=(ACCUEIL,), help="Accueil")
    c[4].button("＋", key="btn_nouvel", on_click=nouvel_onglet, help="Nouvel onglet")
    c[5].button("✕", key="btn_fermer", on_click=fermer_onglet, help="Fermer l'onglet")

    with st.form("form_adresse", clear_on_submit=False):
        colonne_champ, colonne_bouton = st.columns([8, 1])
        colonne_champ.text_input(
            "Adresse", value=texte_adresse(url), key=cle_adresse(), label_visibility="collapsed",
            placeholder="Adresse, mot-clé ou about:accueil",
        )
        colonne_bouton.form_submit_button("Aller", on_click=valider_adresse)

    raccourcis = st.columns(3)
    raccourcis[0].button("🏺 Reliquaire", key="btn_aller_reliquaire", on_click=naviguer, args=("about:reliquaire",))
    raccourcis[1].button("🕰 Historique", key="btn_aller_historique", on_click=naviguer, args=("about:historique",))
    raccourcis[2].button("📖 Aide", key="btn_aller_aide", on_click=naviguer, args=("about:aide",))
    if chaos > 0.3 and url.startswith("http"):
        st.caption(f"Le site se souvient de son adresse ainsi : {degrader(url, chaos * 0.06)}")


def main():
    initialiser()
    chaos = barre_laterale()
    injecter_css(chaos)
    entete()
    barre_onglets()
    barre_outils(chaos)

    url = url_courante(onglet_courant())
    if url == "about:accueil":
        page_accueil()
    elif url == "about:historique":
        page_historique()
    elif url == "about:reliquaire":
        page_reliquaire()
    elif url == "about:aide":
        page_aide()
    elif url.startswith("about:"):
        st.warning("Cette page interne n'existe pas. Elle a peut-être existé demain.")
    elif url.startswith("recherche:"):
        page_recherche(url, chaos)
    else:
        page_web(url, chaos)


main()
