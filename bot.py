import os
import time
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Biblioteca do Pexels (instale com: pip install pexels-api-py)
from pexels_api import API

# Carrega variáveis do .env
load_dotenv()

# --- Variáveis de ambiente ---
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not TOKEN or not GROQ_API_KEY or not PEXELS_API_KEY:
    raise ValueError(
        "Faltam variáveis de ambiente. Configure DISCORD_TOKEN, GROQ_API_KEY e PEXELS_API_KEY."
    )

# --- Servidor Flask para keep-alive (Render) ---
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

# --- Clientes ---
intents = discord.Intents.default()
intents.message_content = True  # necessário para ler mensagens

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)
pexels_api = API(PEXELS_API_KEY)

# --- Função para buscar imagem no Pexels ---
def search_image_pexels(query, per_page=1):
    """
    Busca uma imagem no Pexels.
    Retorna a URL da imagem (tamanho médio) ou None se não encontrar.
    """
    try:
        pexels_api.search(query, page=1, results_per_page=per_page)
        photos = pexels_api.get_entries()
        if photos:
            # Pega a URL da imagem (tamanho médio, boa para Discord)
            return photos[0].url
        return None
    except Exception as e:
        print(f"[ERRO Pexels] {e}")
        return None

# --- Função para responder com a Groq (texto) ---
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
        await thinking.edit(content=f"❌ Erro ao consultar a Groq: {e}")

# --- Eventos do bot ---
@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user} (ID: {bot.user.id})")
    print("---- Pronto para usar! ----")

@bot.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return

    # --- Responde quando o bot é mencionado ---
    if bot.user in message.mentions:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            await responder_groq(message, prompt)
        else:
            await message.channel.send("👀 Me pergunte algo junto com a menção!")
        return

    # --- Comando principal: !groq ---
    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()

        if not prompt:
            await message.channel.send(
                "❓ Use:\n"
                "`!groq sua pergunta` (resposta em texto)\n"
                "`!groq image:gato` (busca imagem)"
            )
            return

        # --- Subcomando de imagem (image:termo) ---
        if prompt.lower().startswith("image:"):
            search_term = prompt[len("image:"):].strip()
            if not search_term:
                await message.channel.send("❓ Especifique o que quer ver. Ex: `!groq image:gato`")
                return

            # Mensagem de "buscando"
            thinking_msg = await message.channel.send(f"🔍 Procurando imagem de `{search_term}`...")

            # Busca a imagem
            image_url = search_image_pexels(search_term)
            if image_url:
                # Envia como embed (mais bonito)
                embed = discord.Embed(title=f"📸 {search_term.capitalize()}")
                embed.set_image(url=image_url)
                embed.set_footer(text="Imagem do Pexels")
                await thinking_msg.edit(content=None, embed=embed)
            else:
                await thinking_msg.edit(content=f"❌ Não encontrei nenhuma imagem para `{search_term}`.")
            return

        # --- Se não for imagem, usa a Groq (texto) ---
        await responder_groq(message, prompt)
        return

    # Processa outros comandos (ex: !ping)
    await bot.process_commands(message)

# --- Handler para comandos desconhecidos (evita erro) ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignora silenciosamente
    raise error

# --- Comando de teste ---
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latência: {round(bot.latency * 1000)}ms")

# --- MAIN ---
if __name__ == "__main__":
    keep_alive()
    # Pequeno delay para o Flask iniciar a porta antes do bot
    time.sleep(2)
    bot.run(TOKEN)
