// Status do OCR, como em src/meter_reading.py.
export const ST = {
  lido: { nome: 'Lido', hint: 'Confiança alta: a leitura pode seguir sem conferência.' },
  leitura_suspeita: { nome: 'Leitura suspeita', hint: 'Confiança baixa: a leitura vai para conferência humana.' },
  ilegivel: { nome: 'Ilegível', hint: 'Display borrado, escuro ou com reflexo: pedir nova foto.' },
  sem_leitura: { nome: 'Sem leitura', hint: 'O detector não achou o display na foto.' },
} as const
export type Status = keyof typeof ST
export const ST_KEYS = Object.keys(ST) as Status[]
export const nomeStatus = (s: string) => (s in ST ? ST[s as Status].nome : s)
/** Ilegível e sem leitura não têm valor no display. */
export const temLeitura = (s: string) => s === 'lido' || s === 'leitura_suspeita'

export type Cmp = 'bate' | 'diverge' | 'na'
export const CMP_TXT: Record<Cmp, string> = { bate: '= PDA', diverge: '≠ PDA', na: '—' }

export type Acao = 'aceitou' | 'corrigiu' | 'recusou'
export const ACAO_TXT: Record<Acao, string> = { aceitou: '✓ Aceita', corrigiu: '✎ Corrigida', recusou: '✗ Recusada' }

export interface LoteResumo {
  id: string
  nome: string
  ordem: number
  total: number
  lido: number
  leitura_suspeita: number
  ilegivel: number
  sem_leitura: number
  diverge: number
}

/** Uma linha de public.leituras. */
export interface Item {
  id: number
  lote_id: string
  ordem: number
  foto: string
  foto_path: string | null
  recorte_path: string | null
  status: Status
  leitura: string | null
  confianca: number | null
  prob_ilegivel: number | null
  score_deteccao: number | null
  medidor: string | null
  leitura_pda: string | null
  nota: string | null
  cmp_pda: Cmp
  gabarito: string | null
}

/** Uma linha de public.decisoes. */
export interface Decisao {
  id?: number
  user_id: string
  participante: string
  leitura_id: number
  lote_id: string
  acao: Acao
  modo: 'individual' | 'em massa'
  status_final: string
  leitura_final: string
  obs: string
  tempo_s: number
  acertou: boolean | null
  criado_em?: string
}

export type Filtro = Status | 'pendente' | null
export type Ordem = 'arquivo' | 'conf' | 'confd'
