import { useState } from 'react'
import logo from '../assets/voltlens_logo.png'
import neo from '../assets/neoenergia.png'
import { LOGIN_DOMAIN, supabase } from '../lib/supabase'

export function Login() {
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [entrando, setEntrando] = useState(false)

  async function entrar() {
    const u = usuario.trim().toLowerCase()
    if (!u || !senha) { setErro('Informe usuário e senha.'); return }
    setEntrando(true); setErro(null)
    const email = u.includes('@') ? u : `${u}@${LOGIN_DOMAIN}`
    const { error } = await supabase.auth.signInWithPassword({ email, password: senha })
    setEntrando(false)
    if (error) setErro(error.message === 'Invalid login credentials' ? 'Usuário ou senha incorretos.' : error.message)
  }
  const enter = (e: React.KeyboardEvent) => { if (e.key === 'Enter') { e.preventDefault(); entrar() } }

  return (
    <div className="login">
      <div className="brand">
        <img src={logo} alt="VoltLens" />
        <p>Validação de leituras de medidores<br />com sugestões do pipeline atual</p>
      </div>
      <div className="form">
        <div className="partner"><img src={neo} alt="Neoenergia" /></div>
        <h1>Entrar</h1>
        <label htmlFor="u">Usuário</label>
        <input id="u" autoFocus placeholder="seu.usuario" autoComplete="username" value={usuario}
          onChange={e => setUsuario(e.target.value)} onKeyDown={enter} />
        <label htmlFor="pw">Senha</label>
        <input id="pw" type="password" placeholder="••••••••" autoComplete="current-password" value={senha}
          onChange={e => setSenha(e.target.value)} onKeyDown={enter} />
        <button className="btn primary" type="button" disabled={entrando} onClick={entrar}>{entrando ? 'Entrando…' : 'Entrar'}</button>
        {erro && <div className="erro">{erro}</div>}
      </div>
    </div>
  )
}
