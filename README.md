# ÉTHER//NAV

Un vrai navigateur web dans Streamlit, stylé (néon, glitch, scanlines) et volontairement étrange.

- Onglets, historique par onglet, retour / avant / actualiser, marque-pages (le Reliquaire)
- Barre d'adresse intelligente : URL, mot-clé (recherche Wikipédia ou DuckDuckGo) ou `about:accueil`
- Les pages sont téléchargées côté serveur, nettoyées (aucun script), puis affichées en 5 modes de perception
- Protection contre l'accès aux réseaux privés (SSRF)

## Lancer en local

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

## Déployer sur Streamlit Community Cloud

1. Pousser ce dossier sur GitHub (fichier principal : `app.py`, à la racine).
2. https://share.streamlit.io → « Create app » → dépôt, branche `main`, fichier `app.py`.

## Limites

- Pas de JavaScript : les pages sont affichées en version nettoyée.
- Certains sites bloquent les IP de serveurs (Cloudflare, etc.) et refuseront de répondre.
- Les liens d'une page sont regroupés dans la « soute à liens » sous la page.
