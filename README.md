# NEXUS PULSE — игровой портал

Премиальный статичный gaming hub на чистом HTML / CSS / vanilla JS.  
Тёмная neon/cyber эстетика, русскоязычный UI (с переключателем на любой язык мира), ежедневный «Пульс дня», скидки с отдельным частым обновлением, тест скорости сети, подбор игры под настроение и Discord-комьюнити.

## Как открыть

1. Открой файл `index.html` в браузере (двойной клик или «Open with Live Server»).
2. Или локальный сервер из этой папки (нужен для `fetch` JSON и теста скорости):

```bash
cd /workspace/gaming-portal
python3 -m http.server 8080
```

Затем перейди на http://localhost:8080/

> При открытии через `file://` daily/deals подтянутся из встроенного fallback в `app.js`. Тест скорости и Google Translate требуют сеть + http(s).

## Структура

| Путь | Назначение |
|------|------------|
| `index.html` | Разметка (single-page + sticky nav + language switcher) |
| `styles.css` | Тёмная тема, glassmorphism, адаптив |
| `app.js` | Каталог (~75 игр), 30 гайдов, инструменты, Discord CTA, i18n, speed test, mood picker, загрузка JSON |
| `data/daily.json` | Ежедневный фид: пульс, **новые интересные игры**, патчи, релизы, новости (без скидок) |
| `data/deals.json` | Скидки + `updatedAt` — обновляется **чаще**, чем daily |
| `scripts/update_daily.py` | Daily cron → `data/daily.json` |
| `scripts/update_deals.py` | Частый cron (напр. каждые 4–6 ч) → `data/deals.json` |
| `assets/nexus-pulse-icon.png` | Иконка / favicon |
| `README.md` | Эта инструкция |

## Секции

1. **Hero** — CTA к инструментам и Discord  
2. **Пульс дня** — игра дня, тренды, советы (`daily.json`)  
3. **Календарь релизов и патчей**  
4. **Новые интересные игры** (`#new-games`) — 6–10 карточек из `daily.json.newInterestingGames`, обновляется ежедневно  
5. **Топ игр** — 75 популярных тайтлов, фильтры жанров, поиск, избранное  
6. **Гайды и советы** — **30** практических карточек (FPS, ранкид, боссы, экономика, чеклисты)  
7. **Факты и лайфхаки** — ротация интересных фактов  
8. **Словарь геймера** — tilt, ping, smurf и др.  
9. **Киберспорт** — турниры и хайлайты  
10. **Скидки** — тикер + карточки из `deals.json`, метка «Скидки обновлены: …»  
11. **Инструменты** — **подбор игры под настроение/время**, FPS, системные требования, **тест скорости**, wishlist  
12. **Новости** — из `daily.json`  
13. **Комьюнити** — Discord NEXUS PULSE  

## Подбор игры под настроение

В секции «Инструменты» → интерактивный квиз:

1. **Настроение** — расслабиться / посоревноваться / сюжет / хоррор / с друзьями / погриндзить  
2. **Время** — 15–30 мин / ~1 час / 2+ часа / весь вечер  
3. **Режим** — не важно / соло / мультиплеер  

Кнопка «Подобрать игры» выдаёт **3 рекомендации** из каталога с кратким обоснованием и ссылкой в каталог.

## Discord

Инвайт задаётся **в одном месте** — константа в начале `app.js`:

```js
const DISCORD_INVITE_URL = "https://discord.gg/7JvfzNrt4x";
```

- Пусто или `#` → кнопки disabled / «Скоро».  
- Реальный URL → все `.discord-cta` открывают инвайт в новой вкладке.

## Тест скорости

В секции «Инструменты» → «Тест скорости»:

1. Несколько round-trip запросов к Cloudflare CDN (пинг).  
2. Прогрессивная загрузка чанков 100KB → 1MB → 5MB → 10MB.  
3. Результат: download Mbps, latency ms, оценка для онлайна.  

## Языковой переключатель

- По умолчанию **русский** (авторский контент).  
- В шапке: глобус + searchable picker (популярные + полный список ISO 639-1).  
- First-class UI-строки (`data-i18n`) для: `ru`, `en`, `uk`, `de`, `es`, `fr`, `pt`, `pl`, `tr`, `zh`, `ja`, `ko`.  
- Любой другой язык: Google Website Translator.  
- Выбор хранится в `localStorage` (`nexus_pulse_lang`).

## Данные и расписание обновлений

### Ежедневно — `data/daily.json`

```bash
python3 scripts/update_daily.py
```

Поля: `date`, `updatedAt`, `gameOfTheDay`, `trending[]`, `tips[]`, `patches[]`, `releases[]`, `news[]`, `newInterestingGames[]`.  
**Скидки сюда больше не пишутся.**

### Чаще (рекомендуется каждые 4–6 часов) — `data/deals.json`

```bash
python3 scripts/update_deals.py
# опционально:
python3 scripts/update_deals.py --count 14
```

Сайт показывает метку **«Скидки обновлены: …»** из `deals.json.updatedAt`.

Пример cron:

```cron
0 6 * * * cd /path/to/gaming-portal && python3 scripts/update_daily.py
0 */4 * * * cd /path/to/gaming-portal && python3 scripts/update_deals.py
```

## Ограничения

- Нет бэкенда: wishlist и язык только в `localStorage`  
- Скидки / новости / турниры / патчи — редакционный контент из JSON-пайплайна (не live API магазинов)  
- FPS-оценка и mood-picker — эвристики по каталогу  
- Тест скорости зависит от Cloudflare CDN и CORS  
- Перевод «любого языка» зависит от Google Translate widget  

## Шрифты

Google Fonts: **Orbitron** (заголовки) + **Manrope** (текст).

## Discord automation

| What | Where | When |
|---|---|---|
| Server structure, roles, rules/welcome messages, invite (idempotent) | `python scripts/discord_post.py setup-server` (box) | on demand |
| Auto-feed: news, deals ≥50%, freebies, esports, patches, videos, releases, game of the day | `scripts/discord_feeds.py` — bot mode on the box (`scripts/discord_box_sync.sh`) or webhook mode in Actions (`.github/workflows/discord-feeds.yml`, secret `DISCORD_WEBHOOKS_JSON`) | hourly (box) / after each data refresh (Actions) |
| Dedupe state | `data/discord_posted.json` (ids only) | — |
| Scheduled events for top matches | `discord_post.py sync-events` (box) | hourly |
| Reaction role-picker in #🎭роли | `discord_post.py sync-roles` (box) | hourly |
| Switch feed to webhooks | `discord_post.py setup-webhooks` (needs Manage Webhooks) → sets `feedMode: "webhook"` | once |

The bot token is never stored in GitHub; webhook URLs live only in the repo secret.
