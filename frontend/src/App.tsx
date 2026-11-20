import type { Session } from '@supabase/supabase-js'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import marca from './assets/voltlens_mark.png'
import { apagarDecisoesDoLote, carregarDecisoes, carregarItens, carregarLotes, salvarDecisoes } from './lib/dados'
import { configErro, supabase } from './lib/supabase'
import type { Acao, Decisao, Item, LoteResumo } from './lib/tipos'
import { temLeitura } from './lib/tipos'
import { acertou } from './lib/util'
import { Detalhe } from './screens/Detalhe'
import { Fila, type FilaEstado } from './screens/Fila'
import { Login } from './screens/Login'
import { Lotes } from './screens/Lotes'
import { ModalCorrigir, ModalRecusar } from './screens/Modais'
import { Resumo } from './screens/Resumo'

function Moldura({ topo, children }: { topo?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="frame">
      {topo}
      <div className="content">{children}</div>
      <div className="foot">
        <span>Protótipo · sugestões vindas do pipeline atual (detector + OCR) · decisões salvas no Supabase</span>
        <span>Atalhos: <kbd>A</kbd> aceitar · <kbd>C</kbd> corrigir · <kbd>R</kbd> recusar · <kbd>←</kbd><kbd>→</kbd> navegar · <kbd>F</kbd> facilitador</span>
      </div>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [pronto, setPronto] = useState(false)
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setPronto(true) })
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  if (configErro) return <Moldura><div className="erro">{configErro}</div></Moldura>
  if (!pronto) return <Moldura><div className="carregando">Carregando…</div></Moldura>
  if (!session) return <Moldura><Login /></Moldura>
  return <Painel key={session.user.id} session={session} />
}

type Tela = 'lotes' | 'fila' | 'detalhe' | 'resumo'
type Modal = { tipo: 'corrigir'; it: Item } | { tipo: 'recusar'; its: Item[]; massa: boolean } | null

const FILA_INICIAL: FilaEstado = { filtro: null, diverge: false, busca: '', ordem: 'arquivo', pag: 0, sel: new Set() }

function Painel({ session }: { session: Session }) {
  const userId = session.user.id
  const participante = (session.user.user_metadata?.usuario as string | undefined) ?? (session.user.email ?? '').split('@')[0]

  const [tela, setTela] = useState<Tela>('lotes')
  const [lotes, setLotes] = useState<LoteResumo[] | null>(null)
  const [decisoes, setDecisoes] = useState<Map<number, Decisao>>(new Map())
  const [lote, setLote] = useState<LoteResumo | null>(null)
  const [itens, setItens] = useState<Item[] | null>(null)
  const [f, setFila] = useState<FilaEstado>(FILA_INICIAL)
  const [idx, setIdx] = useState(0)
  const [fac, setFac] = useState(false)
  const [modal, setModal] = useState<Modal>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const abertoEm = useRef(0)                       // quando a foto atual foi aberta
  const filaAbertaEm = useRef<number | null>(null) // para o tempo médio das decisões em massa

  const setF = useCallback((patch: Partial<FilaEstado>) => setFila(prev => ({ ...prev, ...patch })), [])

  useEffect(() => {
    Promise.all([carregarLotes(), carregarDecisoes()])
      .then(([ls, ds]) => { setLotes(ls); setDecisoes(new Map(ds.map(d => [d.leitura_id, d]))) })
      .catch(e => setErro('Não consegui carregar os dados: ' + e.message))
  }, [])

  const feitosPorLote = useMemo(() => {
    const m = new Map<string, number>()
    for (const d of decisoes.values()) m.set(d.lote_id, (m.get(d.lote_id) ?? 0) + 1)
    return m
  }, [decisoes])

  const vis = useMemo(() => {
    let v = itens ?? []
    if (f.filtro === 'pendente') v = v.filter(it => !decisoes.has(it.id))
    else if (f.filtro) v = v.filter(it => it.status === f.filtro)
    if (f.diverge) v = v.filter(it => it.cmp_pda === 'diverge')
    if (f.busca) {
      const q = f.busca.toLowerCase()
      v = v.filter(it => (it.medidor ?? '').toLowerCase().includes(q) || it.foto.toLowerCase().includes(q) || (it.leitura ?? '').includes(q))
    }
    if (f.ordem === 'conf') v = [...v].sort((a, b) => (a.confianca ?? -1) - (b.confianca ?? -1))
    if (f.ordem === 'confd') v = [...v].sort((a, b) => (b.confianca ?? -1) - (a.confianca ?? -1))
    return v
  }, [itens, decisoes, f.filtro, f.diverge, f.busca, f.ordem])

  // ---------- navegação
  const irFila = (msg?: string) => {
    if (filaAbertaEm.current == null) filaAbertaEm.current = performance.now()
    setToast(msg ?? null); setTela('fila')
  }
  const abrirLote = async (L: LoteResumo) => {
    setLote(L); setItens(null); setFila(FILA_INICIAL); setErro(null); irFila()
    try { setItens(await carregarItens(L.id)) } catch (e) { setErro('Não consegui carregar o lote: ' + (e as Error).message) }
  }
  const abrirDetalhe = (i: number) => {
    if (i < 0 || i >= vis.length) { irFila(); return }
    setIdx(i); abertoEm.current = performance.now(); filaAbertaEm.current = null; setTela('detalhe')
  }
  const voltarLotes = () => {
    setTela('lotes')
    carregarLotes().then(setLotes).catch(() => {})
  }

  // ---------- gravação
  async function gravar(its: Item[], acao: Acao, statusFinal: (it: Item) => string, leituraFinal: (it: Item) => string,
    obs: string, tempo: number, modo: Decisao['modo']) {
    const novas: Decisao[] = its.map(it => {
      const s = statusFinal(it), l = leituraFinal(it)
      return {
        user_id: userId, participante, leitura_id: it.id, lote_id: it.lote_id, acao, modo,
        status_final: s, leitura_final: l, obs, tempo_s: +tempo.toFixed(1), acertou: acertou(it, acao, s, l),
      }
    })
    const antes = decisoes
    setDecisoes(prev => { const m = new Map(prev); novas.forEach(d => m.set(d.leitura_id, d)); return m })
    try {
      const salvas = await salvarDecisoes(novas)
      setDecisoes(prev => { const m = new Map(prev); salvas.forEach(d => m.set(d.leitura_id, d)); return m })
      setErro(null)
      return true
    } catch (e) {
      setDecisoes(antes)
      setErro('Não consegui salvar a decisão: ' + (e as Error).message)
      return false
    }
  }

  /** Decisão na tela de detalhe: grava e segue para a próxima foto do filtro. */
  async function registrar(it: Item, acao: Acao, statusFinal: string, leituraFinal: string, obs = '') {
    const proxima = idx + 1
    const ok = await gravar([it], acao, () => statusFinal, () => leituraFinal, obs, (performance.now() - abertoEm.current) / 1000, 'individual')
    if (!ok) return
    // Com o filtro "Pendentes", a foto decidida sai da lista e a próxima ocupa o mesmo índice.
    const seguinte = f.filtro === 'pendente' ? idx : proxima
    const restantes = f.filtro === 'pendente' ? vis.length - 1 : vis.length
    if (seguinte < restantes) { setIdx(seguinte); abertoEm.current = performance.now() } else irFila()
  }
  const aceitar = (it: Item) => registrar(it, 'aceitou', it.status, temLeitura(it.status) ? it.leitura || '—' : '—')

  async function aceitarMassa(its: Item[]) {
    const t = (performance.now() - (filaAbertaEm.current ?? performance.now())) / 1000 / its.length
    if (await gravar(its, 'aceitou', it => it.status, it => (temLeitura(it.status) ? it.leitura || '—' : '—'), '', t, 'em massa')) {
      setF({ sel: new Set() }); filaAbertaEm.current = performance.now()
      setToast(`${its.length} ${its.length === 1 ? 'foto aceita' : 'fotos aceitas'}.`)
    }
  }
  async function recusar(its: Item[], massa: boolean, obs: string) {
    setModal(null)
    if (!massa) { registrar(its[0], 'recusou', 'recusada', '—', obs); return }
    const t = (performance.now() - (filaAbertaEm.current ?? performance.now())) / 1000 / its.length
    if (await gravar(its, 'recusou', () => 'recusada', () => '—', obs, t, 'em massa')) {
      setF({ sel: new Set() }); filaAbertaEm.current = performance.now()
      setToast(`${its.length} ${its.length === 1 ? 'foto recusada' : 'fotos recusadas'}.`)
    }
  }
  async function apagarLote() {
    if (!lote) return
    try {
      await apagarDecisoesDoLote(lote.id)
      setDecisoes(prev => new Map([...prev].filter(([, d]) => d.lote_id !== lote.id)))
    } catch (e) { setErro('Não consegui apagar: ' + (e as Error).message) }
  }

  // ---------- atalhos (mesmos do protótipo)
  const atual = tela === 'detalhe' ? vis[idx] : undefined
  const teclas = useRef<(e: KeyboardEvent) => void>(() => {})
  useEffect(() => { teclas.current = (e: KeyboardEvent) => {
    const alvo = e.target as HTMLElement
    if (alvo.matches('input,textarea,select')) return
    if (e.key === 'Escape') { setModal(null); return }
    if (modal) return
    const k = e.key.toLowerCase()
    if (k === 'f') { setFac(v => !v); return }
    if (!atual) return
    if (k === 'a') aceitar(atual)
    else if (k === 'c') { e.preventDefault(); setModal({ tipo: 'corrigir', it: atual }) }
    else if (k === 'r') { e.preventDefault(); setModal({ tipo: 'recusar', its: [atual], massa: false }) }
    else if (e.key === 'ArrowRight') abrirDetalhe(idx + 1)
    else if (e.key === 'ArrowLeft' && idx > 0) abrirDetalhe(idx - 1)
  } })
  useEffect(() => {
    const h = (e: KeyboardEvent) => teclas.current(e)
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [])

  const topo = (
    <div className="bar">
      <img className="barlogo" src={marca} alt="" />
      <div className="logo">VoltLens<small>· validação de leituras</small></div>
      <div className="sp" />
      {lote && tela !== 'lotes' && <span className="tag">{lote.nome}</span>}
      <span className="tag">{participante}</span>
      <button className="btn sm" onClick={() => supabase.auth.signOut()}>Sair</button>
    </div>
  )

  let corpo: React.ReactNode
  if (!lotes) corpo = <div className="carregando">Carregando lotes…</div>
  else if (tela === 'lotes' || !lote) corpo = <Lotes participante={participante} lotes={lotes} feitosPorLote={feitosPorLote} onAbrir={abrirLote} />
  else if (!itens) corpo = <div className="carregando">Carregando {lote.nome}…</div>
  else if (tela === 'fila') corpo = (
    <Fila lote={lote} itens={itens} vis={vis} decisoes={decisoes} f={f} setF={setF} toast={toast}
      onAbrir={abrirDetalhe} onLotes={voltarLotes} onFim={() => setTela('resumo')}
      onAceitarMassa={aceitarMassa} onRecusarMassa={its => setModal({ tipo: 'recusar', its, massa: true })} />
  )
  else if (tela === 'detalhe' && atual) corpo = (
    <Detalhe it={atual} proximo={vis[idx + 1] ?? null} idx={idx} total={vis.length} decisao={decisoes.get(atual.id)} fac={fac}
      onFila={() => irFila()} onAnterior={() => abrirDetalhe(idx - 1)}
      onProxima={() => (idx === vis.length - 1 ? irFila() : abrirDetalhe(idx + 1))}
      onAceitar={() => aceitar(atual)} onCorrigir={() => setModal({ tipo: 'corrigir', it: atual })}
      onRecusar={() => setModal({ tipo: 'recusar', its: [atual], massa: false })} />
  )
  else if (tela === 'resumo') corpo = (
    <Resumo lote={lote} itens={itens} decisoes={[...decisoes.values()].filter(d => d.lote_id === lote.id)}
      userId={userId} participante={participante} fac={fac}
      onLotes={voltarLotes} onFila={() => irFila()} onApagar={apagarLote} />
  )
  else corpo = <div className="carregando">Nada para mostrar neste filtro.</div>

  return (
    <Moldura topo={topo}>
      {erro && <div className="erro">{erro}</div>}
      {corpo}
      {modal?.tipo === 'corrigir' && (
        <ModalCorrigir it={modal.it} onFechar={() => setModal(null)}
          onSalvar={(s, l, obs) => { setModal(null); registrar(modal.it, 'corrigiu', s, l, obs) }} />
      )}
      {modal?.tipo === 'recusar' && (
        <ModalRecusar quantos={modal.its.length} onFechar={() => setModal(null)} onRecusar={obs => recusar(modal.its, modal.massa, obs)} />
      )}
    </Moldura>
  )
}
