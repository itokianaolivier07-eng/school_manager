# SchoolManager — gestion d'école (Python · PyQt6 · SQLite)

## Lancer
```bash
pip install -r requirements.txt
python -m scripts.seed_demo --students 30000   # optionnel : données de test (30 000 élèves, 240 000 notes)
python main.py                                  # 1er lancement : création de l'administrateur
python -m pytest                                # tests
```
Données dans `~/.school_manager/` (changer avec la variable `SCHOOL_DATA_DIR`).

## Architecture (couches, dépendances vers le bas uniquement)
```
main.py                      point d'entrée, boucle connexion/déconnexion
app/ui/                      PyQt6 : vues génériques (CrudView), formulaires, dialogues  -> services
app/services/                logique métier : permissions, validation, transactions, audit -> repositories
app/repositories/            SQL paramétré uniquement                                      -> database
app/database/                connexion SQLite durcie, migrations versionnées
app/core/                    sécurité (scrypt), RBAC, session, validateurs, exceptions
```
Modules : élèves (import/export CSV), enseignants, classes, matières, notes (saisie, moyennes pondérées,
classement), utilisateurs, journal d'audit, sauvegardes.

## Sécurité
- Mots de passe : scrypt + sel aléatoire, comparaison à temps constant, politique de complexité.
- Connexion : verrouillage après 5 échecs (5 min), message identique si l'utilisateur n'existe pas, déconnexion après 15 min d'inactivité, changement de mot de passe forcé pour les comptes créés par un admin.
- Pas de mot de passe par défaut : l'admin est créé au premier lancement.
- RBAC (admin / secrétariat / enseignant) vérifié dans **chaque service** (pas seulement dans l'interface).
- SQL : requêtes paramétrées, tri en liste blanche, `LIKE` échappé ; contraintes CHECK/UNIQUE/FOREIGN KEY en base.
- Journal d'audit en ajout seul (triggers qui interdisent UPDATE/DELETE) ; aucun mot de passe journalisé.
- Fichiers de données en 0600 / dossiers 0700, `secure_delete`, `trusted_schema=OFF`, export CSV protégé contre l'injection de formules, import limité à 25 Mo.
- Sauvegarde à chaud avec contrôle d'intégrité et rotation.
- Limite connue : SQLite standard n'est pas chiffré ; pour chiffrer au repos, utiliser SQLCipher ou le chiffrement du disque (BitLocker/LUKS).

## Performance (30 000+ élèves)
Pagination SQL (100 lignes en mémoire), recherche par préfixe sur index NOCASE, tri côté serveur, WAL, insertions en masse par `executemany` dans une seule transaction.

## Ajouter un module
1. migration dans `schema.py` · 2. repository · 3. service (`CrudService` + `validate`) · 4. fonction dans `ui/views.py` · 5. entrée dans `main_window.py`.
