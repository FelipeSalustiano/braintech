import { useEffect, useState } from 'react'
import { carregarQuestionario, salvarQuestionario } from '../lib/dados'
import type { Decisao, Item, LoteResumo } from '../lib/tipos'
import { nomeStatus } from '../lib/tipos'
import { csvDecisoes, fmt, mediana, rotuloStatusFinal } from '../lib/util'

const PERGUNTAS = [
  'A sugestão me ajudou a decidir mais rápido.',
  'Eu confiei nas sugestões com confiança alta.',
  'Eu usaria este painel no meu dia a dia.',
]

export function Resumo({ lote, itens, decisoes, userId, participante, fac, onLotes, onFila, onApagar }: {
  lote: LoteResumo
  itens: Item[]
  decisoes: Decisao[]
  userId: string
  participante: string
  fac: boolean
  onLotes: () => void
  onFila: () => void
  onApagar: () => void
}) {
  const [q, setQ] = useState<(number | null)[]>([null, null, null])
  const [msg, setMsg] = useState('')
  useEffect(() => { carregarQuestionario(lote.id).then(setQ).catch(() => {}) }, [lote.id])

  const responder = (k: number, v: number) => {
    const novo = q.map((x, i) => (i === k ? v : x))
    setQ(novo)
    salvarQuestionario(userId, participante, lote.id, novo).catch(e => setMsg('Não salvou o questionário: ' + e.message))
  }

  const R = decisoes
  const n = (a: string) => R.filter(r => r.acao === a).length
  const G = R.filter(r => r.acertou != null), gOk = G.filter(r => r.acertou).length
  const porId = new Map(itens.map(it => [it.id, it]))
  const recentes = [...R].sort((a, b) => (b.criado_em ?? '').localeCompare(a.criado_em ?? '')).slice(0, 200)
  const csv = () => csvDecisoes(R, porId, q)

  const baixar = () => {
    const b = new Blob(['﻿' + csv()], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(b); a.download = `voltlens_${lote.id}_${participante}.csv`
    document.body.appendChild(a); a.click(); a.remove()
  }
  const copiar = () => navigator.clipboard.writeText(csv()).then(() => setMsg('copiado'), () => setMsg('não foi possível copiar'))

  return (
    <>
      <h1>Resumo · {lote.nome}</h1>
      <div className="note">Obrigado! Agora, três perguntas rápidas.</div>
      <div className="stats">
        <div className="stat sketch"><div className="n">{fmt(R.length)}/{fmt(itens.length)}</div><div className="l">fotos decididas</div></div>
        <div className="stat sketch"><div className="n">{mediana(R.filter(r => r.modo === 'individual').map(r => r.tempo_s)).toFixed(1)} s</div><div className="l">tempo mediano por foto (individual)</div></div>
        <div className="stat sketch"><div className="n">{n('aceitou')}</div><div className="l">sugestões aceitas</div></div>
        <div className="stat sketch"><div className="n">{n('corrigiu')}</div><div className="l">corrigidas</div></div>
        <div className="stat sketch"><div className="n">{n('recusou')}</div><div className="l">recusadas</div></div>
        <div className="stat sketch"><div className="n">{R.filter(r => r.modo === 'em massa').length}</div><div className="l">decididas em massa</div></div>
      </div>

      <div className="box sketch">
        <h3>Questionário pós-teste (1 = discordo totalmente · 5 = concordo totalmente)</h3>
        {PERGUNTAS.map((p, k) => (
          <div className="row" style={{ margin: '8px 0' }} key={k}>
            <span style={{ flex: 1, minWidth: 240 }}>{p}</span>
            {[1, 2, 3, 4, 5].map(v => (
              <label className="r" key={v}><input type="radio" name={`q${k}`} checked={q[k] === v} onChange={() => responder(k, v)} /> {v}</label>
            ))}
          </div>
        ))}
      </div>

      {fac && (
        <div className="fac">
          <h3>Área do facilitador</h3>
          <div>Decisões em fotos com gabarito conferido à mão: <b>{G.length}</b> · iguais ao gabarito: <b>{gOk}/{G.length}</b>{G.length ? ` (${Math.round(gOk / G.length * 100)}%)` : ''}</div>
          <table className="log">
            <thead><tr><th>Foto</th><th>Sugestão</th><th>Ação</th><th>Modo</th><th>Status final</th><th>Leitura final</th><th>Gabarito</th><th>Tempo (s)</th></tr></thead>
            <tbody>{recentes.map(r => {
              const it = porId.get(r.leitura_id)
              return (
                <tr key={r.leitura_id}>
                  <td>{it?.foto.slice(-28)}</td><td>{it ? `${nomeStatus(it.status)} · ${it.leitura || '—'}` : ''}</td>
                  <td>{r.acao}</td><td>{r.modo}</td><td>{rotuloStatusFinal(r.status_final)}</td><td>{r.leitura_final}</td>
                  <td>{it?.gabarito || '—'}</td><td>{r.tempo_s}</td>
                </tr>
              )
            })}</tbody>
          </table>
          {R.length > 200 && <div className="note" style={{ marginTop: 6 }}>Mostrando as 200 decisões mais recentes; o CSV tem todas.</div>}
        </div>
      )}

      <div className="actions" style={{ marginTop: 16 }}>
        <button className="btn primary" onClick={onLotes}>Voltar aos lotes</button>
        <button className="btn" onClick={onFila}>Voltar à fila</button>
        <button className="btn" onClick={baixar}>Baixar resultados (CSV)</button>
        <button className="btn" onClick={copiar}>Copiar CSV</button>
        <button className="btn ghost" onClick={() => { if (confirm(`Apagar as ${R.length} decisões de ${participante} neste lote?`)) onApagar() }}>Apagar decisões deste lote</button>
        <span className="note" style={{ alignSelf: 'center' }}>{msg}</span>
      </div>
    </>
  )
}
