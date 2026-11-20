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

O projeto detecta o medidor e o display e lê o valor do display com um reconhecedor treinado (veja [Leitura do display (OCR)](#leitura-do-display-ocr)). As leituras vão para um painel web de validação (veja [Painel VoltLens](#painel-voltlens-front-end--supabase)).

**Para rodar tudo numa máquina nova, do processamento ao login no painel, siga [Demonstração de ponta a ponta](#demonstração-de-ponta-a-ponta-do-processamento-ao-login).**

## Pré-requisitos

- Python 3.12 ou superior (o `numpy` de `requirements.txt` exige 3.12).
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

## Demonstração de ponta a ponta (do processamento ao login)

Roteiro para rodar a aplicação inteira numa máquina nova, sem treinar nada: processar as fotos
de teste com os modelos já treinados, publicar o resultado no Supabase e validar as leituras no
painel web. Leva uns 20 minutos na primeira vez (a maior parte é a instalação) e 1 a 3 minutos de processamento.

```text
data/imgs_raw_test (18 fotos, vêm com o git)
   │  1. pré-processamento            pipelines/preprocessing_images.py
   │  2. recorte do display           pipelines/crop_detector.py   (detector de display)
   │  3. leitura do display (OCR)     pipelines/read_meter.py      (reconhecedor)
   │  4. publicação                   scripts/supabase_carregar.py
   ▼
Supabase (banco + fotos)  ──►  painel web (frontend/)  ──►  login e validação
```

### O que precisa

- [Python](https://www.python.org/downloads/) 3.12 ou superior (testado com 3.12.10). No Windows, marque
  "Add python.exe to PATH" na instalação.
- [Node.js](https://nodejs.org) 22.12 ou superior (testado com 24.19; o Vite exige 20.19+ ou 22.12+).
- git.
- GPU não é necessária: o processamento roda na CPU de propósito (veja o passo 4).
- ~4 GB livres em disco: o PyTorch de `requirements.txt` vem com CUDA, mesmo em máquina sem GPU.
- O detector de display (`best.pt`, ~173 MB), que não cabe no git: baixe no Drive (passo 2).
- As chaves do projeto Supabase (passo 3). O projeto da demonstração é o `gylsrbkagqjfuipmteca`.

O resto vem com o `git clone`: código, reconhecedor (`models/checkpoints/recognizer/best.pt`),
fotos de teste e a migração do banco.

### Passo a passo

1. **Clonar e instalar o Python** (ver [Instalação](#instalação) para detalhes). O `--depth 1` baixa
   só a versão atual, sem o histórico (que tem centenas de MB de fotos antigas). Depois que a
   branch `painel-voltlens` entrar na `main`, tire o `--branch painel-voltlens`.

   ```bash
   git clone --depth 1 --branch painel-voltlens https://github.com/FelipeSalustiano/braintech.git
   cd braintech
   python -m venv .venv
   .venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Baixar o detector de display** e colocá-lo em `models/checkpoints/display/best.pt`
   (crie a pasta `display/` se não existir):

   **Link:** _[detector de display (best.pt)](https://drive.google.com/file/d/1pfRHWKYFzT1bCrEQLl9Hc6HpCwQCNCwH/view?usp=drive_link)_

3. **Configurar as chaves do Supabase** (os dois arquivos ficam fora do git):

   ```bash
   copy .env.example .env                              # Linux/macOS: cp
   copy frontend\.env.example frontend\.env.local
   ```

   - `.env`: `SUPABASE_URL=https://gylsrbkagqjfuipmteca.supabase.co` e a chave **secreta** (`sb_secret_...`).
   - `frontend/.env.local`: a mesma URL em `VITE_SUPABASE_URL` e a chave **pública** (`sb_publishable_...`).

   As chaves estão em **Project Settings > API Keys** no painel do Supabase. Quem tem acesso ao
   projeto também pode listá-las com `npx supabase login` e
   `npx supabase projects api-keys --project-ref gylsrbkagqjfuipmteca --reveal`.
   A chave secreta dá acesso total: não a mande por chat nem a coloque no git.

4. **Processar e publicar** (etapas 1 a 4 do diagrama):

   ```bash
   python scripts/ponta_a_ponta.py
   ```

   O script confere antes se o detector, as fotos e as chaves estão no lugar e diz o que falta.
   Ele apaga as saídas de uma rodada anterior, então tudo é gerado de novo. Para só processar,
   sem publicar: `--sem-publicar`.

   O processamento roda **na CPU mesmo que a máquina tenha GPU**. Na GPU o detector usa precisão
   reduzida (float16), e nas fotos de confiança baixa isso muda a leitura de algumas fotos. Na CPU
   o resultado é o mesmo em qualquer máquina (testado em Windows e Linux). No fim, o script confere
   o resultado de referência e mostra:

   ```text
   Resultado confere com o de referência (18 fotos — lido: 2, leitura_suspeita: 4, ilegivel: 5, sem_leitura: 7).
   ```

   No painel, isso aparece como 11 displays recortados e 7 fotos sem leitura (o detector não
   achou o display).

5. **Criar a conta** de quem vai entrar no painel:

   ```bash
   python scripts/supabase_criar_usuario.py maria "uma-senha"
   ```

6. **Abrir o painel**:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

   O `npm ci` instala exatamente as versões do `package-lock.json`. Abra http://localhost:5173, entre com o usuário e a senha do passo 5 e valide as leituras.
   Para ver os dados por dentro: https://supabase.com/dashboard/project/gylsrbkagqjfuipmteca
   (Table Editor e Storage).

### Recomeçar do zero

Para ensaiar de novo, apague do Supabase as fotos, as leituras, as decisões e as contas
(as tabelas continuam lá) e volte ao passo 4:

```bash
python scripts/supabase_limpar.py --contas
```

### Projeto Supabase novo

Os passos acima usam um projeto que já tem as tabelas. Num projeto novo, antes do passo 4, crie as
tabelas e desligue o cadastro aberto, como em [Preparar o Supabase na nuvem](#preparar-o-supabase-na-nuvem-uma-vez-por-quem-tem-as-fotos).

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
├── frontend/              (painel web, ver "Painel VoltLens")
├── scripts/               (demonstração de ponta a ponta e Supabase)
├── supabase/              (migrações do banco)
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

## Leitura do display (OCR)

A leitura usa dois modelos treinados: um detector do display (Faster R-CNN, o mesmo do medidor, com a classe `Display`) e um reconhecedor que lê os dígitos no recorte.

```text
fotos pré-processadas --crop_detector.py (detector de display)--> data/display_crops/<lote>/  (recortes + manifest.csv)
                      --read_meter.py (reconhecedor)----------> data/readings/<lote>/       (readings.csv)
                      --evaluate_ocr.py-----------------------> evaluation.csv               (compara com os CSVs)
```

### Modelos treinados

- **Reconhecedor** (`models/checkpoints/recognizer/best.pt`, ~25 MB): está no git.
- **Detector de display** (`models/checkpoints/display/best.pt`, ~166 MB): não fica no git, porque passa do limite de 100 MB por arquivo do GitHub. Peça o arquivo a quem treinou e coloque-o em `models/checkpoints/display/best.pt`. Os `round_N.pt` da mesma pasta são intermediários e não precisam ser copiados.

Sem o detector de display dá para treinar o reconhecedor e rodar o `read_meter.py` em recortes já existentes, mas não dá para gerar recortes de fotos novas.

Os CSVs que o `train_recognizer.py` grava junto do checkpoint (`split.csv`, `test_predictions.csv`, `label_scores.csv`) também ficam fora do git, porque trazem leituras e códigos de instalação das planilhas do cliente. Eles são gerados de novo a cada treino.

### Treinar

1. **Detector de display**: anote a classe `display` no CVAT e exporte em COCO para `data/annotations/instances_default.json`. O treino é o mesmo semi-supervisionado do medidor, com outra seção do config. `max_image_id` diz até qual imagem a tarefa foi anotada, porque as imagens seguintes virariam negativas.

   ```bash
   python pipelines/train_semi_supervised.py --section display_detector
   ```

2. **Recortes de display** de cada lote, tirados da foto original colorida:

   ```bash
   python pipelines/crop_detector.py --checkpoint models/checkpoints/display/best.pt \
       --input data/preprocessed_images/<lote>_preprocessed --crop-source data/raw_images/<lote> \
       --output data/display_crops/<lote> --threshold 0.5 --margin 0.15 --min-size 8
   ```

3. **Reconhecedor**: usa os recortes e a coluna `Posicao do medidor lida` dos CSVs como rótulo, e divide as fotos em treino, validação e teste (80/10/10). As fotos de treino conferidas à mão (`data/review/review_train_*.csv`, ver [Conferência manual](#conferência-manual)) usam a leitura conferida no lugar da do CSV.

   ```bash
   python pipelines/train_recognizer.py
   ```

O reconhecedor (`models/recognizer.py`) é uma CNN com BiLSTM que classifica 6 posições fixas. A leitura entra completada com zeros à esquerda ("4939" vira "004939"), porque o display mostra esses zeros e o CSV não. Testamos CTC antes, e ele ficava preso emitindo só "vazio".

Uma segunda saída estima a probabilidade de o display estar ilegível. Ela só aprende com as fotos conferidas, porque o CSV não diz se a foto é legível: as marcadas como ilegíveis ensinam essa saída e ficam fora da perda dos dígitos. A saída lê as features sem devolver gradiente para elas (`detach`); com gradiente, os dígitos não saíam do platô inicial.

No config, `reviews` é o padrão dos CSVs de conferência e `review_repeat` diz quantas vezes cada foto conferida entra por época. Com 3, o acerto entre as leituras aceitas subiu em relação a 1 (ver resultados abaixo).

### Ler e avaliar

```bash
python pipelines/read_meter.py --input data/display_crops/<lote> --output data/readings/<lote>
python pipelines/evaluate_ocr.py --readings data/readings/<lote> --only-test
```

Status no `readings.csv`:

- `lido`: confiança ≥ `accept_confidence` (0,9), pode ser aceita automaticamente;
- `leitura_suspeita`: confiança baixa, vai para conferência humana;
- `ilegivel`: probabilidade de display ilegível ≥ `max_illegible_prob` (0,5), pedir nova foto;
- `sem_leitura`: o detector não achou display na foto.

O `readings.csv` traz também a coluna `illegible_prob`. Use `--only-test`: o reconhecedor foi treinado com fotos desses mesmos lotes, e avaliar nelas infla o resultado.

### Resultado atual (conjunto de teste, 960 fotos)

| Aceitar se confiança ≥ | Cobertura | Acerto contra o CSV |
|---|---|---|
| 0 (todas) | 100% | 35% |
| 0,7 | 32% | 77% |
| 0,9 | 15% | 87% |
| 0,95 | 10% | 91% |

Com o `read_meter.py` (confiança ≥ 0,9 e filtro de legibilidade), 15% das fotos do teste saem como `lido`, com 89% de acerto contra o CSV, e 43% saem como `ilegivel`. Nas `ilegivel`, a leitura do modelo bate com o CSV em só 7%.

O acerto contra o CSV subestima o modelo. Parte das fotos é ilegível (borrada, escura, reflexo), e parte do CSV está errada: o leiturista digitou outro valor ou outro registro. A acurácia real vem da conferência manual.

### Conferência manual

```bash
python utils/build_review_page.py                             # 200 fotos do teste -> data/review/review.html
python utils/build_review_page.py --subset train --size 1000  # 5 páginas de 200 do treino
python utils/score_review.py --review data/review/review.csv
```

Quem confere digita a leitura que vê, ou marca "ilegível", e exporta o CSV pelo botão da página. Os CSVs vão para `data/review/` com o nome que a página dá. Os do teste (`review.csv`) medem o modelo; os do treino (`review_train_NN.csv`) entram no treino do reconhecedor. Mantenha separadas as páginas de teste e de treino: conferir fotos do teste e treinar com elas invalidaria a medida.

As páginas embutem fotos do cliente e ficam em `data/review/`, fora do git.

Foram conferidas 200 fotos do teste e 1.000 do treino. Nas 1.000 do treino, 47% eram ilegíveis e o CSV errava 16% das legíveis. Resultado nas 200 fotos do teste, por modelo:

| | Antes (só CSV) | Com 1.000 fotos conferidas |
|---|---|---|
| Modelo correto nas fotos legíveis | 63,5% | 61,5% |
| Confiança média nas ilegíveis | 0,38 | 0,26 |
| Aceitas com confiança ≥ 0,7 | 37% das fotos, 72% de acerto | 28% das fotos, 84% de acerto |
| Aceitas com confiança ≥ 0,9 | 24,5% das fotos, 80% de acerto | 15% das fotos, 97% de acerto |
| Ilegíveis aceitas com confiança ≥ 0,9 | 2 | 0 |
| Saída de legibilidade (≥ 0,5) | não havia | marca 88% das ilegíveis e 10% das legíveis |

Nas aceitas, foto ilegível conta como erro. Com o modelo novo, `accept_confidence` 0,7 tem cobertura parecida com a do modelo antigo em 0,9 e acerto maior; 0,9 aceita menos fotos com quase nenhum erro. O maior limitador continua sendo a qualidade da foto: um backbone ResNet18 pré-treinado e uma limpeza de rótulos por validação cruzada (`clean_folds`) não melhoraram o resultado.

A linha de base com EasyOCR pré-treinado e localização heurística com OpenCV ficou em 3%. Mesmo escolhendo o texto certo, o EasyOCR só via a leitura em cerca de 10% das fotos, por causa dos dígitos de 7 segmentos e da resolução baixa.

## Painel VoltLens (front-end + Supabase)

Painel web para validar as leituras do OCR, com login, fotos num bucket do Supabase e
decisões gravadas no banco.

```text
frontend/                 app React (Vite + TypeScript) que roda no navegador
supabase/migrations/      tabelas, regras de acesso (RLS) e bucket "leituras"
scripts/supabase_carregar.py       sobe fotos, recortes e leituras para o Supabase
scripts/supabase_criar_usuario.py  cria a conta de quem vai usar o painel
src/voltlens_dados.py     lê data/readings, data/sheets e o gabarito (usado também pelo protótipo HTML)
```

No banco ficam:

| Tabela | O que guarda |
|---|---|
| `lotes` | Um lote por pasta de `data/readings/` |
| `leituras` | Uma linha por foto: sugestão do OCR, registro do PDA, gabarito e o caminho da foto no bucket |
| `decisoes` | Aceitar / corrigir / recusar de cada pessoa (cada um só vê as próprias) |
| `questionarios` | As três perguntas do fim do lote |

As fotos ficam no bucket privado `leituras` (Storage). O painel lê por URL assinada,
válida por uma hora, e só para quem está logado.

### Pré-requisitos

- [Node.js](https://nodejs.org) 22.12 ou superior (traz o `npm` e o `npx`).
- Para carregar fotos: o ambiente Python do projeto (seção [Instalação](#instalação)) e as fotos em `data/`.
- Só para rodar o Supabase na própria máquina: [Docker Desktop](https://www.docker.com/products/docker-desktop/) aberto.

A CLI do Supabase não precisa ser instalada: os comandos abaixo usam `npx supabase`.

### Usar o painel (projeto na nuvem já carregado)

É o caso de quem só vai validar fotos. Precisa da URL e da chave pública do projeto
(peça a quem administra) e de uma conta criada para você.

```bash
git clone <url-do-repositório>
cd braintech/frontend
npm ci
cp .env.example .env.local        # no Windows: copy .env.example .env.local
```

Preencha `frontend/.env.local`:

```text
VITE_SUPABASE_URL=https://<ref-do-projeto>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<chave publishable ou anon>
VITE_LOGIN_DOMAIN=voltlens.local
```

Rode e abra http://localhost:5173:

```bash
npm run dev
```

Entre com o usuário e a senha que você recebeu.

### Preparar o Supabase na nuvem (uma vez, por quem tem as fotos)

1. Crie o projeto em https://supabase.com/dashboard ("New project"; região South America (São Paulo)).
2. Na raiz do repositório, aplique o esquema do banco:

   ```bash
   npx --yes supabase login                                   # abre o navegador
   npx --yes supabase link --project-ref <ref-do-projeto>     # o ref está na URL do painel
   npx --yes supabase db push --remote                        # pede a senha do banco
   ```

   Rode um comando por vez. O `--remote` é necessário quando o Supabase local também está
   rodando na máquina: sem ele, a CLI aplica a migração no banco local.

3. Desligue o cadastro aberto: no painel, **Authentication > Sign In / Providers**, desmarque
   **Allow new users to sign up**. As contas são criadas pelo script do passo 5.
4. Copie `.env.example` para `.env` (na raiz) e preencha `SUPABASE_URL` e `SUPABASE_SECRET_KEY`
   (em **Project Settings > API Keys**). A chave secreta ignora as regras de acesso: só nos scripts, nunca no git.
5. Suba as fotos e crie as contas:

   ```bash
   python scripts/supabase_carregar.py                          # só as fotos de teste (data/imgs_raw_test)
   python scripts/supabase_criar_usuario.py maria "senha-da-maria"
   ```

   Para mandar também os lotes PSP: `--lotes PSP_EXTRATLEITIMPL_030726_0121` (um ou mais) ou
   `--lotes todos`, de preferência com `--amostra 150` (fotos por lote) para caber no plano gratuito (1 GB).
   O script pode ser rodado de novo: imagens já enviadas são puladas e as linhas são atualizadas.

### Rodar tudo na própria máquina (Supabase local, com Docker)

Bom para testar sem mexer na nuvem. Com o Docker Desktop aberto, na raiz do repositório:

```bash
npx supabase start          # na primeira vez baixa as imagens (alguns minutos) e aplica a migração
npx supabase status         # mostra a URL e as chaves locais
```

Use os valores do `status` nos dois arquivos:

- `.env` (raiz): `SUPABASE_URL` = API URL, `SUPABASE_SECRET_KEY` = Secret (ou service_role key).
- `frontend/.env.local`: `VITE_SUPABASE_URL` = API URL, `VITE_SUPABASE_PUBLISHABLE_KEY` = Publishable (ou anon key).

Depois os mesmos passos da nuvem: `python scripts/supabase_carregar.py`,
`python scripts/supabase_criar_usuario.py ...`, e `npm run dev` dentro de `frontend/`.

Para desligar: `npx supabase stop`. Para apagar o banco local e recomeçar: `npx supabase db reset`
(depois carregue as fotos de novo).

### Ver os dados no navegador

- **Local:** Supabase Studio em http://127.0.0.1:54323.
- **Nuvem:** https://supabase.com/dashboard, no projeto.

No **Table Editor** estão `lotes`, `leituras`, `decisoes` e `questionarios`; em **Storage**, o bucket
`leituras` com `<lote>/fotos/` e `<lote>/recortes/`; em **Authentication > Users**, as contas.
Para tirar as decisões de todos em CSV: Table Editor > `decisoes` > Export.

### Diferenças em relação ao protótipo HTML

- Login de verdade: só entra quem tem conta (as fotos são do cliente). A tela continua pedindo
  "Usuário" e "Senha"; por trás, `maria` vira o e-mail `maria@voltlens.local`.
- As decisões e o questionário ficam no banco: a mesma pessoa vê o progresso em qualquer computador.
- O resto (filas, filtros, ações em massa, atalhos `A`/`C`/`R`/setas/`F`, resumo e CSV) é o mesmo.

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
- `models/recognizer.py`: reconhecedor da leitura (CNN + BiLSTM, 6 dígitos).
- `src/meter_reading.py`: status da leitura pela confiança.
- `pipelines/train_recognizer.py`: treino do reconhecedor com as leituras dos CSVs.
- `pipelines/read_meter.py`: leitura dos recortes de display.
- `pipelines/evaluate_ocr.py`: acurácia das leituras contra os CSVs dos leituristas.
- `utils/build_review_page.py` e `utils/score_review.py`: conferência manual de uma amostra.
- `utils/image_convert.py`: conversão de imagens para matrizes e tensores.
- `configs/detector.json`: configuração de treinamento e inferência.

## Limitações atuais

- O reconhecedor acerta 36% contra o CSV no teste (84% nas leituras com confiança ≥ 0,9, que são 28% das fotos); a acurácia real em fotos legíveis ainda precisa da conferência manual.
- A implementação escolhe a célula de maior confiança na predição.
- Não há cálculo de IoU, mAP, precision ou recall no pipeline.
- A qualidade final depende diretamente da qualidade das bounding boxes COCO.
- O script de treino usa atualmente um arquivo de anotação e uma pasta de imagens padrão.
