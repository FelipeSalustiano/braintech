# Uso de IA generativa neste laboratório

Ferramenta usada por Lucas Rafael: Claude Code (Sonnet 5.5). 

| Integrante | Ferramenta | O que pediu | O que aceitou | O que descartou e por quê |
|---|---|---|---|---|
| Lucas Rafael | Claude Code | Montar a estrutura de `lab-02/`: rascunho da ficha, esquema de rótulos, scripts de amostragem e de kappa, esqueleto do notebook | A estrutura, os scripts e o código do notebook | Substituí o texto genérico dos rascunhos pelos dados reais do grupo. |
| Lucas Rafael | Claude Code | Consolidar os rótulos (acordo + consenso) em `rotulos.csv`, listar as 75 divergências e calcular o kappa nas 300 fotos e em 50 sorteadas | O script `kappa.py` e a amostra de 50 (semente 42) | Trocar o consenso por maioria de 3 rotuladores: não aplicado, o consenso foi mantido |
| Lucas Rafael | Claude Code | Escrever o esquema de rótulos v2 e o histórico de mudanças | A regra do teste do dígito, a ordem de decisão e o histórico | Os exemplos-limite entraram como sugestão; o grupo abriu cada foto e confirmou que a frase batia |
| Lucas Rafael | Claude Code | Rodar o notebook do zero, gerar o `ids.csv` e corrigir o que quebrasse | O ajuste dos caminhos e dos lotes, o `gerar_ids.py` e a troca do treino da cabeça para minibatches (as 3 sementes davam resultado idêntico) | Não aceitei as três sementes com resultado idêntico, porque não mostravam variação; pedi a troca para minibatches. |
| Helder Barros | Claude Code | Medir o desempenho no teste, a meta do V2 e a latência em CPU, e calcular o V3 (fotos órfãs) e o V4 (leituras com valor zero) | Os scripts e as células novas do notebook, e os números | O X = 98% sugerido pelo Claude: troquei por X = 50%, decisão do grupo. |
| Lucas Rafael | Claude Code | Preencher `ARQUITETURA.md` com os números medidos | O preenchimento | Frases sem medição por trás (por exemplo, sobre risco regulatório) foram retiradas depois da revisão. |
| Felipe Salustiano | Claude Code | Redigir o `README.md` com as tabelas de C, D, E e V1–V4 a partir das saídas do notebook e de `ferramentas/v3_v4.py` | A estrutura e o texto. Conferi os números de D, E e do V4 (perda inicial, F1, ECE, T, zeros) contra a saída do notebook reexecutado do zero; kappa e V3 (órfãs) vêm de `kappa.py` e `v3_v4.py` | Nada além de ajustes de redação |
| Lucas Rafael | Claude Code | Limpar o notebook antes da entrega: remover o esqueleto e o `TODO` do V4, trocar a instrução do template em D3 pela leitura do resultado e reexecutar tudo | A célula do V4 que lê `saidas/zeros_predicoes.csv`, o texto da leitura de D3 e a reexecução, que reproduziu os mesmos números | Nada |
| Lucas Mendes | — | Rotulou as 300 fotos de forma independente, com o esquema v1 | — | Não usou IA generativa na rotulagem |
| Kevin | — | Rotulou as 300 fotos às cegas, com o esquema v2 | — | Não usou IA generativa na rotulagem |

## Declaração

Cada integrante é capaz de explicar qualquer parte do código entregue.



