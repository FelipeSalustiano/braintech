# Esquema de rótulos — VoltLens (versão 2)

Tarefa: classificar cada foto em **uma** classe (exclusivas → softmax + entropia cruzada).
Unidade de análise: a foto (nome do arquivo).

| Classe | Definição operacional |
|---|---|
| `legivel` | Há um medidor de energia na foto **e** todos os dígitos do mostrador podem ser transcritos **a partir do que se vê**, sem inferir pelo contexto (dígito vizinho, valor esperado, leituras anteriores). Display inclinado, com sombra ou leve reflexo nas bordas continua `legivel` se cada dígito é distinguível. O valor transcrito não precisa bater com o registro do sistema. |
| `ilegivel` | Há um medidor na foto, mas **ao menos um dígito** não pode ser transcrito só pelo que se vê: borrão, reflexo sobre o display, dígito cortado pela borda, apagado ou encoberto, dígitos pequenos demais para separar 3/8, 1/7, 0/6. |
| `nao_medidor` | Não dá para ver que há um medidor: fachada, portão, rua, animal, dedo na lente, foto preta, tela de celular. Medidor só como mancha ao fundo, sem mostrador identificável, também é `nao_medidor`. |

## Regras de decisão (v2), aplicar nesta ordem

1. **Há um medidor identificável?** Não → `nao_medidor`. Sim → regra 2.
2. **Teste do dígito:** percorra o mostrador da esquerda para a direita. Algum dígito exige chute, ou só se resolve por contexto → `ilegivel`. Todos distinguíveis → `legivel`.
3. **Dúvida na regra 2** → `ilegivel` (custo assimétrico: confirmar leitura errada é pior que mandar à revisão). Dúvida só vale se você consegue apontar *qual dígito* e *por quê*; "parece meio ruim" sem dígito apontado não basta para `ilegivel`.
4. **Dúvida entre `ilegivel` e `nao_medidor`:** "dá para ver que é um medidor?" Sim → `ilegivel`.
5. Várias fotos da mesma leitura (`_000`, `_001`…) são rotuladas **individualmente**.
6. Rotule pelo que se vê, **sem consultar** o valor registrado nos CSVs nem sugestões de outro rotulador ou ferramenta.

## Exemplos-limite

Referenciados por nome de arquivo (nunca anexar a foto). São fotos em que os dois rotuladores
divergiram na v1 e o grupo decidiu por consenso; o rótulo abaixo é o do consenso.

| Classe | Quase é (mas não é): rótulo do consenso | Quase não é (mas é): rótulo do consenso |
|---|---|---|
| `legivel` | `PSP_EXTRATLEITIMPL_030726_0121_20000000000852982572_000.jpg` → `ilegivel` (um rotulador viu `legivel`) · o que se vê: _Display aparentemente nítido, mas ao menos um dígito está cortado ou duvidoso (pode ser 3 ou 8) e só se resolveria por contexto → `ilegivel`._ | `PSP_EXTRATLEITIMPL_030726_0121_20000000002303017005_000.jpg` → `legivel` (um rotulador viu `ilegivel`) · o que se vê: _Display com leve embaçamento, mas todos os dígitos continuam separáveis, sem dúvida entre pares parecidos (3/8, 1/7) → `legivel`._ |
| `ilegivel` | `PSP_EXTRATLEITIMPL_030726_0121_20000000011452973951_000.jpg` → `legivel` (um rotulador viu `ilegivel`) · o que se vê: _Reflexo leve numa lateral do vidro, longe dos dígitos; o mostrador inteiro pode ser transcrito sem chute → `legivel`._ | `PSP_EXTRATLEITIMPL_030726_0121_20000000001803004862_000.jpg` → `ilegivel` (um rotulador viu `legivel`) · o que se vê: _Aparentemente nítido, mas um dígito pode ser 3 ou 8 por causa do reflexo ou da resolução, e só se decide por contexto → `ilegivel`._ |
| `nao_medidor` | `PSP_EXTRATLEITIMPL_200526_0352_20000000004253001242_000.jpg` → `ilegivel` (um rotulador viu `nao_medidor`) · o que se vê: _Foto escura ou muito de longe, mas o contorno do medidor e a região do mostrador ainda são identificáveis, embora os dígitos não sejam transcrevíveis → `ilegivel`._ | `PSP_EXTRATLEITIMPL_030726_0121_20000000003002994797_000.jpg` → `nao_medidor` (um rotulador viu `ilegivel`) · o que se vê: _Há uma caixa ou quadro de medidores, mas nenhum mostrador identificável (tampa fechada ou medidor só como mancha ao fundo) → `nao_medidor`._ |

## Rotulagem dupla às cegas

Duas planilhas separadas (`rotulos_1.csv`, `rotulos_2.csv`), sem conversa até ambos terminarem.
Kappa por classe (um-contra-todos) calculado por `ferramentas/kappa.py` sobre os rótulos
**independentes**, antes do consenso. As discordâncias foram resolvidas em consenso
(`rotulos_finais.csv`) e o resultado está em `rotulos.csv`.

## Histórico

- **v1:** esquema inicial. Kappa nos 300 duplos: legível 0,575 · ilegível 0,514 · não-medidor 0,737 ·
  multiclasse 0,562 (concordância 75%). Nos 50 duplos amostrados: 0,540 / 0,419 / 0,545.
  Legível e ilegível ficaram abaixo de 0,6, logo a definição estava ambígua.
- **Diagnóstico:** das 75 discordâncias, 67 foram legível × ilegível e **todas** na mesma direção
  (um rotulador marcou `ilegivel` onde o outro marcou `legivel`; nunca o inverso). Isso indica
  limiares de rigor diferentes, não ruído. As outras 8 foram `nao_medidor` × `ilegivel`.
  A v1 dizia "se ao menos um dígito exige chute, é `ilegivel`" sem dizer o que conta como chute
  nem como tratar dúvida vaga.
- **v2 (mudanças):**
  1. "Chute" passou a ser definido pelo **teste do dígito**: inferir pelo contexto conta como chute.
  2. A dúvida só leva a `ilegivel` se o rotulador consegue apontar o dígito e o motivo, para
     evitar rotular `ilegivel` por impressão geral.
  3. Display inclinado, sombra ou reflexo apenas nas bordas, com dígitos distinguíveis, ficou
     explícito como `legivel`.
  4. Ordem de decisão fixa (medidor identificável → teste do dígito).
  5. Proibido consultar sugestões de outro rotulador ou ferramenta (regra 6).
- **Medição da v2 (terceiro rotulador, Kevin):** Kevin rotulou as mesmas 300 fotos com o esquema v2
  (planilha `rotulos_3.csv`), **às cegas**: sem consultar as planilhas dos outros nem o consenso. Kappa de Cohen contra cada rotulador da v1:

  | Par | n | Concordância | κ legível | κ ilegível | κ não-medidor | κ multiclasse |
  |---|--:|--:|--:|--:|--:|--:|
  | Kevin × Lucas Rafael | 300 | 0,92 | 0,831 | 0,826 | 1,000 | 0,841 |
  | Kevin × Lucas Rafael | 50 | 0,92 | 0,841 | 0,839 | 1,000 | 0,851 |
  | Kevin × Lucas Mendes | 300 | 0,75 | 0,552 | 0,500 | 0,737 | 0,545 |
  | Kevin × Lucas Mendes | 50 | 0,70 | 0,513 | 0,404 | 0,545 | 0,468 |
  | (v1) Lucas Rafael × Lucas Mendes | 300 | 0,75 | 0,575 | 0,514 | 0,737 | 0,562 |

  Leitura: o par com Lucas Rafael passou de κ ≈ 0,5 para > 0,8 em todas as classes. O par com
  Lucas Mendes continuou em ≈ 0,5: na tabela de contingência, 55 fotos que Kevin marcou `legivel` e
  Lucas Mendes marcou `ilegivel` (o inverso ocorreu 13 vezes). O desacordo restante vem do
  limiar de rigor de um rotulador, não da definição das classes; a v2 sozinha não o corrigiu.
  Ressalva: Rafael e Mendes rotularam com a v1 e Kevin com a v2, então o contraste é indicativo,
  não uma comparação controlada (o ideal seria os três rotularem sob a v2).
- **Limitação:** nenhum dos três rotuladores refez a rotulagem após o consenso; os rótulos em `rotulos.csv` foram feitos com a v1 e as discordâncias resolvidas por consenso.
