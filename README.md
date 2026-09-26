# Facebook Year Collector

Actor Apify pour collecter les publications d'une page Facebook publique pendant une année. L'utilisateur fournit l'URL, l'année, la limite de résultats et la taille maximale d'une fenêtre de dates.

## Mise en route

1. Dans Apify Console, créez un Actor depuis le dépôt GitHub `Salimdz25/facebook-year-collector`, puis construisez-le.
2. Dans Input, utilisez par exemple :

```json
{
  "facebookUrl": "https://www.facebook.com/UC3SB",
  "year": 2025,
  "resultsLimit": 50,
  "maxDays": 10
}
```

3. Lancez un premier passage avec **Start**, puis enregistrez ces paramètres comme **Task**.
4. Créez un Schedule pour cette Task, toutes les 30 minutes (`*/30 * * * *` ou deux minutes fixes distantes de 30 minutes). Activez l'option **Exclusive** pour empêcher les chevauchements et activez le Schedule.
5. Désactivez tout ancien Schedule qui lance directement `apify/facebook-posts-scraper` sur la même page.

## Fonctionnement

Chaque passage du contrôleur déclenche **au plus un appel** à `apify/facebook-posts-scraper`. Il essaie d'abord `maxDays` jours, soit 10 par défaut. Si le scraper retourne moins de `resultsLimit` publications, ces résultats sont enregistrés et la date de reprise avance à la fin de la fenêtre. S'il atteint la limite, le résultat est considéré potentiellement tronqué : il n'est pas publié et la fenêtre est divisée par deux au passage suivant (10 → 5 → 2 → 1 jours). Un jour atteignant encore la limite met la collecte en pause, sans appels payants répétés ; augmentez `resultsLimit` pour reprendre.

Le passage initial de la version précédente sur deux jours, resté provisoire, est automatiquement repris avec la fenêtre de 10 jours. Les dates sont en UTC. Après le 31 décembre, les passages programmés ne relancent plus le scraper.

Le dataset nommé `fb-posts-<année>-<identifiant>` cumule les publications. Le stockage `fb-progress-<année>-<identifiant>`, entrée `CURSOR`, garde la progression pour chaque URL et année. Le dataset par défaut de chaque passage achevé contient un bilan avec l'identifiant du dataset cumulé. Changer l'URL ou l'année commence une progression indépendante.

**Limites :** le scraper peut faire plusieurs requêtes HTTP internes par appel ; ce projet limite ses déclenchements, pas son trafic HTTP. Les anciens posts que Facebook n'expose pas publiquement peuvent manquer. Vérifiez les posts aux bornes de dates et dédoublonnez l'export par URL ou identifiant. Si l'écriture des posts réussit mais que l'enregistrement du curseur échoue, le même créneau peut être rejoué.

## Tests locaux

`python -m unittest discover -s tests`
