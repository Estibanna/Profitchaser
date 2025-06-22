import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')

# Database setup
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/flips.db")
c = conn.cursor()
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

def parse_price(price_str):
    price_str = price_str.lower().replace("gp", "").strip()
    if "b" in price_str:
        return float(price_str.replace("b", "")) * 1_000_000_000
    elif "m" in price_str:
        return float(price_str.replace("m", "")) * 1_000_000
    elif "k" in price_str:
        return float(price_str.replace("k", "")) * 1_000
    else:
        return float(price_str)

# Buy handler
async def handle_buy(ctx, args):
    if len(args) < 2:
        await ctx.send("Usage: `!nib <item name> <price> [x<qty>]`")
        return

    try:
        qty = 1
        if args[-1].lower().startswith("x"):
            qty = int(args[-1][1:])
            price_str = args[-2]
            item = " ".join(args[:-2])
        else:
            price_str = args[-1]
            item = " ".join(args[:-1])

        price = parse_price(price_str)
        item = item.lower().strip()

        c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, ?)",
                  (ctx.author.id, item, price, qty, "buy"))
        conn.commit()

    except Exception as e:
        await ctx.send("❌ Invalid input. Use `!nib dragon pickaxe 22.5m x3`")
        print(f"[ERROR] {e}")
# Sell handler
async def handle_sell(ctx, args):
    if len(args) < 2:
        await ctx.send("Usage: `!nis <item> <price> [x<qty>]`")
        return
    try:
        qty = 1
        if args[-1].startswith("x"):
            qty = int(args[-1][1:])
            price_str = args[-2]
            item = " ".join(args[:-2])
        else:
            price_str = args[-1]
            item = " ".join(args[:-1])

        sell_price = parse_price(price_str) * 0.98
        item = item.lower()

        c.execute("SELECT rowid, price, qty FROM flips WHERE user_id=? AND item=? AND type='buy' ORDER BY timestamp",
                  (ctx.author.id, item))
        rows = c.fetchall()
        remaining = qty
        profit = 0
        for row in rows:
            rowid, buy_price, buy_qty = row
            if remaining == 0:
                break
            used_qty = min(remaining, buy_qty)
            profit += (sell_price - buy_price) * used_qty
            new_qty = buy_qty - used_qty
            if new_qty == 0:
                c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
            else:
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (new_qty, rowid))
            remaining -= used_qty

        if qty - remaining > 0:
            now = datetime.now(timezone.utc)
            c.execute("INSERT INTO profits (user_id, profit, timestamp, month, year) VALUES (?, ?, ?, ?, ?)",
                      (ctx.author.id, profit, now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y")))
            await ctx.send(f"💰 Sold {qty - remaining} x {item} for a profit of {int(profit):,} gp.")
        else:
            await ctx.send("⚠️ Not enough items in stock to match this sale.")
        conn.commit()
    except Exception as e:
        await ctx.send("❌ Invalid input. Use `!nis <item> <price> [x<qty>]`")
        print(e)

# Commands
@bot.command()
async def nib(ctx, *args):
    try:
        if len(args) < 2:
            await ctx.send("⚠️ Usage: !nib <item> <price> [xQuantity]")
            return

        # Detect quantity suffix
        if "x" in args[-1].lower():
            qty_part = args[-1]
            price_part = args[-2]
            item_part = args[:-2]
        else:
            qty_part = "x1"
            price_part = args[-1]
            item_part = args[:-1]

        item = " ".join(item_part).lower()
        price = parse_price(price_part)
        qty = int(qty_part.lower().replace("x", ""))

        c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, ?)",
                  (ctx.author.id, item, price, qty, "buy"))
        conn.commit()
        await ctx.send(f"📥 Added: {item} x{qty} at {int(price):,} gp")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")


@bot.command()
async def inb(ctx, *args):
    await handle_buy(ctx, args)

@bot.command()
async def nis(ctx, *args):
    await handle_sell(ctx, args)

@bot.command()
async def ins(ctx, *args):
    await handle_sell(ctx, args)

@bot.command()
async def stock(ctx):
    c.execute("SELECT item, SUM(qty) FROM flips WHERE user_id=? AND type='buy' GROUP BY item", (ctx.author.id,))
    rows = c.fetchall()
    if not rows:
        await ctx.send("📦 You have no inventory.")
        return
    msg = "**📦 Your inventory:**\n"
    for item, qty in rows:
        msg += f"•  {item} x{qty}\n"
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
    scope_label = "this month" if scope != "all" else "this year"
    await ctx.send(f"📈 Your total profit {scope_label}: {total:,} gp")

@bot.command()
async def top(ctx, scope=None):
    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT user_id, SUM(profit) FROM profits WHERE year=? GROUP BY user_id ORDER BY SUM(profit) DESC LIMIT 10",
                  (now.strftime("%Y"),))
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

bot.run(TOKEN)
