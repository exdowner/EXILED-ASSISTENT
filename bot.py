import os
import time
import requests
import urllib.parse
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import datetime

load_dotenv()

# --- VARIÁVEIS DE AMBIENTE ---
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

if not TOKEN or not GROQ_API_KEY or not PIXABAY_API_KEY:
    raise ValueError("Faltam variáveis: DISCORD_TOKEN, GROQ_API_KEY, PIXABAY_API_KEY")

# --- SERVIDOR FLASK (keep-alive para Render) ---
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

# --- BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)

# =====================================================
#                    FUNÇÕES AUXILIARES
# =====================================================

def search_image_pixabay(query):
    """Busca imagem na Pixabay e retorna URL ou None."""
    try:
        print(f"[Pixabay] Buscando: {query}")
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={encoded_query}&image_type=photo&per_page=3&safesearch=true"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[Pixabay] HTTP {response.status_code}")
            return None
        data = response.json()
        if data.get('hits') and len(data['hits']) > 0:
            image_url = data['hits'][0]['webformatURL']
            print(f"[Pixabay] URL: {image_url}")
            return image_url
        print("[Pixabay] Nenhum hit")
        return None
    except Exception as e:
        print(f"[Pixabay] ERRO: {e}")
        return None

def bypass_link(short_url):
    """
    Expande link encurtado.
    Tenta UnshortAPI primeiro, se falhar tenta Unshorten.me.
    """
    # --- Tentativa 1: UnshortAPI (pública, sem chave) ---
    try:
        api_url = f"https://unshort-api.vercel.app/api/expand?url={short_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            expanded = data.get('destination') or data.get('url')
            if expanded:
                print(f"[UnshortAPI] URL expandida: {expanded}")
                return expanded
    except Exception as e:
        print(f"[UnshortAPI] ERRO: {e}")

    # --- Tentativa 2: Unshorten.me (fallback) ---
    try:
        api_url = f"https://unshorten.me/api/v1/expand?url={short_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            expanded = data.get('url')
            if expanded:
                print(f"[Unshorten.me] URL expandida: {expanded}")
                return expanded
    except Exception as e:
        print(f"[Unshorten.me] ERRO: {e}")

    return None

async def responder_groq(message, prompt):
    """Responde com IA da Groq."""
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

# =====================================================
#                     COMANDOS
# =====================================================

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def bypass(ctx, *, link: str):
    """Expande um link encurtado. Ex: !bypass https://bit.ly/abc123"""
    if not link.startswith("http://") and not link.startswith("https://"):
        await ctx.send("❌ Link inválido. Use `http://` ou `https://`")
        return

    mensagem = await ctx.send(f"🔍 Expandindo `{link}`...")
    expanded = bypass_link(link)

    if expanded:
        await mensagem.edit(content=f"✅ Link expandido: {expanded}")
    else:
        await mensagem.edit(content="❌ Não foi possível expandir o link. Verifique se ele é válido.")

# --- MODERAÇÃO ---
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, motivo="Sem motivo"):
    try:
        await member.ban(reason=motivo)
        await ctx.send(f"✅ {member.mention} banido. Motivo: {motivo}")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, motivo="Sem motivo"):
    try:
        await member.kick(reason=motivo)
        await ctx.send(f"✅ {member.mention} expulso. Motivo: {motivo}")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutos: int, *, motivo="Sem motivo"):
    try:
        duracao = discord.utils.utcnow() + datetime.timedelta(minutes=minutos)
        await member.timeout(duracao, reason=motivo)
        await ctx.send(f"✅ {member.mention} timeout de {minutos}min. Motivo: {motivo}")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, quantidade: int):
    if quantidade < 1:
        await ctx.send("❌ Quantidade deve ser > 0.")
        return
    try:
        deleted = await ctx.channel.purge(limit=quantidade + 1)
        await ctx.send(f"🗑️ {len(deleted)-1} mensagens apagadas.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

# =====================================================
#                     EVENTOS
# =====================================================

@bot.event
async def on_ready():
    print(f"✅ Bot logado como {bot.user} (ID: {bot.user.id})")
    print("---- Pronto para usar! ----")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # --- MENÇÃO AO BOT ---
    if bot.user in message.mentions:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            await responder_groq(message, prompt)
        else:
            await message.channel.send("👀 Me pergunte algo junto com a menção!")
        return

    # --- COMANDO !groq ---
    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()
        if not prompt:
            await message.channel.send("❓ Use: `!groq pergunta` ou `!groq image:gato`")
            return

        # Subcomando de imagem
        if prompt.lower().startswith("image:"):
            search_term = prompt[len("image:"):].strip()
            if not search_term:
                await message.channel.send("❓ Ex: `!groq image:gato`")
                return

            thinking = await message.channel.send(f"🔍 Procurando `{search_term}`...")
            image_url = search_image_pixabay(search_term)

            if image_url:
                embed = discord.Embed(title=f"📸 {search_term.capitalize()}")
                embed.set_image(url=image_url)
                embed.set_footer(text="Imagem da Pixabay")
                await thinking.edit(content=None, embed=embed)
            else:
                await thinking.edit(content=f"❌ Nenhuma imagem encontrada para `{search_term}`.")
            return

        # Resposta de texto com Groq
        await responder_groq(message, prompt)
        return

    # Processa outros comandos (ex: !ping, !ban, etc.)
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignora comandos desconhecidos
    raise error

# =====================================================
#                       MAIN
# =====================================================

if __name__ == "__main__":
    keep_alive()
    time.sleep(2)  # dá tempo do Flask subir
    bot.run(TOKEN)
