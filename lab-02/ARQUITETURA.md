# Ficha de arquitetura — VoltLens

> Itens `[EST]` são estimativas com a origem declarada; os demais números vêm de `lab02.ipynb` (executado do zero) e de `ferramentas/v3_v4.py`.

## 1. Decisão apoiada

| Pergunta | Resposta |
|---|---|
| Decisão | Para cada foto de leitura: **Leitura confirmada / Divergência / Impedimento-inconclusivo** |
| Unidade de análise | Uma foto pareada a um registro de leitura (não o medidor, não o cliente) |
| Quem age | Analista: confere divergências e inconclusivos e uma amostra das confirmadas |
| Erro mais caro | **Confirmar uma leitura errada** (fatura incorreta) > mandar foto boa para revisão (custo de uma conferência) |
| Onde roda | Lote pós-coleta, CPU, sem GPU presumida |

## 2. Sub-tarefas

| Sub-tarefa | Aprendida ou regra? | Tipo | Saída | Ativação | Perda | Rótulo |
|---|---|---|---|---|---|---|
| Legível / ilegível / não é medidor | **Aprendida** (bloco do Lab 2) | Classificação exclusiva | 3 classes | softmax | entropia cruzada | 1 classe por foto (`rotulos/`) |
| Localizar o display | Aprendida (Marco 2+) | Detecção | caixa | por caixa | box + classe | caixas desenhadas |
| Ler dígitos do recorte | Aprendida (Marco 2+) | Sequência | cadeia de dígitos | softmax por passo | CTC | transcrição do recorte |
| Número do medidor na placa | Aprendida (Marco 2+) | Sequência | cadeia | softmax por passo | CTC | transcrição |
| Valor lido == valor digitado | **Regra** | Comparação | igual / diferente | — | — | — |
| Leitura zero + foto mostra ≠ 0 | **Regra** sobre a saída da leitura | Comparação | divergência | — | — | — |
| Mapear para os 3 status | **Regra** | Tabela de decisão | status | — | — | — |

Os três status **não** são classes de uma rede: não existe rótulo final de analista. São o resultado de regras sobre sub-tarefas aprendidas:

- **Leitura confirmada** = legível ∧ leitura extraída ∧ extraída == digitada ∧ confiança ≥ limiar.
- **Divergência** = legível ∧ leitura extraída com confiança ≥ limiar ∧ extraída ≠ digitada.
- **Impedimento-inconclusivo** = ilegível ∨ não é medidor ∨ confiança < limiar.

## 3. Pipeline

Duas versões consideradas (V1 do enunciado):

```
Estágios:   foto → [legível?] → [display] → [dígitos] → regra(==) → status
Ponta a ponta: (foto, valor digitado) → rede → status
```

**Escolha: estágios.** Critério da seção 3 do guia: não existe rótulo final (nenhuma decisão de analista registrada) → ponta a ponta não tem alvo de treino; estágios permitem rotular por etapa, depurar por coluna de erro e reaproveitar o UFPR-AMR na leitura.

Taxas por estágio (origem declarada):

| Estágio | Taxa | Origem |
|---|--:|---|
| É medidor / legível (este lab) | 0,827 acurácia no teste (75 fotos de 03/07) | `lab02.ipynb`, seção F |
| Achou o display | 0,85 [EST] | valor de exemplo do guia; sem medição própria |
| Leu certo (leitura exata) | 0,36 [EST] | Luminus, UFPR-AMR, leitura exata 0,357 (pior caso, modelo pronto) |
| Regra de comparação | 1,00 | determinística |
| **Produto** | 0,827 × 0,85 × 0,36 = **0,253** | cálculo; os dois últimos fatores são estimativas, não medidas nossas |

Leitura: o produto estimado é ≈ 25%: só uma em cada quatro fotos atravessaria os três estágios certa. O estágio que mais perde é o de leitura; por isso a meta de negócio (seção 9) é cobertura sobre **legíveis**, não sobre todas as fotos.

## 4. Contrato de entrada

| Modelo | Tamanho | Proporção | Normalização | Canais |
|---|---|---|---|---|
| Classificador legível/ilegível/não-medidor | 480×360 nativo (ver nota) | mantida 3:4, sem distorção | ImageNet `[0,485; 0,456; 0,406]` / `[0,229; 0,224; 0,225]` | RGB (reflexo tem cor) |

Nota: "legível" depende de dígitos pequenos; reduzir de 480×360 para 224 px encolheria os dígitos em cerca de metade (estimativa, não medida). Mantém-se o nativo (480×360). **Não testamos 224 px neste laboratório**; a latência medida com o nativo (seção 13) é pequena, então não há pressão por reduzir. Várias fotos por leitura (`_001`…`_008`, 4,2%): **cada foto é uma amostra**, mas o particionamento por lote mantém as irmãs juntas.

## 5. Espinha dorsal

| Escolhida | Descartada | Motivo |
|---|---|---|
| MobileNetV3-Small, pré-treinada ImageNet (≈ 0,93 M parâmetros sem cabeça) | ResNet-18 (11,7 M) | 12× mais parâmetros; implantação em CPU; com ~300 rótulos extração de características basta |
| | EfficientNet-B0 (5,3 M) | mais pesada que a MobileNet (5,3 M × 0,93 M parâmetros); não comparamos as duas em CPU neste laboratório |

## 6. Cabeças

| Cabeça | Nº saídas | Ativação | Perda | Classes exclusivas? Por quê |
|---|--:|---|---|---|
| Legibilidade | 3 | softmax (aplicada só na inferência) | `CrossEntropyLoss` com logits | **Sim.** Uma foto é uma coisa só: não pode ser legível e ilegível. Exemplo real: `PSP_EXTRATLEITIMPL_030726_0121_20000000002303017005_000.jpg` tem uma única classe, `legivel` (consenso; nenhum rotulador a viu como duas ao mesmo tempo). |

## 7. Desbalanceamento

Distribuição nas 300 fotos rotuladas: legível 144 (48%), ilegível 140 (47%), não-medidor 16 (5%). A classe rara é `nao_medidor` (8 / 3 / 5 fotos em treino / validação / teste): suas métricas são instáveis. Técnica: `CrossEntropyLoss(weight ∝ 1/freq)`; probabilidades descalibradas são corrigidas por temperature scaling (seção 9).

## 8. Capacidade × rótulos

~300 rótulos (100 por classe se balanceado) → **extração de características** (extrator congelado). Parâmetros: total 928.739, treináveis 1.731 (576×3+3) na extração; 928.739 treináveis no ajuste fino (medido no notebook, B2). Ajuste fino dos últimos blocos só se a baseline linear sobre features congeladas perder.

## 9. Confiança e recusa

- Regra proposta: se `max softmax(z/T) ≥ τ` → decide (legível / ilegível / não-medidor), senão → inconclusivo. Neste laboratório T = 0,91 foi ajustado; τ foi explorado na curva cobertura × risco e a escolha final fica para o Marco 2.
- `T` e `τ` ajustados **na validação** (lote 22/05), nunca no teste.
- Meta do kickoff: "assertividade em ≥ 50% das fotos legíveis" → **cobertura ≥ 50% das legíveis com precisão ≥ X% em Leitura confirmada**. X = **50%**, decisão do grupo ainda sem validação com o cliente; funciona como piso, já que cada leitura confirmada errada gera fatura errada. **Medido:** com o classificador deste laboratório, a 50% de cobertura das legíveis a precisão da decisão "legível" é 0,82 (validação) e 0,84 (teste), acima de 50%. Isso mede só a legibilidade; a precisão em Leitura confirmada depende do leitor de dígitos e da regra de comparação (Marco 2). Ver V2 no README.

## 10. Aumento de dados

| Transformação | Modelo | Muda o rótulo? |
|---|---|---|
| Rotação ±10° | classificador | Não — **planejado para o ajuste fino; não usado neste laboratório** (as *features* do extrator congelado são calculadas uma vez) |
| Brilho/contraste moderados | classificador | Não — idem |
| Espelhamento horizontal | — (proibido) | Sim para leitura (dígito espelhado); não usado |
| Desfoque gaussiano / reflexo sintético | — (proibido neste lab) | **Sim**: legível → ilegível |
| Recorte aleatório agressivo | — (proibido) | Pode cortar o display |

## 11. Partição

Por lote, nunca por foto: treino 20/05 + 21/05, validação 22/05, teste 03/07. Prova numérica (ids de leitura e números de medidor em interseção vazia): `lab02.ipynb`, C4. Rótulos estratificados pelos 4 lotes (≥ 300 fotos).

## 12. Sanidade

Saídas do notebook (`lab02.ipynb`):

| Verificação | Resultado |
|---|---|
| Formas | entrada (1, 3, 480, 360) → extrator (1, 576, 15, 12) → pool (1, 576, 1, 1) → cabeça (1, 3) |
| Perda inicial × ln 3 = 1,099 | 1,121 |
| Sobreajuste de 16 fotos reais | perda 1,157 → 0,0001 em 80 passos |
| F1-macro validação, 3 sementes | profundo (extração) 0,717 ± 0,001 × baseline LR (histograma + Laplaciano) 0,427 |
| Teste (03/07, 75 fotos) | acurácia 0,827 · F1-macro 0,813 |
| ECE validação / teste | 0,086 → 0,070 / 0,108 → 0,111 (T = 0,91) |

Matriz de confusão no teste (linhas = verdade; legível, ilegível, não-medidor): [37 3 0], [8 21 1], [1 0 4]. O erro dominante é ilegível previsto como legível (8 de 30), o mais caro para o negócio.

Nota: a primeira versão da cabeça (200 épocas, lote cheio) deu desvio 0 entre sementes e F1 0,536; a versão final usa minibatches embaralhados (30 épocas, lr 1e-3), ajustada olhando a validação. O teste não foi usado para ajustar nada.

## 13. Implantação

Volume adotado [EST]: ≈ 3.100 fotos por extração (os lotes recebidos; 12.340 fotos nos 4 lotes); hipótese alternativa 50–70 mil/mês ≈ 2.300–3.200/dia, ainda não confirmada com o cliente. **Latência medida** do classificador em CPU (1 foto 480×360, 2 threads): p50 = 14,8 ms, p95 = 19,7 ms; ≈ 0,8 min para 3.100 fotos. Só este estágio; a cascata inteira (display + dígitos) não foi medida. Roda em lote em CPU; exportação ONNX com paridade < 1e-4 (a fazer no Marco 2). Licenças: PyTorch/torchvision BSD; MobileNetV3 pesos torchvision (BSD); sem YOLO/AGPL.

## 14. O que decidimos não fazer

- **Rede ponta a ponta (foto → status):** sem rótulo final.
- **Rede para comparar valores:** regra determinística.
- **Rótulo fraco por degradação sintética:** troca o rótulo e exige prova com amostra real; fora do escopo.
- **YOLO Ultralytics:** AGPL-3.0; alternativa permissiva (SSDlite/Faster R-CNN do torchvision) quando o detector entrar.
- **Ajuste fino completo agora:** ~300 rótulos não sustentam 0,93 M parâmetros livres.
