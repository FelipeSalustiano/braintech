# Detector de Medidores

Projeto de visão computacional para localizar medidores em fotografias usando detecção de objetos supervisionada. O treinamento usa imagens anotadas no formato COCO e a inferência produz uma cópia da imagem com a bounding box desenhada.

## Fluxo geral

```text
Imagens COCO anotadas + JSON de anotações
                    |
                    v
             Treinamento da CNN
                    |
                    v
       models/checkpoints/meter_detector.pt
                    |
                    v
       Imagens novas sem anotação COCO
                    |
                    v
              Pré-processamento
                    |
                    v
              Predição da caixa
                    |
                    v
       Imagens com bounding box desenhada
```

O projeto detecta a região do medidor. Ele não faz OCR nem extrai automaticamente os números exibidos no medidor.

## Pré-requisitos

- Python 3.10 ou superior.
- GPU NVIDIA com CUDA é recomendada, mas o treinamento também pode usar CPU.
- Dependências.

## Instalação

Crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell, use:

```powershell
.venv\Scripts\Activate.ps1
```

Atualize o instalador:

```bash
python -m pip install --upgrade pip
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

O arquivo de dependências inclui PyTorch, Torchvision, NumPy, Pillow, OpenCV e Pandas. A instalação de PyTorch com CUDA pode variar conforme a versão do driver NVIDIA; nesse caso, use o comando recomendado na página oficial do PyTorch.

Verifique se o PyTorch está funcionando:

```bash
python - <<'PY'
import torch
print("PyTorch:", torch.__version__)
print("CUDA disponível:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
PY
```

Se você não ativar o ambiente virtual, use diretamente `.venv/bin/python` nos comandos deste README.

## Arquitetura do projeto

```text
braintech/
├── configs/
│   └── detector.json
├── data/
│   ├── annotations/
│   ├── raw_images/
│   ├── preprocessed_images/
│   ├── predictions_preprocessed/
│   ├── sheets/
│   ├── imgs_raw_test/
│   ├── imgs_preprocessed_test/
│   └── imgs_prediction_test/
├── documents/
├── models/
│   ├── checkpoints/
│   │   ├── meter_detector.pt
│   │   └── semi_supervised/
│   │       └── best.pt        (baixar do Drive, ver "Baixar o modelo treinado")
│   ├── dataset.py
│   ├── detector.py
│   └── model.py
├── notebooks/
│   ├── arquitetura.ipynb
│   └── eda.ipynb
├── pipelines/
│   ├── preprocessing_images.py
│   ├── predict_detector.py
│   └── train_detector.py
├── src/
│   └── image_preprocessing.py
├── utils/
│   ├── image_convert.py
│   └── split_dataset.py
├── Dockerfile
├── README.md
├── requirements.txt
└── .gitignore
```

### Responsabilidade das pastas

| Pasta | Responsabilidade |
|---|---|
| `configs/` | Configurações de treinamento e predição em JSON |
| `data/` | Imagens, anotações COCO, planilhas e resultados gerados |
| `documents/` | Documentos de apoio e análises do projeto |
| `models/` | Dataset PyTorch, arquitetura da rede e checkpoints |
| `notebooks/` | EDA, testes exploratórios e desenvolvimento da arquitetura |
| `pipelines/` | Scripts executáveis de pré-processamento, treino e predição |
| `src/` | Regras centrais de análise e filtragem de imagens |
| `utils/` | Conversões de imagem e utilitários auxiliares |

### Organização dos dados

Dentro de `data/`:

- `annotations/`: arquivos JSON no formato COCO usados como rótulos do treinamento.
- `raw_images/`: imagens históricas originais.
- `preprocessed_images/`: imagens históricas tratadas usadas pelo treinamento.
- `predictions_preprocessed/`: resultados de predições históricas.
- `sheets/`: CSVs com leituras e informações dos medidores.
- `imgs_raw_test/`: imagens novas sem anotação.
- `imgs_preprocessed_test/`: imagens novas após o pré-processamento.
- `imgs_prediction_test/`: imagens novas com as bounding boxes desenhadas.

O JSON COCO deve conter `images`, `annotations` e `categories`. Cada anotação usa uma bounding box no formato `[x, y, largura, altura]`.

O JSON COCO deve conter pelo menos:

- `images`, com `id`, `file_name`, `width` e `height`;
- `annotations`, com `image_id` e `bbox`;
- `categories`, incluindo a classe `Medidor`.

A caixa COCO usa o formato:

```text
[x, y, largura, altura]
```

As imagens usadas no treinamento precisam existir na pasta indicada pelo dataset e ter os mesmos nomes presentes no JSON.

## Configuração central

O arquivo [configs/detector.json](configs/detector.json) concentra os parâmetros da predição e do treinamento:

```json
{
  "checkpoint": "models/checkpoints/meter_detector.pt",
  "input": "data/imgs_preprocessed_test",
  "output": "data/imgs_prediction_test",
  "threshold": 0.3,
  "training": {
    "epochs": 25,
    "batch_size": 8,
    "learning_rate": 0.0001,
    "validation_ratio": 0.2,
    "seed": 42,
    "num_workers": 0,
    "resume": false
  }
}
```

### Parâmetros de predição

- `checkpoint`: caminho do modelo treinado.
- `input`: arquivo ou pasta de imagens de entrada.
- `output`: pasta onde as imagens anotadas serão salvas.
- `threshold`: confiança mínima para considerar uma detecção.

### Parâmetros de treinamento

- `epochs`: número total de épocas.
- `batch_size`: quantidade de imagens por lote.
- `learning_rate`: taxa de aprendizado do Adam.
- `validation_ratio`: proporção usada para validação.
- `seed`: semente para tornar a divisão reproduzível.
- `num_workers`: processos usados pelo DataLoader.
- `resume`: continua a partir do checkpoint existente quando `true`.

Atenção: atualmente os caminhos do JSON COCO e da pasta de imagens de treinamento ficam definidos nos argumentos padrão de `pipelines/train_detector.py`. Os campos `input` e `output` do JSON controlam a predição, não o dataset de treinamento.

## Pré-processamento de imagens

O pré-processamento analisa brilho e nitidez usando `ImageAnalyzer` e pode aplicar:

- aumento de brilho para imagens escuras;
- redução de brilho para imagens claras;
- nitidez para imagens borradas;
- suavização para imagens ruidosas.

Para pré-processar um conjunto de imagens:

```bash
python pipelines/preprocessing_images.py \
  --input data/imgs_raw_test \
  --output data/imgs_preprocessed_test
```

O script processa arquivos `.jpg` e `.jpeg`, preserva os nomes dos arquivos e informa a quantidade processada e os erros.

Para as imagens de treinamento, o diretório pré-processado esperado é:

```text
data/preprocessed_images/PSP_EXTRATLEITIMPL_030726_0121_preprocessed
```

## Treinamento do modelo

O treinamento usa:

```text
data/annotations/PSP_EXTRATLEITIMPL_030726_0121_instances.json
 data/preprocessed_images/PSP_EXTRATLEITIMPL_030726_0121_preprocessed/
```

O dataset seleciona as imagens que possuem anotação, divide os IDs em treino e validação e cria alvos em uma grade `60 x 45`. A rede produz cinco valores por célula:

```text
posição X, posição Y, largura, altura, objectness
```

### Treinamento do zero

Para começar um modelo novo:

```bash
rm -f models/checkpoints/meter_detector.pt
python pipelines/train_detector.py
```

Os parâmetros são lidos de `configs/detector.json`. O melhor checkpoint, definido pela menor `validation_loss`, é salvo em:

```text
models/checkpoints/meter_detector.pt
```

O log é salvo em:

```text
logs/training.log
```

Acompanhe o log em outro terminal:

```bash
tail -f logs/training.log
```

### Continuar um treinamento

Altere o total de épocas e ative `resume`:

```json
"training": {
  "epochs": 60,
  "resume": true
}
```

Depois execute:

```bash
python pipelines/train_detector.py
```

Nesse modo, o script carrega os pesos, o estado do otimizador e a época registrada no checkpoint. O valor de `epochs` representa a época final desejada.

Para iniciar um experimento independente, use `"resume": false` e remova ou renomeie o checkpoint anterior.

### Sobrescrever parâmetros temporariamente

Também é possível substituir um parâmetro sem editar o JSON:

```bash
python pipelines/train_detector.py --epochs 30 --batch-size 8 --learning-rate 0.0001
```

## Predição em imagens novas

Coloque as imagens novas em:

```text
data/imgs_raw_test/
```

Pré-processe-as:

```bash
python pipelines/preprocessing_images.py \
  --input data/imgs_raw_test \
  --output data/imgs_preprocessed_test
```

Confirme no `configs/detector.json`:

```json
"checkpoint": "models/checkpoints/meter_detector.pt",
"input": "data/imgs_preprocessed_test",
"output": "data/imgs_prediction_test"
```

Execute a predição sem argumentos adicionais:

```bash
python pipelines/predict_detector.py
```

As imagens de saída serão gravadas em:

```text
data/imgs_prediction_test/
```

Cada saída mantém o nome da imagem de entrada e recebe a bounding box vermelha com o score da detecção.

O script redimensiona a entrada para `360 x 480`, resolução usada pelo modelo, e projeta a caixa para o tamanho da imagem de saída.

### Testar outro threshold

Altere no JSON:

```json
"threshold": 0.5
```

Depois execute novamente:

```bash
python pipelines/predict_detector.py
```

Para não sobrescrever resultados anteriores, altere também:

```json
"output": "data/imgs_prediction_test_threshold_050"
```

Threshold menor gera mais detecções e pode aumentar falsos positivos. Threshold maior é mais rigoroso e pode eliminar detecções válidas. O threshold não retreina nem altera o modelo.

Também é possível fazer um override temporário:

```bash
python pipelines/predict_detector.py --threshold 0.5
```

## Rotulagem semi-supervisionada

Só o lote `PSP_EXTRATLEITIMPL_030726_0121` (2.992 imagens) tem anotação COCO; os outros três lotes (9.348 imagens) não. Para rotulá-los, o projeto usa um esquema professor-aluno com pseudo-rótulos (self-training / Noisy Student) sobre um Faster R-CNN ResNet50-FPN v2 pré-treinado no COCO.

```text
Rótulos humanos (treino) ──> Professor (rodada 0)
                                  │  prediz com TTA (original + espelhada)
                                  v
              Imagens sem rótulo ──> aceito | negativo | revisar
                                  │
Rótulos humanos + pseudo-rótulos ─┴─> Aluno novo (augmentação forte)
                                  │  só vira professor se melhorar na validação
                                  v
                       Próxima rodada ... ──> best.pt
```

Decisões principais:

- **Imagens sem caixa no JSON são negativas.** As 225 imagens do lote rotulado sem anotação mostram fachadas, portas ou medidores ilegíveis; entram no treino como fundo para o modelo aprender a não rotular.
- **Validação sempre humana.** A validação usa as mesmas 553 imagens com caixa do `train_detector.py` (mesma ordem, seed e proporção) mais 20% das negativas. Ela nunca recebe pseudo-rótulos e decide se o aluno substitui o professor.
- **Filtro de confiança.** Na predição com TTA, caixas vistas nas duas visões têm score médio; caixas vistas em só uma têm o score pela metade. A imagem vira:
  - `aceito`: todas as caixas com score `>= accept_threshold` (0,8). Entra no treino do aluno;
  - `negativo`: nenhuma caixa acima de `negative_threshold` (0,05). Entra como fundo;
  - `revisar`: alguma caixa na zona de incerteza. Fica fora do treino e vai para revisão humana.
- **Caixas aninhadas.** O modelo às vezes propõe o medidor e o gabinete que o contém. Caixas com 80% ou mais da área dentro de outra de score maior são descartadas.
- **Mistura 50/50.** Cada lote do aluno tem, em média, metade de rótulos humanos e metade de pseudo-rótulos, para os pseudo-rótulos não dominarem o treino.

Os parâmetros ficam na seção `semi_supervised` do [configs/detector.json](configs/detector.json).

### Baixar o modelo treinado

O checkpoint do modelo final (`best.pt`, ~173 MB) não fica no git, porque passa do limite de 100 MB por arquivo do GitHub. Ele está no Google Drive:

**Link:**  _[best.pt](https://drive.google.com/file/d/1yEUIxBpmWoSwnLl4IkQONiIlRFzAODCV/view?usp=drive_link)_

Depois de baixar, coloque o arquivo exatamente neste caminho, a partir da raiz do projeto:

```text
braintech/
└── models/
    └── checkpoints/
        └── semi_supervised/
            └── best.pt
```

Se a pasta `semi_supervised/` não existir, crie-a. O nome do arquivo precisa ser `best.pt`: é o caminho que o `pipelines/pseudo_label.py` usa por padrão (`output_dir` do `configs/detector.json` + `/best.pt`). Para usar o arquivo em outro lugar, passe `--checkpoint <caminho>`.

Confira se o arquivo foi baixado inteiro e carrega:

```bash
python -c "import torch; c = torch.load('models/checkpoints/semi_supervised/best.pt', map_location='cpu', weights_only=True); print(c['architecture'], 'época', c['epoch'], c['metrics'])"
```

A saída deve mostrar `fasterrcnn_resnet50_fpn_v2 época 11` e as métricas de validação do modelo, com `'ap50_95': 0.6206...`. Esse valor é medido sem TTA; com TTA, que é como o modelo rotula, o AP50:95 é 0,625 (ver `summary.json`). Com o arquivo no lugar, não é preciso treinar: vá direto para "Rotular as imagens restantes" ou "Testar em imagens específicas".

Os checkpoints de cada rodada (`round_0.pt`, `round_1.pt`, `round_2.pt`) são intermediários e não precisam ser baixados. O `round_2.pt` é idêntico ao `best.pt`.

### Treinar

```bash
python pipelines/train_semi_supervised.py
```

Saídas em `models/checkpoints/semi_supervised/`: `round_N.pt` de cada rodada, `best.pt` (melhor rodada) e `summary.json` com as métricas de validação e a contagem de pseudo-rótulos. O log fica em `logs/semi_supervised.log`. Para um teste rápido:

```bash
python pipelines/train_semi_supervised.py --rounds 1 --teacher-epochs 1 --student-epochs 1 --unlabeled-limit 200
```

### Rotular as imagens restantes

```bash
python pipelines/pseudo_label.py --preview-dir data/predictions_preprocessed/pseudo
```

Para cada lote são gerados, em `data/annotations/pseudo/`:

- `<lote>_instances.json`: COCO no formato do CVAT, pronto para importar. Cada anotação traz `score` e `pseudo_label_status`. Imagens `revisar` trazem as caixas incertas para correção manual;
- `<lote>_status.csv`: status, maior score e número de caixas de cada imagem, para filtrar o que precisa de revisão.

Com `--preview-dir`, as imagens são salvas com as caixas desenhadas, separadas por status. Para ser mais ou menos rigoroso sem retreinar, use `--accept-threshold`.

### Testar em imagens específicas

Para rodar o modelo numa pasta qualquer (por exemplo, fotos novas em `data/imgs_raw_test`), pré-processe as imagens primeiro, porque o modelo foi treinado com imagens pré-processadas:

```bash
python pipelines/preprocessing_images.py --input data/imgs_raw_test --output data/imgs_preprocessed_test
python pipelines/pseudo_label.py --folders data/imgs_preprocessed_test --output data/imgs_test_predictions --preview-dir data/imgs_test_predictions
```

O pré-processamento só lê arquivos `.jpg` e `.jpeg`. Não é preciso redimensionar: o modelo ajusta o tamanho sozinho e as caixas saem nas coordenadas da imagem original.

Para comparar com o detector antigo nas mesmas imagens:

```bash
python pipelines/predict_detector.py --checkpoint models/checkpoints/meter_detector.pt --input data/imgs_preprocessed_test --output data/imgs_test_predictions/modelo_antigo
```

## Verificação rápida

Depois do treinamento, valide o checkpoint:

```bash
ls -lh models/checkpoints/meter_detector.pt
```

Teste o carregamento e o forward do modelo:

```bash
python - <<'PY'
from pathlib import Path
from models.dataset import MeterDataset
from models.model import MeterNetwork

import torch

dataset = MeterDataset(
    Path("data/annotations/PSP_EXTRATLEITIMPL_030726_0121_instances.json"),
    Path("data/preprocessed_images/PSP_EXTRATLEITIMPL_030726_0121_preprocessed"),
)
image, target = dataset[0]
output = MeterNetwork()(image.unsqueeze(0))
print("dataset:", len(dataset))
print("image:", tuple(image.shape))
print("target:", tuple(target.shape))
print("output:", tuple(output.shape))
PY
```

O resultado esperado inclui:

```text
image: (1, 480, 360)
target: (5, 60, 45)
output: (1, 5, 60, 45)
```

## Problemas comuns

### `FileNotFoundError: Input not found`

Confira se o caminho no `detector.json` corresponde à pasta real:

```bash
find data -maxdepth 2 -type d | sort
```

### A predição processa zero imagens

Verifique se a pasta de entrada contém arquivos `.jpg`, `.jpeg`, `.png`, `.bmp` ou `.webp` e se o campo `input` aponta para ela.

### Nenhuma caixa aparece

Confira:

1. se você está abrindo as imagens da pasta de saída, e não as originais;
2. se o checkpoint existe;
3. se o threshold não está alto demais;
4. se a pasta de entrada foi pré-processada;
5. se as caixas das anotações COCO são válidas.

O contador `detections` indica que a confiança passou do threshold, mas a qualidade da caixa depende das anotações usadas no treinamento.

### `validation_loss` aumenta

Isso geralmente indica overfitting quando o `train_loss` continua caindo. Use menos épocas, uma taxa de aprendizado menor ou interrompa o treinamento quando a validação parar de melhorar. O script mantém o melhor checkpoint encontrado, não necessariamente o último estado do treinamento.

### Caixas muito grandes ou deslocadas

O modelo aprende o formato das bounding boxes COCO. Se as caixas anotadas cobrem quase todo o painel, as previsões também serão grandes. Corrija as anotações e retreine para obter caixas mais precisas.

### Erro ao importar `src` ou `models`

Execute os comandos a partir da raiz do projeto:

```bash
cd /home/hcdebarros/cesar/mlops/braintech
```

Os scripts também configuram a raiz do projeto no `sys.path` quando executados diretamente.

## Componentes principais

- `models/dataset.py`: leitura do COCO e conversão das caixas para alvos da grade.
- `models/model.py`: arquitetura convolucional `MeterNetwork`.
- `pipelines/preprocessing_images.py`: diagnóstico e melhoria das imagens.
- `pipelines/train_detector.py`: split, treinamento, validação, logging e checkpoint.
- `pipelines/predict_detector.py`: carregamento do checkpoint e desenho das caixas.
- `src/image_preprocessing.py`: análise de brilho, ruído e filtros.
- `utils/image_convert.py`: conversão de imagens para matrizes e tensores.
- `configs/detector.json`: configuração de treinamento e inferência.

## Limitações atuais

- O projeto detecta a região do medidor, mas não faz OCR da leitura.
- A implementação escolhe a célula de maior confiança na predição.
- Não há cálculo de IoU, mAP, precision ou recall no pipeline.
- A qualidade final depende diretamente da qualidade das bounding boxes COCO.
- O script de treino usa atualmente um arquivo de anotação e uma pasta de imagens padrão.
