
import discord
from discord.ext import commands
import json
import sqlite3
import os
from datetime import datetime, timezone
TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
with open("config.json") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

@bot.command()
async def nib(ctx, item: str, price: str, *, extra="x1"):
    qty = int(extra.replace("x", "")) if "x" in extra else 1
    p = parse_price(price)
    c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, ?)",
              (ctx.author.id, item.lower(), p, qty, "buy"))
    conn.commit()

@bot.command()
async def inb(ctx, item: str, price: str, *, extra="x1"):
    await nib(ctx, item, price, extra=extra)

@bot.command()
async def nis(ctx, item: str, price: str, *, extra="x1"):
    await handle_sell(ctx, item, price, extra)

@bot.command()
async def ins(ctx, item: str, price: str, *, extra="x1"):
    await handle_sell(ctx, item, price, extra)

async def handle_sell(ctx, item, price, extra):
    qty = int(extra.replace("x", "")) if "x" in extra else 1
    sell_price = parse_price(price) * 0.98
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
    conn.commit()

@bot.command()
async def stock(ctx):
    c.execute("SELECT item, SUM(qty) FROM flips WHERE user_id=? AND type='buy' GROUP BY item", (ctx.author.id,))
    rows = c.fetchall()
    if not rows:
        await ctx.send("📦 You have no inventory.")
        return
    msg = "**📦 Your inventory:**\n"
    for item, qty in rows:
        msg += f"- {{item}} x{{qty}}\n"
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
        msg += f"{{i}}. {{user.name}}: {{int(total):,}} gp\n"
    await ctx.send(msg)

bot.run(config["TOKEN"])
