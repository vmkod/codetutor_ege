import sqlite3
from datetime import datetime

DATABASE_NAME = "ege_project.db"


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_number INTEGER NOT NULL,
            condition TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        initial_tasks = [
            (
                5,
                "На вход алгоритма подаётся натуральное число N. Алгоритм строит по нему новое число R следующим образом:\n"
                "1) Строится двоичная запись числа N.\n"
                "2) К этой записи дописываются справа ещё два разряда: если число N чётное, в конец дописывается 01, иначе 10.\n"
                "Полученная таким образом запись является двоичной записью искомого числа R.\n"
                "Укажите минимальное число R, большее 43, которое может быть получено в результате работы этого алгоритма.",
            ),
            (
                8,
                "Игорь составляет 5-буквенные слова из букв К, Р, О, Т. При этом буквы К и Т могут встречаться в слове не более одного раза, а остальные буквы могут повторяться любое количество раз или не встречаться вовсе. Словом считается любая допустимая последовательность букв.\n"
                "Сколько различных слов может составить Игорь?",
            ),
            (
                16,
                "Алгоритм вычисления значения функции F(n), где n – натуральное число, задан следующими соотношениями:\n"
                "F(n) = 1 при n = 1;\n"
                "F(n) = n + F(n - 1), если n чётное;\n"
                "F(n) = 2 * F(n - 2), если n > 1 и при этом n нечётное.\n"
                "Чему равно значение функции F(26)?",
            ),
            (
                23,
                "Исполнитель преобразует число на экране. У исполнителя есть две команды:\n"
                "1. Прибавить 1\n"
                "2. Умножитьло на 2\n"
                "Сколько существует программ, которые преобразуют исходное число 1 в число 20?",
            )
        ]

        cursor.executemany(
            "INSERT INTO tasks (task_number, condition) VALUES (?, ?)",
            initial_tasks,
        )
        conn.commit()

    conn.close()


def get_random_task(task_number: int):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT condition FROM tasks WHERE task_number = ? ORDER BY RANDOM() LIMIT 1",
        (task_number,),
    )
    result = cursor.fetchone()

    conn.close()
    return result[0] if result else None


def add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    joined_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, joined_at))

    conn.commit()
    conn.close()
