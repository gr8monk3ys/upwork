# Lighthouse — live demos, 2026-08-31

Headless Chrome, single run each (`npx lighthouse@12 --chrome-flags="--headless=new"`, desktop default emulation off = mobile). Single-run performance scores vary ±5; re-run before quoting a different number.

| Site | URL | Performance | Accessibility | Best Practices | SEO | LCP | CLS | TBT |
|---|---|---|---|---|---|---|---|---|
| Blog AI | https://blog-ai.vivancedata.com | 83 | 96 | 93 | 100 | 3.7 s | 0 | 20 ms |
| Link Flame | https://link-flame-rouge.vercel.app | 83 | 96 | 93 | 83 | 4.0 s | 0 | 30 ms |
| InfiniStar | https://infini-star.vercel.app | 83 | 100 | 100 | 100 | 4.1 s | 0 | 120 ms |

Lighthouse 12.8.2. Raw JSON was in the session scratchpad; regenerate with the command above.

Portfolio phrasing that these numbers support:

- Link Flame: "Lighthouse accessibility 96, best practices 93"
- InfiniStar: "Lighthouse 100 accessibility / 100 best practices / 100 SEO"
- Blog AI: "Lighthouse 96 accessibility, 100 SEO"

Performance sits at 83 on all three; don't lead with it. Fixing LCP on the storefront would be a cheap way to get a 90+ number to quote.
