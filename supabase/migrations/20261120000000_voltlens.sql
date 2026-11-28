-- VoltLens: painel de validação de leituras.
--
-- lotes / leituras: carregados pelo script scripts/supabase_carregar.py a partir de
--   data/readings, data/sheets e das fotos. Só leitura para quem está logado.
-- decisoes / questionarios: o que cada pessoa decide no painel. Cada um só vê e
--   altera as próprias linhas.
-- Bucket "leituras" (privado): fotos e recortes do display. O painel lê por URL assinada.

create table public.lotes (
  id    text primary key,              -- nome da pasta, ex.: PSP_EXTRATLEITIMPL_030726_0121
  nome  text not null,                 -- rótulo mostrado na tela
  ordem int  not null default 0
);

create table public.leituras (
  id             bigint generated always as identity primary key,
  lote_id        text not null references public.lotes (id) on delete cascade,
  ordem          int  not null,        -- posição da foto no lote (ordem do readings.csv)
  foto           text not null,        -- nome do arquivo original
  foto_path      text,                 -- caminho no bucket
  recorte_path   text,                 -- caminho do recorte do display no bucket (nulo se não houve recorte)
  -- sugestão VoltLens (saída do pipeline de leitura)
  status         text not null check (status in ('lido', 'leitura_suspeita', 'ilegivel', 'sem_leitura')),
  leitura        text,
  confianca      real,
  prob_ilegivel  real,
  score_deteccao real,
  -- registro do leiturista (PDA)
  medidor        text,
  leitura_pda    text,
  nota           text,
  cmp_pda        text not null default 'na' check (cmp_pda in ('bate', 'diverge', 'na')),
  -- leitura conferida à mão (data/readings/evaluation.csv); só aparece no modo facilitador
  gabarito       text,
  unique (lote_id, foto)
);
create index leituras_lote_ordem_idx on public.leituras (lote_id, ordem);

create table public.decisoes (
  id            bigint generated always as identity primary key,
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  participante  text not null,
  leitura_id    bigint not null references public.leituras (id) on delete cascade,
  lote_id       text not null references public.lotes (id) on delete cascade,
  acao          text not null check (acao in ('aceitou', 'corrigiu', 'recusou')),
  modo          text not null check (modo in ('individual', 'em massa')),
  status_final  text not null,
  leitura_final text not null default '—',
  obs           text not null default '',
  tempo_s       real,
  acertou       boolean,             -- nulo quando a foto não tem gabarito
  criado_em     timestamptz not null default now(),
  unique (user_id, leitura_id)
);
create index decisoes_user_lote_idx on public.decisoes (user_id, lote_id);

create table public.questionarios (
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lote_id       text not null references public.lotes (id) on delete cascade,
  participante  text not null,
  q1            smallint check (q1 between 1 and 5),
  q2            smallint check (q2 between 1 and 5),
  q3            smallint check (q3 between 1 and 5),
  atualizado_em timestamptz not null default now(),
  primary key (user_id, lote_id)
);

-- Contagens por lote para a tela de lotes, sem baixar as ~3 mil linhas de cada lote.
create view public.lotes_resumo with (security_invoker = true) as
select l.id, l.nome, l.ordem,
       count(r.id)                                              as total,
       count(r.id) filter (where r.status = 'lido')             as lido,
       count(r.id) filter (where r.status = 'leitura_suspeita') as leitura_suspeita,
       count(r.id) filter (where r.status = 'ilegivel')         as ilegivel,
       count(r.id) filter (where r.status = 'sem_leitura')      as sem_leitura,
       count(r.id) filter (where r.cmp_pda = 'diverge')         as diverge
from public.lotes l
left join public.leituras r on r.lote_id = l.id
group by l.id, l.nome, l.ordem;

-- Permissões: nada para anon; quem está logado lê lotes/leituras e mexe só nas próprias decisões.
revoke all on public.lotes, public.leituras, public.decisoes, public.questionarios, public.lotes_resumo from anon;
grant select on public.lotes, public.leituras, public.lotes_resumo to authenticated;
grant select, insert, update, delete on public.decisoes, public.questionarios to authenticated;

alter table public.lotes         enable row level security;
alter table public.leituras      enable row level security;
alter table public.decisoes      enable row level security;
alter table public.questionarios enable row level security;

create policy "logados leem lotes"    on public.lotes    for select to authenticated using (true);
create policy "logados leem leituras" on public.leituras for select to authenticated using (true);

create policy "cada um ve as proprias decisoes"     on public.decisoes for select to authenticated using (user_id = (select auth.uid()));
create policy "cada um cria as proprias decisoes"   on public.decisoes for insert to authenticated with check (user_id = (select auth.uid()));
create policy "cada um altera as proprias decisoes" on public.decisoes for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "cada um apaga as proprias decisoes"  on public.decisoes for delete to authenticated using (user_id = (select auth.uid()));

create policy "cada um ve o proprio questionario"     on public.questionarios for select to authenticated using (user_id = (select auth.uid()));
create policy "cada um cria o proprio questionario"   on public.questionarios for insert to authenticated with check (user_id = (select auth.uid()));
create policy "cada um altera o proprio questionario" on public.questionarios for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- Bucket privado das fotos e recortes. O upload é feito pelo script com a chave secreta,
-- que ignora RLS; o painel só precisa ler.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('leituras', 'leituras', false, 10485760, array['image/jpeg', 'image/png'])
on conflict (id) do nothing;

create policy "logados leem fotos e recortes" on storage.objects
  for select to authenticated using (bucket_id = 'leituras');
