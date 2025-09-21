import json
import logging
import asyncpg
from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.markdown import hbold
import asyncio
from datetime import datetime, timedelta

# Настройки
API_TOKEN = '8178558928:AAHOG2g-YuQLhzDNuP9A1O-lhBp7YlavywE'
DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/ProgrevTech'

# Реферальные ссылки
REFERRAL_LINKS = {
    "Goy": "https://alfa.me/DyNGcP",
    "Middle Class": "https://vtb.ru/l/ta468989",
    "Future Millionaire": "https://alfa.me/H6Q4i3"
}
# Список литературы для Gray Mass
LITERATURE_LIST = [
    "Думай и богатей — Наполеон Хилл",
    "Самый богатый человек в Вавилоне — Джордж Клейсон",
    "Путь к финансовой свободе — Бодо Шефер"
]

# Список статей для Gray Mass
ARTICLE_LIST = [
    "Как начать инвестировать с нуля: пошаговое руководство — https://example.com/invest-0",
    "Основы финансовой грамотности: как управлять своими деньгами — https://example.com/finance-basics",
    "10 привычек, которые мешают вам разбогатеть — https://example.com/bad-habits",
    "Почему важно ставить финансовые цели — https://example.com/financial-goals"
]

ENDING_MESSAGES = {
    "Полный провал": "Увы, ваш путь закончился неудачей. Попробуйте снова!",
    "Стабильный, но скромный доход": "Вам удалось удержаться на плаву, но без больших прорывов.",
    "Перспективный середнячок": "Ваши усилия приносят плоды, всё идёт к успеху!",
    "Прорыв к успеху": "Вы сделали настоящий прорыв! Поздравляем!",
    "Миллионер в шаге": "Ещё немного — и вы в списке Forbes!",
    "Неожиданный финал": "Ваша история завершилась необычно. Такой исход тоже важен!"
}
# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)
router = Router()
dp.include_router(router)

# Машина состояний
class TestStates(StatesGroup):
    INITIAL_TEST = State()
    TEST_QUESTION = State()
    GOY_QUIZ = State()
    NOVEL = State()
    FINANCE_TEST = State()
    FINISHED = State()

# CallbackData для обработки ответов
class AnswerCallback(CallbackData, prefix="answer"):
    option: str
    question_id: int
    test_type: str

class NovelCallback(CallbackData, prefix="novel"):
    choice: str
    scene_id: str

# Middleware для антиспама
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self.cache = {}

    async def __call__(self, handler, event: TelegramObject, data: str):
        user_id = event.from_user.id
        command = event.text if hasattr(event, 'text') else None
        if command not in ['/test', '/goy_quiz', '/novel', '/finance_test']:
            return await handler(event, data)

        now = datetime.now()
        last_command = self.cache.get((user_id, command))
        if last_command and now - last_command < timedelta(seconds=15):
            await event.answer("Ой вей, не торопись! Подожди 15 секунд.")
            return
        self.cache[(user_id, command)] = now
        return await handler(event, data)

dp.message.middleware(ThrottlingMiddleware())

# Подключение к базе данных
async def get_db_connection():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        logging.info("Успешно подключилися к базе данных")
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        return None

async def get_question(question_id, test_type='initial'):
    conn = await get_db_connection()
    if not conn:
        return None
    try:
        # Подбор таблицы по test_type
        if test_type == 'finance':
            table = 'questions3'
        elif test_type == 'initial':
            table = 'questions2'
        elif test_type == 'goy_quiz':
            table = 'questions'
        else:
            table = 'questions2'  # По умолчанию
        query = f'SELECT * FROM {table} WHERE id = $1 AND test_type = $2'
        question = await conn.fetchrow(query, question_id, test_type)
        return question
    except Exception as e:
        logging.error(f"Ошибка при получении вопроса: {e}")
        return None
    finally:
        await conn.close()

# Получение сцены новеллы
async def get_novel_scene(scene_id):
    conn = await get_db_connection()
    if not conn:
        return None
    try:
        scene = await conn.fetchrow('SELECT * FROM novel_scenes WHERE id = $1', int(scene_id))
        return scene
    except Exception as e:
        logging.error(f"Ошибка при получении сцены: {e}")
        return None
    finally:
        await conn.close()

# Разбиение длинных сообщений
async def send_long_message(message: Message, callback_query: CallbackQuery, text: str, reply_markup=None):
    if len(text) <= 4096:
        if callback_query:
            await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        # Разбиваем на части по 4000 символов
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                if callback_query:
                    await callback_query.message.edit_text(part, reply_markup=reply_markup, parse_mode="HTML")
                else:
                    await message.answer(part, reply_markup=reply_markup, parse_mode="HTML")
            else:
                await message.answer(part, parse_mode="HTML")

# Обработчик команды /progev
@router.message(Command("progev"))
async def handle_progev(message: Message):
    user_id = message.from_user.id
    logging.info(f"Пользователь {user_id} отправил команду /progev")

    disclaimer_text = (
        f"{hbold('Уважаемые пользователи!')}\n\n"
        "Данный Telegram-бот создан исключительно в развлекательных целях. Он не является финансовым советником и не предоставляет профессиональные финансовые, инвестиционные или юридические консультации. Все данные, рекомендации или информация, предоставляемые ботом, носят исключительно справочный характер и не должны рассматриваться как руководство к действию.\n\n"
        f"{hbold('Важно:')}\n"
        "• <b>Отсутствие финансовых рекомендаций:</b> Любые материалы, предоставляемые ботом, не являются индивидуальными инвестиционными рекомендациями. Решения о покупке, продаже или удержании активов вы принимаете самостоятельно на свой страх и риск.\n"
        "• <b>Отказ от ответственности:</b> Разработчики бота и связанные с ним лица не несут ответственности за любые финансовые потери, убытки или иные последствия, возникшие в результате использования бота или информации, предоставленной им. Финансовые рынки связаны с высокими рисками, и прошлые результаты не гарантируют будущих успехов.\n"
        "• <b>Самостоятельное принятие решений:</b> Перед принятием любых финансовых решений настоятельно рекомендуем проконсультироваться с квалифицированным финансовым консультантом, имеющим соответствующую лицензию, и провести собственный анализ.\n"
        "• <b>Ограничения использования:</b> Бот не предназначен для использования в юрисдикциях, где его функциональность может нарушать местное законодательство. Пользователь несет полную ответственность за соблюдение законов своей страны.\n"
        "• <b>Технические риски:</b> Разработчики не гарантируют бесперебойную работу бота, отсутствие ошибок или точность предоставляемой информации. Технические сбои или неточности в данных могут возникать.\n\n"
        "Используя данный бот, вы подтверждаете, что понимаете и принимаете вышеуказанные условия, а также осознаете все риски, связанные с финансовыми операциями. Если вы не согласны с этими условиями, пожалуйста, воздержитесь от использования бота.\n\n"
        "Теперь вы можете начать с команды /start!"
    )

    conn = await get_db_connection()
    if conn:
        try:
            await conn.execute(
                'INSERT INTO users (user_id, disclaimer_accepted) VALUES ($1, TRUE) '
                'ON CONFLICT (user_id) DO UPDATE SET disclaimer_accepted = TRUE',
                user_id
            )
            logging.info(f"Пользователь {user_id} принял дисклеймер")
        except Exception as e:
            logging.error(f"Ошибка при обновлении дисклеймера для пользователя {user_id}: {e}")
            await message.answer("Ошибка при обработке команды. Попробуйте снова.")
            return
        finally:
            await conn.close()

    await send_long_message(message, None, disclaimer_text)
    await message.answer("Дисклеймер принят! Теперь используй /start, чтобы начать.", parse_mode="HTML")

# Обработчик команды /start
@router.message(Command("start"))
async def send_welcome(message: Message):
    user_id = message.from_user.id
    logging.info(f"Получена команда /start от пользователя {user_id}")

    conn = await get_db_connection()
    if not conn:
        await message.answer("Ошибка базы данных!")
        return
    try:
        disclaimer_accepted = await conn.fetchval(
            'SELECT disclaimer_accepted FROM users WHERE user_id = $1', user_id
        )
        if not disclaimer_accepted:
            await message.answer(
                "Для начала работы с ботом, пожалуйста, примите условия использования, отправив команду /progev."
            )
            return

        await conn.execute(
            'INSERT INTO users (user_id, disclaimer_accepted) VALUES ($1, TRUE) '
            'ON CONFLICT (user_id) DO NOTHING',
            user_id
        )
        logging.info(f"Пользователь {user_id} зарегистрирован или уже существует")
    except Exception as e:
        logging.error(f"Ошибка при регистрации пользователя: {e}")
        await message.answer("Ошибка при обработке команды. Попробуйте снова.")
        return
    finally:
        await conn.close()

    await message.answer(
        "Шалом! Я @GoeGrevBot. \nГотов пройти тест и узнать свой уровень понимания нашего мира? Пиши /test\n"
        "Для списка команд: /help"
    )

# Обработчик команды /help
@router.message(Command("help"))
async def output_commands(message: Message):
    user_id = message.from_user.id
    logging.info(f"Пользователь {user_id} запросил список команд")
    response = f"{hbold('Список команд:')}\n\n"
    response += "/start - запускать бота\n"
    response += "/test - начать основной тест\n"
    response += "/goy_quiz - викторина 'Какой ты гой' (доступно для 'Гоев')\n"
    response += "/novel - сыграть в новеллу (доступно для 'Гоев')\n"
    response += "/finance_test - тест по финансам (доступно для 'Среднего класса')\n"
    response += "/toggle_reminders - включить/отключить напоминания\n"
    await message.answer(response, parse_mode="HTML")

# Обработчик команды /test
@router.message(Command("test"))
async def start_test(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Пользователь {user_id} начал основной тест")
    await state.update_data(current_question=1, score=0, test_type='initial')
    question = await get_question(1, test_type='initial')
    if not question:
        await message.answer("Ошибка: вопросы не найдены!")
        return

    options = json.loads(question['options'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for option_key, option_text in options.items():
        callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='initial').pack()
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
        )

    await message.answer(question['text'], reply_markup=keyboard)
    await state.set_state(TestStates.INITIAL_TEST)

# Обработчик ответов на тесты
@router.callback_query(AnswerCallback.filter(), StateFilter(TestStates.INITIAL_TEST, TestStates.FINANCE_TEST, TestStates.GOY_QUIZ))
async def process_answer(callback_query: CallbackQuery, callback_data: AnswerCallback, state: FSMContext):
    user_id = callback_query.from_user.id
    answer = callback_data.option
    question_id = callback_data.question_id
    test_type = callback_data.test_type
    logging.info(f"Пользователь {user_id} ответил {answer} на вопрос {question_id} (тип: {test_type})")

    conn = await get_db_connection()
    if not conn:
        await callback_query.message.answer("Ошибка базы данных!")
        await callback_query.answer()
        return
    try:
        await conn.execute(
            'INSERT INTO user_answers (user_id, question_id, answer) VALUES ($1, $2, $3)',
            user_id, question_id, answer
        )
    except Exception as e:
        logging.error(f"Ошибка при сохранении ответа: {e}")
        await callback_query.message.answer("Ошибка при сохранении ответа!")
        await callback_query.answer()
        return
    finally:
        await conn.close()

    user_data = await state.get_data()
    current_question = user_data['current_question']
    score = user_data['score']
    question = await get_question(current_question, test_type=test_type)
    scores = json.loads(question['scores'])
    score += scores.get(answer, 0)
    correct_by_category = user_data.get('correct_by_category', {})
    if test_type == 'finance' and scores.get(answer, 0) > 0:
        category = question['category']
        correct_by_category[category] = correct_by_category.get(category, 0) + 1

    next_question_id = current_question + 1
    next_question = await get_question(next_question_id, test_type=test_type)

    if next_question:
        options = json.loads(next_question['options'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for option_key, option_text in options.items():
            callback_data = AnswerCallback(option=option_key, question_id=next_question['id'], test_type=test_type).pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
            )
        await callback_query.message.edit_text(next_question['text'], reply_markup=keyboard)
        await state.update_data(current_question=next_question_id, score=score, correct_by_category=correct_by_category)
    else:
        # Тест завершён
        conn = await get_db_connection()
        if not conn:
            await callback_query.message.answer("Ошибка базы данных!")
            await callback_query.answer()
            return

        try:
            # Исправляем таблицу для initial теста
            table = 'questions2' if test_type == 'initial' else 'questions3' if test_type == 'finance' else 'questions'
            answers = await conn.fetch(
                f'SELECT q.category, ua.answer FROM user_answers ua JOIN {table} q ON ua.question_id = q.id WHERE ua.user_id = $1 AND q.test_type = $2',
                user_id, test_type
            )
            category_stats = {}
            for ans in answers:
                category = ans['category'] or 'общее'
                category_stats[category] = category_stats.get(category, 0) + 1
        except Exception as e:
            logging.error(f"Ошибка при анализе категорий: {e}")
            category_stats = {}
        finally:
            await conn.close()

        message = ""
        keyboard = None
        referral_link = None

        if test_type == 'initial':
            if score >= 36:
                result = "Future Millionaire"
                referral_link = REFERRAL_LINKS[result] + f"?telegram_id={user_id}"
                message = (
                    f"Тест завершён! Ты {hbold('Будущий миллионер')} (Баллы: {score})! 🎉\n\n"
                    f"Поздравляем! Ты видишь мир таким, какой он есть, и знаешь, как выжать из него максимум. Твоя финансовая интуиция и амбиции приведут тебя к вершинам! Продолжай в том же духе, и скоро яхта будет твоей! 🚤\n\n"
                    f"Думаю ты уже готов начать инвестировать! Открой брокерский счёт по нашей ссылке и сделай первый шаг к миллионам: {referral_link}"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Открыть брокерский счёт", url=referral_link)],
                    [InlineKeyboardButton(text="Пройти тест заново", callback_data="retest")]
                ])
            elif score >= 30:
                result = "Middle Class"
                referral_link = REFERRAL_LINKS[result] + f"?telegram_id={user_id}"
                message = (
                    f"Тест завершён! Ты {hbold('Средний класс')} (Баллы: {score})!\n"
                    f"Ты понимаешь, как крутятся шестерёнки, и иногда даже их подкручиваешь. Неплохо, но до миллионера ещё шаг-другой!\n"
                    f"Пройди тест по финансам, чтобы стать ближе к миллионерам!\n"
                    f"Начни сейчас свою прокачку! Оформи карту по ссылке и получи 1000 рублей на счет, выполнив условия. Поддержи бота!"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Пройти тест по финансам", callback_data="start_finance_test")],
                    [InlineKeyboardButton(text="Оформить карту", url=referral_link)],
                    [InlineKeyboardButton(text="Пройти тест заново", callback_data="retest")]
                ])
            elif score >= 20:
                result = "Goy"
                referral_link = REFERRAL_LINKS[result] + f"?telegram_id={user_id}"
                message = (
                    f"Тест завершён! Ты {hbold('Гой')} (Баллы: {score})!\n"
                    f"Ты начинаешь подозревать, что мир не так прост, но пока не знаешь, как это использовать. Продолжай копать!\n"
                    f"Хочешь узнать, какой ты гой, или сыграть в новеллу?\n"
                    f"Ничего страшного, и ты сможешь научиться брать от этого мира всё! Начни сейчас, оформи карту по ссылке и получи 500 рублей на счет, выполнив условия. Поддержи бота!"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Викторина 'Какой ты гой'", callback_data="start_goy_quiz")],
                    [InlineKeyboardButton(text="Сыграть в новеллу", callback_data="start_novel")],
                    [InlineKeyboardButton(text="Оформить карту", url=referral_link)],
                    [InlineKeyboardButton(text="Пройти тест заново", callback_data="retest")]
                ])
            else:
                result = "Gray Mass"
                books = "\n".join([f"• {book}" for book in LITERATURE_LIST])
                articles = "\n".join([f"• {article}" for article in ARTICLE_LIST])
                message = (
                    f"Тест завершён! Ты {hbold('Ничем не выдающаяся серая масса')} (Баллы: {score})! 😴\n\n"
                    f"Ты живёшь, как все, и не заморачиваешься. Мир для тебя — это работа, сериалы и котики. Но всё можно изменить! Начни прокачивать свои финансовые знания, чтобы выбраться из серой массы.\n\n"
                    f"{hbold('Рекомендуемые книги:')}\n{books}\n\n"
                    f"{hbold('Полезные статьи:')}\n{articles}\n\n"
                    f"Читай, учись и возвращайся за новым тестом!"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Пройти тест заново", callback_data="retest")]
                ])

            # Сохраняем результат
            conn = await get_db_connection()
            if conn:
                try:
                    await conn.execute(
                        'INSERT INTO test_results (user_id, result, result_category, category_stats, points) VALUES ($1, $2, $3, $4, $5)',
                        user_id, result, result, json.dumps(category_stats), score
                    )
                    await conn.execute(
                        'UPDATE users SET total_score = total_score + $1, test_count = test_count + 1, last_test = NOW() WHERE user_id = $2',
                        score, user_id
                    )
                    if result != "Gray Mass":  # Не сохраняем реферальную ссылку для Gray Mass
                        await conn.execute(
                            'INSERT INTO referrals (user_id, referral_link, result) VALUES ($1, $2, $3)',
                            user_id, referral_link, result
                        )
                except Exception as e:
                    logging.error(f"Ошибка при сохранении результата: {e}")
                finally:
                    await conn.close()

        elif test_type == 'finance':
            message = f"{hbold('Финансовый тест завершён!')} 📊\n\n"
            message += f"Твой результат: {score} из 12 баллов.\n\n"
            if score < 8:
                message += "Результат ниже 8 баллов. Рекомендуется пройти дополнительное обучение и попробовать снова! 📚\n"
            else:
                message += "Поздравляем с успешным прохождением теста! Ты на правильном пути к финансовой грамотности! 🚀\n"
            message += "\nСтатистика по разделам:\n"
            for category in ['Финансовое планирование', 'Налоговая грамотность', 'Экономика и рынки', 'Психология богатства']:
                correct = correct_by_category.get(category, 0)
                total = 3
                message += f"- {category}: {correct} из {total} правильных\n"
            referral_link = REFERRAL_LINKS.get('Middle Class', 'https://example.com') + f"?telegram_id={user_id}"
            message += f"\nОформляй карту по ссылке и поддержи бота: {referral_link}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пройти тест заново", callback_data="retest_finance")],
                [InlineKeyboardButton(text="Оформить карту", url=referral_link)]
            ])
        elif test_type == 'goy_quiz':
            if score >= 8:
                result = "Гой-мастер"
            elif score >= 5:
                result = "Гой"
            elif score >= 2:
                result = "Гой-Новичок"
            else:
                result = "Анти-гой"
            message = f"Викторина завершена! Ты {hbold(result)} (Баллы: {score})!"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пройти викторину заново", callback_data="start_goy_quiz")]
            ])

        if message and keyboard:
            await send_long_message(callback_query.message, callback_query, message, reply_markup=keyboard)
        else:
            logging.error(f"Ошибка: сообщение или клавиатура не определены для test_type={test_type}")
            await callback_query.message.answer("Ошибка при завершении теста. Попробуйте снова.")

        await state.set_state(TestStates.FINISHED)
    await callback_query.answer()

# Обработчик команды /goy_quiz
@router.message(Command("goy_quiz"))
async def start_goy_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = await get_db_connection()
    if conn:
        try:
            result = await conn.fetchval(
                'SELECT result_category FROM test_results WHERE user_id = $1 ORDER BY id DESC LIMIT 1', user_id
            )
            if result != "Goy":
                await message.answer("Эта викторина доступна только для Гоев! Пройди /test сначала.")
                return
        finally:
            await conn.close()

    logging.info(f"Пользователь {user_id} начал викторину 'Какой ты гой'")
    await state.update_data(current_question=1, score=0, test_type='goy_quiz')
    question = await get_question(1, test_type='goy_quiz')
    if not question:
        await message.answer("Ошибка: вопросы викторины не найдены!")
        return

    options = json.loads(question['options'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for option_key, option_text in options.items():
        callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='goy_quiz').pack()
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
        )

    await message.answer(question['text'], reply_markup=keyboard)
    await state.set_state(TestStates.GOY_QUIZ)

# Обработчик команды /novel
@router.message(Command("novel"))
async def start_novel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = await get_db_connection()
    if conn:
        try:
            result = await conn.fetchval(
                'SELECT result_category FROM test_results WHERE user_id = $1 ORDER BY id DESC LIMIT 1', user_id
            )
            if result != "Goy":
                await message.answer("Новелла доступна только для Гоев! Пройди /test сначала.")
                return
        finally:
            await conn.close()

    logging.info(f"Пользователь {user_id} начал новеллу")
    intro_message = (
        f"{hbold('Поздравляю, ты — гой!')} 🔥\n\n"
        "Ты уже начинаешь видеть, как устроен мир, но до больших высот ещё далеко. Хочешь проверить свои силы? Давай сыграем в мини-игру! Ты станешь предпринимателем, который пытается построить бизнес с нуля. Твои решения определят, станешь ли ты миллионером или останешься у разбитого корыта. Готов рискнуть? Тогда вперёд!"
    )
    await message.answer(intro_message, parse_mode="HTML")

    scene = await get_novel_scene(1)
    if not scene:
        await message.answer("Ошибка: сцены новеллы не найдены!")
        return

    choices = json.loads(scene['choices'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for choice_key, choice_data in choices.items():
        callback_data = NovelCallback(choice=choice_key, scene_id=str(scene['id'])).pack()
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=choice_data['text'], callback_data=callback_data)]
        )

    await send_long_message(message, None, scene['scene_text'], reply_markup=keyboard)
    await state.set_state(TestStates.NOVEL)

# Обработчик выбора в новелле
@router.callback_query(NovelCallback.filter(), StateFilter(TestStates.NOVEL))
async def process_novel_choice(callback_query: CallbackQuery, callback_data: NovelCallback, state: FSMContext):
    user_id = callback_query.from_user.id
    choice = callback_data.choice
    scene_id = callback_data.scene_id
    logging.info(f"Пользователь {user_id} выбрал {choice} в сцене {scene_id}")

    current_scene = await get_novel_scene(scene_id)
    if not current_scene:
        await callback_query.message.answer("Ошибка: текущая сцена не найдена!")
        await callback_query.answer()
        return

    choices = json.loads(current_scene['choices'])
    if choice not in choices:
        await callback_query.message.answer("Ошибка: неверный выбор!")
        await callback_query.answer()
        return

    next_scene_id = choices[choice]['next_scene']
    next_scene = await get_novel_scene(next_scene_id)
    if not next_scene:
        await callback_query.message.edit_text("Ошибка: следующая сцена не найдена!")
        await callback_query.answer()
        return

    if next_scene['is_ending']:
        message = (
            f"{next_scene['scene_text']}\n"

            f"\n{hbold('Конец игры!')} Твой результат: {next_scene['ending_result']}\n"
            f"\nОписание: {ENDING_MESSAGES.get(next_scene['ending_result'], 'Нет описания')}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать новеллу заново", callback_data="start_novel")]
        ])
        await state.set_state(TestStates.FINISHED)
    else:
        choices = json.loads(next_scene['choices'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for choice_key, choice_data in choices.items():
            callback_data = NovelCallback(choice=choice_key, scene_id=str(next_scene['id'])).pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=choice_data['text'], callback_data=callback_data)]
            )
            message = next_scene['scene_text']

    await send_long_message(None, callback_query, message, reply_markup=keyboard)
    await callback_query.answer()

# Обработчик команды /finance_test
@router.message(Command("finance_test"))
async def start_finance_test(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = await get_db_connection()
    if conn:
        try:
            result = await conn.fetchval(
                'SELECT result_category FROM test_results WHERE user_id = $1 ORDER BY id DESC LIMIT 1',
                user_id
            )
            if result != "Middle Class":
                await message.answer("Этот тест доступен только для Среднего класса! Пройди /test сначала.")
                return
        except Exception as e:
            logging.error(f"Ошибка при проверке результата пользователя {user_id}: {e}")
            await message.answer("Ошибка при проверке доступа!")
            return
        finally:
            await conn.close()

    logging.info(f"Пользователь {user_id} начал финансовый тест")
    await state.update_data(current_question=101, score=0, test_type='finance', correct_by_category={})
    question = await get_question(101, test_type='finance')
    if not question:
        await message.answer("Ошибка: вопросы теста не найдены!")
        return

    section = question['category']
    options = json.loads(question['options'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for option_key, option_text in options.items():
        callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='finance').pack()
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
        )

    message_text = f"{hbold(f'Раздел: {section}')}\n\n{question['text']}"
    await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TestStates.FINANCE_TEST)


# Обработчик команды /toggle_reminders
@router.message(Command("toggle_reminders"))
async def toggle_reminders(message: Message):
    user_id = message.from_user.id
    logging.info(f"Пользователь {user_id} запросил переключение напоминаний")
    conn = await get_db_connection()
    if not conn:
        await message.answer("Ошибка базы данных!")
        return
    try:
        current = await conn.fetchval(
            'SELECT reminders_enabled FROM users WHERE user_id = $1', user_id
        )
        new_value = not current
        await conn.execute(
            'UPDATE users SET reminders_enabled = $1 WHERE user_id = $2',
            new_value, user_id
        )
        status = "включены" if new_value else "отключены"
        await message.answer(f"Напоминания {status}! 🔔")
    except Exception as e:
        logging.error(f"Ошибка при переключении напоминаний: {e}")
        await message.answer("Ошибка при настройке напоминаний!")
    finally:
        await conn.close()

# Фоновая задача для напоминаний
async def send_reminders(bot: Bot):
    while True:
        logging.info("Проверка пользователей для напоминаний")
        conn = await get_db_connection()
        if conn:
            try:
                users = await conn.fetch(
                    'SELECT user_id, last_test FROM users WHERE reminders_enabled = TRUE AND (last_test IS NULL OR last_test < NOW() - INTERVAL \'1 day\')'
                )
                for user in users:
                    user_id = user['user_id']
                    try:
                        await bot.send_message(
                            user_id,
                            f"Шалом! 🔥 Давно не проходил тест! Пройди /test и узнай, кто ты!"
                        )
                        logging.info(f"Напоминание отправлено пользователю {user_id}")
                        await conn.execute(
                            'UPDATE users SET last_test = NOW() WHERE user_id = $1',
                            user_id
                        )
                    except Exception as e:
                        logging.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
            except Exception as e:
                logging.error(f"Ошибка при получении пользователей: {e}")
            finally:
                await conn.close()
        await asyncio.sleep(24 * 3600)

# Обработчики для ретестов и старта новых активностей
@router.callback_query(lambda c: c.data in ["retest", "start_goy_quiz", "start_novel", "start_finance_test", "retest_finance"])
async def handle_callbacks(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    action = callback_query.data
    logging.info(f"Пользователь {user_id} выбрал действие: {action}")

    if action == "retest":
        await state.clear()
        await state.update_data(current_question=1, score=0, test_type='initial')
        question = await get_question(1, test_type='initial')
        if not question:
            await callback_query.message.edit_text("Ошибка: вопросы не найдены!")
            return
        options = json.loads(question['options'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for option_key, option_text in options.items():
            callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='initial').pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
            )
        await callback_query.message.edit_text(question['text'], reply_markup=keyboard)
        await state.set_state(TestStates.INITIAL_TEST)
    elif action == "start_goy_quiz":
        await state.clear()
        await state.update_data(current_question=1, score=0, goy_type='goy_quiz')
        question = await get_question(1, test_type='goy_quiz')
        if not question:
            await callback_query.message.edit_text("Ошибка: вопросы викторины не найдены!")
            return
        options = json.loads(question['options'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for option_key, option_text in options.items():
            callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='goy_quiz').pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
            )
        await callback_query.message.edit_text(question['text'], reply_markup=keyboard)
        await state.set_state(TestStates.GOY_QUIZ)
    elif action == "start_novel":
        await state.clear()
        intro_message = (
            f"{hbold('Поздравляю, ты — гой!')} 🔥\n\n"
            "Ты уже начинаешь видеть, как устроен мир, но до больших высот ещё далеко. Хочешь проверить свои силы? Давай сыграем в мини-игру! Ты станешь предпринимателем, который пытается построить бизнес с нуля. Твои решения определят, станешь ли ты миллионером или останешься у разбитого корыта. Готов рискнуть? Тогда вперёд!"
        )
        await callback_query.message.answer(intro_message, parse_mode="HTML")
        scene = await get_novel_scene(1)
        if not scene:
            await callback_query.message.edit_text("Ошибка: сцены новеллы не найдены!")
            return
        choices = json.loads(scene['choices'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for choice_key, choice_data in choices.items():
            callback_data = NovelCallback(choice=choice_key, scene_id=str(scene['id'])).pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=choice_data['text'], callback_data=callback_data)]
            )
        await send_long_message(callback_query.message, None, scene['scene_text'], reply_markup=keyboard)
        await state.set_state(TestStates.NOVEL)
    elif action == "start_finance_test":
        await state.clear()
        await state.update_data(current_question=1, score=0, test_type='finance')
        question = await get_question(1, test_type='finance')
        if not question:
            await callback_query.message.edit_text("Ошибка: вопросы теста не найдены!")
            return
        options = json.loads(question['options'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for option_key, option_text in options.items():
            callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='finance').pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
            )
        await callback_query.message.edit_text(question['text'], reply_markup=keyboard)
        await state.set_state(TestStates.FINANCE_TEST)
    elif action == "retest_finance":
        await state.clear()
        await state.update_data(current_question=1, score=0, test_type='finance')
        question = await get_question(1, test_type='finance')
        if not question:
            await callback_query.message.edit_text("Ошибка: вопросы теста не найдены!")
            return
        options = json.loads(question['options'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for option_key, option_text in options.items():
            callback_data = AnswerCallback(option=option_key, question_id=question['id'], test_type='finance').pack()
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=option_text, callback_data=callback_data)]
            )
        await callback_query.message.edit_text(question['text'], reply_markup=keyboard)
        await state.set_state(TestStates.FINANCE_TEST)

    await callback_query.answer()

async def main():
    logging.info("Бот запущен!")
    asyncio.create_task(send_reminders(bot))
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())