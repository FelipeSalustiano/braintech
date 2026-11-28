import { useEffect, useState } from 'react'
import { urlsAssinadas } from './dados'

/** URLs assinadas (bucket privado) dos caminhos pedidos; recarrega quando a lista muda. */
export function useUrls(paths: (string | null)[]) {
  const [urls, setUrls] = useState<Map<string, string>>(new Map())
  const chave = paths.join('|')
  useEffect(() => {
    let vivo = true
    urlsAssinadas(paths)
      .then(m => { if (vivo) setUrls(m) })
      .catch(() => { if (vivo) setUrls(new Map()) })
    return () => { vivo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave])
  return urls
}
