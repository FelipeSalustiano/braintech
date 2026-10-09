# Lab 02 — VoltLens

## 0. Leitura do docente × evidência do grupo

A leitura do enunciado (entendimento concluído, nenhuma arquitetura, meta "50% das legíveis" não mensurável) procede em geral. Duas correções com evidência: (1) o kickoff falava em 150–200 fotos sem registro por pasta; medimos **197 a 242** por lote (866 no total, 7,0% das 12.340 fotos), um pouco acima; (2) os 347 zeros se confirmam, mas só 227 têm foto. Sobre "nenhuma arquitetura": a ficha (`ARQUITETURA.md`) agora fecha a escolha por estágios e o primeiro bloco está treinado.

## Como reproduzir

1. Fotos fora do repositório; ajustar `FOTOS_DIR` e `LOTES` no topo de `lab02.ipynb`.
2. `python ferramentas/amostrar.py --fotos <pasta> --rotuladores a,b,c,d,e` → planilhas `rotulos/rotulos_<nome>.csv` (cada pessoa rotula **só a sua**, sem consultar os CSVs de leitura).
3. `python ferramentas/kappa.py` → gera `rotulos/rotulos.csv`, `rotulos/discordancias.csv` e os kappas (v1 e Kevin).
4. `python ferramentas/gerar_ids.py --zip "<Base de Dados Neoenergia PE.zip>"` → `rotulos/ids.csv` (`nome_arquivo, id_leitura, numero_medidor`), a partir dos CSVs do cliente. Não é versionado (tem números de medidor); fotos sem registro recebem um medidor fictício único `SEM_REGISTRO_<id>`.
5. `Reiniciar e executar tudo` em `lab02.ipynb`.
6. (V3/V4) `python ferramentas/v3_v4.py --zip "<zip>" --fotos <FOTOS_DIR>` → órfãs e teste dos zeros.

## Parte comum

### A. Ficha — ver [ARQUITETURA.md](ARQUITETURA.md)

### B. Modelo
MobileNetV3-Small pré-treinada (ImageNet) + cabeça linear de 3 classes, entrada 480×360 (tabela de formas no notebook).

| Configuração | Parâmetros totais | Treináveis |
|---|--:|--:|
| Extração (extrator congelado) | 928.739 | 1.731 |
| Ajuste fino | 928.739 | 928.739 |

As 3 classes são exclusivas (uma foto é uma coisa só): softmax + `CrossEntropyLoss` sobre logits.

### C. Rótulos
300 fotos, 75 por lote (estratificado pelos 4 lotes). Rótulo final = rótulo comum quando os dois rotuladores concordaram (225) ou consenso do grupo nas 75 divergências.

| Lote | legível | ilegível | não-medidor | total |
|---|--:|--:|--:|--:|
| 20/05 | 37 | 35 | 3 | 75 |
| 21/05 | 32 | 38 | 5 | 75 |
| 22/05 | 35 | 37 | 3 | 75 |
| 03/07 | 40 | 30 | 5 | 75 |
| **Total** | 144 | 140 | 16 | 300 |

**Quem rotulou:** o enunciado sugere dividir as 300 fotos entre os integrantes. Aqui as 300 foram rotuladas integralmente por três pessoas, de forma independente (Lucas Rafael e Lucas Mendes com o esquema v1; Kevin, às cegas, com o v2). Escolhemos isso em vez de dividir porque a rotulagem completa em duplicata permite medir o kappa nas 300 (e nos 50 pedidos) e resolver as 75 divergências por consenso, e a terceira rotulagem permitiu medir a v2. O custo é que cada integrante rotulou 300 fotos, não 45–60.

**Kappa de Cohen (um-contra-todos), esquema v1, Lucas Rafael × Lucas Mendes, rotulagem independente:**

| Classe | κ (300 duplos) | κ (50 duplos, semente 42) | Ação |
|---|--:|--:|---|
| legível | 0,575 | 0,540 | < 0,6: esquema reescrito (v2) |
| ilegível | 0,514 | 0,419 | < 0,6: esquema reescrito (v2) |
| não-medidor | 0,737 | 0,545 | 300: ok; 50: amostra pequena (poucos exemplos) |

**O que mudou na v2** (detalhe em `rotulos/esquema.md`): "chute" definido pelo teste do dígito; dúvida só conta se o rotulador aponta o dígito; ordem de decisão fixa; display inclinado ou com reflexo nas bordas segue `legivel`.
Diagnóstico: 67 das 75 divergências foram legível × ilegível, todas na mesma direção (um rotulador mais rigoroso).

**Medição da v2** (Kevin, às cegas, esquema v2, 300 fotos):

| Par | κ legível | κ ilegível | κ não-medidor |
|---|--:|--:|--:|
| Kevin × Lucas Rafael | 0,831 | 0,826 | 1,000 |
| Kevin × Lucas Mendes | 0,552 | 0,500 | 0,737 |

O acordo com Rafael subiu para > 0,8. Com Mendes continuou ≈ 0,5: em 55 fotos Kevin marcou legível e Mendes ilegível. O desacordo restante é de limiar de rigor de um rotulador. Limitação: Rafael e Mendes usaram a v1 e Kevin a v2, logo a comparação é indicativa. O `rotulos.csv` não foi refeito com a v2.

**Partição por lote:** treino 20/05 + 21/05 (150), validação 22/05 (75), teste 03/07 (75). Interseções (C4, medido no notebook):

| Par | leituras em comum | medidores em comum |
|---|--:|--:|
| treino × validação | 0 | 0 |
| treino × teste | 0 | 0 |
| validação × teste | 0 | 0 |

Observação: 14 das 300 fotos não têm registro nos CSVs do cliente (órfãs); receberam um número de medidor fictício único para a verificação. Não-medidor tem só 8 / 3 / 5 exemplos em treino / validação / teste: as métricas dessa classe são instáveis.

### D. Sanidade e baseline
| Verificação | Resultado |
|---|---|
| D1 perda inicial × ln 3 = 1,099 | 1,121 |
| D2 sobreajuste de 16 fotos | perda 1,157 → 0,0001 em 80 passos |
| D3 F1-macro validação (3 sementes) | profundo (extração) 0,717 ± 0,001 × baseline LR (histograma + Laplaciano) 0,427 (determinística, desvio 0) |

Leitura: o bloco profundo supera a baseline não profunda por ≈ 0,29 de F1-macro, então a escolha por transferência se justifica. O desvio entre sementes é pequeno porque o extrator é congelado e só a cabeça linear varia (inicialização e ordem dos minibatches). Na primeira versão da cabeça (200 épocas, lote cheio, lr 1e-2) as sementes davam resultado idêntico (desvio 0) e F1 0,536; passamos a minibatches (30 épocas, lr 1e-3) olhando a validação. O teste não foi usado para ajustar nada.

### E. Confiança e recusa
| | antes de T | depois de T (T = 0,91, ajustado na validação) |
|---|--:|--:|
| ECE validação | 0,086 | 0,070 |
| ECE teste | 0,108 | 0,111 |

A *temperature scaling* melhora a validação, onde T foi ajustado, mas não o teste (0,108 → 0,111): o ganho não generaliza com 75 fotos por conjunto. A meta do kickoff (cobertura ≥ 50% com risco ≤ 50%, ou seja, X = 50%) **cabe na curva**: com 50% de cobertura o risco é 0,211 na validação e 0,132 no teste, abaixo do limite de 0,50. Nota: o risco é o erro multiclasse nas fotos decididas, não a precisão apenas em "Leitura confirmada" (isso depende do leitor de dígitos, Marco 2).

## Parte específica — VoltLens

### V1. Três status → arquitetura
Ver ficha, seção 2. Escolha: **estágios** (não existe rótulo final; erro por estágio; UFPR-AMR reaproveitável). Ponta a ponta descartada: sem alvo de treino e sem endereço de erro.

| Status | Sub-tarefas aprendidas | Regra |
|---|---|---|
| Leitura confirmada | legibilidade, display, dígitos | extraída == digitada ∧ confiança ≥ τ |
| Divergência | legibilidade, display, dígitos | extraída ≠ digitada ∧ confiança ≥ τ |
| Impedimento-inconclusivo | legibilidade (ilegível / não-medidor) | ilegível ∨ confiança < τ |

### V2. Meta em número
"Assertividade em ≥ 50% das legíveis" → **cobertura ≥ 50% das legíveis com precisão ≥ X% em *Leitura confirmada***.

**Declaramos X = 50%:** em *Leitura confirmada*, aceitamos que no máximo metade das leituras confirmadas esteja errada. O número é uma decisão do grupo, não vem de um dado do cliente, e deve ser confirmado com a Neoenergia. Atenção: uma leitura confirmada errada vira fatura errada (reclamação e retrabalho), enquanto mandar uma foto boa ao analista custa só uma conferência. Por isso 50% deve ser lido como piso mínimo de partida, e não como objetivo de qualidade; um X mais alto (por exemplo 98%, proposta inicial) exigiria o leitor de dígitos.

**Medido (proxy):** o status *Leitura confirmada* depende também do leitor de dígitos (Marco 2), que ainda não existe. Neste laboratório só medimos o estágio de legibilidade: cobertura das fotos legíveis × precisão da decisão "legível" (limiar escolhido na validação, aplicado ao teste).

| Cobertura alvo | Validação: cobertura / precisão | Teste: cobertura / precisão |
|---|--:|--:|
| 30% | 0,31 / 0,92 | 0,55 / 0,85 |
| 50% | 0,51 / 0,82 | 0,65 / 0,84 |
| 70% | 0,71 / 0,76 | 0,72 / 0,83 |

**Conclusão: com X = 50%, o estágio de legibilidade já cumpre a meta.** A 50% de cobertura a precisão é 0,82 (validação) e 0,84 (teste), acima de 0,50. Isso mede só a legibilidade; a precisão em *Leitura confirmada* depende do leitor de dígitos e da regra extraído == digitado (Marco 2), e não foi medida. O teste tem só 40 fotos legíveis, então as precisões acima têm margem larga.

### V3. Pareamento foto ↔ registro
**Regra:** uma foto pertence a um registro se, e somente se, o **nome do arquivo é igual (casamento exato)** ao valor da coluna `Foto do medidor` do CSV do mesmo lote. Foto sem linha correspondente é **órfã** e não recebe rótulo. A chave de leitura é o nome sem o sufixo `_00N`; várias fotos da mesma leitura (`_000`, `_001`…) são amostras separadas.
Cálculo: `ferramentas/v3_v4.py`, sobre os 4 lotes completos (zip do cliente).

| Medida | Valor |
|---|--:|
| Fotos (jpg) nos 4 lotes | 12.340 |
| Registros nos CSVs | 13.669 |
| Registros **com** foto | 11.474 |
| Registros **sem** foto | 2.195 |
| Registros cuja foto não existe no zip | 0 |
| Nomes de foto duplicados nos CSVs | 0 |
| **Fotos órfãs (jpg sem registro)** | **866 (7,0%)** |

| Lote | Órfãs |
|---|--:|
| 20/05 | 208 |
| 21/05 | 219 |
| 22/05 | 242 |
| 03/07 | 197 |

Sobre as órfãs: 515 têm sufixo `_000` e 351 têm `_001` ou mais; **nenhuma** tem o id de leitura presente no CSV. Ou seja, não são fotos extras de uma leitura já pareada: são leituras inteiras sem linha no arquivo. Não tentamos pareá-las por outra chave (data, posição), porque o CSV não traz esse dado; rótulo em foto mal pareada é rótulo errado. Nas 300 fotos rotuladas, 14 (4,7%) são órfãs; elas continuam rotuladas por aparência (a classe `legivel`/`ilegivel`/`nao_medidor` não depende do registro), mas ficam fora de qualquer análise que compare com o valor digitado.

### V4. Os 347 zeros como teste difícil
Há **347** leituras com valor 0; **227** têm foto e **225** não fazem parte das 300 rotuladas (2 fazem, e foram excluídas para não contaminar a avaliação). Passamos as 225 pelo classificador do Lab 2 (cabeça treinada em 20/05 + 21/05, `T` ajustado na validação) e comparamos com um **controle** de 225 leituras de valor ≠ 0 sorteadas (semente 0).

| Classe prevista | Zeros (n = 225) | Controle (n = 225) |
|---|--:|--:|
| legível | 123 (54,7%) | 100 (44,4%) |
| ilegível | 94 (41,8%) | 110 (48,9%) |
| não-medidor | 8 (3,6%) | 15 (6,7%) |
| legível com confiança ≥ 0,7 | 98 | 75 |

Leitura:
- **Os zeros não são, em geral, fotos ruins.** Mais da metade é classificada como legível, até um pouco mais que o controle. Um valor registrado 0 com foto legível é candidato a **divergência**: o zero provavelmente não veio da foto.
- **O classificador sozinho não decide divergência.** Ele só filtra legibilidade (F1-macro de validação 0,717); quem lê os dígitos é o bloco do Marco 2. O que este teste dá é o tamanho do conjunto a investigar: ≈ 98–123 fotos de zero legíveis, das quais saem os casos do tipo "a foto mostra ~6.990 e foi registrada como 0".
- **Não verificamos os dígitos dessas fotos** nem se elas realmente divergem; isso exigiria o leitor de dígitos ou conferência humana. O pipeline "chegaria lá" apenas quando o leitor rodar sobre as fotos `legível` e a regra comparar `extraído ≠ digitado`.
- Por lote, a proporção de zeros legíveis é parecida (25 a 34 por lote), sem concentração em um lote.
- Limitação: o classificador erra (F1-macro de validação 0,72), e o que ele prevê é a classe da foto, não o valor lido.

## Limitações conhecidas
- Só 300 fotos rotuladas: validação e teste têm 75 fotos cada, e o teste tem 40 legíveis, 30 ilegíveis e 5 não-medidores. Uma foto a mais ou a menos muda bastante as métricas.
- O `rotulos.csv` foi feito com o esquema v1 (mais consenso). A v2 foi medida só por um rotulador (Kevin) e não refez os rótulos.
- Lucas Mendes continua mais rigoroso na fronteira legível × ilegível (κ ≈ 0,5 contra o Kevin).
- Medimos só o estágio de legibilidade. Display, dígitos, ONNX e a latência da cascata ficam para o Marco 2; a taxa de 0,85 do display e a de 0,36 da leitura são estimativas de outras fontes.
- A cabeça foi ajustada olhando a validação (épocas e taxa de aprendizado); o teste não entrou em nenhuma escolha.
- 14 das 300 fotos rotuladas não têm registro no CSV; para elas não dá para comparar com o valor digitado.
- Não verificamos se os zeros com foto legível divergem de fato.
