import type { Decisao, Item } from '../lib/tipos'
import { ACAO_TXT, CMP_TXT, ST, temLeitura } from '../lib/tipos'
import { fmt, pct, rotuloStatusFinal, sameNum } from '../lib/util'
import { useUrls } from '../lib/useUrls'
import { ConfBar, StBadge } from './Comuns'

export function Detalhe({ it, proximo, idx, total, decisao, fac, onFila, onAnterior, onProxima, onAceitar, onCorrigir, onRecusar }: {
  it: Item
  proximo: Item | null
  idx: number
  total: number
  decisao: Decisao | undefined
  fac: boolean
  onFila: () => void
  onAnterior: () => void
  onProxima: () => void
  onAceitar: () => void
  onCorrigir: () => void
  onRecusar: () => void
}) {
  // Pede também as imagens da próxima foto, para a troca ficar instantânea.
  const urls = useUrls([it.foto_path, it.recorte_path, proximo?.foto_path ?? null, proximo?.recorte_path ?? null])
  const p = it.foto_path ? urls.get(it.foto_path) : undefined
  const c = it.recorte_path ? urls.get(it.recorte_path) : undefined
  const comLeitura = temLeitura(it.status)
  const gabOk = it.gabarito != null ? sameNum(it.leitura, it.gabarito) : null

  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
        <button className="btn" onClick={onFila}>← Fila</button>
        <span className="note">Foto {idx + 1} de {fmt(total)} no filtro</span>
      </div>
      <div className="detail">
        <div className="photo sketch">
          <div className="ph">{p ? <img src={p} alt={`foto do medidor ${it.medidor ?? ''}`} /> : <span className="note">{it.foto_path ? 'carregando…' : 'foto indisponível'}</span>}</div>
          <div className="fn">{it.foto}</div>
        </div>
        <div>
          <div className="box sketch">
            <h3>Registro do leiturista (PDA)</h3>
            <dl className="kv">
              <dt>Número do medidor</dt><dd className="mono">{it.medidor || '—'}</dd>
              <dt>Leitura digitada</dt><dd className="mono">{it.leitura_pda || '—'}</dd>
              <dt>Nota de leitura</dt><dd>{it.nota || '—'}</dd>
            </dl>
          </div>
          <div className="box sketch sug">
            <div className="head">
              <h3 style={{ margin: 0 }}>Sugestão VoltLens</h3><StBadge s={it.status} />
              <span className={`cmp ${it.cmp_pda}`}>{it.cmp_pda === 'na' ? '' : CMP_TXT[it.cmp_pda]}</span>
            </div>
            {c && <div className="cropbox"><img src={c} alt="recorte do display" /></div>}
            <dl className="kv">
              <dt>Leitura identificada</dt><dd className="big">{it.leitura || '—'}</dd>
              <dt>Confiança da leitura</dt><dd><ConfBar c={it.confianca} /></dd>
              <dt>Prob. display ilegível</dt><dd>{pct(it.prob_ilegivel)}</dd>
              <dt>Score da detecção</dt><dd>{pct(it.score_deteccao)}</dd>
            </dl>
            <div className="hint">{ST[it.status]?.hint}</div>
            {fac && <div className="fac">{it.gabarito != null
              ? <>Gabarito (conferido à mão): <b className="mono">{it.gabarito}</b> · sugestão <b>{gabOk ? 'correta' : 'errada'}</b></>
              : 'Sem gabarito conferido à mão para esta foto.'}</div>}
          </div>
          {decisao && (
            <div className="note" style={{ marginBottom: 8 }}>
              Decisão registrada: <b>{ACAO_TXT[decisao.acao]}</b>
              {decisao.acao === 'corrigiu' && <> → {rotuloStatusFinal(decisao.status_final)}{decisao.leitura_final && decisao.leitura_final !== '—' ? ' · ' + decisao.leitura_final : ''}</>}
            </div>
          )}
          <div className="actions">
            <button className="btn primary" onClick={onAceitar}>
              ✓ {comLeitura ? `Aceitar leitura ${it.leitura ?? ''}` : it.status === 'ilegivel' ? 'Confirmar ilegível' : 'Confirmar sem leitura'}
            </button>
            <button className="btn" onClick={onCorrigir}>✎ Corrigir</button>
            <button className="btn" onClick={onRecusar}>✗ Recusar</button>
          </div>
          <div className="hint">
            {comLeitura
              ? <><b>Aceitar</b>: a leitura está certa. <b>Corrigir</b>: você vê outro valor ou o display está ilegível. <b>Recusar</b>: está errado, mas você não consegue dizer o certo.</>
              : <><b>Confirmar</b>: concorda que {it.status === 'ilegivel' ? 'o display não dá para ler (pedir nova foto)' : 'o display não aparece na foto'}. <b>Corrigir</b>: você consegue ler o display e informa o valor. <b>Recusar</b>: a classificação está errada, mas você não consegue dizer o certo.</>}
          </div>
        </div>
      </div>
      <div className="nav">
        <button className="btn" disabled={idx === 0} onClick={onAnterior}>← Anterior</button>
        <button className="btn" onClick={onProxima}>{idx === total - 1 ? 'Ver fila' : 'Próxima →'}</button>
      </div>
    </>
  )
}
