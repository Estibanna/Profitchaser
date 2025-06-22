import sqlite3
from jinja2 import Template

def export_trades_html():
    conn = sqlite3.connect("data/flips.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, item, price, qty, type FROM flips ORDER BY timestamp DESC LIMIT 100")
    trades = c.fetchall()
    conn.close()

    template = Template("""
    <html>
    <head><title>Live Trades</title></head>
    <body style="font-family:sans-serif;">
        <h1>📈 Recent Trades</h1>
        <table border="1" cellpadding="5">
            <tr><th>Time</th><th>Item</th><th>Price</th><th>Qty</th><th>Type</th></tr>
            {% for t in trades %}
            <tr>
                <td>{{ t[0] }}</td>
                <td>{{ t[1] }}</td>
                <td>{{ "{:,}".format(int(t[2])) }} gp</td>
                <td>{{ t[3] }}</td>
                <td>{{ t[4] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """)

    html = template.render(trades=trades)

    with open("trades.html", "w", encoding="utf-8") as f:
        f.write(html)

# Call this function from your bot every x minutes or via !generatehtml command
