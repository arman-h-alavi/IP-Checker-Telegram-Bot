import time
import asyncio
import aiohttp
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ApplicationBuilder, ContextTypes, ConversationHandler


# Global variables
ip_addresses = []

user_states = {}


# Function to check IP address
async def check_ip_address(ip_address, session):
    url = f"https://check-host.net/check-ping?host={ip_address}&node=ir1.node.check-host.net"
    headers = {'Accept': 'application/json',
               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'}

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            request_id = data["request_id"]
            result_url = f"https://check-host.net/check-result/{request_id}"
            time.sleep(1)
            result = session.get(result_url)

            return ip_address, "OK" if "OK" in result else "not OK"

        else:
            print(f'Request failed with status code {response.status_code}')
            return None


# Function to perform double checks on IP addresses
async def double_check_ips():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for ip_address in ip_addresses:
            task = asyncio.create_task(check_ip_address(ip_address, session))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

    return results

# Defining conversation states
CHOOSING, ADD_IP, REMOVE_IP, SHOW_IP = range(4)


# Function to handle the /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Setting user_state as STARTED
    user_id = update.effective_user.id
    user_states[user_id] = "STARTED"

    reply_markup = ReplyKeyboardMarkup([['اضافه کردن IP', 'حذف کردن IP'], ['نمایش وضعیت IPها']], one_time_keyboard=True, resize_keyboard=True)
    message = "به ربات IP Checker خوش آمدید!"
    await update.message.reply_text(message, reply_markup=reply_markup)

    return CHOOSING


async def push_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup([['/start']], resize_keyboard=True, one_time_keyboard=True)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="برای شروع دکمه start را کلیک کنید",
                                   reply_markup=reply_markup)


# Function to handle the 'Add IP' command
async def add_ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = "لطفا IP مورد نظر را برای اضافه کردن به لیست وارد کنید:"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    return ADD_IP


# Function to handle the IP address input during the 'Add IP' command
async def add_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ip = update.message.text
    ip_addresses.append(ip)
    message = f"{ip} با موفقیت اضافه شد   "
    await update.message.reply_text(message)

    if len(ip_addresses) >= 1:
        asyncio.create_task(run_ip_check_process())  # Start the IP checking process

    return CHOOSING


# Function to handle the 'Remove IP' command
async def remove_ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = "لطفا IP مورد نظر را برای حذف کردن از لیست وارد کنید:"
    await update.message.reply_text(message)
    return REMOVE_IP


# Function to handle the IP address selection during the 'Remove IP' command
async def remove_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ip = update.message.text
    if ip in ip_addresses:
        ip_addresses.remove(ip)
        message = f"{ip} با موفقیت حذف شد   "
    else:
        message = "چنین IP در لیست وجود ندارد!"
    await update.message.reply_text(message)
    return CHOOSING


# Function to handle the 'Show IPs' command
async def show_ips_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(ip_addresses) > 0:
        message = "IP addresses and their status:\n"
        for ip in ip_addresses:
            message += f"IP: {ip}, Status: Unknown\n"  # Status can be updated later during the IP check process
    else:
        message = "No IP addresses found!"
    await update.message.reply_text(message)
    return CHOOSING


# Function to handle unknown commands
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id] is None:
        await push_start(update, context)
        return

    else:
        message = "Unknown command! Please use the provided buttons."
        await update.message.reply_text(message)
        return CHOOSING


# Function to run the IP check process every 3 minutes
async def run_ip_check_process() -> None:
    while True:
        if ip_addresses:
            results = await double_check_ips()

            # Update the status of IP addresses
            ip_status = {}
            try:
                for ip_address, result in results:
                    if isinstance(result, Exception):
                        # Handle the exception here
                        print(f"Exception occurred: {result}")
                        continue

                    if ip_address not in ip_status:
                        ip_status[ip_address] = []

                    ip_status[ip_address].append(result)

            except Exception as e:
                print(e)

            final_results = {}
            for ip_address, statuses in ip_status.items():
                if len(statuses) == 2 and all(status == "OK" for status in statuses):
                    final_results[ip_address] = "✅ سالم است ✅"
                else:
                    final_results[ip_address] = "❌ فیلتر شده ❌"

            # Print the updated IP addresses and their status
            print("IP check results:")
            for ip_address, status in final_results.items():
                print(f"IP: {ip_address}, Status: {status}")

            # Delay for 3 minutes before the next IP check process
            time.sleep(180)


# Entry point of the program
if __name__ == "__main__":
    # Insert your personal telegram token instead of 'YOUR_TOKEN' below
    application = ApplicationBuilder().token('YOUR_TOKEN').build()

    # Create the ConversationHandler and add the handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            CHOOSING: [MessageHandler(filters.Regex ('^اضافه کردن IP$'), add_ip_command),
                       MessageHandler(filters.Regex('^حذف کردن IP$'), remove_ip_command),
                       MessageHandler(filters.Regex('^نمایش وضعیت IPها$'), show_ips_command)],
            ADD_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ip)],
            REMOVE_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_ip)],
            SHOW_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_ips_command)],
        },
        fallbacks=[MessageHandler(filters.COMMAND, unknown_command)]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT, unknown_command))

    application.run_polling()



