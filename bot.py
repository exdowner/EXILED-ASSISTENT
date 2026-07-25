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

# --- Flask keep-alive ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot rodando!"

def run_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Bot ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)
pexels_api = API(PEXELS_API_KEY)

def search_image_pexels(query):
    """Busca uma imagem no Pexels e retorna a URL ou None."""
    try:
        print(f"[Pexels] Buscando por: {query}")
        pexels_api.search(query, page=1, results_per_page=1)
        photos = pexels_api.get_entries()
        print(f"[Pexels] Fotos encontradas: {len(photos) if photos else 0}")
        if photos:
            # Pega a URL da imagem (tamanho médio)
            photo = photos[0]
            # Atributos disponíveis: photo.url, photo.src['medium'], photo.photographer, etc.
            url = photo.url  # ou photo.src.get('medium')
            print(f"[Pexels] URL da imagem: {url}")
            return url
        return None
    except Exception as e:
        print(f"[Pexels] ERRO: {e}")
        return None

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
        await thinking.edit(content=f"❌ Erro: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            await responder_groq(message, prompt)
        else:
            await message.channel.send("👀 Me pergunte algo junto com a menção!")
        return

    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()
        if not prompt:
            await message.channel.send("❓ Use: `!groq sua pergunta` ou `!groq image:gato`")
            return

        # --- Busca de imagem ---
        if prompt.lower().startswith("image:"):
            search_term = prompt[len("image:"):].strip()
            if not search_term:
                await message.channel.send("❓ Especifique o termo. Ex: `!groq image:gato`")
                return

            thinking = await message.channel.send(f"🔍 Procurando `{search_term}`...")
            try:
                image_url = search_image_pexels(search_term)
                print(f"[DEBUG] image_url = {image_url}")
                if image_url:
                    embed = discord.Embed(title=f"📸 {search_term.capitalize()}")
                    embed.set_image(url=image_url)
                    embed.set_footer(text="Imagem do Pexels")
                    await thinking.edit(content=None, embed=embed)
                else:
                    await thinking.edit(content=f"❌ Nenhuma imagem para `{search_term}`.")
            except Exception as e:
                print(f"[ERRO na edição] {e}")
                await thinking.edit(content=f"❌ Erro ao buscar imagem: {e}")
            return

        # --- Resposta de texto com Groq ---
        await responder_groq(message, prompt)
        return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

if __name__ == "__main__":
    keep_alive()
    time.sleep(2)
    bot.run(TOKEN)
