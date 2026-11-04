import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

async def main():
    client = TelegramClient('userbot_session', API_ID, API_HASH)
    await client.connect()
    
    phone = input("Enter your phone number (e.g. +251786458717): ").strip()
    
    # First send code request normally
    sent = await client.send_code_request(phone)
    print(f"Code sent! Type: {sent.type}")
    
    # Ask if they want to resend via SMS
    resend = input("Did you receive the code in your Telegram app? (yes/no): ").strip().lower()
    
    if resend == 'no':
        print("Resending code via SMS to your phone number...")
        sent = await client.send_code_request(phone, force_sms=True)
        print("SMS code sent! Check your phone's text messages.")
    
    code = input("Enter the code: ").strip()
    
    try:
        await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
    except Exception as e:
        if "SessionPasswordNeededError" in str(type(e).__name__):
            password = input("Enter your 2-step verification password: ").strip()
            await client.sign_in(password=password)
        else:
            raise e
    
    print("\n✅ Login successful! Session saved.")
    print("You can now run 'python bot.py' and it will start without asking for login again.")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
