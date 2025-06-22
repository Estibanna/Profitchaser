import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone

# Setup
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Ensure data folder exists
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/flips.db")
c = conn.cursor()

# Database schema
c.execute("""
CREATE TABLE IF NOT EXISTS flips (
    user_id INTEGER,
    item TEXT,
    price REAL,
    qty INTEGER,
    type TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS profits (
    user_id INTEGER,
    profit REAL,
    timestamp TEXT,
    month TEXT,
    year TEXT
)
""")
conn.commit()

# Price parsing

def parse_price(price_str):
    price_str = price_str.lower().replace("gp", "").strip()
    if "b" in price_str:
        return float(price_str.replace("b", "")) * 1_000_000_000
    elif "m" in price_str:
        return float(price_str.replace("m", "")) * 1_000_000
    elif "k" in price_str:
        return float(price_str.replace("k", "")) * 1_000
    return float(price_str)

# Generic parser

def parse_item_args(args):
    qty = 1
    if len(args) >= 3 and args[-1].lower().startswith("x") and args[-1][1:].isdigit():
        qty = int(args[-1][1:])
        price_str = args[-2]
        item_name = " ".join(args[:-2])
    else:
        price_str = args[-1]
        item_name = " ".join(args[:-1])
    return item_name.lower(), parse_price(price_str), qty

# Buy handler

async def record_buy(ctx, args):
    try:
        item, price, qty = parse_item_args(args)
        c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, ?)",
                  (ctx.author.id, item, price, qty, "buy"))
        conn.commit()
    except Exception as e:
        await ctx.send("❌ Invalid input for buy. Use `!nib <item> <price> [x<qty>]`")
        print(e)

# Sell handler

async def record_sell(ctx, args):
    try:
        item, price, qty = parse_item_args(args)
        sell_price = price * 0.98
        c.execute("SELECT rowid, price, qty FROM flips WHERE user_id=? AND item=? AND type='buy' ORDER BY timestamp",
                  (ctx.author.id, item))
        rows = c.fetchall()
        remaining = qty
        profit = 0

        for rowid, buy_price, buy_qty in rows:
            if remaining == 0:
                break
            used = min(remaining, buy_qty)
            profit += (sell_price - buy_price) * used
            new_qty = buy_qty - used
            if new_qty == 0:
                c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
            else:
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (new_qty, rowid))
            remaining -= used

        if qty - remaining > 0:
            now = datetime.now(timezone.utc)
            c.execute("INSERT INTO profits (user_id, profit, timestamp, month, year) VALUES (?, ?, ?, ?, ?)",
                      (ctx.author.id, profit, now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y")))
            conn.commit()
            #await ctx.send(f"💰 Sold {qty - remaining} x {item} for a profit of {int(profit):,} gp.")
        else:
            await ctx.send("⚠️ Not enough stock to sell.")
    except Exception as e:
        await ctx.send("❌ Invalid input for sell. Use `!nis <item> <price> [x<qty>]`")
        print(e)

# Commands

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def nib(ctx, *args):
    await record_buy(ctx, args)

@bot.command()
async def inb(ctx, *args):
    await record_buy(ctx, args)

@bot.command()
async def nis(ctx, *args):
    await record_sell(ctx, args)

@bot.command()
async def ins(ctx, *args):
    await record_sell(ctx, args)

@bot.command()
async def stock(ctx):
    c.execute("SELECT item, SUM(qty) FROM flips WHERE user_id=? AND type='buy' GROUP BY item", (ctx.author.id,))
    rows = c.fetchall()
    if not rows:
        await ctx.send("📦 You have no inventory.")
        return
    msg = "**📦 Your inventory:**\n"
    for item, qty in rows:
        msg += f"• {item} x{qty}\n"
    await ctx.send(msg)

@bot.command()
async def rank(ctx, scope=None):
    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT SUM(profit) FROM profits WHERE user_id=?", (ctx.author.id,))
    else:
        c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND month=?", (ctx.author.id, now.strftime("%Y-%m")))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    label = "this month" if scope != "all" else "this year"
    await ctx.send(f"📈 Your total profit {label}: {total:,} gp")

@bot.command()
async def top(ctx, scope=None):
    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT user_id, SUM(profit) FROM profits GROUP BY user_id ORDER BY SUM(profit) DESC LIMIT 10")
    else:
        c.execute("SELECT user_id, SUM(profit) FROM profits WHERE month=? GROUP BY user_id ORDER BY SUM(profit) DESC LIMIT 10",
                  (now.strftime("%Y-%m"),))
    rows = c.fetchall()
    if not rows:
        await ctx.send("No leaderboard data.")
        return
    msg = "**🏆 Top flippers:**\n"
    for i, (uid, total) in enumerate(rows, 1):
        user = await bot.fetch_user(uid)
        msg += f"{i}. {user.name}: {int(total):,} gp\n"
    await ctx.send(msg)
    
@bot.command()
async def reset(ctx, scope=None):
    if scope == "all":
        c.execute("DELETE FROM flips WHERE user_id=?", (ctx.author.id,))
        c.execute("DELETE FROM profits WHERE user_id=?", (ctx.author.id,))
        conn.commit()
        await ctx.send("🗑️ All your flip and profit history has been deleted.")
    else:
        c.execute("SELECT rowid FROM flips WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (ctx.author.id,))
        row = c.fetchone()
        if row:
            c.execute("DELETE FROM flips WHERE rowid=?", (row[0],))
            conn.commit()
            await ctx.send("↩️ Your last entry has been removed.")
        else:
            await ctx.send("⚠️ You have no flips to reset.")

@bot.command()
async def delete(ctx, *args):
    if len(args) < 2:
        await ctx.send("Usage: `!delete <item> x<qty>`")
        return
    try:
        if args[-1].lower().startswith("x") and args[-1][1:].isdigit():
            qty = int(args[-1][1:])
            item = " ".join(args[:-1]).lower()
        else:
            await ctx.send("Quantity missing or invalid. Use: `!delete item x<qty>`")
            return

        c.execute("SELECT rowid, qty FROM flips WHERE user_id=? AND item=? AND type='buy' ORDER BY timestamp",
                  (ctx.author.id, item))
        rows = c.fetchall()
        remaining = qty
        deleted = 0

        for rowid, available_qty in rows:
            if remaining == 0:
                break
            used = min(remaining, available_qty)
            new_qty = available_qty - used
            if new_qty == 0:
                c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
            else:
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (new_qty, rowid))
            remaining -= used
            deleted += used

        conn.commit()
        if deleted > 0:
            await ctx.send(f"🗑️ Deleted {deleted} x {item} from your inventory.")
        else:
            await ctx.send("❌ You don't have that item or quantity.")
    except Exception as e:
        await ctx.send("❌ Error processing your delete request.")
        print(e)


bot.run(TOKEN)
