# Выгрузка статей Дзен-канала с просмотрами (заголовок = просмотры)

Готовый рецепт для **Claude Code**. Отдаёшь этот файл, называешь канал(ы) и число дней — на выходе `.txt` со строками `Заголовок = количество просмотров`, по одной статье на строку.

Работает для **любого чужого канала** (свой аккаунт/логин НЕ нужен). Метод проверен на канале `worldlord` (2026-07-01): 24 статьи за 60 дней за ~30 секунд.

---

## TL;DR — что сказать Claude Code

> Прочитай `ВЫГРУЗКА-ДЗЕН-статьи-инструкция.md` и сделай выгрузку каналов **worldlord** за **60** дней.

Указываешь:
- **Канал / каналы** — это «слаг» из адреса: `https://dzen.ru/worldlord` → слаг `worldlord`. Можно несколько.
- **За сколько дней** — например 30, 60, 90.

Claude Code сам подставит их в скрипт ниже и сохранит по одному `.txt` на канал на рабочий стол.

---

## Что нужно (окружение)

- **Claude Code** с браузерными инструментами. Подойдёт любой из двух движков:
  - **Playwright MCP** (`mcp__playwright__browser_navigate`, `mcp__playwright__browser_evaluate`) — основной, headless, ничего настраивать не надо.
  - либо **Claude in Chrome** (`mcp__claude-in-chrome__navigate` + `mcp__claude-in-chrome__javascript_tool`) — если расширение подключено.
- Больше ничего: ни ключей, ни логина в Дзен, ни сторонних сервисов.

---

## Как это работает (суть метода)

1. Открываем страницу канала `https://dzen.ru/<слаг>` в браузере. Дальше все запросы идут **из контекста самой страницы** (`fetch` с `credentials: include`) — тот же origin, поэтому нет CORS и не нужны заголовки/куки вручную.
2. Дёргаем внутренний JSON-эндпоинт ленты канала:
   `https://dzen.ru/api/v3/launcher/export?...&channel_name=<слаг>`.
   В ответе среди `tabs` есть вкладка с `id: "article"` — это **чисто хронологическая лента статей** (важно: сам «главный» фид перемешан рекомендациями и для выборки по датам НЕ годится).
3. Идём по её постраничной ссылке `more.link`, собираем карточки статей. У каждой карточки (`type: "card"`) есть:
   - `title` — заголовок,
   - `views` — просмотры (живое число),
   - `publication_object_id` — Mongo ObjectId, **первые 8 hex-символов = Unix-время публикации** (с точностью до минут). Отдельного поля с датой в карточке нет, дату берём отсюда.
4. Останавливаем пагинацию, когда вся страница старше отсечки `сегодня − N дней`. Фильтруем по дате, сортируем от свежих к старым, формируем строки `Заголовок = просмотры`.

---

## Пошагово для Claude Code

1. Задай параметры вверху скрипта: `SLUGS` (массив слагов) и `DAYS` (число дней).
2. **Playwright:** `mcp__playwright__browser_navigate` → `https://dzen.ru/<первый-слаг>` (нужно один раз, чтобы получить рабочий origin dzen.ru).
3. Выполни скрипт через `mcp__playwright__browser_evaluate` (функция ниже целиком, она сама перебирает все каналы из `SLUGS`).
   - В Claude in Chrome: то же самое через `mcp__claude-in-chrome__javascript_tool`.
4. Скрипт вернёт массив объектов `{ slug, count, newest, oldest, fileText, error }`.
5. На каждый канал сохрани `fileText` в файл на рабочий стол с именем `<slug>_статьи_<DAYS>дней.txt` (инструментом Write).

---

## Единый скрипт (copy-paste в browser_evaluate)

```js
async () => {
  // ==== ПАРАМЕТРЫ ====
  const SLUGS = ['worldlord'];   // слаги каналов, напр. ['worldlord','anotherchannel']
  const DAYS  = 60;              // за сколько последних дней
  // ===================

  const CUTOFF = Date.now() - DAYS * 24 * 60 * 60 * 1000;
  const sleep  = ms => new Promise(r => setTimeout(r, ms));
  const oidDate = oid => parseInt(oid.substring(0, 8), 16) * 1000; // ObjectId -> ms

  // рекурсивно собрать все карточки-статьи из произвольно вложенного JSON
  function collect(node, acc, depth) {
    if (depth > 8 || !node || typeof node !== 'object') return;
    if (Array.isArray(node)) { for (const x of node) collect(x, acc, depth + 1); return; }
    if (node.type === 'card' && node.publication_object_id && node.title && typeof node.views === 'number') acc.push(node);
    for (const k of Object.keys(node)) { const v = node[k]; if (v && typeof v === 'object') collect(v, acc, depth + 1); }
  }

  async function getJSON(url) {
    const r = await fetch(url, { credentials: 'include', headers: { accept: 'application/json' } });
    const t = await r.text();
    if (t[0] !== '{') throw new Error('non-JSON (captcha/redirect), status ' + r.status);
    return JSON.parse(t);
  }

  async function dumpChannel(slug) {
    try {
      const exp = await getJSON('https://dzen.ru/api/v3/launcher/export?country_code=ru&lang=ru&clid=300&referrer_place=more&channel_name=' + encodeURIComponent(slug));
      const artTab = (exp.tabs || []).find(t => t.id === 'article');
      if (!artTab || !artTab.url) return { slug, error: 'no article tab (у канала нет статей?)' };

      const byOid = new Map();
      let link = artTab.url, page = 0, stop = false;
      while (link && page < 30 && !stop) {
        const j = await getJSON(link);
        const cards = []; collect(j.items, cards, 0);
        let maxD = -Infinity, added = 0;
        for (const c of cards) {
          const t = oidDate(c.publication_object_id);
          if (t > maxD) maxD = t;
          if (!byOid.has(c.publication_object_id)) {
            byOid.set(c.publication_object_id, { title: String(c.title).trim(), views: c.views, t });
            added++;
          }
        }
        if ((isFinite(maxD) && maxD < CUTOFF) || added === 0) stop = true; // вся страница старше отсечки или ничего нового
        link = j.more && (j.more.link || j.more);
        page++;
        await sleep(300); // бережно к анти-боту
      }

      const recent = [...byOid.values()].filter(x => x.t >= CUTOFF).sort((a, b) => b.t - a.t);
      const iso = ms => new Date(ms).toISOString().slice(0, 10);
      return {
        slug,
        count: recent.length,
        newest: recent[0] ? iso(recent[0].t) : null,
        oldest: recent.length ? iso(recent[recent.length - 1].t) : null,
        fileText: recent.map(x => `${x.title} = ${x.views}`).join('\n') + '\n'
      };
    } catch (e) {
      return { slug, error: String(e) };
    }
  }

  const out = [];
  for (const s of SLUGS) { out.push(await dumpChannel(s)); await sleep(400); }
  return out;
}
```

---

## Грабли и как они обойдены (важно — не наступать заново)

- **Главный фид перемешан рекомендациями.** Первый экран/`channel-more` подмешивает старые популярные статьи (вплоть до 2024 года) к свежим. Стоп «по самой старой на странице» срабатывает ложно и теряет часть свежих. **Решение:** брать только вкладку `id: "article"` — она хронологическая. Отсечку проверять по **максимальной** дате страницы, а не по выбросам.
- **В карточке нет поля даты** (`date: ""`). **Решение:** дата из `publication_object_id` (Mongo ObjectId, первые 8 hex = Unix-секунды). Точность до минут, для границы «N дней» достаточно.
- **`sort_type=new` не работает** — эндпоинт отдаёт HTML вместо JSON. Не использовать; хронология уже есть во вкладке `article`.
- **Страница слетает на `about:blank`** после серии запросов → `fetch` к dzen.ru падает с «Failed to fetch». **Решение:** перед скриптом заново `navigate` на `https://dzen.ru/<слаг>`, чтобы вернуть origin dzen.ru.
- **Анти-бот / капча:** при частых запросах эндпоинт может вернуть HTML. Скрипт это ловит (`getJSON` кидает понятную ошибку). **Решение:** пауза, повторная навигация на канал, пауза 300–400 мс между страницами уже заложена.
- **Видео и «Ролики» (shorts)** отсекаются автоматически: берём только `type: "card"` (статьи `/a/`), а не вкладки «Видео»/«Ролики».
- **Слаг-исключения:** обычный канал = `https://dzen.ru/<слаг>`. Некоторые каналы адресуются через `https://dzen.ru/id/<hex>` — тогда `channel_name` = этот `id/<hex>` (подставить как есть).

---

## Ограничения

- Просмотры — те, что Дзен отдаёт публично в ленте на момент запуска (обновляются в реальном времени).
- Дата = время создания объекта публикации (≈ время выхода, расхождение минуты). Для статьи, вышедшей около полуночи, день теоретически может отличаться на 1 — на выборку «за N дней» влияет пренебрежимо.
- Скорость: ~1 страница (до ~20 статей) за ~0.5 сек. 60–90 дней активного канала = единицы секунд.
- За «последние N дней» отсчёт идёт от текущего момента запуска (`сегодня − N`).

---

## Пример результата (worldlord, 60 дней, 2026-07-01)

```
За своё непокорство пришлось дорого заплатить = 6639
Она перешла от отца к сыну = 71963
Чем пахли русские царевны до появления духов = 1799609
Неприятные обязанности фрейлины = 780897
...
```
24 статьи, от 2026-06-30 до 2026-05-03.
