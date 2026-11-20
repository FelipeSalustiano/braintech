# Painel VoltLens (front-end)

App web para validar as leituras do OCR. Os dados e as fotos ficam no Supabase; este app só roda no navegador.

## Rodar

Precisa de [Node.js](https://nodejs.org) 22.12 ou superior.

```bash
npm ci                            # instala exatamente as versões do package-lock.json
cp .env.example .env.local        # no Windows: copy .env.example .env.local
```

Preencha `.env.local` com a URL e a chave **pública** (publishable) do projeto Supabase — peça a quem
administra o projeto, ou veja em Project Settings > API Keys:

```text
VITE_SUPABASE_URL=https://<ref-do-projeto>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
VITE_LOGIN_DOMAIN=voltlens.local
```

```bash
npm run dev
```

Abra http://localhost:5173 e entre com o usuário e a senha que você recebeu.

## Outros comandos

| Comando | O que faz |
|---|---|
| `npm run build` | Gera a versão de produção em `dist/` (para publicar num servidor estático) |
| `npm run preview` | Serve o `dist/` localmente para conferir |
| `npm run lint` | Verifica o código |

Banco, carga das fotos e criação de contas: veja a seção "Painel VoltLens" no README da raiz do repositório.
