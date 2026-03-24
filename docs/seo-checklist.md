# SEO & Crawler Visibility Checklist

## Google

1. **Google Search Console** — [search.google.com/search-console](https://search.google.com/search-console), adicionar `sponda.capital`, verificar via DNS ou meta tag, submeter sitemap (`/sitemap.xml`).

2. **Pedir indexação** — No Search Console, usar "Inspeção de URL" para pedir indexação das páginas mais importantes (homepage, PETR4, VALE3, ITUB4, etc.).

3. **Google Business Profile** — [business.google.com](https://business.google.com) como serviço online de análise financeira.

## Bing / DuckDuckGo

4. **Bing Webmaster Tools** — [bing.com/webmasters](https://www.bing.com/webmasters). Submeter sitemap. DuckDuckGo usa o índice do Bing.

## AI (ChatGPT, Perplexity, Claude, etc.)

5. **`llms.txt`** — Servido em `/llms.txt`. Explica o que o Sponda faz e como as URLs funcionam para crawlers de AI.

6. **Não bloquear AI crawlers** — O `robots.txt` permite tudo exceto `/api/` e rotas auth. Não bloqueia `GPTBot`, `ClaudeBot`, `PerplexityBot`.

## Backlinks e visibilidade

7. **Diretórios de ferramentas financeiras** — Cadastrar o Sponda em Product Hunt, AlternativeTo, e diretórios BR de ferramentas de investimento.

8. **Compartilhar em comunidades** — Reddit (r/investimentos, r/bolsa), Twitter/X com hashtags de investimento, grupos de Telegram/WhatsApp de investidores.

9. **Conteúdo linkável** — Criar páginas de metodologia e glossário como iscas para backlinks de blogs e fóruns de investimento.

## OG Images

- Pré-gerar: `python manage.py generate_og_images`
- Imagens salvas em `og_images/` (gitignored, gerado no servidor)
- Servidas em `/og/<ticker>.png` (fora de `/api/` para não ser bloqueado pelo robots.txt)
