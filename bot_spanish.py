import random
import telebot
from telebot import types
from config import TOKEN
from PIL import Image, ImageDraw, ImageFont
import os
import csv

bot = telebot.TeleBot(TOKEN, parse_mode='MarkdownV2')
print('Spanish bot started...')

FONT_PATH = 'files/gothamrnd_book.otf'
CSV_FILE_PATH = 'files/dictionary_es.csv'


# Функция загрузки словаря из CSV-файла
def load_dictionary(file_path):
    themes_list = {}
    with open(file_path, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            theme = row['theme']
            word = row['word']
            translate = row['translate']
            if theme not in themes_list:
                themes_list[theme] = {}
            themes_list[theme][word] = translate
    return themes_list


themes = load_dictionary(CSV_FILE_PATH)


def generate_image(text):
    image_width, image_height = 800, 320
    font_size = 130
    font = ImageFont.truetype(FONT_PATH, font_size)

    image = Image.new('RGB', (image_width, image_height), 'white')
    draw = ImageDraw.Draw(image)

    while True:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        if text_width <= image_width - 20:
            break
        font_size -= 1
        font = ImageFont.truetype(FONT_PATH, font_size)

    x_position = (image_width - text_width) // 2
    y_position = (image_height - font_size) // 2 - 30
    draw.text((x_position, y_position), text, fill="black", font=font)

    image_path = 'generated_image.png'
    image.save(image_path)
    return image_path


@bot.message_handler(commands=['start'])
def start(message):
    show_main_menu(message.chat.id)


def show_main_menu(chat_id, message_id=None):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Квиз", callback_data="quiz"))
    keyboard.add(types.InlineKeyboardButton(text="Карточки", callback_data="flashcards"))

    with open('files/main_menu.png', 'rb') as img:
        if message_id:
            bot.edit_message_media(
                media=types.InputMediaPhoto(img, caption="Выберите тип игры:"),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=keyboard
            )
        else:
            bot.send_photo(
                chat_id,
                img,
                caption="Выберите тип игры:",
                reply_markup=keyboard,
                parse_mode='MarkdownV2'
            )


@bot.callback_query_handler(func=lambda call: call.data in ["quiz", "flashcards"])
def choose_game_type(call):
    game_type = call.data

    keyboard = types.InlineKeyboardMarkup()
    for theme_name in themes.keys():
        keyboard.add(types.InlineKeyboardButton(text=theme_name, callback_data=f"{game_type}_{theme_name}"))

    # Обновляем сообщение, предлагая выбрать тему
    bot.edit_message_caption(
        caption="Теперь выберите тему:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard,
        parse_mode='MarkdownV2'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("quiz_") or call.data.startswith("flashcards_"))
def handle_theme_selection(call):
    # Исправлено извлечение данных
    game_type, theme_name = call.data.split("_", 1)  # Разделяем данные по символу "_"

    if game_type == "quiz":
        choose_word(call, theme_name)  # Запуск игры "Квиз" с выбранной темой
    elif game_type == "flashcards":
        send_flashcard(call, theme_name)  # Запуск игры "Карточки" с выбранной темой


# Квиз: выбор слова и создание вариантов ответов
def choose_word(call, theme_name, caption=''):
    theme = themes[theme_name]
    word, correct_translate = random.choice(list(theme.items()))
    answers = [correct_translate]

    while len(answers) < 3:
        next_option = random.choice(list(theme.values()))
        if next_option not in answers:
            answers.append(next_option)

    random.shuffle(answers)
    correct_index = answers.index(correct_translate) + 1

    image_path = generate_image(word)

    keyboard = types.InlineKeyboardMarkup()
    for i, answer in enumerate(answers):
        letter = chr(97 + i)
        button_text = f"{letter}) {answer}"
        callback_data = f"answer_{theme_name}_{word}_{letter}_{chr(96 + correct_index)}"
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))

    keyboard.add(types.InlineKeyboardButton(text='⏪ Выход', callback_data="exit"))

    with open(image_path, 'rb') as img:
        bot.edit_message_media(
            media=types.InputMediaPhoto(img, caption=f"{caption}Выберите перевод:", parse_mode='MarkdownV2'),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboard
        )

    os.remove(image_path)


@bot.callback_query_handler(func=lambda call: call.data.startswith("answer_"))
def check_answer(call):
    _, theme_name, word, selected_letter, correct_letter = call.data.split("_")

    if selected_letter == correct_letter:
        caption = f'✅ Правильно\\!\n*{word}* — это *"{themes[theme_name][word]}"*\n\n'
    else:
        caption = f'❌ Неправильно\\!\n*{word}* — это *"{themes[theme_name][word]}"*\n\n'

    choose_word(call, theme_name, caption)


def send_flashcard(call, theme_name, show_translation=False, word=None, translation=None):
    if word is None or translation is None:
        theme = themes[theme_name]
        word, translation = random.choice(list(theme.items()))

    if not show_translation:
        image_path = generate_image(word)
    else:
        image_path = None

    keyboard = types.InlineKeyboardMarkup()
    if not show_translation:
        keyboard.add(types.InlineKeyboardButton(text="❔ Показать перевод", callback_data=f"reveal_{theme_name}_{word}"))
    else:
        keyboard.add(types.InlineKeyboardButton(text=f"✅ {translation}", callback_data="noop"))

    keyboard.add(types.InlineKeyboardButton(text="⏩ Следующее слово", callback_data=f"flashcard_{theme_name}"))
    keyboard.add(types.InlineKeyboardButton(text="⏪ Выход", callback_data="exit"))

    if image_path:
        with open(image_path, 'rb') as img:
            bot.edit_message_media(
                media=types.InputMediaPhoto(img),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
        os.remove(image_path)
    else:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboard
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reveal_"))
def reveal_translation(call):
    _, theme_name, word = call.data.split("_")
    translation = themes[theme_name][word]
    send_flashcard(call, theme_name, show_translation=True, word=word, translation=translation)


@bot.callback_query_handler(func=lambda call: call.data == "noop")
def noop_callback(call):
    bot.answer_callback_query(call.id, text="Перевод уже показан")


@bot.callback_query_handler(func=lambda call: call.data.startswith("flashcard_"))
def show_next_flashcard(call):
    _, theme_name = call.data.split("_")
    send_flashcard(call, theme_name)


@bot.callback_query_handler(func=lambda call: call.data == "exit")
def exit_to_main_menu(call):
    show_main_menu(call.message.chat.id, call.message.message_id)


# Функция для добавления слова в CSV-файл
def add_word_to_csv(theme, word, translation):
    with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([theme, word, translation])


# Обработчик команды add_word
@bot.message_handler(commands=['add_word'])
def add_word(message):
    available_themes = "\n".join([f"\\- {theme}" for theme in themes.keys()])

    message_text = (
        "Введите строку следующего типа\\:\n\\- Тема,Слово,Перевод\n\n"
        "Вот какие есть темы сейчас:\n"
        f"{available_themes}"
        '\nВведи "выход", чтобы отменить добавление слова'
    )

    bot.send_message(message.chat.id, message_text)
    bot.register_next_step_handler(message, process_add_word_input)


# Функция обработки ввода пользователя
def process_add_word_input(message):
    user_input = message.text.strip()

    if user_input.lower() == 'выход':
        show_main_menu(message.chat.id)
        return
    parts = user_input.split(',')

    if len(parts) == 3:
        theme, word, translation = parts

        theme = theme.strip().capitalize()
        word = word.strip().lower()
        translation = translation.strip().lower()

        add_word_to_csv(theme, word, translation)

        global themes
        themes = load_dictionary(CSV_FILE_PATH)

        bot.send_message(message.chat.id, f'Слово *"{word}"* успешно добавлено\nв тему *"{theme}"*\\!')
        show_main_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Ошибка ввода\\. Введите строку в формате: Тема,Слово,Перевод;")
        bot.register_next_step_handler(message, process_add_word_input)


bot.infinity_polling()
