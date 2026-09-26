# Collecteur annuel de publications Facebook

Ce projet est un Actor Apify à installer dans votre compte. Vous entrez l'URL d'une **page Facebook publique** et l'année dans un formulaire. Il utilise ensuite `apify/facebook-posts-scraper` et avance automatiquement dans cette année. L'exemple proposé dans le formulaire est `https://www.facebook.com/UC3SB`, pour l'année 2025.

## Comment l'exécuter

1. Le code se trouve à la racine du dépôt GitHub `facebook-year-collector`. Ne mettez jamais un jeton Apify dans le dépôt.
2. Dans la console Apify, ouvrez **Actors → Develop new**, sélectionnez l'intégration GitHub et ce dépôt, construisez l'Actor et ouvrez son onglet **Input**.
3. Entrez `facebookUrl` (par exemple `https://www.facebook.com/UC3SB`), `year` (par défaut `2025`) et `resultsLimit` (par défaut `50`). Cliquez sur **Start** pour une première exécution. Vérifiez le bilan dans le dataset de cette exécution.
4. Depuis cet Actor, créez une **Task** avec les mêmes champs, puis un **Schedule** associé à cette Task. Choisissez `*/30 * * * *` (toutes les 30 minutes) et l'option **Exclusive** pour éviter deux exécutions simultanées. Vous pouvez aussi programmer directement l'Actor si son input est enregistré.
5. Le bilan de chaque exécution fournit `combined_dataset_id`, qui pointe vers le dataset cumulé de la page et de l'année. Le stockage nommé `fb-progress-<année>-<identifiant>` contient l'entrée `CURSOR` et la prochaine date. Les datasets et stockages sont séparés par page et par année.

Une exécution du contrôleur lance **au maximum un appel** à `apify/facebook-posts-scraper`. Le premier passage sur `2025` essaie le 1er et le 2 janvier, bornes UTC du `2025-01-01T00:00:00Z` au `2025-01-03T00:00:00Z`. S'il trouve moins de 50 publications, il garde ce résultat provisoirement. **Trente minutes plus tard**, le passage suivant essaie aussi le 3 janvier, jusqu'au `2025-01-04T00:00:00Z`. Si ce nouvel essai atteint 50, seul le résultat sauvegardé des deux premiers jours est publié et le 3 janvier est repris au prochain passage. Si les deux premiers jours atteignent 50, le passage suivant essaie un seul jour. À 50 résultats sur un jour, la collecte se met en pause sans répéter un appel payant à chaque demi-heure : augmentez `resultsLimit` dans la Task pour reprendre.

Il faut au minimum 244 exécutions réussies du contrôleur pour une année ordinaire si toutes les fenêtres atteignent trois jours : une tentative de deux jours puis une de trois jours pour chaque fenêtre. Une fenêtre raccourcie augmente le nombre de passages nécessaires. Après le 31 décembre, les exécutions suivantes ne relancent plus le scraper. Le scraper lui-même peut faire plusieurs requêtes HTTP internes par appel : le présent projet limite ses **déclenchements**, pas son trafic HTTP interne.

## Reprise et limites

- Une erreur du scraper ne fait pas avancer le curseur. Le passage horaire suivant recommence au même jour.
- Le scraper ne traite que les publications accessibles publiquement. Son accès aux anciens posts peut être incomplet. Un créneau traité ne garantit pas une archive exhaustive.
- Les bornes exactes dépendent de l'implémentation du scraper. Contrôlez les publications autour de minuit et dédoublonnez l'export final par URL ou identifiant.
- Si l'écriture dans le dataset cumulé réussit, mais que la mise à jour du curseur échoue, le créneau peut être rejoué et créer des doublons. Les datasets de chaque exécution source restent disponibles.
- Modifier l'URL ou l'année démarre une progression distincte. Modifier seulement `resultsLimit` reprend la progression en cours.
- Pour recommencer une page et une année depuis le début, supprimez son entrée `CURSOR` et utilisez un nouveau dataset cumulé afin d'éviter les doublons.

## Vérifier le code localement

Depuis la racine du projet : `python -m unittest discover -s tests`.
