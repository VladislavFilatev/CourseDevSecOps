import os
import logging
from dotenv import load_dotenv
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

load_dotenv()
bot = Bot(os.getenv("BOT_TOKEN"))
dp = Dispatcher()

import psycopg2
from psycopg2 import sql


DB_CONFIG = {
	"dbname": os.getenv("POSTGRES_DB"),
	"user": os.getenv("POSTGRES_USER"),
	"password": os.getenv("POSTGRES_PASSWORD"),
	"host": "bd",
	"port": "5432"
}

  

def add_user_if_not_exists(user_id, name, db_connection_params):
	query_check = sql.SQL("SELECT 1 FROM users WHERE user_id = %s")
	query_insert = sql.SQL("INSERT INTO users (user_id, name) VALUES (%s, %s)")
 
	try:
		with psycopg2.connect(**db_connection_params) as conn:
			with conn.cursor() as cursor:
				cursor.execute(query_check, (user_id,))
				if cursor.fetchone() is not None:
					print(f"Пользователь с id={user_id} уже существует")
					return False

				cursor.execute(query_insert, (user_id, name))
				conn.commit()
				print(f"Добавлен пользователь: id={user_id}, name={name}")
				return True

	except psycopg2.Error as e:
		print(f"Ошибка при работе с БД: {e}")
		return False

  
def add_note(record, user_id, db_connection_params):

	try:
		conn = psycopg2.connect(**db_connection_params)
		cursor = conn.cursor()

		query = sql.SQL("""
			INSERT INTO notes (record, user_id)
			VALUES (%s, %s)
			RETURNING id
		""")

		cursor.execute(query, (record, user_id))
		note_id = cursor.fetchone()[0]
		conn.commit()
		return note_id

	except psycopg2.Error as e:
		print(f"Ошибка при добавлении заметки: {e}")
		if conn:
			conn.rollback()
			return None
	finally:
		if conn:
			conn.close()

  

def get_all_notes(user_id, db_connection_params):
	conn = None
	try:
		conn = psycopg2.connect(**db_connection_params)
		cursor = conn.cursor()

		query = sql.SQL("""
			SELECT id, record
			FROM notes
			WHERE user_id = %s
		""")

		cursor.execute(query, (user_id,))
		notes = cursor.fetchall()
		return notes

	except psycopg2.Error as e:
		print(f"Ошибка при получении заметок: {e}")
		return None

	finally:
		if conn:
			conn.close()


@dp.message(CommandStart())
async def cmd_start(message: Message):
	user_id = message.from_user.id
	user_name = message.from_user.username

	add_user_if_not_exists(str(user_id), user_name, DB_CONFIG)
	await message.answer("📝 Добро пожаловать в бота для заметок!\n"
		"Доступные команды:\n"
		"/add - добавить заметку\n"
		"/all - посмотреть все заметки")


class AddNote(StatesGroup):
	wait = State()


@dp.message(Command('add'))
async def cmd_add(message: Message, state: FSMContext):
	await state.set_state(AddNote.wait)
	await message.answer("Что хотите записать?✏️")


@dp.message(AddNote.wait)
async def reg_hosts(message: Message, state: FSMContext):
	user_id = str(message.from_user.id)
	text = message.text

	add_note(text, user_id, DB_CONFIG)

	await state.clear()
	await message.answer("Заметка добавлена📝")

  
@dp.message(Command('all'))
async def cmd_all(message: Message):
	user_id = str(message.from_user.id)
	notes = get_all_notes(user_id, DB_CONFIG)

	if not notes:
		await message.answer("У вас пока нет заметок")
		return

	response = "📖 Ваши заметки:\n\n"
	for note in notes:
		response += f"📌 {note[1]}\n\n"

	await message.answer(response)

  
async def main():
	await dp.start_polling(bot)


if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print("Exit")
