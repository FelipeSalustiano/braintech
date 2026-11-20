import { BUCKET, supabase } from './supabase'
import type { Decisao, Item, LoteResumo } from './tipos'

const PAGINA_API = 1000 // o PostgREST devolve no máximo 1000 linhas por chamada

async function todasAsPaginas<T>(consulta: (de: number, ate: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>) {
  const linhas: T[] = []
  for (let de = 0; ; de += PAGINA_API) {
    const { data, error } = await consulta(de, de + PAGINA_API - 1)
    if (error) throw new Error(error.message)
    linhas.push(...(data ?? []))
    if (!data || data.length < PAGINA_API) return linhas
  }
}

export async function carregarLotes(): Promise<LoteResumo[]> {
  const { data, error } = await supabase.from('lotes_resumo').select('*').order('ordem')
  if (error) throw new Error(error.message)
  return data as LoteResumo[]
}

export function carregarItens(loteId: string): Promise<Item[]> {
  return todasAsPaginas<Item>((de, ate) =>
    supabase.from('leituras').select('*').eq('lote_id', loteId).order('ordem').range(de, ate),
  )
}

export function carregarDecisoes(): Promise<Decisao[]> {
  // A RLS já limita às decisões de quem está logado.
  return todasAsPaginas<Decisao>((de, ate) => supabase.from('decisoes').select('*').order('id').range(de, ate))
}

export async function salvarDecisoes(ds: Decisao[]): Promise<Decisao[]> {
  const out: Decisao[] = []
  for (let i = 0; i < ds.length; i += 500) {
    const { data, error } = await supabase
      .from('decisoes')
      .upsert(ds.slice(i, i + 500), { onConflict: 'user_id,leitura_id' })
      .select()
    if (error) throw new Error(error.message)
    out.push(...(data as Decisao[]))
  }
  return out
}

export async function apagarDecisoesDoLote(loteId: string) {
  const { error } = await supabase.from('decisoes').delete().eq('lote_id', loteId)
  if (error) throw new Error(error.message)
}

export async function carregarQuestionario(loteId: string): Promise<(number | null)[]> {
  const { data, error } = await supabase.from('questionarios').select('q1,q2,q3').eq('lote_id', loteId).maybeSingle()
  if (error) throw new Error(error.message)
  return data ? [data.q1, data.q2, data.q3] : [null, null, null]
}

export async function salvarQuestionario(userId: string, participante: string, loteId: string, q: (number | null)[]) {
  const { error } = await supabase
    .from('questionarios')
    .upsert(
      { user_id: userId, participante, lote_id: loteId, q1: q[0], q2: q[1], q3: q[2], atualizado_em: new Date().toISOString() },
      { onConflict: 'user_id,lote_id' },
    )
  if (error) throw new Error(error.message)
}

// ---------- imagens: URLs assinadas do bucket privado, com cache
const VALIDADE_S = 3600
const cache = new Map<string, { url: string; expira: number }>()

/** Devolve as URLs assinadas dos caminhos pedidos (os que já estão no cache não vão à rede). */
export async function urlsAssinadas(paths: (string | null)[]): Promise<Map<string, string>> {
  const agora = Date.now()
  const faltam = [...new Set(paths.filter((p): p is string => !!p))].filter(p => {
    const c = cache.get(p)
    return !c || c.expira < agora + 60_000
  })
  if (faltam.length) {
    const { data, error } = await supabase.storage.from(BUCKET).createSignedUrls(faltam, VALIDADE_S)
    if (error) throw new Error(error.message)
    for (const d of data ?? []) {
      if (d.path && d.signedUrl) cache.set(d.path, { url: d.signedUrl, expira: agora + VALIDADE_S * 1000 })
    }
  }
  const out = new Map<string, string>()
  for (const p of paths) if (p && cache.has(p)) out.set(p, cache.get(p)!.url)
  return out
}
