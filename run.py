import os
from configparser import ConfigParser

import discord
from discord.ext import commands
from gunbroker import GunBroker

path = os.path.normpath(os.getcwd() + "/config.ini")
config = ConfigParser()
if os.path.isfile(path):
    config.read(path)

TOKEN = str(os.getenv("TOKEN", config.get('discord', 'token', fallback="")))
CHANNEL = str(os.getenv("TOKEN", config.get('discord', 'channel', fallback="")))
DB_URI = str(os.getenv("DB_URL", config.get('storage', 'uri', fallback="")))
DEFAULT = int(os.getenv("RESULTS", config.getint('gunbroker', 'results', fallback=3)))
MAX = int(os.getenv("MAX", config.getint('gunbroker', 'max', fallback=10)))
PREFIX = str(os.getenv("PREFIX", config.get('discord', 'prefix', fallback="!")))
USER_AGENT = str(os.getenv("USER_AGENT", config.get('gunbroker', 'user_agent', fallback="")))

if len(USER_AGENT) < 1:
    print("This bot now requires you set a user agent with the ENV var of \"USER_AGENT\"")
    exit(0)

if len(DB_URI) > 0:
    storage = True
    from sqlalchemy import create_engine, Column, String, Integer
    from sqlalchemy.orm import scoped_session, sessionmaker
    from sqlalchemy.ext.declarative import declarative_base

    Engine = create_engine(DB_URI)
    Base = declarative_base(bind=Engine)


    def gen_ses():
        return scoped_session(sessionmaker(bind=Engine))()


    class SearchModel(Base):
        __tablename__ = "searches"
        id = Column(Integer, primary_key=True, autoincrement=True)
        search = Column(String(256))
        limit = Column(Integer)


    Base.metadata.create_all()

else:
    storage = False

bot = commands.Bot(command_prefix=PREFIX)
gb = GunBroker(user_agent=USER_AGENT)


@bot.command()
async def gunbroker(ctx):
    if str(ctx.channel.id) or len(CHANNEL) == 0:
        message = [x for x in str(ctx.message.content).split(" ") if len(x) > 0]
        if len(message) <= 1:
            await ctx.send('To use: !gunbroker [search text] <?limit,default:{}, max: {}>'.format(DEFAULT, MAX))
        else:
            async with ctx.channel.typing():
                parsed = {"search": "", 'limit': DEFAULT}
                for x in message[1:]:
                    if x.startswith("?"):
                        parsed.update({'limit': int(x[1:])})
                    else:
                        parsed.update({'search': parsed['search'] + " " + x})

                parsed.update({'search': parsed['search'].lstrip(" ")})
                if int(parsed['limit']) > MAX:
                    parsed['limit'] = MAX
                if len(parsed['search']) > 256:
                    parsed['search'] = parsed['search'][0:255]

                if storage:
                    ses = gen_ses()
                    ses.add(SearchModel(search=str(parsed['search']), limit=int(parsed['limit'])))
                    ses.commit()
                    ses.close()

                results = gb.search(**parsed)[0:int(parsed['limit'])]
                from pprint import pprint
                pprint(results)

                for result in results:
                    embed = discord.Embed(title="{} | Qty: {}".format(result['name'], result['qty']),
                                          url=result['url'],
                                          description=result['desc'])

                    embed.set_thumbnail(url=result['image'])
                    embed.set_author(name=result['seller'])

                    if result['buy_now'] is not None:
                        embed.add_field(name="Buy Now Price", value=result['buy_now'])

                    if result['starting_bid'] is not None:
                        embed.add_field(name="Starting Bid:", value=result['starting_bid'])
                        embed.add_field(name="Bids:", value=result['bids'])
                        m, s = divmod(result['time_left'], 60)
                        h, m = divmod(m, 60)
                        d, h = divmod(h, 24)
                        d, h, m, s = (d + 0, h + 0, m + 0, s + 0)
                        msg = "{}{}:{}".format(str(h).zfill(2), str(m).zfill(2), str(s).zfill(2))
                        if d > 0:
                            msg = "{}D ".format(str(d).zfill(2)) + msg
                        embed.add_field(name="Time Left:", value=msg)

                    embed.add_field(name="Seller Rating:", value=result['seller_rating'])
                    await ctx.send(embed=embed)


bot.run(TOKEN)
