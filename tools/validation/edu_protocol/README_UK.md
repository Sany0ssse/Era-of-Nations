# EDU: перевірка production source та межі native acceptance

Цей пакет строго виконує AST фактичних production файлів репозиторію.
Невідомі primitives зупиняють тест. Native113 зафіксував фактичне створення
фракції без підтвердження через on_faction_formed; його невдалий результат
збережено окремо. Native114 підтвердив constructor-return завершення, але
залишив475PASS/1FAIL без RUN_END: після передачі керівництва команда
самовидалення не завершила вихід. Виправлення області видалення ще
потребує ізольованої нативної перевірки115. Попередній результат не переписано.

Перед constructor засновник резервує монотонний generation, actor та
позитивний одноденний intent та witness перевіреного factionless constructor.
Спільний helper підтверджує cohort після фактичного успіху constructor або
зі справжнього on_faction_formed. В обох випадках він перевіряє чинні actor,
generation, deadline, політику і фактичне лідерство у фракції. Лічильники та
логи розрізняють creation_return і native_formed; пряме підтвердження не
збільшує native hook serial. Пізній hook після creation_return зберігає cohort
і не повторює новину. Return receipt очищається при leave/archive/dissolution.
Короткий global lock серіалізує тільки створення, а не індивідуальні заявки.

Модель явно дозволяє вимкнути formation hook. Окремі негативні тести
виконують точний source prefix до constructor і оголошують переривання
перед його return continuation. Це контроль pending intent, не твердження
про реальний engine scheduler. Збережено46 тестів з адаптацією7 таких
fixtures і додано5 перевірок завершення constructor. Усі51 збережено;
додано3 перевірки області виходу, поточний пакет має54 тести.

Кандидат добровільно звертається до поточного фактичного лідера. Заявка має
leader/instance/round і позитивний строк42дні. Лідер приймає або відхиляє;
кандидат відкликає. Expiry або зміна умов закриває заявку; перед новою діє
14денний cooldown. Попапи лише інформують, а current decisions повторно
перевіряють пару, строк, instance і національну політику. Прийняття через
targeted decisions є scripted admission; native Ask/Invite окремо не доведено.

Засновник і кандидат мають бути поза іншими фракціями. Національні правила
вступу, нейтралітет, суверенітет, наступальна війна і поріг напруги збережені.
Security reform є конкретним ігровим дозволом заснувати optional EDU.
can_create_factions не додається, бо ця idea задає його no. Інші країни
не виводяться автоматично з НАТО та не вступають автоматично в EDU.

Вихід використовує тільки фактичну confirmed cohort. Лідер спочатку
передає керування actual чинному члену, перевіряє результат, тоді виходить.
Останній лідер розпускає confirmed EDU. Native failure зберігає identity,
result2 та одноразове повідомлення. Daily retry застосовується після
формальної втрати EU_member/recognized або власних регіонів. Саме subject
pause при чинному ЄС cohort не видаляє. Архів цілого ЄС повторює розпуск
лише confirmed EDU; сторонні фракції залишаються незмінними.
Після позитивно перевіреного scripted remove членство і return receipt
очищаються навіть без native leave hook. Невдалий remove їх зберігає;
лічильники native leave/leadership через пряме очищення не зростають.
В обох явних маршрутах видалення виконує фактичний керівник тієї самої
підтвердженої cohort з target PREV; сторонній ROOT не стає ціллю. Модель
використовує явну консервативну політику leader/same-faction removal. Це
не твердження про універсальні правила рушія: isolated remove-only,
передача керівництва та кінцевий вихід ще потребують native115.

Legacy adoption можливий лише за actual has_faction_template рівно одного
лідера EDU, без current cohort і pending intent. Він отримує новий generation
без creation news. Native107 довів, що faction goals без NCNS не зберігаються.
Без доступної metadata стару невідому EDU не можна безпечно визначити;
name, global EDU та founder pointer не є ідентифікацією.

Межі моделі: зовнішні EU/національні/influence helpers, engine construction,
membership mutations, hooks, events та AI. Тести не доводять GUI, multiplayer,
campaign AI, save/reload або native дипломатичний діалог.

Збережено принциповий контрприклад: без on_leave_faction при знищенні pending
або підтвердженої constructor-return фракції відкладений formed callback не
має документованого native faction ID і може сплутати сторонню фракцію того
ж засновника. Це acceptance blocker, а не бажана поведінка. Новий native
запуск має перевірити leave cleanup і збереження підтвердження на пізньому
hook. Static GREEN не замінює formation/leave/leadership/dismantle/
recreate proof. Позитивну legacy adoption перевіряють тільки за actual DLC.

```powershell
python -B tools/validation/edu_protocol/test_protocol.py
```
