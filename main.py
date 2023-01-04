import os
import discord
import urllib3
import xmltodict
import asyncio
import datetime
from replit import db
from discord import app_commands

# Create a discord client to allow interacting with a discord server
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

MY_GUILD = 1012809878701613157


#Allows adding a server through a slash command
@tree.command(name="fss_add",
              description="Adds an embed for a new server to this channel",
              guild=discord.Object(id=MY_GUILD))
@app_commands.describe(ip="The IP of the FS22 server",
                       port="The port of the FS22 server",
                       code="The API token required for accessing the XML file"
                       )
async def fss_add(interaction, ip: str, port: str, code: str):

  if not interaction.permissions.administrator:
    await interaction.response.send_message(
      "Only administrators are allowed to add servers")
    return

  if any(entry["IP"] == ip and entry["Port"] == port for entry in servers):
    await interaction.response.send_message(
      "There already is a panel for %s:%s" % (ip, port))
    return

  # Create a server entry
  serverDesc = {}
  serverDesc["IP"] = ip
  serverDesc["Port"] = port
  serverDesc["Code"] = code

  # Create an embed and remember its details
  embed = discord.Embed(title="Pending...")
  message = await interaction.channel.send(embed=embed)
  serverDesc["ChannelId"] = message.channel.id
  serverDesc["EmbedId"] = message.id

  # Store the server description in the database
  servers.append(serverDesc)

  await interaction.response.send_message(content="Successfully added %s:%s" %
                                          (ip, port),
                                          ephemeral=True,
                                          delete_after=10)


@tree.command(name="fss_remove",
              description="Removes an embed for a server",
              guild=discord.Object(id=MY_GUILD))
@app_commands.describe(ip="The IP of the FS22 server",
                       port="The port of the FS22 server")
async def fss_remove(interaction, ip: str, port: str):
  """
  Allows removing a server through a slash command
  """
  if not interaction.permissions.administrator:
    await interaction.response.send_message(
      "Only administrators are allowed to remove servers")
    return

  try:
    await remove_server(ip, port)
    await interaction.response.send_message("Successfully removed %s:%s" %
                                            (ip, port))
  except:
    await interaction.response.send_message("Could not find %s:%s" % (ip, port)
                                            )


async def remove_server(ip, port):
  """
  Removes a server entry from the database
  """
  serverDesc = next(serverDesc for serverDesc in servers
                    if serverDesc["IP"] == ip and serverDesc["Port"] == port)
  if serverDesc.get("EmbedId") is not None:
    try:
      channel = client.get_channel(serverDesc["ChannelId"])
      embedMessage = await channel.fetch_message(serverDesc["EmbedId"])
      embedMessage.delete()
    except:
      # Remove the server anyway. The embed has most likely been removed by a discord admin anyway, or the bot is
      # no longer in the channel, so we can ignore this.
      print("WARN: Failed to remove embed for %s:%s" % (ip, port))

  servers.remove(serverDesc)
  db["servers"] = servers
  print("Removed server %s:%s" % (ip, port))


@tree.command(
  name="fss_enable_member_log",
  description=
  "Makes the bot post a message in the current channel when a member logs in or out",
  guild=discord.Object(id=MY_GUILD))
@app_commands.describe(ip="The IP of the FS22 server",
                       port="The port of the FS22 server")
async def fss_enable_member_log(interaction, ip: str, port: str):
  """
  Allows setting the channel which will receive updates about members leaving or joining a server
  """
  if not interaction.permissions.administrator:
    await interaction.response.send_message(
      "Only administrators are allowed to run commands on this bot")
    return

  serverDesc = next(serverDesc for serverDesc in servers
                    if serverDesc["IP"] == ip and serverDesc["Port"] == port)
  if serverDesc is not None:
    serverDesc["MemberLogChannelId"] = interaction.channel_id
    await interaction.response.send_message(
      content="Activated member log messages for %s:%s" % (ip, port),
      ephemeral=True,
      delete_after=10)
    db["servers"]=servers
  else:
    await interaction.response.send_message(
      content="Nothing registered for %s:%s" % (ip, port),
      ephemeral=True,
      delete_after=10)


@client.event
async def on_ready():
  """
  Tells us when the bot is logged in to discord (in the replit console)
  """

  # Enable slash commands like /fss_add
  await tree.sync(guild=discord.Object(id=MY_GUILD))

  # Scan servers regulary
  client.loop.create_task(update_status_embeds())

  # Let us know the bot is ready
  print("Ready")
  print(client.user)


async def update_status_embeds():
  """
  Update the registered embeds every minute
  """
  await client.wait_until_ready()
  while not client.is_closed():
    serverData = await get_status()
    for entry in serverData:
      # Try finding the message for the embed
      try:
        channel = client.get_channel(entry["ChannelId"])
        embedMessage = await channel.fetch_message(entry["EmbedId"])
      except:
        print("WARN: Could not find embed for server %s." % (entry["Name"]))
        continue

      # Build the description
      replyMessage = \
        "**Name: **" + entry["Name"] + "\r\n" + \
        "**Map: **" + entry["Map"] + "\r\n" + \
        "**Status: **" + entry["Status"] + "\r\n" + \
        "**Mods Link: **" + entry["Mods Link"] + "\r\n" + \
        "**Players Online: **" + entry["Players Online"] + "\r\n" + \
        "**Players: **"
      players = entry["Players"]
      if not players:
        replyMessage = replyMessage + "(none)"
      else:
        for player in players:
          replyMessage = replyMessage + "\r\n- " + player

      # Update the embed
      print("Updating embed for %s" % entry["Name"])
      embed = discord.Embed(title=entry["Name"], description=replyMessage)
      embed.add_field(name="Last Update", value="%s" % datetime.datetime.now())
      await embedMessage.edit(embed=embed)

      # Wait two seconds before updating the next embed so we don't flood discord
      await asyncio.sleep(2)

    # Repeat after 60 seconds
    await asyncio.sleep(60)


async def set_player_online(server, serverName, playerName):
  """
  Remembers that a player is online on the given server and writes a message if they were offline on that server before
  """

  # get or create data for the current server
  if players.get(serverName) == None:
    players[serverName] = {}
  playersKnownByServer = players[serverName]

  # get or create data for the current player on that server
  if playersKnownByServer.get(playerName) == None:
    playersKnownByServer[playerName] = {"online": False}
  playerDetails = playersKnownByServer[playerName]

  # Check if the player was online already
  if playerDetails["online"] == False:
    playerDetails["online"] = True
    print("Player %s is now online on %s" % (playerName, serverName))
    channelId = server.get("MemberLogChannelId")
    if channelId is not None:
      channel = client.get_channel(channelId)
      await channel.send(content="%s is now online on %s" % (playerName, serverName))
    
  db["players"] = players


async def set_players_offline(server, serverName, onlinePlayerNames):
  print(onlinePlayerNames)

  playersKnownByServer = players.get(serverName)
  if playersKnownByServer == None:
    return

  for playerName in playersKnownByServer:
    if playerName not in onlinePlayerNames and playersKnownByServer[playerName]["online"] == True:
      print("Player %s is no longer on %s" % (playerName, serverName))
      playersKnownByServer[playerName]["online"] = False
      channelId = server.get("MemberLogChannelId")
      if channelId is not None:
        channel = client.get_channel(channelId)
        await channel.send(content="%s signed out of %s" % (playerName, serverName))

  db["players"] = players


async def get_status():
  """
  Retrieves the server status from each server
  """
  http = urllib3.PoolManager()

  allServersData = []
  for server in servers:
    print("Processing server %s:%s" % (server["IP"], server["Port"]))
    serverData = {}
    serverData["Status"] = "Online"
    serverData["Mods Link"] = "%s:%s/mods.html" % (server["IP"],
                                                   server["Port"])
    serverData["Players"] = []
    onlinePlayers = []
    try:
      url = "http://%s:%s/feed/dedicated-server-stats.xml?code=%s" % (
        server["IP"], server["Port"], server["Code"])
      print("Connecting to %s" % url)
      response = http.request('GET', url, timeout=urllib3.util.Timeout(2))
      try:
        data = xmltodict.parse(response.data)
        serverElement = data["Server"]
        serverData["Name"] = serverElement["@name"]
        serverData["Map"] = serverElement["@mapName"]
        serverData["Players Online"] = "%s/%s" % (
          serverElement["Slots"]["@numUsed"],
          serverElement["Slots"]["@capacity"])
        for playerElement in serverElement["Slots"]["Player"]:
          if playerElement is not None and playerElement["@isUsed"] == "true":
            serverData["Players"].append(
              "%s (%s min)" %
              (playerElement["#text"], playerElement["@uptime"]))
            await set_player_online(server, serverData["Name"], playerElement["#text"])
            onlinePlayers.append(playerElement["#text"])
        serverData["EmbedId"] = server["EmbedId"]
        serverData["ChannelId"] = server["ChannelId"]
        serverData["IP"] = server["IP"]
        serverData["Port"] = server["Port"]
      except:
        print("Failed to parse data")
        serverData["Name"] = "Unknown"
        serverData["Map"] = "Unknown"
        serverData["Players Online"] = "Unknown"
    except:
      print("Failed to connect to %s" % url)
      serverData["Status"] = "Unreachable"
      serverData["Name"] = "Unknown"
      serverData["Map"] = "Unknown"
      serverData["Players Online"] = "Unknown"

    await set_players_offline(server, serverData["Name"], onlinePlayers)

    allServersData.append(serverData)

  return allServersData


# Retrieve the current list of servers
if db.get("servers") == None:
  db["servers"] = []
servers = db["servers"]

# Remember player info
#if db.get("players") == None:
db["players"] = {}
players = db["players"]

# Run the bot
discord_token = os.environ['DISCORD_TOKEN']
client.run(discord_token)
