<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
  <img src="assets/banner-light.png" alt="gonjineh (گنجینه): حافظه‌ی مشترک مبتنی بر git برای عامل‌های هوش مصنوعی تیم؛ جلسه‌های هم‌تیمی‌ها (Claude Code، Codex، Gemini) به یادداشت‌های قابل‌جستجو در یک مخزن git تبدیل می‌شوند" width="100%">
</picture>

<div dir="rtl">

[English](README.md) · **فارسی** · [🌐 نمونه‌ی زنده](https://mrzroot.github.io/gonjineh/) · [📦 انتشار نسخه‌ی ۰٫۱٫۰](https://github.com/mrzroot/gonjineh/releases/tag/v0.1.0) · [🗒 تغییرات](CHANGELOG.md)

</div>

![version](https://img.shields.io/badge/version-0.1.0-8e3f4a) ![python](https://img.shields.io/badge/python-3.9%2B-8e3f4a) ![deps](https://img.shields.io/badge/dependencies-none-6f4e37) ![server](https://img.shields.io/badge/server-none-6f4e37) ![llm](https://img.shields.io/badge/LLM%20calls-none-6f4e37) ![tests](https://img.shields.io/badge/tests-99%20passing-6f4e37) ![license](https://img.shields.io/badge/license-MIT-a07a2c)

</div>

<div dir="rtl">

> **گنجینه (gonjineh)** کاری می‌کند که هوش مصنوعیِ شما بداند هوش مصنوعیِ هم‌تیمی‌تان قبلاً چه کرده است. وقتی کسی یک جلسه‌ی Claude Code یا Codex را تمام می‌کند، یک hook متن گفتگو را به یک یادداشت کوچکِ مارک‌داونِ پاک‌سازی‌شده از رمز و کلید در **مخزن git خودتان** تبدیل می‌کند. همه‌ی عامل‌ها می‌توانند آن را جستجو کنند و با هر پرامپت، چند یادداشتِ مرتبطِ هم‌تیمی‌ها به متن اضافه می‌شود.

**فهرست:** [چرا](#-چرا) · [نصب](#-نصب) · [شروع سریع](#-شروع-سریع) · [خروجی واقعی](#-خروجی-واقعی) · [راه‌اندازی برای هر ابزار](#-راهاندازی-برای-هر-ابزار) · [چگونه کار می‌کند](#-چگونه-کار-میکند) · [حریم خصوصی](#-حریم-خصوصی-و-پاکساز) · [محدودیت‌ها](#-محدودیتها-و-صداقت) · [جایگزین‌ها](#-جایگزینها) · [نقشه‌ی راه](#-نقشهی-راه) · [مشارکت](#-مشارکت) · [مجوز](#-مجوز)

## 🎯 چرا

یک اکانت هوش مصنوعی (یا چند تا) می‌خرید و تیم روی یک کدبیس کار می‌کند: یکی فرانت، یکی بکند. ولی عامل هر نفر فقط گفتگوهای خودش را می‌داند. پس عامل فرانت برای اندپوینتی که وجود دارد mock می‌نویسد، یا JWT در localStorage پیشنهاد می‌دهد در حالی که جلسه‌ی بکند خلاف آن را تصمیم گرفته.

`gonjineh` گفتگوها را بدون سرور و بدون حساب کاربری به یک **سابقه‌ی مشترک و قابل‌جستجو** تبدیل می‌کند:

- **منفعل.** hook ها جلسه‌های تمام‌شده را ثبت می‌کنند و کسی دستی یادداشت نمی‌نویسد (می‌شود با `gonjineh note` هم نوشت).
- **git حمل‌ونقل است.** برای هر جلسه یک فایل، و فقط نویسنده‌اش آن را می‌نویسد؛ پس push ها تداخل ندارند. تیم شما همین حالا هم دسترسی git دارد.
- **بدون LLM.** خلاصه‌سازی قاعده‌محور است (درخواست‌ها، نتیجه، تصمیم‌ها، دردسرها، کارهای باقی‌مانده، فایل‌ها، اندپوینت‌ها، دستورها). هزینه‌ی API اضافه و ارسال داده به شخص ثالث ندارد.
- **پیش از نوشتن روی دیسک پاک‌سازی می‌شود.** توکن، کلید، شماره‌کارت و موبایل ایرانی ابتدا ماسک می‌شوند. پاک‌ساز رمزها قابل خاموش‌کردن نیست.
- **آگاه از فارسی.** جستجو ی/ک عربی، نیم‌فاصله و ارقام فارسی را یکسان می‌کند؛ پس «ورود» و «login» هر دو در یک مجموعه کار می‌کنند.

## 📦 نصب

پایتون ۳٫۹ به بالا و فقط کتابخانه‌ی استاندارد. هنوز روی PyPI نیست:

</div>

```sh
pipx install git+https://github.com/mrzroot/gonjineh     # یا: pip install git+https://github.com/mrzroot/gonjineh
gonjineh --help
```

<div dir="rtl">

## 🚀 شروع سریع

یک مخزن خصوصی خالی برای «مغز تیم» بسازید (هر میزبان git: GitHub، GitLab یا یک bare repo روی سرور مشترک). سپس **هر هم‌تیمی یک بار** داخل پوشه‌ی پروژه:

</div>

```sh
gonjineh init --brain git@github.com:your-team/team-brain.git --area backend    # --codex هم Codex را وصل می‌کند (تنظیم سطح کاربر)
git add .gonjineh.json CLAUDE.md AGENTS.md GEMINI.md .github .cursor .mcp.json .gemini .vscode .claude/settings.json
git commit -m "Add gonjineh" && git push
```

<div dir="rtl">

بقیه‌ی اعضا آن commit را می‌گیرند و `gonjineh init --area frontend` را اجرا می‌کنند (area مخصوص خودشان؛ نشانی مغز از `.gonjineh.json` خوانده می‌شود). از آن به بعد:

۱. **شروع جلسه:** عامل با کارهای اخیر هم‌تیمی‌ها توجیه می‌شود.
۲. **هر پرامپت:** اگر یادداشت‌های هم‌تیمی‌ها با آن بخوانند، تا ۳ مورد به متن اضافه می‌شود (هرگز یادداشت‌های خودتان نه).
۳. **پایان جلسه یا فشرده‌سازی:** گفتگو خلاصه، پاک‌سازی، commit و در پس‌زمینه push می‌شود.

دستی هم می‌شود: `gonjineh search "refund screen"`، `gonjineh who server/routes/auth.py`، `gonjineh recall`، `gonjineh show <id>`، `gonjineh doctor`، `gonjineh uninstall`.

## 🎬 خروجی واقعی

تولیدشده با [`examples/demo.py`](examples/demo.py) (دو هم‌تیمی، یک bare repo محلی، بدون شبکه)؛ متن کامل در [`docs/demo.txt`](docs/demo.txt). گزیده:

</div>

```text
[reza] $ gonjineh search --pull refund screen
[7b88d6deca] 2026-03-02 maryam (claude-code) · backend · Add a refund endpoint for orders. Use POST /api/orders/refund …  (score 3.194)
    files: server/routes/refunds.py, server/models/refund.py
    api:   POST /api/orders/refund
    decision: We decided to store only the last four digits because PCI scope is out of budget.

[reza] $ gonjineh search ورود login
[d737c50590] 2026-03-02 maryam (claude-code) · backend · ایجاد API ورود با ایمیل و رمز: POST /api/login  (score 2.753)
    decision: تصمیم گرفتیم توکن JWT را در کوکی httpOnly بگذاریم چون ذخیره در localStorage امن نیست.

sk_live in git history: False  |  commits: 2      # the fake key in maryam's chat was masked first
```

<div dir="rtl">

یادداشت ذخیره‌شده مارک‌داونِ ساده با یک front-matter کوچک از نوع JSON است؛ می‌توانید مثل هر فایل دیگری بخوانید، `grep` کنید و در pull request مرور کنید.

## 🧩 راه‌اندازی برای هر ابزار

`gonjineh init` چه می‌نویسد، و **هر ابزار واقعاً تا کجا آزموده شده** (جزئیات در [docs/VERIFICATION.md](docs/VERIFICATION.md)):

| ابزار | ثبت (نوشتن) | بازیابی (خواندن) | چگونه آزموده شد |
|---|---|---|---|
| **Claude Code** | hook های `SessionStart`، `UserPromptSubmit`، `Stop`، `SessionEnd`، `PreCompact` در `.claude/settings.json` | توجیه + تزریق برای هر پرامپت + MCP | CLI واقعیِ ۲٫۱٫۱۹۷ روی **API ساختگی**: گفتگو ثبت شد و توجیه و یادداشت‌های هم‌تیمی در بدنه‌ی درخواست دیده شد |
| **Codex** | hook از نوع `notify` (سطح کاربر در `~/.codex/config.toml` با `init --codex`)، خواندن rollout از `~/.codex/sessions` | سرور MCP + `AGENTS.md` | CLI واقعیِ ۰٫۱۶۴٫۰ روی **API ساختگی**: notify همان rollout واقعی را ثبت کرد و ابزار MCP فهرست شد |
| **Gemini CLI** | `gonjineh capture --format gemini` (بدون hook؛ تجزیه‌گر در حد تلاش) | MCP + `GEMINI.md` | CLI واقعیِ ۰٫۶۵٫۰: `mcp list` وضعیت **Connected** نشان می‌دهد. تجزیه‌گر روی فایل‌های واقعی **آزموده نشده** |
| **Cursor** | `gonjineh note` / ابزار MCP `add_note` | `.cursor/mcp.json` + `.cursor/rules` | فقط فایل‌های پیکربندی، **اجرا نشده** |
| **Copilot (VS Code)** | `gonjineh note` | `.vscode/mcp.json` + `copilot-instructions.md` | فقط فایل‌های پیکربندی، **اجرا نشده** |
| هر کلاینت MCP دیگر | ابزار `add_note` | `search_memory`، `read_entry`، `who_knows_about`، `recent` | پروتکل MCP روی stdio در تست‌های واحد آزموده شد |

> ⚠️ هیچ جلسه‌ی زنده‌ای با مدل واقعی و کلید API واقعی اجرا نشده است. CLI های واقعی روی API ساختگی اجرا شدند؛ این لوله‌کشی را ثابت می‌کند (hook اجرا می‌شود، فایل نوشته می‌شود، متن به درخواست می‌رسد) ولی نه اینکه مدل واقعی چقدر از آن متن استفاده می‌کند.

## ⚙️ چگونه کار می‌کند

</div>

```
 hook کلود/کدکس ─▶ تجزیه‌ی گفتگو ─▶ خلاصه (قاعده‌محور) ─▶ پاک‌سازی ─▶ entries/<project>/<area>/<date>-<author>-<tool>-<id>.md
                                                                              │ git commit، fetch، rebase، push (با تلاش مجدد)
                                                                              ▼
 پرامپت ─▶ BM25 روی مارک‌داون محلی (+ who-knows) ◀─ git pull ◀──────── مخزن team-brain شما
```

<div dir="rtl">

- **خلاصه‌سازی.** قاعده‌ها استخراج می‌کنند: چه خواسته شد، نتیجه، جمله‌های دارای نشانه‌ی تصمیم/دردسر (انگلیسی و فارسی)، کارهای باقی‌مانده، فایل‌های دست‌خورده، اندپوینت‌ها و دستورها. area (frontend / backend / infra / docs) از الگوی مسیر فایل‌ها می‌آید و در `.gonjineh.json` قابل تغییر است.
- **ذخیره.** یک فایل مارک‌داون برای هر جلسه که فقط نویسنده‌اش می‌نویسد؛ پس push های همزمان تداخل ندارند. ثبت دوباره‌ی همان جلسه فایل خودش را بازنویسی می‌کند. `INDEX.md` محلی ساخته و git-ignore می‌شود.
- **جستجو.** BM25 با وزن فیلدها، گسترش پیشوندی و نرمال‌سازی فارسی. بدون embedding، بدون daemon، بدون پایگاه‌داده. روی مجموعه‌ی کوچک امتیاز BM25 ریز است؛ پس hook ی هر پرامپت یک دروازه دارد: آستانه‌ی امتیاز *یا* دست‌کم دو واژه‌ی متمایز از پرسش در یادداشت.
- **همگام‌سازی.** commit، fetch، `rebase origin/<branch>`، push و تا ۴ بار تلاش مجدد. آفلاین هم مشکلی نیست: یادداشت‌ها محلی می‌مانند و در همگام‌سازی بعدی می‌روند. Codex در هر نوبت `notify` می‌زند؛ پس push آن ۴۵ ثانیه debounce می‌شود.
- **MCP.** `gonjineh mcp` یک سرور JSON-RPC روی stdio است: `search_memory`، `read_entry`، `add_note`، `who_knows_about`، `recent`.

## 🔒 حریم خصوصی و پاک‌ساز

پاک‌سازی روی همه‌ی فیلدها **پیش از هر نوشتن** اجرا می‌شود؛ پس رمزها هرگز به تاریخچه‌ی git نمی‌رسند.

- **همیشه ماسک می‌شود:** توکن‌های AWS، GitHub، GitLab، Slack، Stripe، Anthropic، OpenAI، Google، npm، SendGrid، Twilio، Telegram، JWT، کلید خصوصی، URL های دارای `user:pass@`، `Bearer …`، انتساب‌هایی مثل `password=` یا `secret=`، رشته‌های طولانیِ پرآنتروپی، و شماره‌کارت معتبر طبق Luhn (ارقام لاتین یا فارسی).
- **اطلاعات شخصی (به‌طور پیش‌فرض روشن؛ برای شل‌کردن در `.gonjineh.json` مقدار `"pii": false`):** موبایل ایرانی. **ایمیل ماسک نمی‌شود مگر `"mask_email": true` بگذارید.**
- **کنارگذاشتن یک جلسه:** در پرامپت `#private` یا `gonjineh:off` یا `#نهان` بنویسید؛ آن جلسه کلاً رد می‌شود.
- **کنارگذاشتن فایل‌ها:** `.brainignore` (سبک gitignore) مسیرهای منطبق را از یادداشت‌ها حذف می‌کند.
- **مخزن شما، کنترل دسترسی شما.** مخزن مغز را خصوصی بگیرید. یادداشت‌ها کد و تصمیم‌های شما را توصیف می‌کنند؛ دسترسی خواندن را مثل دسترسی خواندن به کد در نظر بگیرید.

پاک‌ساز الگو‌محور است و رمزهای با شکل غیرمعمول را از دست می‌دهد. تنها کنترل خود نکنید؛ بخش بعد را ببینید.

## ⚖️ محدودیت‌ها و صداقت

- **خلاصه‌ساز قاعده‌محور است، نه فهمنده.** استخراج و نقل می‌کند. بعضی یادداشت‌ها پرنویز خواهند بود یا اصل مطلب را از دست می‌دهند. پیش از اعتماد، با `gonjineh show <id>` بخوانید.
- **جستجو واژه‌ای است.** BM25 مترادف‌هایی را که واژه‌ی مشترک ندارند پیدا نمی‌کند.
- **پاک‌سازی در حد تلاش است.** همه‌ی رمزها و جزئیات شخصی را نمی‌گیرد و هر چه هم‌تیمی‌تان تایپ کند برای کل تیم دیده می‌شود.
- **راستی‌آزمایی ناقص است.** جدول بالا و [docs/VERIFICATION.md](docs/VERIFICATION.md). آزموده نشده: مدل زنده با کلید واقعی، ویندوز، macOS، remote واقعی GitHub (از bare repo محلی استفاده شد)، رفتار Cursor و Copilot، فایل‌های واقعی گفتگوی Gemini.
- **تنظیمات Codex سطح کاربر است:** `init --codex` فایل `~/.codex/config.toml` را در یک بلوک علامت‌دار ویرایش می‌کند (`uninstall --codex` پاکش می‌کند). hook های Claude سطح پروژه‌اند و commit می‌شوند.
- **تأییدها:** در Claude Code سرور MCP سطح پروژه تأیید شما را می‌خواهد؛ Gemini پوشه‌ی مورد اعتماد می‌خواهد.
- **هنوز CI ندارد.** توکنی که این مخزن با آن منتشر شد دسترسی GitHub Actions (workflow) نداشت؛ پس `.github/workflows` وجود ندارد. تست‌ها را محلی اجرا کنید: `pip install pytest && PYTHONPATH=src pytest tests`.
- **پروژه‌ی تازه (۰٫۱٫۰).** پیش از ۱٫۰ انتظار ناهمواری و تغییر قالب داشته باشید.

## 🔍 جایگزین‌ها

این حوزه شلوغ است و چند پروژه‌ی خوب دارد. **اگر یکی به کارتان می‌آید، از آن استفاده کنید.** نقشه‌ای ناکامل از جستجوی ۳ آبان ۱۴۰۵ (۲۰۲۶-۱۰-۲۵)؛ جزئیات و ملاحظات در [NOVELTY.md](NOVELTY.md):

| پروژه | شکل | تفاوت با gonjineh |
|---|---|---|
| **gitmem** (dev-boz) | حافظه‌ی تیمیِ همگام با git | نزدیک‌ترین؛ تفاوت‌ها و جاهایی که شاید برای شما بهتر باشد در NOVELTY.md |
| **team-memory** (blain3white)، **ai-memory** (akitaonrails) | حافظه‌ی مشترک عامل‌ها | انتخاب‌های متفاوت ذخیره و بازیابی |
| **TeamBrain**، **Krimto**، **Knowit**، **CrewMemory**، **Commonwealth** | حافظه‌ی تیمی/مشترک، گوناگون | چند مورد میزبانی‌شده‌اند یا سرور یا LLM دارند |
| **claude-mem-sync** | همگام‌سازی claude-mem بین دستگاه‌ها | روی ذخیره‌ی محلی دیگری بنا شده |
| **iHow Memory**، **mex** | ابزار حافظه / زمینه‌ی پروژه | هدف متفاوت (شخصی یا scaffold زمینه) |

شرط‌بندی `gonjineh`: **ثبت منفعل با hook ← خلاصه‌ی بدون LLM ← پاک‌ساز اجباری ← مارک‌داون ساده در git ← BM25 محلی**، در یک بسته‌ی پایتونِ فقط‌-stdlib که فارسی را شهروند درجه‌یک می‌داند. اگر embedding، رابط وب، همگام‌سازی میزبانی‌شده یا خلاصه‌ی نوشته‌ی LLM می‌خواهید، عمداً این‌ها را ندارد.

## 🗺️ نقشه‌ی راه

- آزمون با جلسه‌های زنده و remote واقعی GitHub و انتشار نتیجه.
- تجزیه‌گر واقعی گفتگوی Gemini پس از تأیید قالب، و ثبت برای Cursor/Copilot.
- `gonjineh prune` / نگهداری محدود، و خروجی HTML ایستا و فقط‌خواندنی از مغز.
- خلاصه‌ی اختیاری با LLM (پیش‌فرض خاموش، کلید خودتان)، فقط اگر پاک‌ساز جلوتر از آن بماند.
- انتشار روی PyPI و CI، وقتی توکن انتشار اجازه‌ی workflow بدهد.

## 🤝 مشارکت

PR های کوچک و صادقانه خوش‌آمدند: رمزهایی که پاک‌ساز از دست می‌دهد، قالب گفتگوی ابزارهای دیگر، خطاهای خلاصه‌ساز. [CONTRIBUTING.md](CONTRIBUTING.md) را ببینید. لطفاً هرگز رمز واقعی در issue نگذارید.

## 📄 مجوز

MIT © محمدرضا زارع. [LICENSE](LICENSE). برای ارجاع، [CITATION.cff](CITATION.cff) را ببینید.

</div>
