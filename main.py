import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from groq import Groq

import firebase_admin
from firebase_admin import credentials, db

# =====================
# ENV
# =====================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =====================
# GROQ IA
# =====================
client = Groq(api_key=GROQ_API_KEY)

# =====================
# FIREBASE INIT
# =====================
cred = credentials.Certificate("firebase.json")

firebase_admin.initialize_app(cred, {
    "databaseURL": "https://olivroproibido-a618f-default-rtdb.firebaseio.com"
})

# =====================
# DISCORD BOT
# =====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# FIREBASE FUNÇÕES
# =====================

def get_user(user_id):
    ref = db.reference(f"users/{user_id}")
    data = ref.get()

    if data:
        return data

    return {
        "nickname": None,
        "memory": []
    }


def save_user(user_id, data):
    db.reference(f"users/{user_id}").set(data)


def add_memory(user_id, text):
    ref = db.reference(f"users/{user_id}/memory")
    memory = ref.get() or []

    memory.append(text)
    ref.set(memory[-20:])  # limita memória

# =====================
# EVENTO
# =====================
@bot.event
async def on_ready():
    print(f"Bot online como {bot.user}")

# =====================
# COMANDO NICK
# =====================
@bot.command()
async def nick(ctx, *, name):
    user = get_user(ctx.author.id)
    user["nickname"] = name
    save_user(ctx.author.id, user)

    await ctx.send(f"👍 Agora vou te chamar de {name}")

# =====================
# COMANDO CHAT COM MEMÓRIA
# =====================
@bot.command()
async def chat(ctx, *, message):
    try:
        user = get_user(ctx.author.id)

        nickname = user.get("nickname")
        memory = user.get("memory", [])

        contexto = "\n".join(memory)

        prompt = f"""
Você é um assistente no Discord.

Nome do usuário: {nickname}

Memória da conversa:
{contexto}

Usuário disse:
{message}

Responda naturalmente e curto.
"""

        await ctx.send("🧠 Pensando...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content

        # salva memória
        add_memory(ctx.author.id, f"user: {message}")
        add_memory(ctx.author.id, f"bot: {reply}")

        await ctx.send(reply)

    except Exception as e:
        await ctx.send(f"Erro: {e}")

# =====================
# RUN BOT
# =====================
bot.run(DISCORD_TOKEN)