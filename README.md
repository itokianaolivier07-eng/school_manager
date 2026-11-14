# SchoolManager

Application de bureau de gestion d'un établissement scolaire, écrite en Python avec PyQt6 et SQLite.

## Installation et lancement
```bash
pip install -r requirements.txt
python main.py
```

Au premier lancement, l'application demande la création du compte administrateur. Les données sont stockées dans
`~/.school_manager/`. La variable `SCHOOL_DATA_DIR` permet de choisir un autre emplacement.

Pour générer des données de démonstration dans une base vide :
```bash
python -m scripts.seed_demo --students 30000
```

Les tests se lancent avec `python -m pytest`.

## Architecture (couches, dépendances vers le bas uniquement)
```
main.py                      point d'entrée, boucle connexion/déconnexion
app/ui/                      PyQt6 : vues génériques (CrudView), formulaires, dialogues  -> services
app/services/                logique métier : permissions, validation, transactions, audit -> repositories
app/repositories/            SQL paramétré uniquement                                      -> database
app/database/                connexion SQLite durcie, migrations versionnées
app/core/                    sécurité (scrypt), RBAC, session, validateurs, exceptions
```
Fonctions : tableau de bord, élèves (import/export CSV), enseignants, classes, matières, notes et classements,
tarifs scolaires, encaissements, reçus PDF, annulations, impayés, utilisateurs, journal d'audit et sauvegardes.
La section Salaires sépare les rémunérations de base et l'historique des sorties ; les postes de professeur
peuvent être rémunérés à l'heure, avec calcul automatique selon les heures saisies.
Les tarifs sont associés à une classe et à une année scolaire. Les coordonnées historiques générales des élèves restent dans les bases déjà créées, mais ne sont plus
affichées ni exportées. La fiche élève permet de renseigner les noms et téléphones facultatifs du tuteur,
du père et de la mère, ainsi que leurs professions ; ces informations sont incluses dans l'import/export CSV.
Les tarifs d'écolage sont définis par classe et année scolaire : droit, photocopie, tenue, calendrier,
classe verte, enveloppe, fête de fin d'année, autre et
mensualités de septembre à juin. La situation de chaque élève affiche ces 18 postes séparément.
L'onglet Impayés permet de filtrer par classe, année scolaire et mois d'écolage, puis d'exporter les postes
impayés détaillés en CSV.
La fiche élève peut contenir le tuteur et les noms du père et de la mère ; ces trois informations sont facultatives.

## Sécurité
- Mots de passe : scrypt + sel aléatoire, comparaison à temps constant, politique de complexité.
- Connexion : verrouillage après 5 échecs (5 min), message identique si l'utilisateur n'existe pas, déconnexion après 15 min d'inactivité, changement de mot de passe forcé pour les comptes créés par un admin.
- Pas de mot de passe par défaut : l'admin est créé au premier lancement.
- Accès par rôle (administrateur / secrétariat / enseignant), vérifié dans les services et dans l'interface.
- SQL : requêtes paramétrées, tri en liste blanche, `LIKE` échappé ; contraintes CHECK/UNIQUE/FOREIGN KEY en base.
- Journal d'audit en ajout seul (triggers qui interdisent UPDATE/DELETE) ; aucun mot de passe journalisé.
- Fichiers de données en 0600 / dossiers 0700, `secure_delete`, `trusted_schema=OFF`, export CSV protégé contre l'injection de formules, import limité à 25 Mo.
- Sauvegarde à chaud avec contrôle d'intégrité et rotation.
- Les paiements enregistrés sont conservés ; une erreur se traite par une annulation motivée.
- Limite connue : SQLite standard n'est pas chiffré ; pour chiffrer au repos, utiliser SQLCipher ou le chiffrement du disque (BitLocker/LUKS).

## Performance (30 000+ élèves)
Pagination SQL (100 lignes en mémoire), recherche par préfixe sur index NOCASE, tri côté serveur, WAL, insertions en masse par `executemany` dans une seule transaction.

## Ajouter un module
1. migration dans `schema.py` · 2. repository · 3. service (`CrudService` + `validate`) · 4. fonction dans `ui/views.py` · 5. entrée dans `main_window.py`.
