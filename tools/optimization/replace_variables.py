from pathlib import Path
import re

# Скрипт должен лежать здесь:
# Hearts of Iron IV/mod/mdredux/tools/optimization/replace_variables.py
#
# Поэтому поднимаемся на 2 папки выше от optimization:
# optimization -> tools -> mdredux
# Никаких абсолютных путей и имени пользователя не нужно — будет работать у всех,
# если структура папок мода такая же.
ROOT_DIR = Path(__file__).resolve().parents[2]

# Поддерживаются оба варианта:
#
# subtract_from_variable = { debt_default_left = 10 }
# -> add_to_variable = { debt_default_left = -10 }
#
# subtract_from_temp_variable = { some_temp_var = 1.5 }
# -> add_to_temp_variable = { some_temp_var = -1.5 }
#
# Если справа стоит НЕ число, а другая переменная, строка не меняется:
# subtract_from_variable = { debt_default_left = debt_default_reduction }
# subtract_from_temp_variable = { a = b }

pattern = re.compile(
    r'(?P<command>subtract_from(?:_temp)?_variable)'
    r'(?P<prefix>\s*=\s*\{\s*[A-Za-z0-9_.^@:-]+\s*=\s*)'
    r'(?P<value>-?\d+(?:\.\d+)?)'
    r'(?P<suffix>\s*\})'
)

changed_files = 0
changed_count = 0


def replace_match(match):
    command = match.group("command")
    prefix = match.group("prefix")
    value = match.group("value")
    suffix = match.group("suffix")

    # Меняем знак числа:
    # 10   -> -10
    # -10  -> 10
    # 1.5  -> -1.5
    # -1.5 -> 1.5
    if value.startswith("-"):
        new_value = value[1:]
    else:
        new_value = "-" + value

    # Сохраняем тип переменной:
    # subtract_from_variable      -> add_to_variable
    # subtract_from_temp_variable -> add_to_temp_variable
    if command == "subtract_from_temp_variable":
        new_command = "add_to_temp_variable"
    else:
        new_command = "add_to_variable"

    return new_command + prefix + new_value + suffix


print(f"Папка мода: {ROOT_DIR}")
print("Поиск .txt файлов...")
print()

for file_path in ROOT_DIR.rglob("*.txt"):
    try:
        text = file_path.read_text(encoding="utf-8")
        new_text, count = pattern.subn(replace_match, text)

        if count > 0:
            # Без .bak — файл сразу перезаписывается.
            file_path.write_text(new_text, encoding="utf-8")

            changed_files += 1
            changed_count += count

            print(f"[OK] {file_path} — заменено: {count}")

    except UnicodeDecodeError:
        print(f"[SKIP] Не UTF-8: {file_path}")
    except Exception as e:
        print(f"[ERROR] {file_path}: {e}")

print()
print("=" * 50)
print(f"Изменено файлов: {changed_files}")
print(f"Всего замен:     {changed_count}")
print("=" * 50)
input("Нажми Enter для выхода...")
