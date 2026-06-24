import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from motor.motor_asyncio import AsyncIOMotorClient

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["anon_chat_db"]
users_col = db["users"]
queue_col = db["queue"]

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await users_col.update_one({"_id": message.from_user.id}, {"$set": {"status": "idle", "partner": None}}, upsert=True)
    await message.answer("👋 স্বাগতম অ্যানোনিমাস চ্যাটে!\n\n🔍 পার্টনার খুঁজতে টাইপ করুন: /search\n❌ চ্যাট বন্ধ করতে টাইপ করুন: /stop")

@dp.message(Command("search"))
async def search_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await users_col.find_one({"_id": user_id})
    
    if user and user.get("status") == "chatting":
        return await message.answer("⚠ আপনি অলরেডি একজনের সাথে চ্যাট করছেন! বন্ধ করতে /stop লিখুন।")
        
    await message.answer("🔍 পার্টনার খোঁজা হচ্ছে... দয়া করে অপেক্ষা করুন।")
    await users_col.update_one({"_id": user_id}, {"$set": {"status": "searching"}})
    
    partner = await queue_col.find_one_and_delete({})
    if partner:
        p_id = partner["_id"]
        if p_id == user_id:
            await queue_col.insert_one({"_id": user_id})
            return
            
        await users_col.update_one({"_id": user_id}, {"$set": {"status": "chatting", "partner": p_id}})
        await users_col.update_one({"_id": p_id}, {"$set": {"status": "chatting", "partner": user_id}})
        
        await bot.send_message(user_id, "🎉 পার্টনার পাওয়া গেছে! এখন চ্যাট শুরু করতে পারেন।")
        await bot.send_message(p_id, "🎉 পার্টনার পাওয়া গেছে! এখন চ্যাট শুরু করতে পারেন।")
    else:
        await queue_col.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

@dp.message(Command("stop"))
async def stop_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await users_col.find_one({"_id": user_id})
    
    if user and user.get("status") == "chatting":
        p_id = user["partner"]
        await users_col.update_many({"_id": {"$in": [user_id, p_id]}}, {"$set": {"status": "idle", "partner": None}})
        await bot.send_message(user_id, "❌ চ্যাট বন্ধ করা হয়েছে। আবার খুঁজতে /search লিখুন।")
        await bot.send_message(p_id, "❌ পার্টনার চ্যাট বন্ধ করে দিয়েছে। নতুন পার্টনার খুঁজতে /search লিখুন।")
    elif user and user.get("status") == "searching":
        await queue_col.delete_one({"_id": user_id})
        await users_col.update_one({"_id": user_id}, {"$set": {"status": "idle"}})
        await message.answer("❌ অনুসন্ধান বাতিল করা হয়েছে।")
    else:
        await message.answer("আপনি এখন কোনো চ্যাটে নেই।")

@dp.message()
async def chat_handler(message: types.Message):
    user_id = message.from_user.id
    user = await users_col.find_one({"_id": user_id})
    
    if user and user.get("status") == "chatting":
        p_id = user["partner"]
        try:
            if message.text:
                await bot.send_message(p_id, message.text)
            elif message.sticker:
                await bot.send_sticker(p_id, message.sticker.file_id)
            elif message.photo:
                await bot.send_photo(p_id, message.photo[-1].file_id, caption=message.caption)
        except Exception:
            pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
