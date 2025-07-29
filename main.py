# original
from discord.ext import tasks
import json
import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone
from decimal import Decimal
import re
from datetime import datetime, timezone, timedelta
def is_mod_or_owner(member):
    role_names = [role.name.lower() for role in member.roles]
    return "mods" in role_names or "owners" in role_names
ALLOWED_WATCH_USERS = {"estibanna", "noltie"}  # usernames in kleine letters
ALLOWED_GUILD_IDS = [1334260436098355250, 1397853269971304468]

def is_allowed_guild(ctx):
    return ctx.guild and ctx.guild.id in ALLOWED_GUILD_IDS
    
ALLOWED_DM_USERS = {"sdw2003", "estibanna"}
user_track_requests = {}
def is_allowed_dm_user(ctx):
    return isinstance(ctx.channel, discord.DMChannel) and ctx.author.name.lower() in ALLOWED_DM_USERS





DUELS_FILE = "data/duels.json"

def load_duels():
    if os.path.exists(DUELS_FILE):
        with open(DUELS_FILE, "r") as f:
            data = json.load(f)
            return {tuple(map(int, k.split(","))): datetime.fromisoformat(v) for k, v in data.items()}
    return {}

def save_duels():
    with open(DUELS_FILE, "w") as f:
        data = {f"{k[0]},{k[1]}": v.isoformat() for k, v in active_duels.items()}
        json.dump(data, f)

# Stup
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

bot.remove_command('help')
active_duels = {}  # Dict met (user1_id, user2_id): start_time
# Ensure data folder exists
os.makedirs("data", exist_ok=True)
volume_path = "/app/data/flips.db" if os.getenv("RAILWAY_ENVIRONMENT") else "data/flips.db"
conn = sqlite3.connect(volume_path)

print("[DEBUG] Using database:", os.path.abspath("data/flips.db"))
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
c.execute("""
CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER,
    item TEXT,
    max_price REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS sell_details (
    sell_rowid INTEGER,
    buy_price REAL,
    qty_used INTEGER
)
""")






c.execute("""
CREATE TABLE IF NOT EXISTS finances (
    user_id INTEGER PRIMARY KEY,
    start_balance REAL DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS costs (
    user_id INTEGER,
    item TEXT,
    amount REAL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS drops (
    user_id INTEGER,
    item TEXT,
    amount REAL
)
""")
conn.commit()




try:
    c.execute("ALTER TABLE profits ADD COLUMN item TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Kolom bestaat al, negeer de fout
try:
    c.execute("ALTER TABLE profits ADD COLUMN sell_rowid INTEGER")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Kolom bestaat al, negeer de fout


conn.commit()



















@bot.command()
async def start(ctx, amount: str):
    try:
        value = parse_price(amount)
        c.execute("INSERT OR REPLACE INTO finances (user_id, start_balance) VALUES (?, ?)",
                  (ctx.author.id, value))
        conn.commit()
        await ctx.send(f"🏁 Startamount set to **{int(value):,} gp**.")
    except:
        await ctx.send("❌ Use: `!start 10m` of `!start 250000000GP`")


@bot.command()
async def saldo(ctx):
    c.execute("SELECT COALESCE(start_balance, 0) FROM finances WHERE user_id=?", (ctx.author.id,))
    row = c.fetchone()
    start = row[0] if row else 0

    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=?", (ctx.author.id,))
    profit = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM costs WHERE user_id=?", (ctx.author.id,))
    costs = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM drops WHERE user_id=?", (ctx.author.id,))
    drops = c.fetchone()[0] or 0

    c.execute("SELECT SUM(price * qty) FROM flips WHERE user_id=? AND type='buy'", (ctx.author.id,))
    invested = c.fetchone()[0] or 0

    saldo = start + profit + drops - costs - invested
    total = saldo + invested

    await ctx.send(
        f"💼 Start: {int(start):,} gp\n"
        f"📈 Profit: {int(profit):,} gp\n"
        f"📦 Drops: {int(drops):,} gp\n"
        f"💸 Costs: {int(costs):,} gp\n"
        f"📥 Invested: {int(invested):,} gp\n"
        f"🧮 Liquid wealth: **{int(saldo):,} gp**\n"
        f"💰 Total wealth: **{int(total):,} gp**"
    )

@bot.command()
async def cost(ctx, *args):
    if len(args) < 2:
        await ctx.send("❌ Use: `!cost item amount`")
        return
    try:
        amount = parse_price(args[-1])
        item = " ".join(args[:-1]).lower()
        c.execute("INSERT INTO costs (user_id, item, amount) VALUES (?, ?, ?)", (ctx.author.id, item, amount))
        conn.commit()
        await ctx.send(f"💸 Cost added: {item} — {int(amount):,} gp")
    except:
        await ctx.send("❌ Invalid input. Use: `!cost item 10m`")

@bot.command()
async def drop(ctx, *args):
    if len(args) < 2:
        await ctx.send("❌ Use: `!drop item amount`")
        return
    try:
        amount = parse_price(args[-1])
        item = " ".join(args[:-1]).lower()
        c.execute("INSERT INTO drops (user_id, item, amount) VALUES (?, ?, ?)", (ctx.author.id, item, amount))
        conn.commit()
        await ctx.send(f"📦 Drop added: {item} — {int(amount):,} gp")
    except:
        await ctx.send("❌ Invalid input. Use: `!drop item 10m`")





@bot.command()
@commands.is_owner()
async def clear_all_data(ctx):
    c.execute("DELETE FROM flips")
    c.execute("DELETE FROM profits")
    c.execute("DELETE FROM sell_details")
    c.execute("DELETE FROM costs")
    c.execute("DELETE FROM drops")
    c.execute("DELETE FROM finances")
    c.execute("DELETE FROM watchlist")
    conn.commit()

    # Wis .json-bestanden

    with open("data/duels.json", "w") as f:
        json.dump({}, f)

    await ctx.send("🧹 All data has been wiped.")


def parse_price(price_str):
    price_str = price_str.lower().replace(",", "").strip()
    match = re.fullmatch(r"([\d\.]+)\s*(b|m|k|gp)", price_str)
    if not match:
        raise ValueError("❌ Invalid price: add a suffix like `k`, `m`, `b`, or `gp` (e.g. `540m`).")

    number_str, suffix = match.groups()
    number = Decimal(number_str)

    if suffix == "b":
        return int(number * Decimal("1000000000"))
    elif suffix == "m":
        return int(number * Decimal("1000000"))
    elif suffix == "k":
        return int(number * Decimal("1000"))
    elif suffix == "gp":
        return int(number)
    else:
        raise ValueError("❌ Invalid price suffix. Use `k`, `m`, `b`, or `gp`.")




def parse_item_args(args):
    args = list(args)
    while args and not args[-1].lower().startswith("x") and not any(c.isdigit() for c in args[-1]):
        args.pop()

    qty = 1
    if len(args) >= 3 and args[-1].lower().startswith("x") and args[-1][1:].isdigit():
        qty = int(args[-1][1:])
        price_str = args[-2]
        item_name = " ".join(args[:-2])
    else:
        price_str = args[-1]
        item_name = " ".join(args[:-1])

    if not re.fullmatch(r"[\d\.]+(b|m|k|gp)", price_str.lower()):
        raise ValueError("❌ Invalid price. Add a suffix like `k`, `m`, `b`, or `gp` (e.g. `540m`, `2.5k`).")

    return item_name.lower(), parse_price(price_str), qty




# Buy handler
async def record_buy(ctx, args):
    try:
        item, price, qty = parse_item_args(args)
        now = datetime.now(timezone.utc)
        c.execute(
            "INSERT INTO flips (user_id, item, price, qty, type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (ctx.author.id, item, price, qty, "buy", now.isoformat())
        )

        conn.commit()
        
    except ValueError as ve:
        await ctx.send(str(ve))  # toont fout over ontbrekende suffix
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: `{type(e).__name__}` – {str(e)}")
        print("[BUY ERROR]", type(e).__name__, e)


async def record_sell(ctx, args):
    try:
        # Zorg dat 'buy_user_id' kolom bestaat
        try:
            c.execute("ALTER TABLE sell_details ADD COLUMN buy_user_id INTEGER")
            conn.commit()
            print("[DB MIGRATIE] Kolom 'buy_user_id' toegevoegd")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[DB MIGRATIE] Kolom 'buy_user_id' bestaat al")
            else:
                print("[DB MIGRATIE FOUT]", e)
        
        args = list(args)
        is_p2p = False
        is_p2p = any(arg.lower() == "p2p" for arg in args)
        clean_args = [arg for arg in args if arg.lower() != "p2p"]
        item, price, qty = parse_item_args(clean_args)
        sell_price = price if is_p2p else round(price * 0.98)


        # Haal bestaande buys op mét timestamp
        c.execute("""
            SELECT rowid, price, qty, timestamp
            FROM flips
            WHERE user_id=? AND item=? AND type='buy'
            ORDER BY timestamp
        """, (ctx.author.id, item))
        rows = c.fetchall()

        remaining = qty
        profit = 0
        sell_details = []

        for rowid, buy_price, buy_qty, buy_time in rows:
            if remaining == 0:
                break
            used = min(remaining, buy_qty)
            profit += (sell_price - buy_price) * used
            sell_details.append((buy_price, used, buy_time))
            new_qty = buy_qty - used
            if new_qty == 0:
                c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
            else:
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (new_qty, rowid))
            remaining -= used

        if qty - remaining > 0:
            
            dt_now = datetime.now(timezone.utc)
            now = dt_now.isoformat()

            # Insert verkoop
            c.execute("INSERT INTO flips (user_id, item, price, qty, type, timestamp) VALUES (?, ?, ?, ?, 'sell', ?)",
                      (ctx.author.id, item, sell_price, qty, now))
            
            sell_rowid = c.lastrowid
            # Profits loggen
            c.execute("""
                INSERT INTO profits (user_id, profit, timestamp, month, year, item, sell_rowid)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ctx.author.id, profit, now, dt_now.strftime("%Y-%m"), dt_now.strftime("%Y"), item, sell_rowid))


            # Sell_details vullen met originele koper
            for buy_price, used_qty, buy_time in sell_details:
                c.execute("""
                    SELECT user_id FROM flips
                    WHERE item = ? AND price = ? AND type = 'buy'
                    ORDER BY timestamp ASC LIMIT 1
                """, (item, buy_price))
                result = c.fetchone()
                buy_user_id = result[0] if result else ctx.author.id
                c.execute("""
                    INSERT INTO sell_details (sell_rowid, buy_price, qty_used, buy_user_id)
                    VALUES (?, ?, ?, ?)
                """, (sell_rowid, buy_price, used_qty, buy_user_id))

            # Check marge binnen 5 uur
            max_margin = None
            best_buy = None
            print("sell_details:", sell_details)
            for buy_price, used_qty, buy_time in sell_details:
                if isinstance(buy_time, str):
                    buy_time = datetime.fromisoformat(buy_time)
                if (dt_now - buy_time) <= timedelta(hours=10):
                    margin = price - buy_price
                    if max_margin is None or margin > max_margin:
                        max_margin = margin
                        best_buy = buy_price

            # DM sturen naar Estibanna
            if max_margin is not None:
                try:
                    formatted_buy = format_price(best_buy)
                    formatted_sell = format_price(price)
                    formatted_margin = format_price(max_margin)

                    estibanna_id = 285207995221147648
                    estibanna = await bot.fetch_user(estibanna_id)
                    if estibanna:
                        await estibanna.send(
                            f"📊 `{item}`: {formatted_buy} → {formatted_sell} (+{formatted_margin}) by `{ctx.author.name}`")
                except Exception as e:
                    print("[DM ERROR]", e)

            conn.commit()
        else:
            await ctx.send("⚠️ Not enough stock to sell.")

    except Exception as e:
        print("[UNEXPECTED SELL ERROR]", e)



def get_flipper_rank(total_profit):
    if total_profit >= 1_000_000_000_000:
        return "🪙 Flipping Titan"
    elif total_profit >= 500_000_000_000:
        return "God of GE"
    elif total_profit >= 100_000_000_000:
        return "Market Phantom"
    elif total_profit >= 50_000_000_000:
        return "Shark"
    elif total_profit >= 5_000_000_000:
        return "Capitalist"
    elif total_profit >= 1_000_000_000:
        return "Investor"
    elif total_profit >= 500_000_000:
        return "Tycoon"
    elif total_profit >= 100_000_000:
        return "Merchant"
    elif total_profit >= 10_000_000:
        return "Apprentice"
    else:
        return "Noob"










# Commands

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    global active_duels
    active_duels = load_duels()
    
        
     


def is_allowed_user(ctx):
    return (
        ctx.guild or
        (isinstance(ctx.channel, discord.DMChannel) and ctx.author.name.lower() in ALLOWED_DM_USERS)
    )
@bot.command()
async def nib(ctx, *args):
    if not is_allowed_user(ctx):
        return
    await record_buy(ctx, args)

@bot.command()
async def inb(ctx, *args):
    if not is_allowed_user(ctx):
        return
    await record_buy(ctx, args)

@bot.command()
async def nis(ctx, *args):
    if not is_allowed_user(ctx):
        return
    await record_sell(ctx, args)

@bot.command()
async def ins(ctx, *args):
    if not is_allowed_user(ctx):
        return
    await record_sell(ctx, args)



# Helper om af te ronden naar m/k/gp
def format_price(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}".rstrip("0").rstrip(".") + "k"
    else:
        return f"{int(value)}gp"    

def is_allowed_user(ctx):
    return (
        (ctx.guild and is_allowed_guild(ctx)) or
        (isinstance(ctx.channel, discord.DMChannel) and ctx.author.name.lower() == "estibanna")
    )




@bot.command()
async def stock(ctx):
    c.execute("""
        SELECT item, price, SUM(qty) 
        FROM flips 
        WHERE user_id=? AND type='buy' 
        GROUP BY item, price 
        ORDER BY item, price DESC
    """, (ctx.author.id,))
    rows = c.fetchall()

    if not rows:
        await ctx.author.send("📦 You have no inventory.")
        return

    def short_price(value):
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}".rstrip("0").rstrip(".") + "k"
        else:
            return f"{int(value)}gp"

    msg = "**📦 Your inventory:**\n\n"
    msg += "`{:<18} {:>10} {:>8}`\n".format("Item", "Buy", "Qty")
    msg += "`{:<18} {:>10} {:>8}`\n".format("─" * 18, "─" * 10, "─" * 8)
    for item, price, qty in rows:
        msg += "`{:<18} {:>10} {:>8}`\n".format(item[:18].title(), short_price(price), qty)

    try:
        await ctx.author.send(msg)
        await ctx.send("📬 I’ve sent your inventory in DM.")
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you. Please enable DMs from server members.")


@bot.command()
async def profit(ctx, *, item: str):
    item = item.lower()

    # 1. Totaal aantal stuks via sell_details
    c.execute("""
        SELECT SUM(sd.qty_used)
        FROM profits p
        JOIN sell_details sd ON p.sell_rowid = sd.sell_rowid
        WHERE p.user_id = ? AND p.item = ?
    """, (ctx.author.id, item))
    modern_qty = c.fetchone()[0] or 0

    # 2. Aantal legacy flips zonder sell_details
    c.execute("""
        SELECT COUNT(*)
        FROM profits p
        WHERE p.user_id = ? AND p.item = ?
          AND NOT EXISTS (
              SELECT 1 FROM sell_details sd WHERE sd.sell_rowid = p.sell_rowid
          )
    """, (ctx.author.id, item))
    legacy_flips = c.fetchone()[0] or 0

    # 3. Totale winst (blijft gewoon SUM(profit))
    c.execute("""
        SELECT SUM(profit)
        FROM profits
        WHERE user_id = ? AND item = ?
    """, (ctx.author.id, item))
    total_profit = c.fetchone()[0] or 0

    total_qty = int(modern_qty) + int(legacy_flips)

    if total_qty > 0:
        formatted = format_price(total_profit)
        await ctx.send(f"📈 You have flipped `{total_qty}`x **{item}** with a total profit of **{formatted}**.")
    else:
        await ctx.send(f"❌ No profit data found for `{item}`.")




@bot.command()
async def rank(ctx, scope=None):
    if scope == "all":
        c.execute("SELECT SUM(profit) FROM profits WHERE user_id=?", (ctx.author.id,))
    else:
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND month=?", (ctx.author.id, current_month))

    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    rank = get_flipper_rank(total)
    label = "all-time" if scope == "all" else "this month"
    await ctx.send(f"🏷️ Your current rank ({label}): **{rank}**\n💰 Profit: {total:,} gp")



@bot.command()
async def ranks(ctx):
    msg = "**📊 Flipper Ranks:**\n"
    msg += "• 🪙 Flipping Titan – 1T+\n"
    msg += "• God of GE – 500B+\n"
    msg += "• Market Phantom – 100B+\n"
    msg += "• Shark – 50B+\n"
    msg += "• Capitalist – 5B+\n"
    msg += "• Investor – 1B+\n"
    msg += "• Tycoon – 500M+\n"
    msg += "• Merchant – 100M+\n"
    msg += "• Apprentice – 10M+\n"
    msg += "• Noob – 0+"
    await ctx.send(msg)


    
@bot.command(name="top")
async def top(ctx, scope=None):
    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT user_id, SUM(profit) FROM profits GROUP BY user_id ORDER BY SUM(profit) DESC")
        title = "**🏆 Top flippers of all time:**\n"
    else:
        c.execute("SELECT user_id, SUM(profit) FROM profits WHERE month=? GROUP BY user_id ORDER BY SUM(profit) DESC",
                  (now.strftime("%Y-%m"),))
        title = "**🏆 Top flippers this month:**\n"

    rows = c.fetchall()
    msg = title
    count = 0

    for uid, total in rows:
        member = ctx.guild.get_member(uid)
        if member and not is_mod_or_owner(member):
            display_name = member.display_name
        else:
            user = await bot.fetch_user(uid)
            display_name = user.name

        count += 1
        msg += f"{count}. {display_name}: {int(total):,} gp\n"
        if count == 10:
            break

    await ctx.send(msg if count > 0 else "⚠️ No flips found.")


@bot.command()
async def removewin(ctx):
    c.execute("DELETE FROM profits WHERE user_id=?", (ctx.author.id,))
    conn.commit()
    await ctx.send("💸 All your recorded profits have been removed.")


@bot.command()
async def reset(ctx, scope=None):
    if scope == "all":
        c.execute("DELETE FROM flips WHERE user_id=?", (ctx.author.id,))
        c.execute("DELETE FROM profits WHERE user_id=?", (ctx.author.id,))
        c.execute("DELETE FROM sell_details WHERE sell_rowid IN (SELECT rowid FROM flips WHERE user_id=? AND type='sell')", (ctx.author.id,))
        conn.commit()
        await ctx.send("🗑️ All your flip and profit history has been deleted.")
        return

    elif scope == "cost":
        c.execute("""SELECT rowid, item, amount FROM costs 
                     WHERE user_id=? ORDER BY rowid DESC LIMIT 1""", (ctx.author.id,))
        last = c.fetchone()
        if not last:
            await ctx.send("⚠️ No cost to reset.")
            return
        rowid, item, amount = last
        c.execute("DELETE FROM costs WHERE rowid=?", (rowid,))
        conn.commit()
        await ctx.send(f"↩️ Last cost for `{item}` ({int(amount):,} gp) has been removed.")
        return

    elif scope == "drop":
        c.execute("""SELECT rowid, item, amount FROM drops 
                     WHERE user_id=? ORDER BY rowid DESC LIMIT 1""", (ctx.author.id,))
        last = c.fetchone()
        if not last:
            await ctx.send("⚠️ No drop to reset.")
            return
        rowid, item, amount = last
        c.execute("DELETE FROM drops WHERE rowid=?", (rowid,))
        conn.commit()
        await ctx.send(f"↩️ Last drop for `{item}` ({int(amount):,} gp) has been removed.")
        return

    # Laatste flip (buy of sell)
    c.execute("""SELECT rowid, item, price, qty, type, timestamp
                 FROM flips
                 WHERE user_id=? ORDER BY timestamp DESC LIMIT 1""", (ctx.author.id,))
    last = c.fetchone()

    if not last:
        await ctx.send("⚠️ You have no flips to reset.")
        return

    rowid, item, sell_price, qty, type_, timestamp = last
    item = item.lower()

    if type_ == "buy":
        c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
        conn.commit()
        await ctx.send(f"↩️ Last buy of `{item}` has been removed.")
        return

    elif type_ == "sell":
        # 1. Haal eerst sell_details op
        c.execute("SELECT buy_price, qty_used, buy_user_id FROM sell_details WHERE sell_rowid=?", (rowid,))
        used_buys = c.fetchall()

        if not used_buys:
            await ctx.send("⚠️ Cannot undo sell – no matching sell details found.")
            return

        # 2. Herstel de gebruikte buys
        for buy_price, used_qty, buy_user_id in used_buys:
            c.execute("""SELECT rowid, qty FROM flips 
                         WHERE user_id=? AND item=? AND price=? AND type='buy'
                         ORDER BY timestamp ASC LIMIT 1""",
                      (buy_user_id, item, buy_price))
            existing = c.fetchone()
            if existing:
                buy_rowid, current_qty = existing
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (current_qty + used_qty, buy_rowid))
            else:
                c.execute("""INSERT INTO flips (user_id, item, price, qty, type)
                             VALUES (?, ?, ?, ?, 'buy')""", (buy_user_id, item, buy_price, used_qty))

        # 3. Verwijder sell_details en de verkoop zelf
        c.execute("DELETE FROM sell_details WHERE sell_rowid=?", (rowid,))
        c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))

        # 4. Verwijder bijbehorende winst
        c.execute("""SELECT rowid FROM profits
                     WHERE user_id=? AND item=? ORDER BY timestamp DESC LIMIT 1""", (ctx.author.id, item))
        profit = c.fetchone()
        if profit:
            c.execute("DELETE FROM profits WHERE rowid=?", (profit[0],))

        # 5. Commit pas helemaal op het einde
        conn.commit()
        await ctx.send(f"↩️ Last sell of `{item}` has been undone and {qty}x returned to inventory.")
        return




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


@bot.command()
async def day(ctx):
    today = datetime.now(timezone.utc).date().isoformat()
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND DATE(timestamp)=?", (ctx.author.id, today))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    await ctx.send(f"📅 Your profit today: {total:,} gp")


@bot.command()
async def week(ctx):
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND timestamp >= ?", (ctx.author.id, one_week_ago.isoformat()))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    await ctx.send(f"🗓️ Your profit in the last 7 days: {total:,} gp")


@bot.command()
async def month(ctx):
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND month=?", (ctx.author.id, current_month))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    await ctx.send(f"📆 Your profit this month: {total:,} gp")

@bot.command()
async def year(ctx):
    current_year = datetime.now(timezone.utc).strftime("%Y")
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND year=?", (ctx.author.id, current_year))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    await ctx.send(f"📈 Your profit this year: {total:,} gp")
from ftplib import FTP

@bot.command()
async def payed(ctx, *args):
    item = " ".join(args).lower()
    c.execute("""
        SELECT price, SUM(qty) as total_qty, SUM(price * qty) as total_paid 
        FROM flips 
        WHERE user_id = ? AND item = ? AND type = 'buy' 
        GROUP BY price ORDER BY price DESC
    """, (ctx.author.id, item))
    rows = c.fetchall()

    if not rows:
        await ctx.send(f"❌ No purchases found for `{item}`.")
        return

    msg = f"📊 You paid for: **{item}**\n"
    total_qty = 0
    total_sum = 0
    for price, qty, paid in rows:
        msg += f"• {int(qty)}x at {int(price):,} gp\n"
        total_qty += qty
        total_sum += paid

    msg += f"**Total:** {int(total_qty)} items, {int(total_sum):,} gp"
    await ctx.send(msg)




@bot.command()
async def avgprofit(ctx):
    # 1. Totale winst
    c.execute("""
        SELECT SUM(profit)
        FROM profits
        WHERE user_id = ?
    """, (ctx.author.id,))
    total_profit = c.fetchone()[0] or 0

    # 2. Aantal stuks via sell_details
    c.execute("""
        SELECT SUM(sd.qty_used)
        FROM profits p
        JOIN sell_details sd ON p.sell_rowid = sd.sell_rowid
        WHERE p.user_id = ?
    """, (ctx.author.id,))
    modern_qty = c.fetchone()[0] or 0

    # 3. Aantal flips zonder sell_details
    c.execute("""
        SELECT COUNT(*)
        FROM profits p
        WHERE p.user_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM sell_details sd WHERE sd.sell_rowid = p.sell_rowid
          )
    """, (ctx.author.id,))
    legacy_flips = c.fetchone()[0] or 0

    total_qty = int(modern_qty) + int(legacy_flips)

    if total_qty == 0:
        await ctx.send("❌ No profit data found.")
    else:
        avg = total_profit / total_qty
        await ctx.send(f"📊 Your average profit per flip is: {int(avg):,} gp.")




@bot.command()
async def flips(ctx):
    # Telling van moderne flips met sell_details
    c.execute("""
        SELECT SUM(sd.qty_used)
        FROM profits p
        JOIN sell_details sd ON p.sell_rowid = sd.sell_rowid
        WHERE p.user_id = ?
    """, (ctx.author.id,))
    modern_qty = c.fetchone()[0] or 0

    # Telling van oude flips zonder sell_details
    c.execute("""
        SELECT COUNT(*)
        FROM profits p
        WHERE p.user_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM sell_details sd WHERE sd.sell_rowid = p.sell_rowid
          )
    """, (ctx.author.id,))
    legacy_flips = c.fetchone()[0] or 0

    total_flips = int(modern_qty) + int(legacy_flips)
    await ctx.send(f"🔁 You have completed {total_flips} flips.")












@bot.command()
async def duel(ctx, opponent: discord.Member):
    user1 = ctx.author.id
    user2 = opponent.id

    if user1 == user2:
        await ctx.send("⚠️ You can't duel yourself.")
        return

    key = tuple(sorted((user1, user2)))

    if key in active_duels:
        await ctx.send("⚔️ A duel between you two is already ongoing.")
        return

    start_time = datetime.now(timezone.utc)
    active_duels[key] = start_time
    save_duels()  # Save after starting a duel

    await ctx.send(f"🏁 Duel started between <@{user1}> and <@{user2}>! Ends in 24h.")


@bot.command()
async def duelscore(ctx, opponent: discord.Member):
    user1 = ctx.author.id
    user2 = opponent.id
    key = tuple(sorted((user1, user2)))

    if key not in active_duels:
        await ctx.send("❌ No active duel found between you two.")
        return

    start_time = active_duels[key]
    now = datetime.now(timezone.utc)

    # Check if the duel has expired
    if now > start_time + timedelta(days=1):
        # Fetch scores
        c.execute("""
            SELECT user_id, SUM(profit) FROM profits
            WHERE (user_id = ? OR user_id = ?) AND timestamp >= ?
            GROUP BY user_id
        """, (user1, user2, start_time.isoformat()))
        rows = c.fetchall()

        scores = {user1: 0, user2: 0}
        for uid, total in rows:
            scores[uid] = total

        winner = None
        if scores[user1] > scores[user2]:
            winner = user1
        elif scores[user2] > scores[user1]:
            winner = user2

        # End the duel
        del active_duels[key]

        # Find the #bot-talk channel
        bot_talk_channel = discord.utils.get(ctx.guild.text_channels, name="💬bot-talk")
        if bot_talk_channel:
            if winner:
                await bot_talk_channel.send(
                    f"🏆 The duel between <@{user1}> and <@{user2}> has ended!\n"
                    f"🎉 <@{winner}> wins with {scores[winner]:,.0f} gp!"
                )
            else:
                await bot_talk_channel.send(
                    f"🤝 The duel between <@{user1}> and <@{user2}> ended in a tie!"
                )
        else:
            await ctx.send("⚠️ Could not find the #bot-talk channel to announce the winner.")

        await ctx.send("⏰ The duel has expired and is now over.")
        return

    # Duel is still active
    c.execute("""
        SELECT user_id, SUM(profit) FROM profits
        WHERE (user_id = ? OR user_id = ?) AND timestamp >= ?
        GROUP BY user_id
    """, (user1, user2, start_time.isoformat()))
    rows = c.fetchall()

    scores = {user1: 0, user2: 0}
    for uid, total in rows:
        scores[uid] = total

    await ctx.send(
        f"📊 Duel score (still ongoing):\n"
        f"<@{user1}>: {scores[user1]:,.0f} gp\n"
        f"<@{user2}>: {scores[user2]:,.0f} gp"
    )



@bot.command()
async def watch(ctx, *args):
    if ctx.author.name.lower() not in ALLOWED_WATCH_USERS:
        return  # Alleen toegestane users mogen dit

    if len(args) < 2:
        await ctx.send("❌ Usage: `!watch item price` (e.g. `!watch sirenic scale 10m`)")
        return

    try:
        price_str = args[-1]
        item = " ".join(args[:-1]).lower()

        # Check op geldige eenheid
        if not any(price_str.lower().endswith(suffix) for suffix in ["gp", "k", "m", "b"]):
            raise ValueError("❌ Invalid price. Use `gp`, `k`, `m`, or `b` at the end.")

        parsed_price = parse_price(price_str)

        c.execute("INSERT INTO watchlist (user_id, item, max_price) VALUES (?, ?, ?)",
                  (ctx.author.id, item, parsed_price))
        conn.commit()
        await ctx.send(f"🔔 Watching `{item}` for {int(parsed_price):,} gp or less.")
    except ValueError as ve:
        await ctx.send(str(ve))
    except Exception as e:
        await ctx.send("❌ An error occurred while adding to your watchlist.")
        print(e)



@bot.command()
async def unwatch(ctx, *, item: str):
    c.execute("DELETE FROM watchlist WHERE user_id=? AND item=?", (ctx.author.id, item.lower()))
    conn.commit()
    await ctx.send(f"❌ Stopped watching `{item}`.")

@bot.command()
async def mywatchlist(ctx):
    c.execute("SELECT item, max_price FROM watchlist WHERE user_id=?", (ctx.author.id,))
    rows = c.fetchall()
    if not rows:
        await ctx.send("📭 You're not watching any items.")
        return
    msg = "**👁️ Your watchlist:**\n"
    for item, price in rows:
        msg += f"• {item} ≤ {int(price):,} gp\n"
    await ctx.send(msg)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📘 EDF FlipBot Help",
        description="Here’s a full list of commands you can use:",
        color=discord.Color.blue()
    )

    embed.add_field(name="📥 Buy Commands", value=(
        "`!nib item price`\n"
        "`!inb item price x2`\n"
        "➤ Add items to your inventory"
    ), inline=False)

    embed.add_field(name="💸 Sell Commands", value=(
        "`!nis item price`\n"
        "`!ins item price x2`\n"
        "➤ Sell items and calculate profit (GE tax)"
    ), inline=False)

    embed.add_field(name="📦 Inventory", value=(
        "`!stock` – Show your current inventory\n"
        "`!payed item` – Show what you paid for an item"
    ), inline=False)

    embed.add_field(name="🗑️ Delete & Reset", value=(
        "`!reset` – Undo your last entry\n"
        "`!reset all` – Delete all flips & profits\n"
        "`!delete item x2` – Remove items manually\n"
        "`!removewin` – Remove all your tracked profit"
    ), inline=False)

    embed.add_field(name="📈 Profit Tracking", value=(
        "`!day` – Today's profit\n"
        "`!month` – This month's profit\n"
        "`!year` – This year's profit"
    ), inline=False)

    embed.add_field(name="🏆 Leaderboard", value=(
        "`!top` – Top 10 this month\n"
        "`!top all` – Top 10 all time\n"
        "`!rank` – Your profit this month\n"
        "`!rank all` – Your all-time profit"
    ), inline=False)

    embed.add_field(name="🪙 Extra Stats", value=(
        "`!flips` – Total flips\n"
        "`!avgprofit` – Average profit per flip\n"
        "`!bestitem` – See your most profitable item\n"
    ), inline=False)

    embed.add_field(name="🎖️ Ranks", value=(
        "`!myrank` – Show your rank\n"
        "`!ranks` – See all rank tiers"
    ), inline=False)

    embed.add_field(name="⚔️ Flip Duel", value=(
        "`!duel @user` – Start a 3-day profit duel\n"
        "`!duelscore` – Check your current duel scores"
    ), inline=False)

    

    embed.set_footer(text="Happy flipping! 🧠")

    try:
        await ctx.author.send(embed=embed)
        await ctx.message.add_reaction("📬")
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you. Please enable DMs from server members.")
@bot.command()
async def bestitem(ctx):
    c.execute("""
        SELECT item, SUM(profit) as total_profit
        FROM profits
        WHERE user_id = ?
        GROUP BY item
        ORDER BY total_profit DESC
        LIMIT 1
    """, (ctx.author.id,))
    
    result = c.fetchone()
    if result:
        item, total = result
        await ctx.send(f"🏆 Your best item is **{item}** with **{int(total):,} gp** profit.")
    else:
        await ctx.send("❌ You have no flip data yet.")




@bot.command()
async def fliptoday(ctx):
    today = datetime.now(timezone.utc).date().isoformat()
    c.execute("""
        SELECT p.item, p.profit, f.price AS sell_price, f.qty, p.sell_rowid
        FROM profits p
        JOIN flips f ON p.sell_rowid = f.rowid
        WHERE p.user_id = ? AND DATE(p.timestamp) = ?
        ORDER BY p.timestamp
    """, (ctx.author.id, today))
    rows = c.fetchall()

    if not rows:
        await ctx.send("📭 You haven't completed any flips today (buy + sell).")
        return

    def format_profit(value):
        sign = "+" if value >= 0 else "-"
        value = abs(value)
        if value >= 1_000_000:
            return f"{sign}{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
        elif value >= 1_000:
            return f"{sign}{value / 1_000:.2f}".rstrip("0").rstrip(".") + "k"
        else:
            return f"{int(value)}gp"

    def short_price(value):
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}".rstrip("0").rstrip(".") + "k"
        else:
            return f"{int(value)}gp"

    total_profit = 0
    lines = []

    for item, profit, sell_price, qty, sell_rowid in rows:
        total_profit += profit

        # Bepaal of het een p2p-verkoop was
        original_price = round(sell_price / 0.98)
        expected_ge_price = round(original_price * 0.98)
        is_p2p = abs(sell_price - expected_ge_price) > 2
        display_sell = sell_price if is_p2p else original_price
        sell_display = short_price(display_sell) + (" p2p" if is_p2p else "")

        # Haal de gemiddelde aankoopprijs op uit sell_details
        c.execute("""
            SELECT SUM(qty_used), SUM(buy_price * qty_used)
            FROM sell_details
            WHERE sell_rowid = ?
        """, (sell_rowid,))
        result = c.fetchone()

        if result and result[0]:
            qty_used, total_buy = result
            avg_buy = total_buy / qty_used
            lines.append((item.title(), short_price(avg_buy), sell_display, int(qty_used), format_profit(profit)))
        else:
            lines.append((item.title(), "-", sell_display, int(qty), format_profit(profit)))

    # Bouw output
    msg = "**📊 Flips completed today:**\n\n"
    msg += "`{:<18} {:>9} {:>13} {:>5} {:>10}`\n".format("Item", "Buy", "Sell", "Qty", "Profit")
    msg += "`{:<18} {:>9} {:>13} {:>5} {:>10}`\n".format("─"*18, "─"*9, "─"*13, "─"*5, "─"*10)
    for item, buy, sell, qty, profit in lines:
        msg += "`{:<18} {:>9} {:>13} {:>5} {:>10}`\n".format(item[:18], buy, sell, qty, profit)

    msg += f"\n**Total profit today: {format_profit(total_profit)}**"

    try:
        await ctx.author.send(msg)
        await ctx.send("📬 I’ve sent your flips in DM.")
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you. Please enable DMs from server members.")



@bot.command()
async def modundo(ctx, member: discord.Member, *, item: str):
    if not is_mod_or_owner(ctx.author):
        await ctx.send("❌ Only mods or owners can use this command.")
        return

    uid = member.id
    item = item.lower()

    # Haal laatste SELL op voor dat item
    c.execute("""SELECT rowid, qty FROM flips 
                 WHERE user_id=? AND item=? AND type='sell' 
                 ORDER BY timestamp DESC LIMIT 1""", (uid, item))
    sell = c.fetchone()

    if not sell:
        await ctx.send(f"⚠️ No recent sell found for `{item}` from {member.display_name}.")
        return

    sell_rowid, qty = sell

    # Verwijder SELL
    c.execute("DELETE FROM flips WHERE rowid=?", (sell_rowid,))

    # Probeer recentste buy op te krikken (mag imperfect zijn)
    c.execute("""SELECT rowid FROM flips 
                 WHERE user_id=? AND item=? AND type='buy' 
                 ORDER BY timestamp DESC LIMIT 1""", (uid, item))
    buy = c.fetchone()
    if buy:
        c.execute("UPDATE flips SET qty = qty + ? WHERE rowid=?", (qty, buy[0]))
    else:
        c.execute("""INSERT INTO flips (user_id, item, price, qty, type) 
                     VALUES (?, ?, 0, ?, 'buy')""", (uid, item, qty))

    # Verwijder laatste profit voor dat item
    c.execute("""SELECT rowid FROM profits 
                 WHERE user_id=? AND item=? 
                 ORDER BY timestamp DESC LIMIT 1""", (uid, item))
    profit = c.fetchone()
    if profit:
        c.execute("DELETE FROM profits WHERE rowid=?", (profit[0],))

    conn.commit()
    await ctx.send(f"↩️ Last `{item}` flip from {member.display_name} has been undone.")
    
@bot.command()
async def invested(ctx):
    c.execute("""
        SELECT item, SUM(qty), SUM(price * qty) 
        FROM flips 
        WHERE user_id = ? AND type = 'buy'
        GROUP BY item
    """, (ctx.author.id,))
    rows = c.fetchall()

    if not rows:
        await ctx.send("📭 You currently have no active investments.")
        return

    total = 0
    msg = "**💼 Your current investments:**\n"
    for item, qty, subtotal in rows:
        total += subtotal
        msg += f"• {item} — {int(qty)}x → {int(subtotal):,} gp\n"

    msg += f"\n💰 **Total invested:** {int(total):,} gp"
    await ctx.send(msg)

@bot.command()
async def costs(ctx):
    c.execute("""
        SELECT item, SUM(amount)
        FROM costs
        WHERE user_id = ?
        GROUP BY item
        ORDER BY SUM(amount) DESC
    """, (ctx.author.id,))
    rows = c.fetchall()

    if not rows:
        await ctx.send("📭 You have no recorded costs.")
        return

    msg = "**💸 Your costs:**\n"
    total = 0
    for item, amount in rows:
        total += amount
        msg += f"• {item.title()}: {int(amount):,} gp\n"

    msg += f"\n**Total costs:** {int(total):,} gp"
    await ctx.send(msg)
@bot.command()
async def drops(ctx):
    c.execute("""
        SELECT item, SUM(amount)
        FROM drops
        WHERE user_id = ?
        GROUP BY item
        ORDER BY SUM(amount) DESC
    """, (ctx.author.id,))
    rows = c.fetchall()

    if not rows:
        await ctx.send("📭 You have no recorded drops.")
        return

    msg = "**📦 Your drops:**\n"
    total = 0
    for item, amount in rows:
        total += amount
        msg += f"• {item.title()}: {int(amount):,} gp\n"

    msg += f"\n**Total drops:** {int(total):,} gp"
    await ctx.send(msg)


@bot.command()
async def clearexpenses(ctx):
    c.execute("DELETE FROM costs WHERE user_id=?", (ctx.author.id,))
    c.execute("DELETE FROM drops WHERE user_id=?", (ctx.author.id,))
    conn.commit()
    await ctx.send("🧹 All your costs and drops have been deleted.")
#modstuff


@bot.command()
async def debugprofit(ctx, *, item: str):
    c.execute("SELECT rowid, profit, item, sell_rowid FROM profits WHERE user_id=? AND item=?", (ctx.author.id, item.lower()))
    rows = c.fetchall()
    if not rows:
        await ctx.send("❌ No profit entries found.")
        return
    msg = "**🔎 Profit records:**\n"
    for rowid, profit, name, sell_rowid in rows:
        msg += f"• rowid={rowid}, profit={int(profit)}, item={name}, sell_rowid={sell_rowid}\n"
    await ctx.send(msg)


@bot.command()
async def debugsell(ctx, rowid: int):
    c.execute("SELECT buy_price, qty_used FROM sell_details WHERE sell_rowid = ?", (rowid,))
    rows = c.fetchall()
    if not rows:
        await ctx.send(f"❌ No sell_details found for rowid={rowid}.")
        return
    msg = f"📦 Sell details for rowid {rowid}:\n"
    for price, qty in rows:
        msg += f"• {int(qty)}x bought at {int(price)} gp\n"
    await ctx.send(msg)
    
bot.run(TOKEN)

