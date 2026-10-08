# Esquema de rótulos — VoltLens

Tarefa: classificar cada foto em **uma** classe (exclusivas → softmax + entropia cruzada).
Unidade de análise: a foto (nome do arquivo). Versão 1 do esquema — ver "Histórico" no fim.

| Classe | Definição operacional |
|---|---|
| `legivel` | Há um medidor de energia na foto **e** um observador humano consegue transcrever o valor do mostrador (todos os dígitos) sem adivinhar. Basta o display estar inteiro e nítido; a leitura não precisa estar correta em relação ao sistema. |
| `ilegivel` | Há um medidor na foto, mas o valor **não** pode ser transcrito com certeza: borrão, reflexo sobre o display, display cortado/apagado, tampa suja, dígito encoberto. Se ao menos um dígito exige chute, é `ilegivel`. |
| `nao_medidor` | Nenhum medidor identificável: fachada, portão fechado, rua, cão, dedo na lente, foto escura/preta, tela de celular, etc. Medidor visível apenas como mancha minúscula ao fundo também é `nao_medidor`. |

## Regras de desempate

1. Dúvida entre `legivel` e `ilegivel` → `ilegivel` (custo assimétrico: confirmar leitura errada é pior que mandar à revisão).
2. Dúvida entre `ilegivel` e `nao_medidor` → pergunta: "dá para ver que é um medidor?" Sim → `ilegivel`.
3. Várias fotos da mesma leitura (`_000`, `_001`…) são rotuladas **individualmente**.
4. Rotule pelo que se vê na foto, **sem consultar** o valor registrado nos CSVs (evita viés).

## Exemplos-limite (a preencher com as fotos reais — referenciar por nome de arquivo, nunca anexar a foto)

| Classe | Quase é (mas não é) | Quase não é (mas é) |
|---|---|---|
| `legivel` | _TODO: arquivo — display nítido mas último dígito cortado pela borda → `ilegivel`_ | _TODO: arquivo — display inclinado/com leve reflexo nas bordas, dígitos íntegros → `legivel`_ |
| `ilegivel` | _TODO: arquivo — leve desfoque mas todos os dígitos distinguíveis → `legivel`_ | _TODO: arquivo — medidor longe, display visível mas dígitos ~5 px → `ilegivel`_ |
| `nao_medidor` | _TODO: arquivo — quadro de medidores com tampa fechada → depende da regra 2_ | _TODO: arquivo — medidor muito ao fundo, sem display visível → `nao_medidor`_ |

## Rotulagem dupla às cegas (50 fotos)

Duas planilhas separadas (`rotulos_<rotulador>.csv`), sem conversa até ambos terminarem.
Kappa por classe (um-contra-todos) calculado por `ferramentas/kappa.py`. Kappa < 0,6 → reescrever a definição e registrar abaixo.

## Histórico

- v1: esquema inicial.
