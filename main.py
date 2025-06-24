import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone, timedelta
def is_mod_or_owner(member):
    role_names = [role.name.lower() for role in member.roles]
    return "mods" in role_names or "owners" in role_names

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

conn.commit()


try:
    c.execute("ALTER TABLE profits ADD COLUMN item TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Kolom bestaat al, negeer de fout



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
            c.execute("INSERT INTO profits (user_id, profit, timestamp, month, year, item) VALUES (?, ?, ?, ?, ?, ?)",
                      (ctx.author.id, profit, now.isoformat(), now.strftime("%Y-%m"), now.strftime("%Y"), item))

            # Voeg de sell toe aan flips zodat !reset werkt
            c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, ?, ?, 'sell')",
                      (ctx.author.id, item, price, qty))
            # Notificeer watchers uit de database
            c.execute("SELECT user_id, max_price FROM watchlist WHERE item=?", (item,))
            watchers = c.fetchall()
            for watcher_id, max_price in watchers:
                if price <= max_price:
                    user = await bot.fetch_user(watcher_id)
                    try:
                        await user.send(f"🔔 `{item}` has been sold for {int(price):,} gp or less!")
                        # Verwijder de watchlist-entry na melding
                        c.execute("DELETE FROM watchlist WHERE user_id=? AND item=?", (watcher_id, item))
                    except:
                        pass  # gebruiker staat DMs niet toe
                
             
           
            
            conn.commit()

            # Check of iemand deze item trackt (watchlist-alert)
            for user_id, items in user_track_requests.items():
                for tracked_item, limit_price in items:
                    if tracked_item == item.lower() and sell_price <= limit_price:
                        user = await bot.fetch_user(user_id)
                        if user:
                            await user.send(f"📉 `{item}` just hit `{price}` (below your `{limit_price}` alert)")
                            break  # Stuur max 1 bericht per user

        else:
            await ctx.send("⚠️ Not enough stock to sell.")

    except Exception as e:
        await ctx.send("❌ Invalid input for sell. Use `!nis <item> <price> [x<qty>]`")
        print(e)



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

@bot.command()
async def nib(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return
    await record_buy(ctx, args)

@bot.command()
async def inb(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return
    await record_buy(ctx, args)

@bot.command()
async def nis(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return
    await record_sell(ctx, args)

@bot.command()
async def ins(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return
    await record_sell(ctx, args)

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

@bot.command()
async def top(ctx, scope=None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ This command can only be used in a server.")
        return

    now = datetime.now(timezone.utc)
    if scope == "all":
        c.execute("SELECT user_id, SUM(profit) FROM profits GROUP BY user_id ORDER BY SUM(profit) DESC")
        title = "**🏆 Top flippers of all time (non-mods):**\n"
    else:
        c.execute("SELECT user_id, SUM(profit) FROM profits WHERE month=? GROUP BY user_id ORDER BY SUM(profit) DESC",
                  (now.strftime("%Y-%m"),))
        title = "**🏆 Top flippers this month (non-mods):**\n"

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
        conn.commit()
        await ctx.send("🗑️ All your flip and profit history has been deleted.")
        return

    # Probeer eerst laatste SELL te verwijderen
    c.execute("SELECT rowid, item, qty FROM flips WHERE user_id=? AND type='sell' ORDER BY timestamp DESC LIMIT 1", (ctx.author.id,))
    sell = c.fetchone()

    if sell:
        rowid, item, qty = sell
        c.execute("DELETE FROM flips WHERE rowid=?", (rowid,))
        # Zet item terug in voorraad
        c.execute("SELECT rowid, qty FROM flips WHERE user_id=? AND item=? AND type='buy' ORDER BY timestamp DESC LIMIT 1", (ctx.author.id, item))
        existing = c.fetchone()
        if existing:
            c.execute("UPDATE flips SET qty = qty + ? WHERE rowid=?", (qty, existing[0]))
        else:
            c.execute("INSERT INTO flips (user_id, item, price, qty, type) VALUES (?, ?, 0, ?, 'buy')", (ctx.author.id, item, qty))

        # Verwijder laatst geregistreerde winst (correcte aanpak)
        c.execute("SELECT rowid FROM profits WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (ctx.author.id,))
        profit_row = c.fetchone()
        if profit_row:
            c.execute("DELETE FROM profits WHERE rowid=?", (profit_row[0],))

        conn.commit()
        await ctx.send(f"↩️ Last sell of `{item}` has been undone and {qty}x returned to inventory.")
        return

    # Indien geen sell, probeer laatste buy
    c.execute("SELECT rowid, item FROM flips WHERE user_id=? AND type='buy' ORDER BY timestamp DESC LIMIT 1", (ctx.author.id,))
    buy = c.fetchone()
    if buy:
        c.execute("DELETE FROM flips WHERE rowid=?", (buy[0],))
        conn.commit()
        await ctx.send(f"↩️ Last buy of `{buy[1]}` has been removed.")
        return

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


@bot.command()
async def day(ctx):
    today = datetime.now(timezone.utc).date().isoformat()
    c.execute("SELECT SUM(profit) FROM profits WHERE user_id=? AND DATE(timestamp)=?", (ctx.author.id, today))
    row = c.fetchone()
    total = int(row[0]) if row and row[0] else 0
    await ctx.send(f"📅 Your profit today: {total:,} gp")

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
    end_time = start_time + timedelta(days=1)
    active_duels[key] = start_time

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

    c.execute("SELECT user_id, SUM(profit) FROM profits WHERE (user_id=? OR user_id=?) AND timestamp >= ? GROUP BY user_id",
              (user1, user2, start_time.isoformat()))
    rows = c.fetchall()

    scores = {user1: 0, user2: 0}
    for uid, total in rows:
        scores[uid] = total

    await ctx.send(f"📊 Duel score:\n<@{user1}>: {scores[user1]:,.0f} gp\n<@{user2}>: {scores[user2]:,.0f} gp")


@bot.command()
async def watch(ctx, item: str, price: str):
    try:
        parsed_price = parse_price(price)
        c.execute("INSERT INTO watchlist (user_id, item, max_price) VALUES (?, ?, ?)",
                  (ctx.author.id, item.lower(), parsed_price))
        conn.commit()
        await ctx.send(f"🔔 Watching `{item}` for {int(parsed_price):,} gp or less.")
    except Exception as e:
        await ctx.send("❌ Usage: `!watch item price`")
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

bot.run(TOKEN)
