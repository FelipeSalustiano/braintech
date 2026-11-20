import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined

/** Mensagem para a tela quando o .env não foi preenchido. */
export const configErro =
  !url || !key
    ? 'Faltam VITE_SUPABASE_URL e VITE_SUPABASE_PUBLISHABLE_KEY em frontend/.env.local (veja frontend/.env.example).'
    : null

// A chave pública (anon / publishable) pode ficar no navegador: o que cada pessoa
// lê e grava é limitado pelas regras de acesso (RLS) da migração em supabase/migrations.
export const supabase = createClient(url ?? 'http://localhost', key ?? 'sem-chave')

/** "maria" -> "maria@voltlens.local": o Supabase Auth usa e-mail, a tela pede só o usuário. */
export const LOGIN_DOMAIN = (import.meta.env.VITE_LOGIN_DOMAIN as string | undefined) || 'voltlens.local'
export const BUCKET = 'leituras'
