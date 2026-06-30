import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
import json
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
# GROQ
# =========================
client = Groq(api_key=GROQ_API_KEY)

# =========================
# FIREBASE INIT (ENV BASED)
# =========================
firebase_dict = json.loads(FIREBASE_KEY)

cred = credentials.Certificate(firebase_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# FIREBASE FUNCTIONS
# =========================
def get_nickname(user_id):
    doc = db.collection("users").document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict().get("nickname")
    return None

def set_nickname(user_id, nickname):
    db.collection("users").document(str(user_id)).set({
        "nickname": nickname
    })

# =========================
# COMMANDS
# =========================
@bot.event
async def on_ready():
    print(f"Bot online como {bot.user}")

@bot.command()
async def nick(ctx, *, name):
    set_nickname(ctx.author.id, name)
    await ctx.send(f"👍 Beleza, agora vou te chamar de {name}")

@bot.command()
async def chat(ctx, *, message):
    try:
        nickname = get_nickname(ctx.author.id)

        prompt = message
        if nickname:
            prompt = f"O usuário se chama {nickname}. Responda de forma natural: {message}"

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
# FAKE WEB SERVER (RENDER FIX)
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# =========================
# START BOT
# =========================
bot.run(DISCORD_TOKEN)
