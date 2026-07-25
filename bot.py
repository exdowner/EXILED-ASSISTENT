import os
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Carrega variáveis do .env (só pra teste local)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN or not GROQ_API_KEY:
    raise ValueError("Faltam variáveis de ambiente. Configure DISCORD_TOKEN e GROQ_API_KEY.")

# ---------- Servidor Flask (keep-alive pro Render) ----------
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot do Discord está rodando!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ---------- Bot do Discord ----------
intents = discord.Intents.default()
intents.message_content = True  # Obrigatório pra ler mensagens

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)

@bot.event
async def on_ready():
    print(f"✅ Bot logado como {bot.user} (ID: {bot.user.id})")
    print("---- Pronto para usar! ----")

@bot.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return

    # Responde quando o bot é mencionado (ex: @meubot qual a capital?)
    if bot.user in message.mentions:
        # Remove a menção do começo da mensagem
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            await responder_groq(message, prompt)
        else:
            await message.channel.send("👀 Me mencionou? Me faça uma pergunta junto com a menção!")

    # Comando clássico !groq
    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()
        if not prompt:
            await message.channel.send("❓ Use: `!groq sua pergunta aqui`")
            return
        await responder_groq(message, prompt)

    # Processa outros comandos (ex: !ping)
    await bot.process_commands(message)

# Função que consulta a Groq e responde
async def responder_groq(message, prompt):
    thinking = await message.channel.send("🤔 Processando...")

    try:
        completion = groq_client.chat.completions.create(
            # 🔥 MODELO ATUALIZADO (substituto do antigo llama3-70b-8192)
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )
        resposta = completion.choices[0].message.content

        # Discord limita mensagens em 2000 caracteres
        if len(resposta) > 2000:
            resposta = resposta[:1997] + "..."

        await thinking.edit(content=resposta)

    except Exception as e:
        await thinking.edit(content=f"❌ Erro ao consultar a Groq: {e}")

# Comando de teste
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latência: {round(bot.latency * 1000)}ms")

# ---------- MAIN ----------
if __name__ == "__main__":
    # Inicia o servidor Flask em background (pro Render não hibernar)
    keep_alive()
    # Roda o bot
    bot.run(TOKEN)
