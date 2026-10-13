# Дипломатичні представництва в меню країни

Запуск із кореня моду:

```powershell
python -B tools/validation/diplomatic_relations_ui/test_menu.py
```

Перевірка читає 20 нових дипломатичних дій і незмінні рішення, triggers та effects пакета26. Вона порівнює точні AST підготовки, видимості, доступності й виконання: початковий `FROM → PREV` у рішенні замінюється лише переходом `ROOT` у дипломатичній дії. Основний frame дії має `THIS = адресат`, `ROOT = гравець`; `FROM` навмисно позначає третю країну. Невідомі команди в строгому старому evaluator не пропускаються. Локальний adapter додає булевий `is_ai` для людської доступності та строго розгортає лише нову обгортку `custom_trigger_tooltip → hidden_trigger` з `tooltip_evaluation = eval`. Вона залишає точний старий ROOT trigger і тимчасові параметри, але замінює технічний перелік умов зрозумілою підказкою. Зайві приховані вузли, інший scope або режим оцінювання відхиляються; старі файли перевірок не змінюються.

Повний чинний `test_relations.main()` виконується двічі. Другий запуск використовує нове дипломатичне меню замість decision dispatcher. На кожному виклику порівнюється точний durable стан усіх країн, грошей, PP, flags, deadline, records, arrays та інших угод із виконанням старого рішення. Для інформаційних подій порівнюються ID, країна одержувача та ROOT; недокументоване `FROM` доставки подій не проголошується підтвердженим.

Окремі тести перевіряють позитивну досяжність усіх20 дій, три перестановки GER/GRE/USA, AI-категорію, відсутність постійних мутацій від наведення, одноразову плату відправника після згоди, точні пороги10 PP та0.01/0.02, щомісячну обслугу, прострочені й змінені kind/level/head, повторний або примусовий callback, зникнення країни, війну та self-target. Шість нових текстових статусів порівнюються зі старими для напрямлених записів; EN/RU engine keys, aliases, BOM/CRLF і числові ROOT/THIS getters перевіряються окремо. Навмисні mutants показують, що помилковий scope, пропущений type guard або змінена обгортка справді змінюють результат чи відхиляються. Дипломатичний запис має просту підказку; його повний динамічний стан відкривається через `status_send_desc`. Інші 19 підстановок збережено без зміни. Окрема перевірка відхиляє непарні або неіснуючі підстановки `$KEY$` у нових UI-текстах. Поточний runner має 16 тестів.

Старі20 decision bodies залишаються для AI; їхні перевірки не потрібно послаблювати. `diplomacy_package_26/test_source.py` продовжує перевіряти старий `FROM → PREV` і не охоплює нові action файли самостійно. Повний runner26 також містить Git baseline checks. Додатково ROOT запускає:

```powershell
python -B tools/validation/diplomacy_package_26/run_checks.py
python -B tools/validation/diplomacy_completion/check_localisation.py
python -B tools/validation/diplomacy_completion/check_native_grammar.py
python -B tools/validation/diplomacy_completion/check_integration_sources.py
```

`diplomacy_completion/run_checks.py` є ширшою регресією інших систем та Git; це окремий aggregate, його кількість перевірок не додається до нового menu runner. Новий runner лише друкує JSON, не запускає Git/гру, не змінює мод, launcher, saves або Workshop. Source/model PASS не підтверджує нативний клік, rendering, AI response scheduling, кампанію чи multiplayer — це треба перевірити в грі окремо.
