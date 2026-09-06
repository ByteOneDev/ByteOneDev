# Maintenance du profil

Ce repo génère le README affiché sur mon profil GitHub. Deux choses seulement sont
à connaître pour le faire évoluer.

## 1. Le repo doit s'appeler comme le compte

GitHub n'affiche le README de profil que si le repo porte **exactement** le nom du
compte : `ByteOneDev/ByteOneDev`. Renommer le compte sans renommer le repo fait
disparaître le profil sans le moindre avertissement.

## 2. Les widgets

| Widget | Origine | Rafraîchi |
|---|---|---|
| Bannière, échecs, cartes projets | `scripts/build_widgets.py` (maison) | toutes les 6 h — `.github/workflows/widgets.yml` |
| Snake des contributions | action `Platane/snk`, publiée sur la branche `output` | chaque nuit — `.github/workflows/snake.yml` |
| Stats / langages / streak | services externes (Vercel) | à chaque chargement de la page |

Tout ce qui est configurable vit dans **`widgets.config.json`** : nom affiché, accroche,
liste des 4 projets mis en avant, et `chess_accounts` — autant de comptes que voulu, chacun
avec sa plateforme (`chesscom` ou `lichess`), son pseudo et son label. Le widget crée un
panneau par compte et s'élargit tout seul. Modifier ce
fichier et pousser suffit : l'Action régénère les SVG automatiquement.

Pour tester en local :

```bash
python3 scripts/build_widgets.py   # écrit les SVG dans assets/
```

Le script n'a **aucune dépendance** (stdlib uniquement) et absorbe les erreurs réseau :
si une API est injoignable, il reprend les valeurs de repli de `scripts/seed.json`
plutôt que de produire un fichier vide. Un widget moche vaut mieux qu'une image cassée.

## Limite connue

GitHub interdit `<script>`, `<iframe>` et le CSS custom dans les README. La seule
« interactivité » possible est donc : SVG animés, sections `<details>` repliables et
images cliquables. Tout ce qui est ici respecte ces contraintes.
