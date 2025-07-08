# original
from discord.ext import tasks
import json
import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone, timedelta
def is_mod_or_owner(member):
    role_names = [role.name.lower() for role in member.roles]
    return "mods" in role_names or "owners" in role_names
ALLOWED_WATCH_USERS = {"estibanna", "noltie"}  # usernames in kleine letters
TRIAL_FILE = "data/trials.json"
TRIAL_ROLE_NAME = "Millionaire"

ALLOWED_GUILD_ID = 696926502171836506

def is_allowed_guild(ctx):
    return ctx.guild and ctx.guild.id == ALLOWED_GUILD_ID
    
ALLOWED_DM_USERS = {"sdw2003", "estibanna"}

def is_allowed_dm_user(ctx):
    return isinstance(ctx.channel, discord.DMChannel) and ctx.author.name.lower() in ALLOWED_DM_USERS


# Ensure trials file exists
if not os.path.exists(TRIAL_FILE):
    with open(TRIAL_FILE, "w") as f:
        json.dump({}, f)

def load_trials():
    with open(TRIAL_FILE, "r") as f:
        return json.load(f)

def save_trials(data):
    with open(TRIAL_FILE, "w") as f:
        json.dump(data, f)


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
    c.execute("SELECT start_balance FROM finances WHERE user_id=?", (ctx.author.id,))
    row = c.fetchone()
    if not row:
        await ctx.send("⚠️ You have not set a start amount yet, use `!start`.")
        return

    start = row[0]
    c.execute("SELECT SUM(price * qty) FROM flips WHERE user_id=? AND type='buy'", (ctx.author.id,))
    invested = c.fetchone()[0] or 0

    saldo = start - invested
    await ctx.send(f"💼 Start: {int(start):,} gp\n💸 Invested: {int(invested):,} gp\n🧮 Remaining saldo: **{int(saldo):,} gp**")

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
async def end(ctx):
    c.execute("SELECT start_balance FROM finances WHERE user_id=?", (ctx.author.id,))
    row = c.fetchone()
    if not row:
        await ctx.send("⚠️ Je hebt nog geen startbedrag ingesteld. Gebruik `!start`.")
        return
    start = row[0]

    # Winst
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=?", (ctx.author.id,))
    profit = c.fetchone()[0] or 0

    # Kosten
    c.execute("SELECT SUM(amount) FROM costs WHERE user_id=?", (ctx.author.id,))
    costs = c.fetchone()[0] or 0

    # Drops
    c.execute("SELECT SUM(amount) FROM drops WHERE user_id=?", (ctx.author.id,))
    drops = c.fetchone()[0] or 0

    # Investering
    c.execute("SELECT SUM(price * qty) FROM flips WHERE user_id=? AND type='buy'", (ctx.author.id,))
    invested = c.fetchone()[0] or 0

    # Berekeningen
    liquid = start + profit + drops - costs - invested
    total = liquid + invested

    msg = (
        f"📘 **General Overview:**\n"
        f"Start: {int(start):,} gp\n"
        f"+ Profit: {int(profit):,} gp\n"
        f"- Costs: {int(costs):,} gp\n"
        f"+ Drops: {int(drops):,} gp\n"
        f"+ Total investment atm: {int(invested):,} gp\n"
        f"----------------------------------\n"
        f"💼 Liquid wealth: {int(liquid):,} gp\n"
        f"📦 Total wealth (incl. stock): {int(total):,} gp"
    )
    await ctx.send(msg)












# Price parsing
def parse_price(price_str):
    original = price_str  # Bewaar voor foutmelding
    price_str = price_str.lower().replace("gp", "").strip()

    if price_str.endswith("b"):
        return float(price_str[:-1]) * 1_000_000_000
    elif price_str.endswith("m"):
        return float(price_str[:-1]) * 1_000_000
    elif price_str.endswith("k"):
        return float(price_str[:-1]) * 1_000
    elif original.lower().endswith("gp"):
        return float(price_str)
    else:
        raise ValueError("❌ Invalid price: include a unit like `k`, `m`, `b`, or `gp`.")

# Generic parser
def parse_item_args(args):
    args = list(args)
    # Strip trailing non-qty words like 'stretch', 'gl', 'fast'
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
        print("✅ Inserted flip into database.")
        print("📂 Current DB path:", os.path.abspath("data/flips.db"))

#sell_handle
async def record_sell(ctx, args):
    try:
        is_p2p = False
        if args and args[-1].lower() == "p2p":
            args = args[:-1]
            is_p2p = True

        item, price, qty = parse_item_args(args)
        sell_price = price if is_p2p else price * 0.98
        c.execute("SELECT rowid, price, qty FROM flips WHERE user_id=? AND item=? AND type='buy' ORDER BY timestamp",
                  (ctx.author.id, item))
        rows = c.fetchall()
        remaining = qty
        profit = 0
        sell_details = []  # ← Nieuw: om bij te houden wat er is gebruikt

        for rowid, buy_price, buy_qty in rows:
            if remaining == 0:
                break
            used = min(remaining, buy_qty)
            profit += (sell_price - buy_price) * used
            sell_details.append((buy_price, used))  # ← Log de gebruikte buy
            new_qty = buy_qty - used
            if new_qty == 0:
                c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
            else:
                c.execute("UPDATE flips SET qty=? WHERE rowid=?", (new_qty, rowid))
            remaining -= used

        if qty - remaining > 0:
            now = datetime.now(timezone.utc)
            c.execute("INSERT INTO profits (user_id, profit, timestamp, month, year, item) VALUES (?, ?, ?, ?, ?, ?)",
                      (ctx.author.id, profit, now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y"), item))

            # Voeg sell toe zodat !reset weet wat de verkoop was
            c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, 'sell')",
                      (ctx.author.id, item, price, qty))
            
            # Haal rowid van zojuist toegevoegde sell op
            c.execute("""SELECT rowid FROM flips 
                         WHERE user_id=? AND item=? AND price=? AND qty=? AND type='sell' 
                         ORDER BY timestamp DESC LIMIT 1""",
                      (ctx.author.id, item, price, qty))
            sell_row = c.fetchone()
            if sell_row:
                sell_rowid = sell_row[0]
                # Voeg gebruikte buys toe aan sell_details-tabel
                for buy_price, used_qty in sell_details:
                    c.execute("INSERT INTO sell_details (sell_rowid, buy_price, qty_used) VALUES (?, ?, ?)",
                              (sell_rowid, buy_price, used_qty))

            # Notificeer watchers uit de database
            c.execute("SELECT user_id, max_price FROM watchlist WHERE item=?", (item,))
            watchers = c.fetchall()
            for watcher_id, max_price in watchers:
                if price <= max_price:
                    user = await bot.fetch_user(watcher_id)
                    try:
                        await user.send(f"🔔 `{item}` has been sold for {int(price):,} gp or less!")
                        c.execute("DELETE FROM watchlist WHERE user_id=? AND item=?", (watcher_id, item))
                    except:
                        pass

            conn.commit()

            # Check user_track_requests alerts
            for user_id, items in user_track_requests.items():
                for tracked_item, limit_price in items:
                    if tracked_item == item.lower() and sell_price <= limit_price:
                        user = await bot.fetch_user(user_id)
                        if user:
                            await user.send(f"📉 `{item}` just hit `{price}` (below your `{limit_price}` alert)")
                            break
        else:
            await ctx.send("⚠️ Not enough stock to sell.")

    except Exception as e:
        await ctx.send("❌ Invalid input for sell. Use `!nis <item> <price> [x<qty>]`")
        print("[SELL ERROR]", e)
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






@bot.command()
async def trial(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    # Load existing trials
    trials = load_trials()

    # Already had a trial?
    if str(member.id) in trials:
        await ctx.send(f"❌ <@{member.id}> has already received a trial before.")
        return

    role = discord.utils.get(ctx.guild.roles, name=TRIAL_ROLE_NAME)
    if not role:
        await ctx.send("❌ Role 'Millionaire' not found.")
        return

    if role in member.roles:
        await ctx.send(f"⚠️ <@{member.id}> already has the role.")
        return

    # Give role
    await member.add_roles(role)
    trials[str(member.id)] = {
        "start": datetime.now(timezone.utc).isoformat(),
        "end": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    }
    save_trials(trials)

    await ctx.send(f"✅ Trial started for <@{member.id}>. The role will be removed automatically in 7 days.")

@tasks.loop(hours=6)
async def check_trial_expiry():
    now = datetime.now(timezone.utc)
    trials = load_trials()
    updated = False

    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=TRIAL_ROLE_NAME)
        if not role:
            continue

        for uid, info in list(trials.items()):
            try:
                end_time = datetime.fromisoformat(info["end"])
                if now >= end_time:
                    member = guild.get_member(int(uid))
                    if member and role in member.roles:
                        await member.remove_roles(role)
                        channel = discord.utils.get(guild.text_channels, name="💬bot-talk")
                        if channel:
                            await channel.send(f"⏳ The trial of <@{uid}> has expired. Role removed.")
                    del trials[uid]
                    updated = True
            except Exception as e:
                print(f"[trial-check] Error with {uid}: {e}")

    if updated:
        save_trials(trials)

@check_trial_expiry.before_loop
async def before_trial_check():
    await bot.wait_until_ready()




# Commands

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    global active_duels
    active_duels = load_duels()
    if not check_trial_expiry.is_running():
        check_trial_expiry.start()
        
     


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





@bot.command()
async def stock(ctx):
    c.execute("SELECT item, SUM(qty) FROM flips WHERE user_id=? AND type='buy' GROUP BY item", (ctx.author.id,))
    rows = c.fetchall()

    if not rows:
        await ctx.author.send("📦 You have no inventory.")
        return

    msg = "**📦 Your inventory:**\n"
    for item, qty in rows:
        msg += f"• {item} x{qty}\n"

    try:
        await ctx.author.send(msg)
        await ctx.send("📬 I’ve sent your inventory in DM.")
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you. Please enable DMs from server members.")


@bot.command()
async def profit(ctx, *, item: str):
    item = item.lower()

    # Haal totaal winst en aantal flips op voor dat item
    c.execute("""
        SELECT COUNT(*), SUM(profit)
        FROM profits
        WHERE user_id = ? AND item = ?
    """, (ctx.author.id, item))

    row = c.fetchone()
    if row and row[0]:
        count, total_profit = row
        formatted = format_price(total_profit)
        await ctx.send(f"📈 You have flipped `{count}`x **{item}** with a total profit of **{formatted}**.")
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

def is_allowed_user(ctx):
    return (
        (ctx.guild and is_allowed_guild(ctx)) or
        (isinstance(ctx.channel, discord.DMChannel) and ctx.author.name.lower() == "estibanna")
    )

    
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
            user = await bot.fetch_user(uid)
            display_name = member.display_name if member else user.name
            count += 1
            msg += f"{count}. {display_name}: {int(total):,} gp\n"
        if count == 10:
            break

    await ctx.send(msg if count > 0 else "⚠️ No flips found.")

@bot.command()
async def topmod(ctx, scope=None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return

    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT user_id, SUM(profit) FROM profits GROUP BY user_id ORDER BY SUM(profit) DESC")
        title = "**👑 Top Mod Flippers of all time:**\n"
    else:
        c.execute("SELECT user_id, SUM(profit) FROM profits WHERE month=? GROUP BY user_id ORDER BY SUM(profit) DESC",
                  (now.strftime("%Y-%m"),))
        title = "**👑 Top Mod Flippers this month:**\n"

    rows = c.fetchall()
    msg = title
    count = 0

    for uid, total in rows:
        member = ctx.guild.get_member(uid)
        if member and is_mod_or_owner(member):
            user = await bot.fetch_user(uid)
            display_name = member.display_name if member else user.name
            count += 1
            msg += f"{count}. {display_name}: {int(total):,} gp\n"
        if count == 10:
            break

    await ctx.send(msg if count > 0 else "⚠️ No mod/owner flips found.") 



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

    # Laatste transactie ophalen (buy of sell)
    c.execute("""
        SELECT rowid, item, price, qty, type, timestamp
        FROM flips
        WHERE user_id=?
        ORDER BY timestamp DESC LIMIT 1
    """, (ctx.author.id,))
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
        # Gebruik sell_details om exact te herstellen
        c.execute("SELECT buy_price, qty_used FROM sell_details WHERE sell_rowid=?", (rowid,))
        used_buys = c.fetchall()

        if not used_buys:
            await ctx.send("⚠️ Cannot undo sell – no matching sell details found.")
            return

        # Verwijder de verkoop zelf + details
        c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
        c.execute("DELETE FROM sell_details WHERE sell_rowid=?", (rowid,))

        # Zet de aankopen terug in voorraad
        for buy_price, q in used_buys:
            c.execute("""
                INSERT INTO flips (user_id, item, price, qty, type)
                VALUES (?, ?, ?, ?, 'buy')
            """, (ctx.author.id, item, buy_price, q))

        # Verwijder bijbehorende winstregel
        c.execute("""
            SELECT rowid FROM profits
            WHERE user_id=? AND item=?
            ORDER BY timestamp DESC LIMIT 1
        """, (ctx.author.id, item))
        profit = c.fetchone()
        if profit:
            c.execute("DELETE FROM profits WHERE rowid=?", (profit[0],))

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
    c.execute("SELECT AVG(profit) FROM profits WHERE user_id=?", (ctx.author.id,))
    row = c.fetchone()
    if row and row[0]:
        await ctx.send(f"📊 Your average profit per flip is: {int(row[0]):,} gp.")
    else:
        await ctx.send("❌ No profit data found.")

@bot.command()
async def flips(ctx):
    c.execute("SELECT COUNT(*) FROM profits WHERE user_id=?", (ctx.author.id,))
    row = c.fetchone()
    if row:
        await ctx.send(f"🔁 You have completed {row[0]} flips.")
    else:
        await ctx.send("❌ No flips found.")





# Globale dict om track requests bij te houden
user_track_requests = {}

@bot.command()
async def track(ctx, item: str, price: str):
    try:
        gp_price = parse_price(price)  # Zorg dat deze functie bestaat zoals elders in je code
        user_track_requests.setdefault(ctx.author.id, []).append((item.lower(), gp_price))
        await ctx.send(f"🔔 Tracking `{item}`. You'll get a DM if it drops below {price}.")
    except Exception as e:
        await ctx.send("❌ Usage: `!track [item] [price]`")
        print(e)






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
async def rolls(ctx):
    member = ctx.guild.get_member(ctx.author.id)
    if not member:
        await ctx.send("❌ Bot kon je member-info niet ophalen (get_member is None).")
        return

    rollen = [f"{role.name} ({role.id})" for role in member.roles]
    await ctx.send("🧾 Jouw rollen:\n" + "\n".join(rollen))


@bot.command()
async def fliptoday(ctx):
    today = datetime.now(timezone.utc).date().isoformat()
    c.execute("""
        SELECT item, profit, timestamp
        FROM profits
        WHERE user_id = ? AND DATE(timestamp) = ?
        ORDER BY timestamp
    """, (ctx.author.id, today))
    rows = c.fetchall()

    if not rows:
        await ctx.send("📭 You haven't completed any flips today (buy + sell).")
        return

    # Helper om winst/verlies mooi te formatteren
    def format_profit(value):
        sign = "+" if value >= 0 else "-"
        value = abs(value)
        if value >= 1_000_000:
            return f"{sign}{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
        elif value >= 1_000:
            return f"{sign}{value / 1_000:.2f}".rstrip("0").rstrip(".") + "k"
        else:
            return f"{sign}{int(value)}gp"

    msg = "**📊 Flips completed today:**\n"
    total_profit = 0
    for item, profit, _ in rows:
        total_profit += profit
        msg += f"{item.title()}: **{format_profit(profit)}**\n"

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


    
bot.run(TOKEN)

