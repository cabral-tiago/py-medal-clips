from discord.channel import TextChannel
import requests
from discord import Embed
from discord.ext import tasks, commands
from dotenv import load_dotenv
import os
import pickle

## TOKENS
load_dotenv()
MEDAL_TOKEN = os.getenv('MEDAL_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

### Globals

medalUsers = {} # Key: MedalUserID, Value: GuildID[]
medalLatest = {} # Key: MedalUserID, Value: contentID

discordChannels = {} # Key: GuildID, Value: ChannelID
guildUsers = {} # Key: GuildID, Value: MedalUserID[]

### General Functions
def isChannelSetup(guildID):
    if guildID in discordChannels:
        return True
    return False

def premadeEmbed(title, description="", error=False):
    colour = COLOUR_OKAY
    if error:
        colour = COLOUR_ERROR
    embed=Embed(title=title, description=description, color=colour)
    embed.set_author(name="Medal Bot", icon_url="https://cdn.discordapp.com/avatars/870660111268458546/1d295f0981466621694e8843a22eccd0.webp")
    return embed

### Medal Functions
def getValidUserID(arg):
    userID = -1
    if "medal.tv/users" in arg:
        if arg[-1] == '/':
            userID = arg[:-1].split('/')[-1]
        else:
            userID = arg.split('/')[-1]
    elif arg.isnumeric():
        userID = arg
    return userID

def requestLatestUserClip(userID):
    requestHeader = {'Authorization' : MEDAL_TOKEN}
    requestURL = "https://developers.medal.tv/v1/latest?userId="+ userID +"&limit=1"
    response = requests.get(requestURL, headers=requestHeader)

    return response.json()['contentObjects']

def checkMedalUserID(userID):
    request = requestLatestUserClip(userID)

    if(len(request) == 0):
        return False
    else:
        return True

def getNewClips(userID):
    request = requestLatestUserClip(userID)
    LastVideoID = medalLatest[userID]

    if LastVideoID != request[0]['contentId']:
        medalLatest[userID] = request[0]['contentId']
        backupDatabase()
        return request[0]
    else:
        return -1

def getNameFromCredits(arg):
    username = arg[11:].split("(")[0]

    return username

def getNameFromUserID(userID):
    request = requestLatestUserClip(userID)
    
    return getNameFromCredits(request[0]['credits']).strip()

### Database Area
#TODO change to mongo

def backupDatabase():
    with open("users.pkl", "wb") as fileA:
        pickle.dump(medalUsers, fileA)
    with open("latest.pkl", "wb") as fileB:
        pickle.dump(medalLatest, fileB)
    with open("channels.pkl", "wb") as fileC:
        pickle.dump(discordChannels, fileC)
    with open("gusers.pkl", "wb") as fileD:
        pickle.dump(guildUsers, fileD)

def loadFromDatabase():
    users = loadPickleDict("users")
    latest = loadPickleDict("latest")
    channels = loadPickleDict("channels")
    gusers = loadPickleDict("gusers")

    return users, latest, channels, gusers

def loadPickleDict(name):
    if os.path.exists(name+".pkl"):
        print("Loading "+name)
        file = open(name+".pkl", "rb")
        return pickle.load(file)
    else:
        return {}


### Discord Bot Area
CHANNEL_NOT_SET_MSG = "The clips channel for this Discord server isn't set yet.\nUse **medal channel #[channel_here]** to set the channel."

COLOUR_ERROR = 0xb00000
COLOUR_OKAY = 0x3e852c

bot = commands.Bot(command_prefix="medal ")

@bot.command()
async def ping(ctx):
    await ctx.channel.send("pong")

@bot.command(help="Follows a Medal profile in the current Discord server")
async def follow(ctx, arg):
    if not isChannelSetup(ctx.guild.id):
        embed = premadeEmbed(CHANNEL_NOT_SET_MSG, error=True)
    else:
        userID = getValidUserID(arg)
        if userID!= -1:
            isUser = checkMedalUserID(userID)
            if isUser:
                #Adding to medalUsers
                if userID not in medalUsers:
                    medalUsers[userID] = []
                medalUsers[userID].append(ctx.guild.id)
                #Adding to guildUsers
                if ctx.guild.id not in guildUsers:
                    guildUsers[ctx.guild.id] = []
                guildUsers[ctx.guild.id].append(userID)

                medalLatest[userID] = "nothing"
                username = getNameFromCredits(getNewClips(userID)['credits'])
                embed = premadeEmbed("Following " + username + " [ID:" + userID + "]\n")
                backupDatabase()
            else:
                embed = premadeEmbed("Cannot find active Medal User with ID "+userID, error=True)
        else:
            embed = premadeEmbed("Invalid Medal Profile Link or Medal User ID", error=True)
    await ctx.channel.send(embed=embed)

@follow.error
async def follow_error(ctx, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        embed = premadeEmbed("Incorrect command", "How to use: *medal follow link-to-medal-profile*", error=True)
        await ctx.channel.send(embed=embed)
    else:
        print(error)

@bot.command(name="list", help="Shows all Medal profiles being followed in the current Discord server")
async def members_in_guild(ctx):
    if not isChannelSetup(ctx.guild.id):
        embed = premadeEmbed(CHANNEL_NOT_SET_MSG, error=True)
        await ctx.channel.send(embed=embed)
    else:
        if ctx.guild.id not in guildUsers or len(guildUsers[ctx.guild.id])==0:
            embed = premadeEmbed("Not following any Medal users in this Discord server.", "Follow by using **medal follow link-to-medal-profile**", error=True)
            await ctx.channel.send(embed=embed)
        else:
            embed = premadeEmbed("# Following")
            for userID in guildUsers[ctx.guild.id]:
                embed.add_field(name=getNameFromUserID(userID), value="ID:"+userID, inline=True)
            await ctx.channel.send(embed=embed)

@bot.command(help="Unfollows a Medal profile in the current Discord server")
async def unfollow(ctx, arg):
    userID = getValidUserID(arg)
    if userID!= -1:
        if ctx.guild.id in guildUsers and userID in guildUsers[ctx.guild.id]:
            guildUsers[ctx.guild.id].remove(userID)
            medalUsers[userID].remove(ctx.guild.id)
            backupDatabase()
            embed = premadeEmbed("Unfollowed **" + getNameFromUserID(userID) + "** [ID:" + userID + "] in this Discord server\n")
        else:
            embed = premadeEmbed("Not following the Medal profile with ID "+userID+" in this Discord server", error=True)
    else:
        embed = premadeEmbed("Invalid Medal Profile Link or Medal User ID", error=True)
    await ctx.channel.send(embed=embed)

@bot.command(help="Sets the channel to post new Medal clips")
async def channel(ctx, channel: TextChannel=None):
    if(channel==None):
        if not isChannelSetup(ctx.guild.id):
            embed = premadeEmbed(CHANNEL_NOT_SET_MSG, error=True)
            await ctx.channel.send(embed=embed)
        else:
            embed = premadeEmbed(title="Clips are being posted in #"+bot.get_channel(discordChannels[ctx.guild.id]).name, description="Use **medal channel #new_channel** to change the channel.")
            await ctx.channel.send(embed=embed)
    else:
        discordChannels[ctx.guild.id] = channel.id
        backupDatabase()
        embed = premadeEmbed("Now posting clips in #"+channel.name+"!")
        await ctx.channel.send(embed=embed)

@channel.error
async def channel_error(ctx, error):
    if isinstance(error, commands.errors.ChannelNotFound):
        embed = premadeEmbed("Channel not found", error=True)
        await ctx.channel.send(embed=embed)
    else:
        print(error)

@bot.command()
@commands.is_owner()
async def debug(ctx):
    print(medalUsers)
    print(medalLatest)
    print(discordChannels)
    print(guildUsers)

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await bot.close()

@tasks.loop(seconds=10)
async def check_for_clips():
    for user in medalUsers:
        newClip = getNewClips(user)
        if newClip != -1:
            userName = getNameFromCredits(newClip['credits'])
            print("New clip from" + userName)
            message = "Check out this new clip from **" + userName + "**!\n" + newClip['directClipUrl']
            for guildID in medalUsers[user]:
                channel = bot.get_channel(discordChannels[guildID])
                await channel.send(message)
    

if __name__=="__main__":
    medalUsers, medalLatest, discordChannels, guildUsers = loadFromDatabase()
    check_for_clips.start()
    bot.run(DISCORD_TOKEN)
