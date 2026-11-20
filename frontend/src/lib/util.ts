import type { Acao, Decisao, Item } from './tipos'
import { nomeStatus } from './tipos'

export const fmt = (n: number) => n.toLocaleString('pt-BR')
export const pct = (v: number | null | undefined) => (v == null ? '—' : Math.round(v * 100) + '%')

const digits = (v: string | null | undefined) => (v == null ? '' : String(v).replace(/\D/g, ''))
export function sameNum(a: string | null | undefined, b: string | null | undefined) {
  const x = digits(a), y = digits(b)
  return x !== '' && y !== '' && Number(x) === Number(y)
}

/** A decisão bate com o gabarito conferido à mão? null quando a foto não tem gabarito. */
export function acertou(it: Item, acao: Acao, statusFinal: string, leituraFinal: string): boolean | null {
  if (it.gabarito == null) return null
  if (acao === 'recusou') return !sameNum(it.leitura, it.gabarito)
  if (statusFinal === 'ilegivel' || statusFinal === 'sem_leitura') return false
  return sameNum(leituraFinal, it.gabarito)
}

export function mediana(a: number[]) {
  if (!a.length) return 0
  const s = [...a].sort((x, y) => x - y), m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** CSV com as mesmas colunas do protótipo em HTML, mais o questionário no fim. */
export function csvDecisoes(ds: Decisao[], itens: Map<number, Item>, questionario: (number | null)[]) {
  const linhas = ds.map(d => {
    const it = itens.get(d.leitura_id)
    return {
      participante: d.participante, lote: d.lote_id, foto: it?.foto ?? '', medidor: it?.medidor ?? '',
      leitura_pda: it?.leitura_pda ?? '', nota: it?.nota ?? '', sug_status: it?.status ?? '', sug_leitura: it?.leitura ?? '',
      confianca: it?.confianca ?? '', prob_ilegivel: it?.prob_ilegivel ?? '', acao: d.acao, modo: d.modo,
      status_final: d.status_final, leitura_final: d.leitura_final, gabarito: it?.gabarito ?? '',
      acertou: d.acertou ?? '', tempo_s: d.tempo_s, obs: d.obs, quando: d.criado_em ?? '',
    }
  })
  const h = Object.keys(linhas[0] ?? { participante: '' })
  const cel = (v: unknown) => String(v ?? '').replace(/[;\n]/g, ',')
  return [h.join(';'), ...linhas.map(l => h.map(k => cel((l as Record<string, unknown>)[k])).join(';')),
    '# questionario;' + questionario.map(v => v ?? '').join(';')].join('\n')
}

export const rotuloStatusFinal = (s: string) => (s === 'recusada' ? 'Recusada' : nomeStatus(s))
