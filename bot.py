import os
import time
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from pexels_api import API

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not TOKEN or not GROQ_API_KEY or not PEXELS_API_KEY:
    raise ValueError("Faltam variáveis: DISCORD_TOKEN, GROQ_API_KEY, PEXELS_API_KEY")

# --- Servidor Flask (keep-alive para Render) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot do Discord está rodando!"

def run_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)
pexels_api = API(PEXELS_API_KEY)

# ---------- FUNÇÃO DE BUSCA DE IMAGEM ----------
def search_image_pexels(query):
    """Retorna a URL da imagem ou None se não encontrar."""
    try:
        print(f"[Pexels] Buscando por: {query}")
        pexels_api.search(query, page=1, results_per_page=1)
        photos = pexels_api.get_entries()
        if photos:
            # Pega a primeira foto
            photo = photos[0]
            # Tenta obter URL em tamanho médio (fallback para large)
            url = photo.src.get('medium') or photo.src.get('large') or photo.url
            print(f"[Pexels] URL encontrada: {url}")
            return url
        else:
            print("[Pexels] Nenhuma foto encontrada.")
            return None
    except Exception as e:
        print(f"[Pexels] ERRO: {e}")
        return None

# ---------- FUNÇÃO DE RESPOSTA (GROQ) ----------
async def responder_groq(message, prompt):
    thinking = await message.channel.send("🤔 Processando...")
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )
        resposta = completion.choices[0].message.content
        if len(resposta) > 2000:
            resposta = resposta[:1997] + "..."
        await thinking.edit(content=resposta)
    except Exception as e:
        await thinking.edit(content=f"❌ Erro ao consultar Groq: {e}")

# ---------- EVENTOS DO BOT ----------
@bot.event
async def on_ready():
    print(f"✅ Bot logado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Responde quando mencionado
    if bot.user in message.mentions:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            await responder_groq(message, prompt)
        else:
            await message.channel.send("👀 Me pergunte algo junto com a menção!")
        return

    # Comando !groq
    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()
        if not prompt:
            await message.channel.send("❓ Use: `!groq sua pergunta` ou `!groq image:gato`")
            return

        # ---------- COMANDO DE IMAGEM ----------
        if prompt.lower().startswith("image:"):
            search_term = prompt[len("image:"):].strip()
            if not search_term:
                await message.channel.send("❓ Especifique o que quer ver. Ex: `!groq image:gato`")
                return

            # Mensagem de "buscando"
            thinking = await message.channel.send(f"🔍 Procurando `{search_term}`...")

            # Busca a imagem
            image_url = search_image_pexels(search_term)

            if image_url:
                # Cria embed com a imagem
                embed = discord.Embed(title=f"📸 {search_term.capitalize()}")
                embed.set_image(url=image_url)
                embed.set_footer(text="Imagem do Pexels")
                # Edita a mensagem para mostrar o embed
                await thinking.edit(content=None, embed=embed)
            else:
                # Se não encontrou, edita com mensagem de erro
                await thinking.edit(content=f"❌ Nenhuma imagem encontrada para `{search_term}`.")
            return

        # ---------- RESPOSTA DE TEXTO (GROQ) ----------
        await responder_groq(message, prompt)
        return

    # Processa outros comandos (ex: !ping)
    await bot.process_commands(message)

# Trata comandos desconhecidos silenciosamente
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

# ---------- MAIN ----------
if __name__ == "__main__":
    keep_alive()
    time.sleep(2)  # Dá tempo do Flask subir
    bot.run(TOKEN)
