# Ficha de arquitetura — VoltLens

> **Rascunho.** Itens marcados `[MEDIR]` dependem de rótulos e do notebook executado; itens `[EST]` são estimativas com a origem declarada. Substituir antes da entrega.

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
| É medidor / legível (este lab) | [MEDIR] acurácia no teste | `lab02.ipynb`, D3 |
| Achou o display | 0,85 [EST] | valor de exemplo do guia; sem medição própria |
| Leu certo (leitura exata) | 0,36 [EST] | Luminus, UFPR-AMR, leitura exata 0,357 (pior caso, modelo pronto) |
| Regra de comparação | 1,00 | determinística |
| **Produto** | `taxa_legível × 0,85 × 0,36` = [CALCULAR] | — |

Leitura: o estágio que mais perde é o de leitura; por isso a meta de negócio (seção 9) é cobertura sobre **legíveis**, não sobre todas as fotos.

## 4. Contrato de entrada

| Modelo | Tamanho | Proporção | Normalização | Canais |
|---|---|---|---|---|
| Classificador legível/ilegível/não-medidor | 480×360 nativo (K1 não se aplica; ver nota) | mantida 3:4, sem distorção | ImageNet `[0,485; 0,456; 0,406]` / `[0,229; 0,224; 0,225]` | RGB (reflexo tem cor) |

Nota: "legível" depende de dígitos pequenos (~12 px nativos); reduzir para 224 px derrubaria para ~7 px. Mantém-se o nativo; reduzir só se a medição de D3 mostrar queda desprezível. Várias fotos por leitura (`_001`…`_008`, 4,2%): **cada foto é uma amostra**, mas o particionamento por lote mantém as irmãs juntas.

## 5. Espinha dorsal

| Escolhida | Descartada | Motivo |
|---|---|---|
| MobileNetV3-Small, pré-treinada ImageNet (≈ 0,93 M parâmetros sem cabeça) | ResNet-18 (11,7 M) | 12× mais parâmetros; implantação em CPU; com ~300 rótulos extração de características basta |
| | EfficientNet-B0 (5,3 M) | mais lenta em CPU que a MobileNet; ganho de acurácia não justificado sem rótulos |

## 6. Cabeças

| Cabeça | Nº saídas | Ativação | Perda | Classes exclusivas? Por quê |
|---|--:|---|---|---|
| Legibilidade | 3 | softmax (aplicada só na inferência) | `CrossEntropyLoss` com logits | **Sim.** Uma foto é uma coisa só: não pode ser legível e ilegível. Exemplo real: [preencher com arquivo de `rotulos.csv`] |

## 7. Desbalanceamento

Distribuição na amostra rotulada: [MEDIR]. Técnica: `CrossEntropyLoss(weight ∝ 1/freq)`; probabilidades descalibradas são corrigidas por temperature scaling (seção 9).

## 8. Capacidade × rótulos

~300 rótulos (100 por classe se balanceado) → **extração de características** (extrator congelado). Parâmetros: total ≈ 0,93 M [MEDIR], treináveis ≈ 1.731 (576×3+3) [MEDIR]. Ajuste fino dos últimos blocos só se a baseline linear sobre features congeladas perder.

## 9. Confiança e recusa

- Regra: se `max softmax(z/T) ≥ τ` → decide (legível / ilegível / não-medidor), senão → inconclusivo.
- `T` e `τ` ajustados **na validação** (lote 22/05), nunca no teste.
- Meta do kickoff: "assertividade em ≥ 50% das fotos legíveis" → **cobertura ≥ 50% das legíveis com precisão ≥ X% em Leitura confirmada**. X [DECLARAR]: proposta 98%, pois cada leitura confirmada errada gera fatura errada; ver V2 no README.

## 10. Aumento de dados

| Transformação | Modelo | Muda o rótulo? |
|---|---|---|
| Rotação ±10° | classificador | Não |
| Brilho/contraste moderados | classificador | Não |
| Espelhamento horizontal | — (proibido) | Sim para leitura (dígito espelhado); não usado |
| Desfoque gaussiano / reflexo sintético | — (proibido neste lab) | **Sim**: legível → ilegível |
| Recorte aleatório agressivo | — (proibido) | Pode cortar o display |

## 11. Partição

Por lote, nunca por foto: treino 20/05 + 21/05, validação 22/05, teste 03/07. Prova numérica (ids de leitura e números de medidor em interseção vazia): `lab02.ipynb`, C4. Rótulos estratificados pelos 4 lotes (≥ 300 fotos).

## 12. Sanidade

Saídas coladas do notebook: formas, perda inicial vs ln 3 = 1,099, sobreajuste de 10–20 fotos reais, baseline (regressão logística sobre features congeladas / histograma+Laplaciano). [COLAR]

## 13. Implantação

Volume adotado [EST]: 3.100 fotos/extração (os lotes recebidos); hipótese alternativa 50–70 mil/mês ≈ 2.300–3.200/dia. Latência p50/p95 do classificador em CPU [MEDIR]. Roda em lote em CPU; exportação ONNX com paridade < 1e-4 (a fazer no Marco 2). Licenças: PyTorch/torchvision BSD; MobileNetV3 pesos torchvision (BSD); sem YOLO/AGPL.

## 14. O que decidimos não fazer

- **Rede ponta a ponta (foto → status):** sem rótulo final.
- **Rede para comparar valores:** regra determinística.
- **Rótulo fraco por degradação sintética:** troca o rótulo e exige prova com amostra real; fora do escopo.
- **YOLO Ultralytics:** AGPL-3.0; alternativa permissiva (SSDlite/Faster R-CNN do torchvision) quando o detector entrar.
- **Ajuste fino completo agora:** ~300 rótulos não sustentam 0,93 M parâmetros livres.
