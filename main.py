import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from groq import Groq
import firebase_admin
from firebase_admin import credentials, db
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# =========================
# ENV
# =========================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FIREBASE_KEY = os.getenv("FIREBASE_KEY")

# =========================
# GROQ IA
# =========================
client = Groq(api_key=GROQ_API_KEY)

# =========================
# FIREBASE REALTIME DB
# =========================
firebase_dict = json.loads(FIREBASE_KEY)

cred = credentials.Certificate(firebase_dict)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://olivroproibido-a618f-default-rtdb.firebaseio.com/'
})

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# MEMÓRIA (REALTIME DB)
# =========================
def set_nickname(user_id, nickname):
    ref = db.reference(f"users/{user_id}")
    ref.set({
        "nickname": nickname
    })

def get_nickname(user_id):
    ref = db.reference(f"users/{user_id}")
    data = ref.get()
    if data:
        return data.get("nickname")
    return None

# =========================
# EVENTO
# =========================
@bot.event
async def on_ready():
    print(f"🤖 Bot online como {bot.user}")

# =========================
# COMANDO DE APELIDO
# =========================
@bot.command()
async def nick(ctx, *, name):
    set_nickname(ctx.author.id, name)
    await ctx.send(f"👍 Agora vou te chamar de {name}")

# =========================
# CHAT COM MEMÓRIA + PT-BR FORÇADO
# =========================
@bot.command()
async def chat(ctx, *, message):
    try:
        nickname = get_nickname(ctx.author.id)

        if nickname:
            prompt = f"""
Você é um assistente inteligente.

REGRAS:
- fale SEMPRE em português do Brasil
- seja natural, direto e útil
- lembre que o usuário se chama {nickname}

Usuário ({nickname}) disse: {message}
"""
        else:
            prompt = f"""
Você é um assistente inteligente.

REGRAS:
- fale SEMPRE em português do Brasil
- seja natural e útil

Usuário disse: {message}
"""

        await ctx.send("🧠 Pensando...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        await ctx.send(response.choices[0].message.content)

    except Exception as e:
        await ctx.send(f"Erro: {e}")

# =========================
# RENDER KEEP ALIVE (PORTA)
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot online")

    def log_message(self, format, *args):
        return

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# =========================
# START BOT
# =========================
bot.run(DISCORD_TOKEN)
