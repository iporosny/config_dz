import sys
import re
import argparse
import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path


class ConfigParser:

    def __init__(self):
        self.constants: Dict[str, Any] = {}
        self.data: Dict[str, Any] = {}

    def clean_text(self, text: str) -> str:
        lines = []
        for line in text.split('\n'):
            if '#' in line:
                line = line[:line.index('#')]
            line = line.rstrip()
            if line:
                lines.append(line)
        return '\n'.join(lines)

    def parse_value(self, value_str: str) -> Any:
        value_str = value_str.strip()

        if not value_str:
            return ''

        if value_str.endswith(';'):
            value_str = value_str[:-1].strip()

        # Строки в кавычках
        if (value_str.startswith('"') and value_str.endswith('"')) or \
                (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]

        # Числа
        if value_str.isdigit():
            return int(value_str)

        # Числа с плавающей точкой
        if re.match(r'^-?\d+\.\d+$', value_str):
            return float(value_str)

        # Булевы значения
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False

        # Массивы
        if value_str.startswith('{') and value_str.endswith('}'):
            content = value_str[1:-1].strip()
            if not content:
                return []

            items = []
            current = ''
            in_quotes = False
            quote_char = None
            brace_count = 0

            for char in content:
                if char in '\'"' and not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char and in_quotes:
                    in_quotes = False
                    quote_char = None
                elif char == '{' and not in_quotes:
                    brace_count += 1
                elif char == '}' and not in_quotes:
                    brace_count -= 1
                elif char == ',' and not in_quotes and brace_count == 0:
                    items.append(self.parse_value(current.strip()))
                    current = ''
                    continue

                current += char

            if current.strip():
                items.append(self.parse_value(current.strip()))

            return items

        # Константы
        if value_str in self.constants:
            return self.constants[value_str]

        # Идентификатор
        return value_str

    def parse_dict(self, lines: List[str], start_idx: int, depth: int = 0) -> Tuple[Dict[str, Any], int]:
        # парсит словарь
        result = {}
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Конец словаря
            if line == '}':
                return result, i + 1

            # Разделение ключ и значение
            if ':' in line:
                if line.endswith('{'):
                    key = line.split(':', 1)[0].strip()
                    nested_dict, next_idx = self.parse_dict(lines, i + 1, depth + 1)
                    result[key] = nested_dict
                    i = next_idx
                    continue

                key, value_part = line.split(':', 1)
                key = key.strip()
                value_part = value_part.strip()

                if value_part == '{':
                    nested_dict, next_idx = self.parse_dict(lines, i + 1, depth + 1)
                    result[key] = nested_dict
                    i = next_idx
                else:
                    # Простое значение
                    value = self.parse_value(value_part)
                    result[key] = value
                    i += 1
            elif '=' in line:
                key, value_part = line.split('=', 1)
                key = key.strip()
                value_part = value_part.strip()

                if value_part == '{':
                    nested_dict, next_idx = self.parse_dict(lines, i + 1, depth + 1)
                    result[key] = nested_dict
                    i = next_idx
                else:
                    value = self.parse_value(value_part)
                    result[key] = value
                    i += 1
            elif line.endswith('{'):
                key = line[:-1].strip()
                nested_dict, next_idx = self.parse_dict(lines, i + 1, depth + 1)
                result[key] = nested_dict
                i = next_idx
            else:
                i += 1

        return result, i

    def parse(self, text: str) -> Dict[str, Any]:
        # Очищаем
        self.constants.clear()
        self.data.clear()

        text = self.clean_text(text)

        define_pattern = r'\(define\s+([a-z][a-z0-9_]*)\s+([^);]+)\)\s*;?'

        for match in re.finditer(define_pattern, text, re.DOTALL):
            name = match.group(1)
            value_str = match.group(2).strip()
            value = self.parse_value(value_str)
            self.constants[name] = value

        text = re.sub(r'\(define[^)]*\)\s*;?', '', text)

        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            if ':' in line and line.endswith('{'):
                key = line.split(':', 1)[0].strip()
                nested_dict, next_idx = self.parse_dict(lines, i + 1, 0)
                self.data[key] = nested_dict
                i = next_idx
            elif '=' in line and line.endswith('{'):
                key = line.split('=', 1)[0].strip()
                nested_dict, next_idx = self.parse_dict(lines, i + 1, 0)
                self.data[key] = nested_dict
                i = next_idx
            elif line.endswith('{'):
                key = line[:-1].strip()
                nested_dict, next_idx = self.parse_dict(lines, i + 1, 0)
                self.data[key] = nested_dict
                i = next_idx
            elif ':' in line:
                key, value_part = line.split(':', 1)
                key = key.strip()
                value = self.parse_value(value_part)
                self.data[key] = value
                i += 1
            elif '=' in line:
                key, value_part = line.split('=', 1)
                key = key.strip()
                value = self.parse_value(value_part)
                self.data[key] = value
                i += 1
            else:
                i += 1

        # Добавляем константы в результат
        for key, value in self.constants.items():
            if key not in self.data:
                self.data[key] = value

        return self.data


class TOMLConverter:

    @staticmethod
    def escape_string(value: str) -> str:
        replacements = {
            '\\': '\\\\',
            '"': '\\"',
            '\n': '\\n',
            '\t': '\\t',
            '\r': '\\r',
            '\b': '\\b',
            '\f': '\\f',
        }

        result = []
        for char in value:
            if char in replacements:
                result.append(replacements[char])
            elif ord(char) < 32:
                result.append(f'\\u{ord(char):04x}')
            else:
                result.append(char)

        return ''.join(result)

    @staticmethod
    def to_toml(data: Dict[str, Any], indent: int = 0, path: str = '') -> str:
        if not data:
            return ''

        lines = []
        indent_str = '  ' * indent

        simple_keys = []
        dict_keys = []

        for key, value in data.items():
            if isinstance(value, dict):
                dict_keys.append(key)
            else:
                simple_keys.append(key)

        simple_keys.sort()
        dict_keys.sort()

        for key in simple_keys:
            value = data[key]

            if isinstance(value, str):
                escaped = TOMLConverter.escape_string(value)
                lines.append(f'{indent_str}{key} = "{escaped}"')
            elif isinstance(value, bool):
                lines.append(f'{indent_str}{key} = {str(value).lower()}')
            elif isinstance(value, (int, float)):
                lines.append(f'{indent_str}{key} = {value}')
            elif isinstance(value, list):
                items = []
                for item in value:
                    if isinstance(item, str):
                        escaped = TOMLConverter.escape_string(item)
                        items.append(f'"{escaped}"')
                    elif isinstance(item, bool):
                        items.append(str(item).lower())
                    elif isinstance(item, (int, float)):
                        items.append(str(item))
                    elif isinstance(item, list):
                        inner_items = [f'"{i}"' if isinstance(i, str) else str(i) for i in item]
                        items.append(f'[{", ".join(inner_items)}]')
                    else:
                        items.append(f'"{str(item)}"')
                lines.append(f'{indent_str}{key} = [{", ".join(items)}]')
            else:
                lines.append(f'{indent_str}{key} = "{value}"')

        # Вывод словарей
        for key in dict_keys:
            value = data[key]

            if path:
                full_path = f"{path}.{key}"
            else:
                full_path = key

            if indent == 0:
                lines.append(f'[{full_path}]')
            else:
                lines.append(f'{indent_str}[{full_path}]')

            lines.append(TOMLConverter.to_toml(value, indent + 1, full_path))

        return '\n'.join(lines)


def convert_file(input_file: str) -> str:
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = ConfigParser()
        data = parser.parse(content)

        return TOMLConverter.to_toml(data)

    except FileNotFoundError:
        return f"Ошибка: Файл '{input_file}' не найден"
    except SyntaxError as e:
        return f"Синтаксическая ошибка: {e}"
    except NameError as e:
        return f"Ошибка имени: {e}"
    except Exception as e:
        import traceback
        return f"Ошибка: {str(e)}\n{traceback.format_exc()}"


def main():
    parser = argparse.ArgumentParser(
        description='Конвертер учебного конфигурационного языка в TOML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s config.config                # Вывод в консоль
  %(prog)s config.config -o output.toml # Сохранение в файл
  %(prog)s config.config --test         # Запуск тестового режима

Поддерживаемый синтаксис:
  (define имя значение)                 # Определение константы
  ключ: значение                       # Присваивание
  ключ: {                              # Словарь
    вложенный_ключ: значение
  }
        """
    )

    parser.add_argument(
        'input_file',
        help='Путь к входному файлу на учебном конфигурационном языке'
    )

    parser.add_argument(
        '-o', '--output',
        help='Путь к выходному файлу TOML',
        default=None
    )

    parser.add_argument(
        '-t', '--test',
        help='Запустить тестовый режим',
        action='store_true'
    )

    parser.add_argument(
        '-v', '--verbose',
        help='Подробный вывод',
        action='store_true'
    )

    args = parser.parse_args()

    if not Path(args.input_file).exists():
        print(f"Ошибка: Файл '{args.input_file}' не найден")
        sys.exit(1)

    if args.verbose:
        print(f"Обработка файла: {args.input_file}")
        print("-" * 50)

    result = convert_file(args.input_file)

    if args.test:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = ConfigParser()
        data = parser.parse(content)

        print("Парсированные данные (JSON):")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("\n" + "=" * 50 + "\n")
        print("Результат в TOML:")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)

        if args.verbose:
            print(f"Результат сохранен в: {args.output}")
        else:
            print(f"Конвертация завершена. Файл: {args.output}")
    else:
        print(result)


if __name__ == '__main__':
    main()
