# Era of Nations 0.1.0 — initial development baseline

Current verification updated on 2026-10-09. Migration, division and missile results
are stated below; native probes retain their historical source scope. Earlier
diplomacy and publication entries do not establish acceptance of the full mod.

## Міграція, біженці та цивільна допомога

Трудові угоди тепер проводять парне переміщення населення між територіями
країни походження й приймача за дефіциту працівників. Старе безпарне
нарахування населення, дубль робочої сили й автоматичний дохід казни від
приватних переказів прибрано. Прийняття, повторна відповідь, скасування й
очистка трудових угод використовують точні взаємні записи партнерів.
Скасування припиняє новий найм і зберігає вже прибулих жителів.

Для всіх країн діє територіальний облік біженців із походженням, свіжими
прибуттями, інтегрованою й довгостроковою частинами. Потоки враховують війну,
окупацію, пошкодження, вільні місця й політику приймання; дальні маршрути
використовують наявні дипломатичні канали. Є часткове добровільне повернення
за тривалого миру та придатних контрольованих домашніх територій, а також
подальше переселення за перевантаження служб. Люди не копіюються при зміні
контролера території. Слоти походження цілі й сталі; реєстр зберігає повні
нативні country tokens та відновлює власний перезаписаний покажчик.

Додано три режими приймання, платне тимчасове розширення служб, показники
людей/місць/витрат і російські та англійські пояснення. Гуманітарний грант
100 млн потребує згоди отримувача й фінансує цільову цивільну допомогу,
зокрема у пошкоджених контрольованих регіонах країни у війні. Фонд реально
витрачається раз на тиждень; повторний виклик не списує платіж вдруге.
Справді новий тег не отримує копію успадкованого цільового фонду, а відновлення
слота існуючої країни зберігає її кошти. Чинні економічні гранти й борги
збережено; додано лише дві перевірки меж казни для старих грантів.

Вісім груп актуального джерела пройшли: 34 перевірки потоків/реєстру,
5 інтеграційних перевірок, 14 трудової угоди, 44 гуманітарної допомоги,
14 меж казни, 57 scopes чинної допомоги, 166 сценаріїв старої aid/debt
та перевірка меж нативних синтаксичних виправлень. У гуманітарній моделі
реєстрація є явно обмеженою межею вже зареєстрованих fixtures; її фактичний
AST виконують тести потоків і нативна проба. Це не повна історична cumulative suite.

Завершена проба98 в HOI4 1.19.3 підтвердила **70/70 перевірок** для
NEP/GER/FRA, окремої тестової території NZL та двох динамічних тегів.
Фактичний трудовий потік зменшує й збільшує STATE населення на рівну суму;
дальній приймач із 1 000 вільних місць прийняв рівно 1 000 людей. У реальному
місячному циклі 100 людей повернулися додому за частки контрольованих
домашніх територій 0.5; сумарна зміна світового STATE населення дорівнює нулю.
Підтверджено точну згоду на грант, одноразове списання фонду й незмінність
усіх шести ledger arrays трьох пробних територій під час створення тегів.

Перед внесенням модельованих успадкованих значень новий динамічний token
у пробі98 вже був зареєстрований. Перевірена нативна гілка — відновлення його
власного слота зі збереженням коштів; гілку очищення справді нового,
незареєстрованого скопійованого запису виконують фактичні AST-тести потоків.
Ранні проби92/94 виявили помилки fixture й потребу окремих цілих origin slots.
Проби96/97 зберігають невдалі очікування щодо повторно використаного або вже
зареєстрованого тегу; фінальні очікування прив'язані до стану реєстру до seed.
Пробу95, що завершилася до перевірок без діагностики причини, не зараховано.

PID152732 завершений, лаунчер відновлено, початкові settings/dlc_load збережено.
У нових скриптах немає пов'язаних помилок; успадковані графічні/звукові та
інші попередження мода не оголошено усуненими. Квитанції в
`.local/migration-relief/`: `native-98-result.json`,
`native98-evidence/confirmed-terminal-and-config.json`,
`source-validation-final-v2/receipt.json` і `final-source-and-native-seal.json`.

Трудова угода не надає автоматичного притулку, ПМП чи громадянства. Пауза
приймання не депортує людей. Числові коефіцієнти — калібрування мода;
індивідуальні юридичні процедури, транспорт кожного маршруту, старі нагороди
фокусів, кампанійний баланс, GUI, save/load та MP цим пакетом не підтверджені.
Опис, міжнародні джерела та ручні кроки: [MIGRATION_RELIEF_UK.md](MIGRATION_RELIEF_UK.md).

## Організація дивізій та полкова підтримка

Додано дві платні за оснащенням полкові артилерійські батареї: легку для
групи `infantry` та моторизовану для `mobile`/`armor`. Вони використовують
штатні нижні клітинки підтримки полку в HOI4 1.19.3. Стовпці — організація
полків; вертикальний порядок батальйонів не оголошено лініями бою.
Збережено штатну вимогу трьох сумісних батальйонів. Нова підтримка має
власні потреби в артилерії, управлінні, людях, постачанні й транспорті;
десять наявних артилерійських покращень охоплюють обидві батареї.

Виправлено дев'ять неправильних посилань/розміщень зенітних підрозділів
у шаблонах ШІ та прогалини заводських порогів. До чотирьох чинних типів
шаблонів ШІ й відповідних початкових шаблонів додано сумісні батареї.
До реєстру додано відсутню категорію полкової підтримки; з початкової
піхотної технології прибрано неіснуючий ванільний ID `infantry`.

Для гравця є коротка довідка із зображенням, двома додатковими сторінками
та підказками в конструкторі. Російський і англійський тексти входять у
пакет. Автоматичний показ — один раз за країну в кампанії, повторне
відкриття безкоштовне через рішення. Старі кампанії й перехід країни
від ШІ до людини мають щоденну перевірку першого показу.

Шість груп перевірок актуального джерела пройшли: 56 цільових шаблонів
ШІ й 548 посилань, заводські пороги, технологічні ID, дві нові батареї,
повний набір покращень, життєвий цикл довідки та сам тестовий сценарій.
Негативні варіанти джерела також перевірені.

Завершена приватна проба91 у **HOI4 1.19.3** підтвердила **28/28** умов
для **NEP/GER/FRA/RAJ**: реєстрацію шаблонів, реально розгорнуті підрозділи
обох нових типів, прапорець першої довідки для країни гравця й відсутність
такого прапорця у країн ШІ. Вісім додаткових спостережень показали, що
старий `has_template_containing_unit` не бачить нову полкову підтримку;
вони не зараховуються як успішні перевірки. Механіка моду від цього
лічильника не залежить. Нових помилок скриптів цього пакета не знайдено.
PID `123320` завершений, crash-файлів немає, лаунчер і початкові
налаштування відновлені. 21 ігровий файл звірений з перевіреною копією;
решта байтів GUI, BOM і завершення рядків локалізацій збережені.

Проби89/90 збережено як невдалі. Перша виявила відсутню категорію та
помилкову область створення військ у тесті. Друга підтвердила розгорнуті
батареї, але містила неправильні перевірки тестового сценарію; вони
виправлені до проби91. Це не приховується й не зараховується як прийомка.

Ці результати **не підтверджують** ручні обмеження клітинок конструктора,
вигляд і натискання вікон, бойовий баланс, повний save/load чи мультиплеєр.
Виявлена успадкована помилка `sub_unit_bonus` у надважкій піддоктрині
танків залишена окремою задачею: її виправлення потребує узгодженого
перенесення бонусів батальйонів і техніки, а не випадкової зміни балансу.

Опис і джерела: [DIVISION_DESIGN_UK.md](DIVISION_DESIGN_UK.md).
Відтворення перевірок: [README](../../tools/validation/division_design/README.md).
Квитанції в `.local/division-design/`: `native91-result-v2.json`,
`native91-evidence/confirmed-terminal-and-config.json`,
`final-source-checks-v3.json`, `final-source-bytes-v2.json`. Фінальний аналізатор
відхиляє відсутній журнал помилок; цей захист підтверджено негативним тестом.
SHA256 завершеного журналу91:
`0d956e5a07c17dea49772e7cc5f4d5fe2cff1f24336efccc642439aceda942fe`;
SHA256 квитанції запуску:
`41d94235fbeb7048683691b9c8b482f6a31328139d5d545d2c4f8914d0f98868`.

## Виправлення ракет збережено, неповне утримання вимкнене

За рішенням користувача прототип утримання вимкнений: меню й рішення
приховані, нова вартість дорівнює нулю, режими та відновлення не працюють.
Старі прапорці безпеки й відновлення не заважають запуску. Виправлення
досліджень, ракетних умов, списання одного достатнього типу запасу та прив'язки
відповідей ШІ збережено; національні заборони залишаються.

Поточні 18 груп перевірок джерела пройшли. Вони читають вимкнений readiness
із фактичного коду; негативні перевірки старих режимів явно вмикають лише
тестову модель прототипу. Це не підтвердження ігрової кампанії.

Завершена проба88 підтвердила **185/185 перевірок, 62 знімки** для
GER/FRA/RAJ/USA/SWI, включно зі справжнім тижневим викликом 10 січня:
вартість нульова, старі safety/recovery не блокують готовність і не
змінюються, виклики прототипу не витрачають запаси, кошти чи паливо.
Бюджет збігається з точною версією без арсенальної вставки; SWI сплатив
одну ракету з одного запасу. PID `107824` завершений без crash-файлів,
лаунчер відновлено, початкові налаштування збережено. Прототип залишається
вимкненим. Це не прийомка GUI, нальоту, `one_use_only`, повного save/load чи MP.

Квитанції в `.local/missile-system/`:
`disabled-upkeep-88/final-sealed-result.json` і
`default-off-source-checks-v2.json`. Фінальні 18 груп звіряють незмінний
enum baseline (639 старих позицій та два append-записи) й актуальні
метадані проби. SHA256 завершеного журналу88:
`5222547424a15aa393187bdbcfe96250b0057bafab4cb9cca4734b8dd523f02c`;
SHA256 квитанції запуску:
`37be6bb9ce77e3cc8c770fa32fd50e40390d43fa5b36d2fd2be77db8ac002812`.

Повний ракетний пакет ще не прийнято. Завершена приватна проба83 підтвердила
бюджетний цикл і списання запасу, але проби83/85 довели недорахування
фізично завантажених ядерних ракет. Деталі:
[MISSILE_SYSTEM_UK.md](MISSILE_SYSTEM_UK.md) та
[NUCLEAR_ARSENAL_UK.md](NUCLEAR_ARSENAL_UK.md).

| Історична проба | Прийнятий результат | Межа |
| --- | --- | --- |
| Бюджет/відновлення V4, проба83 | 132/132 | GER/FRA/RAJ, 4 справжні `on_weekly` по 168 годин; одна бюджетна стаття та захист від повторних викликів. Правильність deployed-кількості не підтверджена. |
| Повтор закупівель, проба83 | 10/10 | Скидання старої тимчасової суми в чинному ринковому блоці; не повний торговельний грошовий потік. |
| Спільний захист/оплата, проба83 | 18/18 | 9 перевірок `4 → 3 → 3` та 9 перевірок списання 1/10 ракет з одного достатнього сімейства. |
| Старт без Gotterdammerung, проба81 | 115/115 | Проєкція наявних технологій/пускових і повторний виклик адаптера; не ручне виробництво, ядерне дерево без DLC чи запуск ракети. |

У пробі85 на тій самій годині `2000.01.17.01` фізичний ядерний запас у
пускових дорівнює GER — 5, RAJ — 5, PAK — 200, USA — 150 коротких ракет.
Архетипні/модельні deployed-лічильники та колекції за ядерними категоріями
повернули 0. Тому відповідний статус і повний рахунок утримання
**не прийняті**, прототип вимкнений. Можливе виправлення обліку поки досліджується
окремо; історичні 132/132 не означають, що утримання активне в поточному моді.
Доказ: `.local/missile-system/count-candidates-85/same-hour-comparison.json`.

Квитанції83: `upkeep-83/result-final-strict.json`,
`market-repeat-83/final-native-read-v2.json` та
`latch-83/helper/joint-sealed-native83.json` у `.local/missile-system/`.
Квитанція без DLC: `non-got-81/result.json` у тій самій локальній папці.
Для завершеного PID `134768` SHA256 журналу —
`289c2d0269ab8b73bf79aaaed65f2216143f5a05e77149f25602ea7f31e03ce3`;
SHA256 квитанції запуску —
`acc3014ebd77562535640b81d7f79843b6d4456b8911ce75b27c475e064e9790`.
Початкову конфігурацію лаунчера відновлено, налаштування й вибір DLC гравця
збережено; попередні невдалі докази не переписані та не додаються до Git.

Ручний цикл GUI, фактичний наліт, витрата саме вибраного одноразового
боєприпасу, повна сумісність збережень і мультиплеєр залишаються
неперевіреними. Прийняті компоненти не означають завершення всього моду.

## Current diplomacy acceptance

The isolated HOI4 1.19.3.0.c01a probe 05 on 2026-10-08 completed frontend
loading with zero errors naming the 58 changed game files or the explicit
legacy diplomacy dependencies. Tested source hashes remained exact.
Probe 02 had recorded 201 matched error lines; a broader probe 03 check also
identified 34 cascading lines in the legacy aid event file. These syntax roots,
country-variable targets, opinion-query restrictions and faction-rule groups
have now been repaired. See [NATIVE_DIPLOMACY_119_UK.md](NATIVE_DIPLOMACY_119_UK.md).
Existing game settings and DLC selection were verified unchanged and the
temporary launcher configuration was restored.

Probe 05 also launched a fresh single-player campaign through the USA start
parameter and completed the mod's on_startup initialization, remaining alive
on pause. No contract execution, campaign accounting, save/load or multiplayer
session has been accepted. Probe 04 had ended after frontend loading without
an established exit cause; probe 05 has 33 inherited graphics, menu, music and
equipment log lines. The
complete objective and its remaining requirements are preserved in
[DIPLOMACY_COMPLETION_UK.md](DIPLOMACY_COMPLETION_UK.md).

The graphite/navy UI update is now installed. Its 109 sprite opt-ins and final
DirectX 11 startup passed mapping and compilation checks; visual acceptance of
the unobstructed menu and campaign controls remains pending. See
[UI_THEME.md](UI_THEME.md) for scope, receipts and exact limitations.
The existing diplomacy audit and twenty-three implementation packages have
historical source checks. Initial native startup contradicted their earlier
apparent parsing readiness; the current syntax corrections passed probes 04/05.
The earlier SCO rejection and Arctic observer
repairs are retained.
The first package reconciles NATO/CSTO/SCO membership and native exits,
repairs investment cancellation, debt assumption and operative ransom/exchange,
and gives the existing energy agreement a guarded proposal/response/execution/
revision/termination cycle. Reproducible source models and independent reviews
passed. The second package guards trade and mutual investment treaty proposals,
responses and bilateral cleanup, freezes foreign building proposals before
consent, rechecks execution conditions and repairs refunds. It retains existing
prices, political rules and separate storyline paths. The third package opens
ordinary defensive alliances without a great-power rank: a consensual diplomatic
proposal, a native template, current national rights, retained join thresholds,
defensive call guards and lifecycle cleanup. AI national alliance-desire modifiers
are retained. Current diplomacy source has now loaded in HOI4 after repairing
the errors described above; new-campaign acceptance, native callback timing,
actual accounting and save/load remain pending. See
[DIPLOMACY_PACKAGE_03_UK.md](DIPLOMACY_PACKAGE_03_UK.md),
[DIPLOMACY_PACKAGE_02_UK.md](DIPLOMACY_PACKAGE_02_UK.md) and
[DIPLOMACY_PACKAGE_01_UK.md](DIPLOMACY_PACKAGE_01_UK.md) for changes, checks and
runtime checklists. [ORDINARY_ALLIANCES_PLAN_UK.md](ORDINARY_ALLIANCES_PLAN_UK.md)
retains the original D1 audit; its source implementation is now package 03.
Standard no-DLC creator callback coverage, native rule composition and exact
selected-war treaty obligations remain runtime acceptance items. [DIPLOMACY_AUDIT_UK.md](DIPLOMACY_AUDIT_UK.md) preserves the earlier
baseline audit and subsequent priorities.

The fourth diplomacy package implements a bounded repair after the player's
report of rejected larger electricity exports. It covers signed quantity,
buyer/seller AI inputs, replacement capacity, partner selection, current cached
supplier-capacity rechecks and initial resets of contractual aggregates.
Fresh cumulative source models passed 4510 scenarios (4423 earlier plus 87 new),
with 27 new source assertions and the repeated package 03 source checks.
Final independent review completed with no unresolved P1/P2 findings;
the reported gameplay sale is unverified.
The old signed-volume AI acceptance cliff was reproduced for a human buying
from an AI supplier; GUI replacement limits affect both directions. The latest
cached balance is used without immediate global-generation recalculation.
The later package05 caps the former raw-GW bonus at 20 points; full
contract affordability remains unproven. No physical grid or new budget law is added.
See [DIPLOMACY_PACKAGE_04_UK.md](DIPLOMACY_PACKAGE_04_UK.md) for scope and runtime
acceptance criteria. [DIPLOMACY_ROADMAP_UK.md](DIPLOMACY_ROADMAP_UK.md) explains
why alliances came first and prioritises one existing energy negotiation cycle,
state support, consultations and mediation before broader new relations.

The fifth package develops the existing energy agreement into editable human
counteroffers, one automatic AI counteroffer, proposal withdrawal, draft reopening
and immutable reason notices. Active deliveries/payments persist until agreement;
counterdraft zero/reversal and stale responses are guarded. Contracts remain
explicitly indefinite. The bounded volume bonus cannot override every price or
budget concern merely through huge GW. Source scenarios, byte boundaries and
independent review passed 4620 cumulative scenarios (110 new) and 86 new source
checks. Two invalidated-response P2 findings were repaired and reproduced;
no unresolved P1/P2 findings remain. See [DIPLOMACY_PACKAGE_05_UK.md](DIPLOMACY_PACKAGE_05_UK.md).
Native GUI/callbacks, real AI choice, accounting and save/load still require
new-campaign acceptance.

The sixth package completes the existing one-time economic aid flow: frozen
5/15/35-billion tiers, paired draft/response reservations, donor-owned escrow,
explicit recipient consent, withdrawal, fresh cash/policy checks and refund
claims retained above the treasury cap. It repairs AI weights, restores only
identifiable older prepaid tiers, and keeps ambiguous legacy or disappeared
pairs retired while other partners remain available. Debt support preserves
its existing consent, national policies, 75PP cost and cash-funded settlement;
fresh sending guards, dead-partner cleanup, AI cooldown/affordability and
truthful frozen-ceiling descriptions are repaired. Aid and debt remain separate
consent flows. Cumulative source checks passed 4786 scenarios (166 new);
exact-byte boundaries cover five existing and nine new game files.
See [DIPLOMACY_PACKAGE_06_UK.md](DIPLOMACY_PACKAGE_06_UK.md) for limitations
and new-campaign acceptance. No diplomatic package has been run in HOI4.
The seventh package adds human-initiated bilateral economic consultations:
literal trade, electricity or support topics; free draft/cancellation, a single
10PP send cost, recipient consent/refusal, withdrawal and a 30-day active channel.
Its financial follow-up opens the existing separate grant draft under the
actual aid policy and funding checks. Forced pending expiry or structurally
invalid/missing-partner cleanup retires only the affected pair permanently;
other partners stay usable. Normal consistent channel
closure preserves independent contracts and pending support. Source models
passed 4942 cumulative scenarios (4786 previous plus 156 new), with 208
new source checks; 68,270 existing gameplay files remain byte-identical and
exactly seven new game files were added. Independent source review and native
documentation checks passed; native compilation, GUI, timers, scopes, AI,
save/load and campaign acceptance remain pending. See
[DIPLOMACY_PACKAGE_07_UK.md](DIPLOMACY_PACKAGE_07_UK.md).
The eighth package adds a bounded three-country mediation mandate. A human
initiator selects a specific opponent and a deescalation or humanitarian agenda
through targeted decisions. A 20PP send, explicit mediator consent and separate
opponent consent precede the 30-day mandate. Each participant can withdraw;
current war/neutrality, reciprocal identities, callbacks, expiry and annex
cleanup are guarded. No peace, access, territory or treasury effect follows
from the mandate. Forced unresolved cleanup permanently retires the A/M and
M/B channels; another eligible mediator remains possible. Source models passed
5151 cumulative scenarios (209 new), with 301 new source checks and
68277 preserved old gameplay files. Native compilation, decision/GUI
scopes, timers, AI, save/load and campaign acceptance remain unverified.
See [DIPLOMACY_PACKAGE_08_UK.md](DIPLOMACY_PACKAGE_08_UK.md).
Its procedural terms and revision are implemented in package09 below; actual
peace execution requires separate native multiwar/subject/faction acceptance.

The ninth package adds concrete procedural review of the mediation mandate:
six literal agenda/duration offers, separate M then B consent, free proposals,
unchanged accepted agenda/deadline while pending, and atomic 30/60/90-day renewal
after final consent. Every human participant can cancel the pending revision.
A single pre-clear hook in package08 protects outstanding original replies
before any base identity is erased; forced cleanup quarantines terms-only A/M
and M/B edges while package08 mandates retain their own independent rules.
Normal consumed replies allow successive review rounds. Orphan cancellation
and missing existing AI opinion weights were reproduced and repaired.
Source models passed 5289 cumulative scenarios (5151 previous plus 138 new),
with 292 new source/API checks. Exactly 68285 old gameplay files remain
byte-identical, one has the sole pre-clear hook, and eight new files were added.
These terms govern talks only. Binding peace, humanitarian access and delivery
monitoring require separate mechanisms and native acceptance. Native scopes,
timers, AI, GUI, save/load and campaign remain unverified. See
[DIPLOMACY_PACKAGE_09_UK.md](DIPLOMACY_PACKAGE_09_UK.md).

The tenth package repairs the existing native antiterror agreement. A paired
30-day proposal and fresh consent apply exactly one .05/-5/+5 contribution per
participant and partner. Native proposal/active termination costs remain 75PP;
the new free withdrawal belongs only to the original human sender. Existing
political AI weights remain weighted rather than becoming universal bans;
the original 120-day send cooldowns are now enforced for human sends too.
Termination and both old/new annex hooks reverse only identifiable pair
components, preserving other CT and AI command-power sources. Legacy active
flags are adopted without adding a second contribution; ambiguous old pending
pointers and unidentified historical bonus residues are not reconstructed.
Forced unanswered cleanup permanently retires only the known CT pair.
Six game files and one action are added; only two treaty actions and two annex
branch bodies change inside two existing files. The 31 existing paid delayed
operations remain byte-identical and are the next execution-lifecycle task.
Source checks passed 5401 cumulative scenarios (5289 previous plus 112 new)
and 178 separate new source/API checks; 68292 existing gameplay files and all
unowned bytes inside the two changed files remain exact. Independent review
closed duplicate completion/termination, annex residue, incoming withdrawal
and orphan cancellation findings.
See [DIPLOMACY_PACKAGE_10_UK.md](DIPLOMACY_PACKAGE_10_UK.md). Native GUI,
cost timing, scopes, timers, AI, save/load and campaign acceptance remain pending.

The eleventh package completes the existing 31 paid CT decision lifecycles:
25CP charged once, immutable territory owner, the original five-day delay,
fresh bilateral cooperation and national checks, one inherited random outcome,
individual free cancellation and measured CP refund claims. Existing >25CP
admission, 35-day native re-enable, all original visibility/AI/NOR rules and
virtual terrorism accounting tags remain unchanged. Cancelled records retain
the original timer lock; a seven-day unresolved watchdog or operator annex
retires only the affected per-country decision. Refund claims survive capacity
limits and stay owned by the payer after annexation. Negative observed native
credit moves clipped over-cap CP into the claim; native cap behavior is not yet
accepted. Old untracked paid decisions are not inferred or refunded. Exactly
31 blocks in one existing file change, 23 unrelated decisions and all unowned
bytes are preserved, and seven game files add 31 cancellation decisions.
Native diplomatic action IDs remain 65. Full source checks and independent
review passed 5541 cumulative scenarios (5401 previous plus 140 new in 23
groups), with 1381 separate new source/API checks and no new adapter cases.
All eight owned game-file hashes agree; 68299 unrelated existing gameplay
files remain byte-exact. See
[DIPLOMACY_PACKAGE_11_UK.md](DIPLOMACY_PACKAGE_11_UK.md). Native scopes, timers,
CP limits, GUI, AI, extinct-country variable persistence and save/load remain
unverified. Civilian satellite access is addressed by package 12 below.

The twelfth package develops the existing six civilian GNSS/COM actions:
actor-owned outgoing partner/kind/frozen-level records, fresh acceptance,
free withdrawal, a 30-day response window and a separate native revocation
reason. Pending records stay reserved until their response is consumed;
forced cleanup quarantines only that sender/partner/family route. Live
reciprocal provider IDs are canonical, cached tiers rebuild from those IDs,
and current-country bonuses use the original native cap tables. Zero,
invalid or weaker systems and direct war leave dormant consent without
foreign bonuses; service recovery cannot recreate a revoked agreement.
Existing COM demand now sums all recipients' 100 receivers per controlled
state. Two files change only inside six civilian action and five civilian
effect blocks; seven game files are added. All 65 native action IDs and
military/SPY behavior remain unchanged. Full source checks passed 5647 cumulative
scenarios (5541 previous plus 106 new in 23 groups), with 347 separate new
source/API checks and no new adapter cases. All nine game-file hashes agree;
68305 unrelated existing gameplay files remain byte-exact. The existing full
COM traffic-stat calculation retains its weekly schedule. See
[DIPLOMACY_PACKAGE_12_UK.md](DIPLOMACY_PACKAGE_12_UK.md). Unknown old outgoing
pointers remain conservatively locked; native scopes, timers, arrays,
modifiers, GUI/AI/save-load and campaign acceptance are unverified. Existing
COM traffic/base guards and shared cooldown need separate follow-up.
Correction after package 13 audit: capacity already summed qualifying tiers;
the earlier overwrite claim was incorrect. Its capacity arithmetic is preserved.

## Diplomacy package 13

The remaining twelve native military GNSS/COM/SPY and civilian SPY access
actions now use separate actor-owned proposals, frozen provider levels,
fresh acceptance, withdrawal, reciprocal canonical IDs and current bonuses.
Revocation removes the exact provider; dormant consent gives no foreign benefit.
Existing native IDs, costs, AI policy and historical cooldown flags remain.
The original positive-tier rule is extended only for a working tier0 provider
with a positive native satellite count; its benefit uses the native tier0 cap.
The original provider>=recipient comparison and rules for tiers1–7 are retained.
Military COM demand counts each consenting recipient once, checks military
overload and clears stale service at zero capacity. Both zero coverage maxima
use explicit guarded zero coverage. Negative SPY weather benefits use the
native lower cap. Capacity sums and the weekly COM stats schedule are retained.

The cumulative source run passes 5932 scenarios (5647 previous plus 285
new actual-source traces) and 656 new source/API checks; no new adapter cases.
Nine gameplay file hashes agree and 68312 unrelated old gameplay files are
byte-exact. The previous capacity-overwrite description has been corrected;
the append-only archive of prior evidence is preserved. See
[DIPLOMACY_PACKAGE_13_UK.md](DIPLOMACY_PACKAGE_13_UK.md).
Native scopes/timers/arrays/modifiers/UI/AI/save-load and campaign acceptance
remain unverified. The civilian GNSS/COM tier0 ban and old SPY weather
base/COM AI predicates were deferred at this stage and addressed by package14.
Unknown legacy callbacks, shared COM cooldown and immediate traffic/base
freshness remain open. No game, saves, launcher or Workshop changes were made.

The fourteenth package admits working first-generation civilian GNSS/COM
services using positive corresponding satellite counts in current system stats,
and applies their native tier0 bonus caps. It fixes the negative SPY weather
base interval and adds explicit nonpositive-capacity branches to two projected
COM AI predicates. Positive-capacity arithmetic, traffic thresholds, native
action IDs/weights, proposal/consent lifecycle and weekly stats cadence are retained.
The native documentation gives divide_temp_variable a default if_zero=0;
the reproduced defect was a permissive AI traffic result, not a proven crash.
Fresh checks passed 6026 cumulative source-model scenarios (5932 earlier plus
94 new actual-source scenarios),
with two adapter checks counted separately and 108 new source/boundary checks.
Six existing game files changed in nine blocks/eight locale lines; 68,315 others
remain byte-exact. Historical assertions remain enabled through narrow byte
restoration, with two old absent-system fixtures made explicit about zero inventory.
Independent review binds the current six game hashes. See
[DIPLOMACY_PACKAGE_14_UK.md](DIPLOMACY_PACKAGE_14_UK.md).
Game acceptance remains pending. The shared COM cooldown and event-driven
traffic/base freshness deferred here are addressed at source level by package15;
unknown legacy callbacks retain their prior limitations. No game, saves,
launcher, Workshop, DLC, source ZIP or attribution changes were made.

The fifteenth package separates new civilian/military COM actor-owned 180-day
AI cooldowns while retaining old shared flags until natural expiry. It updates
own native COM data before known proposal/response checks and refreshes a bounded
provider/client neighborhood on consent, revocation, daily and level-selection
hooks. All own bases precede aggregate bonuses; foreign aggregates are not lent
again. Active service, client load and AI current-client detection share reciprocal
consent, live/level/peace and positive physical-capacity checks. Signed unavailable
service is dormant; positive-capacity overloaded service still counts client load.
Native own weak floors, higher-tier sending rights, unit/state weights and full
weekly update/news/downgrade remain unchanged. AI prospective traffic now covers
the current 1–1.249 gap and does not double-count active existing clients, retaining
the >1.249 threshold and native scoring weights. Four EN/RU granted rows reflect
active recipients. Fresh checks passed 6148 cumulative source-model
scenarios (6026 prior plus 122 new actual-source scenarios), separately
2 adapter semantics cases and 155 new source/boundary checks.
Eleven existing game paths contain
20 changed blocks within 22 allowed boundaries/six helpers/four locale rows;
68,310 other game files are exact. The two original revoke bodies are preserved.
All 106/285/94 previous satellite scenarios remain enabled with physically coherent
fixtures executing current game code; narrow historical byte views affect source
assertions only. Independent review binds all eleven gameplay hashes. See
[DIPLOMACY_PACKAGE_15_UK.md](DIPLOMACY_PACKAGE_15_UK.md).
Native execution, performance, AI choice, timers, arrays, modifiers, GUI, annex and
save/load still need new-campaign acceptance. Unhooked raw orbital/unit/control
changes update daily; no instantaneous global atomicity is claimed. Old request/
offer cooldown ownership asymmetry remains; it is soft AI scoring, not a human
termination ban. No game, saves, launcher, ZIP, Workshop, DLC, playsets or attribution
changes were made. Next: accept existing service cycles in game and extend the
verified lifecycle to other existing diplomatic agreements/support.

The sixteenth package develops the existing 100,000-unit `Send_ammo` offer:
donor-owned reservation, explicit recipient consent, fresh supply-node storage,
withdrawal, exact-once credit/refund and unpaid refund claims. One outgoing offer
per donor does not lock other incoming donors. Known forced cleanup retires only
the unresolved directed pair; unknown or incomplete records conservatively close
the donor's ammunition channel. Annexation queues held ownership for the successor
without changing ordinary ammunition inheritance or paying before its native hook.
The inherited political AI weights remain, with one technical readiness gate.
Official ATT and ICRC sources inform the procedural design; export licences,
embargoes, humanitarian-risk assessment and historical treaty participation are
not implemented. The ATT's 2014 entry into force is not backdated to the 2000 start.
See [DIPLOMACY_PACKAGE_16_UK.md](DIPLOMACY_PACKAGE_16_UK.md).
Fresh cumulative checks pass 6240 source-model scenarios (6148 prior plus 92
new in 32 groups), with one separately counted adapter case and 142 new
source/boundary checks (125 source/API plus 17 memory-only boundaries).
Three existing and seven new game paths are bound by matching source/behavior
hashes and independent review. All 65 existing action IDs and 41 prior
behavior/helper/runner files remain unchanged; one withdrawal action and 14
bilingual keys are added. Fourteen strict historical source adapters use narrow
prior-byte views and account for the exact new ID; current behavior proofs are
not bypassed.
Native UI, country-ID resolution, callback order, AI, timers, annexation and
save/load need new-campaign acceptance. Complete pre-upgrade ammunition offers
before upgrading an existing campaign; their unrecorded ownership cannot be
reconstructed. No game, save, launcher, Workshop, DLC, playset or attribution
change is part of this package. Next: existing logistics/reconnaissance aid and
foreign support, then permanent diplomatic relations; the current broad peace
helper needs a separate war/authority audit before executing mediation outcomes.

## Diplomacy package 17

The seventeenth package develops the existing paid logistics and reconnaissance
choices in influence.501. New responses own a concrete supplier, recipient and
service; the old unsigned influence.506 cannot establish a new paid agreement.
Acceptance checks the payer's funds, full supplier credit and current conditions
before applying the original 3/4 upfront fee, 80-day idea and political effects.
Unaccepted withdrawal is free. Active cooperation records its supplier; either
party can end the selected service type in both matching directions. Other
partners, service types and pending offers remain separate.

Official pre-2000 logistics and classified-information agreements inform the
procedural design. Their country-specific legal regimes are not universal game
rules. The original upfront fee has no proportional early-termination refund;
actual freight, personnel capacity, disclosure controls and full performance
accounting remain future work. See
[DIPLOMACY_PACKAGE_17_UK.md](DIPLOMACY_PACKAGE_17_UK.md).
The cumulative runner passed 6413 source-model scenarios (6240 retained,
173 new in 61 groups), 2 separate scoped-temporary adapter checks, and
180 new source checks (164 API/structure + 16 memory-only byte-boundary
mutations). All 43 older behavior/helper/runner Python files remain raw-byte
unchanged; 15 historical source validators retain their assertions and counters
through exact byte journals. Typed logistics/recon response events prevent an
old response of the other service type from closing a new proposal for the same
pair; arbitrary consumed same-pair/same-type replay lacks a native generation
token and remains outside the proof. Native engine acceptance remains
outstanding. No game launch or changes to saves, launcher configuration,
Workshop files or playsets are made here.

## Diplomacy package 18

The eighteenth package develops only the existing cash choice AB_mobilization.4.c.
The initial 50-PP/360-day request and troop/equipment/refusal choices are
byte-unchanged and remain separate unfinished work. A donor now offers a
specific 7-unit grant; the recipient explicitly approves it before a guarded
provider-side commit preserves the original ROOT-sensitive influence context.
Fresh funds, complete recipient credit, original political eligibility and
pair identity are checked before one transfer. Withdrawal before consent,
decline, timeout, malformed-record cleanup and annex hooks do not pay money.

Official historical cash-assistance and diplomatic-request documents inform
the procedure. UN Charter Article 51 is defensive-war context, not authority
for an automatic worldwide grant. There is no purpose-use audit, escrow,
guaranteed future payment or debt. The initial request flag does not prove
its generation; expired unresolved cash pairs are permanently retired and
unknown records quarantine that donor cash channel only. Native acceptance
and arbitrary consumed same-pair replay across a later identical offer remain
outside proof. See [DIPLOMACY_PACKAGE_18_UK.md](DIPLOMACY_PACKAGE_18_UK.md).

The cumulative runner passed 6539 source-model scenarios (6413 retained,
126 new in 25 groups), 4 separate defensive-war fixture adapter checks,
and 147 new source checks (130 API/structure + 17 memory-only byte-boundary
mutations). All 45 older behavior/helper/runner Python files remain raw-byte
unchanged; 16 historical source validators retain assertions and counters
through exact byte journals. Gameplay, validation, source-run and independent
review receipts are bound by hashes. Native engine acceptance remains pending.
No game launch or changes to saves, launcher configuration, Workshop files
or playsets are made here.

## Diplomacy package 19

The nineteenth package develops only the existing equipment choice AB_mobilization.4.b.
A donor freezes a nonempty subset of the nine original full-size equipment
packets actually available in stored-count guards. The recipient approves that
specific list; all selected packets must still be fully stocked and politically
eligible before any provider-side native dispatch call. Quantities cannot shrink
silently, and newly available unselected types cannot be added after consent.
The original provider ROOT/recipient FROM influence call remains +3 after dispatch.

The initial 50-PP/360-day request, troop/cash/refusal choices, all mercenary paths,
the old AB6 event and its localization remain byte-unchanged. Own notices describe
a dispatch order rather than claiming delivery. Withdrawal before assent, decline,
expiry, malformed-record cleanup and both annex hooks cannot send equipment.
Known unresolved pairs retire only their directed equipment channel; unidentified
partners or unowned partial fields quarantine only the donor equipment channel.
The cash channel and other agreements remain separate. Consumed same-pair callbacks
across a later identical record still lack a native generation-token proof.

Official dated GAO and FRUS material informs stock availability, precise agreed
items and the distinction between authorization, shipment and delivery. Historical
draft notes are not treated as executed universal agreements. The frozen subset,
packet sizes, ranks and 30-day window remain game choices, without a full export
control, end-use monitoring, parliament or legal-conflict assessment system.
See [DIPLOMACY_PACKAGE_19_UK.md](DIPLOMACY_PACKAGE_19_UK.md).

The cumulative runner passed 7171 source-model scenarios (6539 retained,
632 new in 23 groups), 37 separate stock-query and dispatch-observer checks,
and 202 new source checks (184 API/structure + 18 memory-only byte-boundary
mutations). All 511 nonempty manifests are covered. All 47 older behavior/
helper/runner Python files remain raw-byte unchanged; 17 historical source
validators retain assertions and counters through exact byte journals.
Gameplay, validation, source-run and independent review receipts are hash-bound.
The ordered observer records native send calls without inventing stock debits,
recipient credit, variant selection, transit or delivery completion. Native
inventory conservation and in-game acceptance remain pending. No game launch or
changes to saves, launcher configuration, Workshop or playsets are made here.

## Diplomacy package 20

The twentieth package repairs AB_mobilization.4.a as an offer to equip one
recipient-national defence formation. The recipient supplies its own 5480
personnel; the donor supplies 1623 infantry equipment, 150 command equipment,
36 artillery, 76 ATGM and 50 MANPADS. These nominal full-template amounts are
recomputed from the retained six infantry/two artillery/recon/engineer composition.
Donor manpower is no longer charged. Recipient assent precedes all resource calls;
hidden provider ROOT execution rechecks both countries, all inputs, recipient
controlled-owned states and reserved-template ownership before consuming the record.

The formation order assigns the recipient as owner and uses an isolated locked template.
Only an owned existing reserved template can be reused, without editing it.
This is irrevocable national formation support, not a sending-state contingent
or UN peacekeeping mission. There is no new automatic war entry, unit transfer,
peace-time deletion, survivor return or foreign military access. The old AB5
acknowledgement is inert and can no longer create free units. Existing legacy
units and costs are not automatically migrated or refunded.

The original request, equipment19, cash18, refusal, mercenaries and legacy
peacekeeper idea remain unchanged. Only AB4.a and AB5.a are edited in the war
file, with AB4.a and AB5 title/description display strings in English/Russian;
existing IDs, AI, influence invocation, BOM and line endings are retained.
Pending reply/withdrawal/expiry/annex cleanup belongs only to this proposal channel.
Same-pair identical later-record callback generations remain outside the proof.

GAO's dated 1997 Bosnia Train and Equip report supports recipient national-force
assistance as a distinct category. NATO SOFA informs why recipient-owned units
must not be described as a foreign sending-state contingent. The quantities,
30-day reply period, ranks, defensive-war access and initial experience remain
game choices; transport, delivery, training and full readiness are not simulated.
See [DIPLOMACY_PACKAGE_20_UK.md](DIPLOMACY_PACKAGE_20_UK.md).

The cumulative runner passed 7293 source-model scenarios (7171 retained,
122 new in 25 groups), 29 separate adapter semantics checks,
and 155 new source checks (134 API/structure + 21 memory-only
byte-boundary mutations). All 49 older behavior/helper/runner Python files
remain raw-byte unchanged; 18 historical source validators retain assertions
and counters through exact byte journals. Gameplay, validation, source-run
and independent review receipts are hash-bound.
Native resource debits, stock aggregation, create_unit filling, possible extra
engine charges, placement, AI, timing and save/load still need in-game acceptance.
Observers record actual commands only. No game launch or changes to saves,
launcher configuration, Workshop or playsets are made here.

## Diplomacy package 21

The twenty-first package replaces only influence.501.c's broken Grey Men route
with a donor-funded military advisory and training agreement. The donor spends
the existing 1.5 treasury amount once after recipient consent and a current
budget/political/ownership check. There is no recipient cash credit or separate
contractor bank model. The retained 60-day service uses an isolated idea with
the same training-time, planning and special-force-cap bonuses. No new unit,
template, stock or manpower commands represent this abstract service.

Paired incoming/outgoing records identify the provider and client. One provider
can sponsor one programme; one recipient can receive one such programme.
The original influence macro retains recipient ROOT/provider FROM; the 4-point
military-faction reaction remains internal provider politics. Current entry
policy, GUI cooldown, national restrictions and valid refusal reaction are
retained. Proposal withdrawal is free before assent. Either party can end
matched cooperation; if both sponsor each other, both matched directions end.
Other partners and pending proposals stay separate. Paid services end at 60 days,
peace, direct war, withdrawal or disappearance, not merely changed entry rank
or government. The fee is a nonrefundable start expense under declared game rules.

Old 502a/b, 503a and 505a become inert acknowledgements. The old grey_men idea
loses only its global 505 broadcast; its shared-template deletion stays exact.
Legacy costs, units and flags have no automatic migration or survivor refunds;
unidentified legacy missions may block this new service. Unresolved expired
proposal pairs remain retired and unknown records quarantine this channel;
later identical same-pair callback generations remain outside the proof.

Exactly 16 game paths change: five named influence options, one old idea-hook
fragment, six existing English/Russian display files and eight new adviser files.
Other existing bytes, IDs, BOM/EOL, logistics/recon services, state cash/equipment
support, the national formation and domestic mobilisation remain preserved.
The dated GAO 1997 private training contract informs this category; Protocol I
Article 47 informs its distinction from combat mercenaries. This does not certify
legal authority, procurement, contractor status or real training outcomes.
See [DIPLOMACY_PACKAGE_21_UK.md](DIPLOMACY_PACKAGE_21_UK.md).

The new reply uses game-design AI weights 100/10 for acceptance/refusal;
an invalid pending proposal retains a positive-weight closing choice.
Legacy 502 retains its raw 100/0 metadata inside inert acknowledgements.
Entry policy and GUI are preserved; native AI behavior remains unverified.

The cumulative runner passed 7414 source-model scenarios (7293 retained,
121 new in 33 groups), 18 separate adapter semantics checks,
and 190 new source checks (163 API/structure + 27 memory-only
byte-boundary mutations). All 71 prior public validation files outside the
journals remain raw-byte unchanged, including 51 older behavior/helper/runner
Python files; 19 historical
source validators retain assertions and counters through exact byte journals.
Three effective military-aid menu tooltip rows now describe equipment,
logistics, intelligence and advisory support without promising a mercenary
brigade, an ideological exception or automatic bilateral opinion changes.
The unused Russian base tooltip is retained beneath the corrected replace
locale; the native merged locale still requires in-game acceptance.
Five firsthand RED regressions now pass GREEN. Gameplay, validation,
source-run and independent review receipts are hash-bound.
Native treasury, idea bonuses, event/action scopes, AI, timers, annexation and
save/load require HOI4 acceptance. No game launch, save, launcher or Workshop
changes are performed. The existing initial aid request remains the next
consistency step before new permanent diplomatic relations and representations.

## Diplomacy package 22

The twenty-second package gives the existing AB_ask_foreign_support action
an identified initial request, a 30-day review window and a guarded single
handoff from AB_mobilization.4. The provider stores one requester's positive
country ID and owns one pending review slot; a requester may approach several
different providers. Formation, equipment and cash choices consume that initial
record before opening one unchanged separate offer from packages18-20. Those
offers retain their own recipient consent, current resource checks and execution.
The initial request itself transfers no resources and grants no military rights.

The native 50PP cost and directed 360-day cooldown remain declared once.
There is no extra manual debit or invented PP refund. Fresh completion checks
policy, identity, cooldown and slot state; repeated or stale callbacks cannot
create an additional menu for the current record. Free requester withdrawal,
matching guarded refusal, daily expiry and both annex hooks clear only the
initial request. Active support, independent offers and other partners remain
separate. Cancelled identity persists until matching closure or cleanup.

Exactly11 game paths change: one native action, four named AB4 menu choices,
six named rows in each English/Russian decision locale and seven new files.
The three child trigger/effect sources retain their legacy internal API contracts
byte-for-byte; owned22 checks belong to the actual user entry and menu router.
Old unowned AB4 windows cannot initiate new offers, while existing child offers
continue their own cycle. Old action/menu AI metadata and game IDs/BOM/EOL remain.

Actual FRUS1947/1950 bodies inform the distinction between requests, programme
assessment, bilateral terms and delivery. These are dated US examples, not a
universal administrative law. UN Charter Article51 does not itself make every
request an automatic grant or war-entry obligation. Rank restrictions, defensive
war, opinion,50PP,360/30days and one review slot are game policy choices.
No permanent pair ban is added; an ancient same-pair popup during a later renewed
request cannot be distinguished by an immutable event token and remains outside
the source proof. See [DIPLOMACY_PACKAGE_22_UK.md](DIPLOMACY_PACKAGE_22_UK.md).

The frozen cumulative run passed 7508 scenarios:7414 historical-caller
compatibility scenarios and 94 actual current22 scenarios in 28 groups.
Separate checks passed 28 adapter semantics cases and 164 source
checks (136 API/structure and 28 exact byte boundaries). Six original
public regressions were captured RED and repeated GREEN. All74 prior public
files outside the20 literal source journals remain raw-exact, including53
behavior/helper/runner Python files. Source/review/documentation hashes are
bound before publication.
Native action cost timing, scopes, windows, AI, timers, annexation and save/load
require HOI4 acceptance. The game was not launched; saves, launcher and Workshop
were not changed.
The next planned design is permanent diplomatic relations and representations.

The7414 preceding scenarios are explicitly compatibility coverage. Only older
package18-20 behavior callers receive exact baseline AB4.a/b/c byte views;
unchanged child helpers and scenario assertions still execute. Current22 cases
execute the new owned entry/router and all three child continuations separately.
This historical caller adapter is not proof of the current22 initial entry.
Historical source validators still inspect current bytes with exact journals.

The twenty-third package repairs the existing PER_talks_with_the_americans
to USA iranian_focus.64 national restoration route. A reciprocal positive-ID
request, fresh national policy and directed no_ties markers, one-use issuance,
30-day review, guarded acceptance/refusal, free withdrawal and initial-only
daily/annex cleanup replace the former unowned response. Agreement is recorded
on both sides once; only reciprocal no_diplomatic_ties is removed. All historical
grievances remain. Existing friendship and +2 influence macro parameters remain
explicit national political terms, not generic effects of diplomatic relations.
The inaccurate AI tooltip no longer guarantees sanctions reconsideration at 20
or a 20 percent improvement; sanctions and USA AI sources remain unchanged.

Official 1999/2000 State bodies establish the Iran/U.S. historical discontinuity,
while Vienna Article 2 supplies mutual-consent context. Articles 4/13 staff/head
steps remain separate future work. Historical main-convention ratifications
predate 2000; no optional-protocol or full legal-compliance claim follows.
This is a counterfactual result of an existing national story, not a claim that
embassies actually reopened in 2000. Missing new receipt never means absence of
worldwide relations, and other existing national normalization routes remain.
The receipt records this agreement once, not comprehensive current live state.
No buildings, staff, credentials, protecting-power transfer or worldwide mission
system is implemented. 30 days/one-use issuance are mod choices. Old same-pair
pre-upgrade or forged callback aliasing remains outside the native proof.

The frozen cumulative run passed 7655 scenarios: 7508 prior and 147
actual current package 23 scenarios in 30 groups. Separate checks passed
12 adapter cases and 152 source checks (127 API/structure,
25 exact byte boundaries). Root captured five original assertions
RED and repeated the same entries GREEN on frozen game sources. A separate
candidate withdrawal-provenance finding was reproduced RED and repaired
GREEN; the five baseline and one candidate defect receipts remain distinct. All 77
prior public files outside 21 literal source journals remain raw-exact,
including 55 behavior/helper/runner Python files. No new historical behavior
projection was added; prior package 22 retains its explicitly scoped 7414 historical
caller compatibility and 94 current-entry cases. Exact game/source/doc
hashes and independent reviews are bound before publication.
See [DIPLOMACY_PACKAGE_23_UK.md](DIPLOMACY_PACKAGE_23_UK.md).
Native scopes, response timers, windows, AI, actual influence, annexation and
save/load require new-campaign acceptance. The game was not launched; saves,
launcher and Workshop were not changed.

The separate Shift+R feature enables existing mod cheat decisions for the
player's country even with both global cheat rules disabled. A second press
disables the personal override and restores normal rule-based access; it does
not change global rules or another player's access. The native console is not
unlocked. All multiplayer participants need the same mod version. See
[CHEAT_HOTKEY_UK.md](CHEAT_HOTKEY_UK.md) for usage and acceptance steps.
Current source/model checks passed 28568 assertions (including 28160 visibility
truth-table rows) and 179 byte checks. All 102 previous validation files remain
raw-exact. Current scoped package 22/23 behavior models also passed 94/147
scenarios. The earlier cumulative 7655 result belongs to diplomacy commit
79c35a0673186223256a5146e7e2bb6809f5fe5f; it was not rerun against this new
feature. The dated whole-game source inventories retain their original closed
scope. Native Shift+R routing, button layout, multiplayer synchronization,
cheat execution and save/load remain unverified; the game was not launched.

## Completed setup

- Imported all 74,465 source files directly into `E:\Era of Nations`; the archive
  wrapper directory was removed and ZIP CRC checks passed during extraction.
- Renamed both mod descriptors, removed the inherited Workshop ID, and retained
  all source `replace_path` directives and HOI4 `1.19.*` compatibility metadata.
- Registered a private local **Era of Nations** playset and enabled only this
  mod. Existing playset memberships and all 10 DLC selections were preserved.
- Updated 104 visible localisation values across 36 files. Keys, UTF-8 BOMs and
  line counts match the imported source. No full upstream brand remains in
  quoted localisation values.
- Installed the new logo, cover, music/radio sheets and icons. Native image
  sizes, alpha and file formats passed validation; see [BRANDING.md](BRANDING.md).
- Retained original authors and all four music credit files byte-for-byte;
  moved visible upstream notices into the attributed source archive documents.
- Connected `origin` to `Sany0ssse/Era-of-Nations`, branch `main`. Initial GitHub
  publication uses five successive asset batches without Git LFS. The final
  publication receipt is local in `.local/publication-result.json`.

## Actual game startup

HOI4 **1.19.3.0.c01a** was launched with the local descriptor. Its fresh
`system.log` reports **Active Mod Count: 1** and **Active Mod: Era of Nations**.
`setup.log` records a completed frontend startup at game date 2000.01.01.
The game process remained responsive after startup.

This confirms startup and mod selection. An unobstructed screenshot of the game
menu, starting a country, and campaign simulation have not been accepted yet.
Existing saves were not opened or changed. Local log receipts are in
`.local/runtime-check/` and launcher backups are in `.local/launcher-backups/`.

## Inherited issues to investigate next

The startup log contains inherited errors. Targeted checks confirmed that the
affected gameplay files match the supplied ZIP; the frontend differs only in
project promotional controls and links.

- The inherited frontend omits the `change_background` GUI type and background
  selection controls expected by the current game. The engine explicitly warns
  that opening that feature may crash. Do not use the background selection
  feature until its compatibility is repaired.
- `common/doctrines/subdoctrines/land/land_equipment.txt` contains a rejected
  `sub_unit_bonus` token; unit/Special_Forces references also report errors.
- Some mesh/entity, landmark, radio-song and particle references are missing or
  duplicated in the source.
- The earlier generated `gfx/main_menu/main_menu.dds` fallback has been removed;
  the static sprite directly references existing `gfx/loadingscreens/load_1.dds`.
  The final restart has no former missing-path message, but still reports two
  binary-token parse errors for that DDS. The inherited frontend lacks the
  current game's root background and selector types; the exact internal parser
  call is unverified. This compatibility issue remains unresolved.

No observed startup error names the replaced Era of Nations textures or changed
localisation syntax. This is a development baseline for further work; campaign
stability and Steam Workshop readiness remain unverified. Workshop publication
is deferred by the user.
