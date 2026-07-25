import os
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN or not GROQ_API_KEY:
    raise ValueError("Faltam variáveis de ambiente. Configure DISCORD_TOKEN e GROQ_API_KEY.")

intents = discord.Intents.default()
intents.message_content = True  # Permite ler conteúdo das mensagens

bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)

@bot.event
async def on_ready():
    print(f"Bot logado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Responde apenas se a mensagem começar com "!groq" ou se for um mencionar o bot
    if message.content.startswith("!groq"):
        prompt = message.content[len("!groq"):].strip()
        if not prompt:
            await message.channel.send("❓ Você precisa fornecer um prompt. Ex: `!groq O que é Python?`")
            return

        # Envia uma mensagem de "processando"
        thinking_msg = await message.channel.send("🤔 Pensando...")

        try:
            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
            )
            resposta = completion.choices[0].message.content
            # Limita a resposta a 2000 caracteres (limite do Discord)
            if len(resposta) > 2000:
                resposta = resposta[:1997] + "..."
            await thinking_msg.edit(content=resposta)
        except Exception as e:
            await thinking_msg.edit(content=f"❌ Erro ao consultar Groq: {e}")

    # Importante: processar outros comandos se houver
    await bot.process_commands(message)

# Comando simples de ping
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

if __name__ == "__main__":
    bot.run(TOKEN)