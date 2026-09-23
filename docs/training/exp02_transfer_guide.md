# Transfert et lancement de YOLO EXP-02 sur un autre ordinateur

- Expérience : `exp02_yolo11n_h250_960_b4`
- Modèle : YOLO11n, initialisation COCO fraîche
- Dataset : SoccerNet-v3 H250, rôle `training`
- Paramètres gelés : 960 px, batch 4, 50 époques, patience 15, seed 42
- Branche : `feat/chapter4-detector-optimization`

EXP-02 ne doit jamais démarrer depuis le `best.pt` d'EXP-01. Celui-ci sert uniquement de référence comparative. Aucun média, export ou résultat `golden_eval` ne peut entrer dans l'entraînement.

## 1. Ce qui passe par Git

Après le push, l'autre ordinateur récupère par Git :

- la spec gelée `configs/training/exp02_yolo11n_h250_960_b4.json` ;
- le lanceur portable `scripts/run_exp02.py` ;
- les contrôles H250 `scripts/h250_dataset.py` ;
- le téléchargeur/extracteur H250 avec vérification SHA-256 ;
- le script de préparation du support de transfert ;
- les métriques réelles EXP-01 et les tests.

Le dataset, les poids et les runs restent hors Git. Ils sont volumineux, régénérables ou privés et sont déjà couverts par `.gitignore`.

## 2. Fichiers binaires à transférer

### Obligatoires

| Fichier source | Taille | SHA-256 | Destination conseillée |
|---|---:|---|---|
| `D:\datasets\h250\YOLO.zip` | 2 544 758 991 octets | `da2cca388ec51500c5c9ef4d974d7c28cb73b3a75e8c506299d2715028f8bc37` | `D:\datasets\h250\YOLO.zip` |
| `<repo>\yolo11n.pt` | 5 613 764 octets | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` | racine du nouveau clone |

### Optionnel, référence EXP-01 uniquement

| Fichier | Taille | SHA-256 |
|---|---:|---|
| `D:\runs\detect\exp01_yolo11n_h250_640_b4\weights\best.pt` | 5 450 643 octets | `590dcb69ee501bddc61de0cded5f40b0bf65c00d83c2ebbe8e5962a646eb9844` |

Le checkpoint EXP-01 ne doit pas être fourni à `--weights` pour EXP-02.

## 3. Préparer un disque externe sur le PC source

Vérifier d'abord toutes les sources sans rien copier :

```powershell
python scripts/prepare_exp02_transfer.py --check-only
```

Brancher un disque disposant d'au moins 3 Go libres, puis remplacer `E:\VISION-BALLING-EXP02` par sa destination réelle :

```powershell
python scripts/prepare_exp02_transfer.py `
  --destination E:\VISION-BALLING-EXP02
```

Pour inclure aussi le checkpoint EXP-01 de référence :

```powershell
python scripts/prepare_exp02_transfer.py `
  --destination E:\VISION-BALLING-EXP02 `
  --include-exp01-best
```

Le script refuse d'écraser un fichier différent, vérifie chaque copie et écrit `exp02_transfer_manifest.json`. Il n'inclut aucun golden.

## 4. Préparer le nouveau PC

Cloner le dépôt et sélectionner la branche :

```powershell
git clone https://github.com/GAdrianK/VISION-BALLING.git
Set-Location VISION-BALLING
git switch feat/chapter4-detector-optimization
git status -sb
```

Créer un environnement Python dédié :

```powershell
py -3.11 -m venv .venv-training
.\.venv-training\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Installer d'abord une version de PyTorch compatible avec le GPU et le pilote du nouveau PC, en suivant le sélecteur officiel PyTorch. Vérifier que cette installation voit réellement CUDA avant d'installer le reste :

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
python -m pip install -r backend/requirements-training.txt
```

Une sortie `False` pour `torch.cuda.is_available()` bloque le lancement GPU. Ne pas lancer 50 époques avant correction.

## 5. Restaurer et valider H250

Copier `dataset\YOLO.zip` du support externe vers `D:\datasets\h250\YOLO.zip`, puis extraire et vérifier sans nouveau téléchargement :

```powershell
python scripts/download_h250.py `
  --dest-dir D:\datasets\h250 `
  --skip-download
```

Le résultat valide doit contenir exactement :

- train : 14 368 images et 14 368 labels ;
- valid : 2 726 images et 2 726 labels ;
- test : 2 692 images et 2 692 labels ;
- classes : `0 = ball`, `1 = person`.

Copier ensuite `weights\yolo11n.pt` à la racine du clone.

## 6. Porte obligatoire avant entraînement

```powershell
python scripts/run_exp02.py `
  --check-only `
  --data D:\datasets\h250\YOLO\data.yaml `
  --weights .\yolo11n.pt `
  --runs-dir D:\runs\detect `
  --device 0
```

La commande vérifie la spec, les 19 786 paires image/label, les classes, les SHA-256, les dépendances et CUDA. Le statut doit être `READY`. Un statut `BLOCKED` interdit de lancer l'expérience.

## 7. Lancer, reprendre ou évaluer EXP-02

Nouveau run, uniquement si le dossier EXP-02 n'existe pas :

```powershell
python scripts/run_exp02.py `
  --data D:\datasets\h250\YOLO\data.yaml `
  --weights .\yolo11n.pt `
  --runs-dir D:\runs\detect `
  --device 0
```

Reprendre après interruption :

```powershell
python scripts/run_exp02.py `
  --resume `
  --data D:\datasets\h250\YOLO\data.yaml `
  --weights .\yolo11n.pt `
  --runs-dir D:\runs\detect `
  --device 0
```

Relancer volontairement depuis zéro dans un dossier existant : utiliser `--restart`. Évaluer seulement un `best.pt` existant : utiliser `--eval-only`. Ces trois modes sont mutuellement exclusifs.

## 8. Résultats à retransmettre

Après entraînement et évaluation, conserver hors Git :

- `D:\runs\detect\exp02_yolo11n_h250_960_b4\weights\best.pt` ;
- `D:\runs\detect\exp02_yolo11n_h250_960_b4\weights\last.pt` ;
- le dossier de run Ultralytics complet.

Le fichier `exp02_evaluation_report.json` contient automatiquement le SHA du checkpoint, le commit Git, les versions, le GPU, les paramètres, les métriques Ultralytics, le benchmark canonique et les deltas contre EXP-00/EXP-01. Ne publier ce rapport comme résultat officiel qu'après vérification complète ; ne jamais inventer de métrique si le run est interrompu.
