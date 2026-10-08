# Lab 02 — VoltLens

> **Rascunho.** Seções com `[PREENCHER]` dependem da rotulagem e da execução do notebook.

## 0. Leitura do docente × evidência do grupo

A leitura do enunciado (entendimento concluído, nenhuma arquitetura, meta "50% das legíveis" não mensurável) procede. [PREENCHER: discordâncias com evidência, se houver.]

## Como reproduzir

1. Fotos fora do repositório; ajustar `FOTOS_DIR` e `LOTES` no topo de `lab02.ipynb`.
2. `python ferramentas/amostrar.py --fotos <pasta> --rotuladores a,b,c,d,e` → planilhas `rotulos/rotulos_<nome>.csv` (cada pessoa rotula **só a sua**, sem consultar os CSVs de leitura).
3. `python ferramentas/kappa.py` → gera `rotulos/rotulos.csv` e o kappa.
4. Gerar `rotulos/ids.csv` (`nome_arquivo, id_leitura, numero_medidor`) a partir dos CSVs do cliente.
5. `Reiniciar e executar tudo` em `lab02.ipynb`.

## Parte comum

### A. Ficha — ver [ARQUITETURA.md](ARQUITETURA.md)

### B. Modelo
| Configuração | Parâmetros totais | Treináveis |
|---|--:|--:|
| Extração (extrator congelado) | [MEDIR] | [MEDIR] (≈ 1.731) |
| Ajuste fino | [MEDIR] | [MEDIR] |

### C. Rótulos
| Lote | legível | ilegível | não-medidor | total |
|---|--:|--:|--:|--:|
| [PREENCHER] | | | | ≥ 300 |

Kappa de Cohen (50 duplas, às cegas):
| Classe | Kappa | Ação |
|---|--:|---|
| legível | [MEDIR] | |
| ilegível | [MEDIR] | |
| não-medidor | [MEDIR] | |

Se algum kappa < 0,6: o que mudou no esquema (v2): [PREENCHER].

Partição: treino 20/05+21/05, validação 22/05, teste 03/07. Interseções (leitura / medidor): [COLAR do notebook, C4].

### D. Sanidade e baseline
| Verificação | Resultado |
|---|---|
| D1 perda inicial × ln 3 = 1,099 | [COLAR] |
| D2 sobreajuste de 16 fotos | [COLAR] |
| D3 F1-macro validação (3 sementes) | profundo [m ± s] × baseline [m ± s] |

Leitura: [PREENCHER — se o profundo perder, por quê].

### E. Confiança e recusa
ECE antes/depois de T: [COLAR]. Cobertura × risco no ponto da meta: [COLAR]. Se a meta não cabe na curva, dizer aqui.

## Parte específica — VoltLens

### V1. Três status → arquitetura
Ver ficha, seção 2. Escolha: **estágios** (não existe rótulo final; erro por estágio; UFPR-AMR reaproveitável). Ponta a ponta descartada: sem alvo de treino e sem endereço de erro.

| Status | Sub-tarefas aprendidas | Regra |
|---|---|---|
| Leitura confirmada | legibilidade, display, dígitos | extraída == digitada ∧ confiança ≥ τ |
| Divergência | legibilidade, display, dígitos | extraída ≠ digitada ∧ confiança ≥ τ |
| Impedimento-inconclusivo | legibilidade (ilegível / não-medidor) | ilegível ∨ confiança < τ |

### V2. Meta em número
"Assertividade em ≥ 50% das legíveis" → **cobertura ≥ 50% das legíveis com precisão ≥ X% em Leitura confirmada**. Proposta X = 98%: uma leitura confirmada errada vira fatura errada (reclamação, retrabalho, risco regulatório), enquanto mandar uma foto boa ao analista custa uma conferência. [Defender com custo estimado; confirmar X com o grupo.]

### V3. Pareamento foto ↔ registro
Regra: [PREENCHER — chave candidata: nome do arquivo sem sufixo `_00N` ↔ id da leitura no CSV; desempate por data/lote]. Fotos órfãs: [MEDIR]. Rótulos só são feitos em fotos pareadas.

### V4. Os 347 zeros
Fotos de leituras com valor 0 passadas pelo classificador: [MEDIR]. Foto que mostra ~6.990 registrada como 0 é divergência; o pipeline chegaria nela se o leitor de dígitos (Marco 2) rodar sobre fotos `legível` e a regra comparar ≠ 0. Hoje o bloco treinado só filtra legibilidade: [PREENCHER].

## Limitações conhecidas
- Preencher honestamente o que não foi medido.
