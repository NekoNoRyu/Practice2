# Документация Telegram-бота "GoyGrevBot"

## Описание проекта

Этот Telegram-бот разработан для проведения интерактивных тестов и новеллы, которые помогают пользователям определить свой "уровень понимания мира" и финансовой грамотности. В зависимости от результатов тестов, пользователям предлагаются различные рекомендации, реферальные ссылки и доступ к дополнительному контенту. Бот также включает систему напоминаний и механизм принятия пользовательского соглашения.

## Зависимости и требования

Для работы бота требуются следующие библиотеки:

*   `aiogram` (для взаимодействия с Telegram API)
*   `asyncpg` (для асинхронного взаимодействия с PostgreSQL)
*   `json` (встроенный, для работы с JSON-строками в ответах)
*   `logging` (встроенный, для логирования)
*   `asyncio` (встроенный, для асинхронной работы)
*   `datetime`, `timedelta` (встроенные, для работы со временем)

### Установка зависимостей

pip install aiogram asyncpg

### Настройки базы данных (PostgreSQL 17)

PostgreSQL Tables

```sql
CREATE TABLE novel_scenes (
    choices jsonb,
    is_ending boolean,
    id integer,
    ending_result character varying,
    scene_text text
);

CREATE TABLE game_points (
    points integer,
    last_game timestamp without time zone,
    user_id bigint
);

CREATE TABLE referrals (
    result text,
    id integer,
    referral_link text,
    user_id bigint,
    created_at timestamp without time zone
);

CREATE TABLE user_answers (
    question_id integer,
    timestamp timestamp without time zone,
    answer text,
    user_id bigint,
    test_type text
);

CREATE TABLE questions2 (
    scores jsonb,
    text text,
    options jsonb,
    id integer,
    category character varying,
    test_type character varying
);

CREATE TABLE users (
    last_test timestamp without time zone,
    test_count integer,
    created_at timestamp without time zone,
    total_score integer,
    user_id bigint,
    reminders_enabled boolean,
    disclaimer_accepted boolean
);

CREATE TABLE questions3 (
    id integer,
    scores jsonb,
    options jsonb,
    test_type character varying,
    category character varying,
    text text
);

CREATE TABLE test_results (
    result character varying,
    result_category character varying,
    points integer,
    id integer,
    timestamp timestamp without time zone,
    user_id bigint,
    category_stats jsonb
);

CREATE TABLE questions (
    id integer,
    category character varying,
    options jsonb,
    test_type character varying,
    scores jsonb,
    text text
);
```

PostgreSQL Sequences

```sql
CREATE SEQUENCE public.novel_scenes_id_seq
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 2147483647
    NO CYCLE;

CREATE SEQUENCE public.questions3_id_seq
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 2147483647
    NO CYCLE;

CREATE SEQUENCE public.questions_id_seq
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 2147483647
    NO CYCLE;

CREATE SEQUENCE public.referrals_id_seq
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 2147483647
    NO CYCLE;

CREATE SEQUENCE public.test_results_id_seq
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 2147483647
    NO CYCLE;
```


### Переменные окружения/Конфигурация

*   `API_TOKEN`: Токен Telegram-бота.
*   `DATABASE_URL`: Строка подключения к базе данных PostgreSQL.
*   `REFERRAL_LINKS`: Словарь с реферальными ссылками, зависящими от результата теста.
*   `LITERATURE_LIST`, `ARTICLE_LIST`: Списки рекомендуемой литературы и статей для категории "Gray Mass".
*   `ENDING_MESSAGES`: Словарь с описаниями окончаний новеллы.

## Структура кода и основные функции

### Настройки и константы

*   `API_TOKEN`, `DATABASE_URL`: Конфигурация для доступа к Telegram и базе данных.
*   `REFERRAL_LINKS`, `LITERATURE_LIST`, `ARTICLE_LIST`, `ENDING_MESSAGES`: Константы, содержащие данные для логики бота.

### Логирование

*   `logging.basicConfig`: Настройка базового логирования для вывода информации в консоль.

### Инициализация бота

*   `bot = Bot(token=API_TOKEN)`: Инициализация объекта бота.
*   `storage = MemoryStorage()`: Инициализация хранилища состояний в памяти (для FSM).
*   `dp = Dispatcher(bot=bot, storage=storage)`: Инициализация диспетчера.
*   `router = Router()`: Создание роутера для обработки сообщений и колбэков.
*   `dp.include_router(router)`: Включение роутера в диспетчер.

### Машина состояний (FSM)

```text
class TestStates(StatesGroup):
    INITIAL_TEST = State()
    TEST_QUESTION = State() # Не используется, можно удалить
    GOY_QUIZ = State()
    NOVEL = State()
    FINANCE_TEST = State()
    FINISHED = State()
```

Определяет состояния, в которых может находиться пользователь во время прохождения различных активностей.

### CallbackData

```text
class AnswerCallback(CallbackData, prefix="answer"):
    option: str
    question_id: int
    test_type: str

class NovelCallback(CallbackData, prefix="novel"):
    choice: str
    scene_id: str
```

Служат для удобной обработки колбэков от кнопок, инкапсулируя необходимые данные.

### `ThrottlingMiddleware` (Антиспам)

```text
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self.cache = {}

    async def __call__(self, handler, event: TelegramObject, data: str):
        # ... логика антиспама ...
```

*   **Назначение**: Предотвращает частые вызовы определённых команд одним пользователем, ограничивая их интервалом в 15 секунд.
*   **Параметры**:
    *   `handler`: Следующий обработчик в цепочке.
    *   `event`: Объект события Telegram (Message, CallbackQuery и т.д.).
    *   `data`: Дополнительные данные.
*   **Возвращаемое значение**: Результат выполнения следующего обработчика или `None`, если запрос заблокирован.
*   **Известные ограничения**:
    *   Отслеживает только команды `/test`, `/goy_quiz`, `/novel`, `/finance_test`. Другие команды не регулируются.
    *   Кеш хранится в памяти и сбрасывается при перезапуске бота. Для продакшн-систем рекомендуется использовать Redis или другую внешнюю систему кеширования.

### `get_db_connection()`

```text
async def get_db_connection():
    # ... логика подключения к БД ...
```

*   **Назначение**: Устанавливает асинхронное соединение с базой данных PostgreSQL.
*   **Параметры**: Нет.
*   **Возвращаемое значение**: Объект соединения `asyncpg.Connection` в случае успеха, `None` в случае ошибки.

### `get_question(question_id, test_type='initial')`

```text
async def get_question(question_id, test_type='initial'):
    # ... логика получения вопроса ...
```

*   **Назначение**: Получает данные вопроса из соответствующей таблицы базы данных по его ID и типу теста.
*   **Параметры**:
    *   `question_id` (int): Идентификатор вопроса.
    *   `test_type` (str, optional): Тип теста ('initial', 'finance', 'goy_quiz'). По умолчанию 'initial'.
*   **Возвращаемое значение**: Строка из базы данных (`asyncpg.Record`) с данными вопроса или `None`, если вопрос не найден или произошла ошибка.

### `get_novel_scene(scene_id)`

```text
async def get_novel_scene(scene_id):
    # ... логика получения сцены новеллы ...
```

*   **Назначение**: Получает данные сцены интерактивной новеллы из базы данных по её ID.
*   **Параметры**:
    *   `scene_id` (int): Идентификатор сцены.
*   **Возвращаемое значение**: Строка из базы данных (`asyncpg.Record`) с данными сцены или `None`, если сцена не найдена или произошла ошибка.

### `send_long_message(message: Message, callback_query: CallbackQuery, text: str, reply_markup=None)`

```text
async def send_long_message(message: Message, callback_query: CallbackQuery, text: str, reply_markup=None):
    # ... логика отправки длинных сообщений ...
```

*   **Назначение**: Отправляет длинные текстовые сообщения, разбивая их на части по 4000 символов, если это необходимо. Поддерживает отправку как новых сообщений, так и редактирование существующих (в случае `callback_query`).
*   **Параметры**:
    *   `message` (Message): Объект сообщения (если отправляется новое сообщение).
    *   `callback_query` (CallbackQuery): Объект колбэка (если редактируется сообщение).
    *   `text` (str): Текст для отправки.
    *   `reply_markup` (InlineKeyboardMarkup, optional): Встроенная клавиатура.
*   **Возвращаемое значение**: `None`.

### Обработчики команд

*   **`handle_progev(message: Message)`**
    *   **Назначение**: Обрабатывает команду `/progev`. Отправляет пользователю дисклеймер и записывает в базу данных факт его принятия.
    *   **Пример использования**: Пользователь отправляет `/progev`.

*   **`send_welcome(message: Message)`**
    *   **Назначение**: Обрабатывает команду `/start`. Проверяет, принял ли пользователь дисклеймер. Если нет, просит принять. Если да, регистрирует пользователя в БД (если ещё не зарегистрирован) и отправляет приветственное сообщение.
    *   **Пример использования**: Пользователь отправляет `/start`.

*   **`output_commands(message: Message)`**
    *   **Назначение**: Обрабатывает команду `/help`. Отправляет список доступных команд.
    *   **Пример использования**: Пользователь отправляет `/help`.

*   **`start_test(message: Message, state: FSMContext)`**
    *   **Назначение**: Обрабатывает команду `/test`. Инициирует основной тест, загружает первый вопрос и отправляет его с вариантами ответов. Устанавливает состояние `TestStates.INITIAL_TEST`.
    *   **Пример использования**: Пользователь отправляет `/test`.

*   **`start_goy_quiz(message: Message, state: FSMContext)`**
    *   **Назначение**: Обрабатывает команду `/goy_quiz`. Проверяет, является ли пользователь "Гоем" по результатам основного теста. Если да, инициирует викторину "Какой ты гой", загружает первый вопрос и отправляет его. Устанавливает состояние `TestStates.GOY_QUIZ`.
    *   **Пример использования**: Пользователь отправляет `/goy_quiz`.

*   **`start_novel(message: Message, state: FSMContext)`**
    *   **Назначение**: Обрабатывает команду `/novel`. Проверяет, является ли пользователь "Гоем". Если да, инициирует интерактивную новеллу, загружает первую сцену и отправляет её с вариантами выбора. Устанавливает состояние `TestStates.NOVEL`.
    *   **Пример использования**: Пользователь отправляет `/novel`.

*   **`start_finance_test(message: Message, state: FSMContext)`**
    *   **Назначение**: Обрабатывает команду `/finance_test`. Проверяет, является ли пользователь "Средним классом". Если да, инициирует финансовый тест, загружает первый вопрос и отправляет его. Устанавливает состояние `TestStates.FINANCE_TEST`.
    *   **Пример использования**: Пользователь отправляет `/finance_test`.

*   **`toggle_reminders(message: Message)`**
    *   **Назначение**: Обрабатывает команду `/toggle_reminders`. Переключает статус напоминаний для пользователя в базе данных.
    *   **Пример использования**: Пользователь отправляет `/toggle_reminders`.

### Обработчики колбэков

*   **`process_answer(callback_query: CallbackQuery, callback_data: AnswerCallback, state: FSMContext)`**
    *   **Назначение**: Обрабатывает ответы пользователя на вопросы тестов (`INITIAL_TEST`, `FINANCE_TEST`, `GOY_QUIZ`). Сохраняет ответ в БД, обновляет счёт, загружает следующий вопрос или выводит результаты теста, включая реферальные ссылки и рекомендации.
    *   **Пример использования**: Пользователь нажимает кнопку с ответом в тесте.

*   **`process_novel_choice(callback_query: CallbackQuery, callback_data: NovelCallback, state: FSMContext)`**
    *   **Назначение**: Обрабатывает выбор пользователя в интерактивной новелле. Загружает следующую сцену или выводит финальный результат новеллы.
    *   **Пример использования**: Пользователь нажимает кнопку с вариантом выбора в новелле.

*   **`handle_callbacks(callback_query: CallbackQuery, state: FSMContext)`**
    *   **Назначение**: Универсальный обработчик для колбэков, которые инициируют перезапуск тестов (`retest`, `retest_finance`) или запуск других активностей (`start_goy_quiz`, `start_novel`, `start_finance_test`). Сбрасывает состояние FSM и запускает соответствующую активность.
    *   **Пример использования**: Пользователь нажимает "Пройти тест заново", "Начать новеллу заново" и т.п.

### Фоновая задача

*   **`send_reminders(bot: Bot)`**
    *   **Назначение**: Асинхронная фоновая задача, которая периодически (раз в 24 часа) проверяет пользователей, у которых включены напоминания и которые давно не проходили тест. Отправляет им напоминания.
*   **Параметры**:
    *   `bot` (Bot): Объект бота для отправки сообщений.
*   **Известные ограничения**:
    *   Напоминания отправляются всем пользователям, которые не проходили тест более 1 дня и у которых включены напоминания. Нет более тонкой настройки частоты или содержимого напоминаний.

### Точка входа

*   **`main()`**
    *   **Назначение**: Основная асинхронная функция, запускающая бота и фоновую задачу по отправке напоминаний.
*   **`if __name__ == "__main__":`**
    *   Запускает функцию `main()` при непосредственном выполнении скрипта.