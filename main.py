import os
import discord
import urllib3
import xmltodict
import asyncio
import datetime
from serverconfiguration import ServerConfiguration
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

  # Currently, only a single panel is allowed per ip:port combination
  new_server_config = ServerConfiguration(ip, port, code)
  if new_server_config.identifier in serverConfigs:
    await interaction.response.send_message("There already is a panel for %s" %
                                            new_server_config.identifier)
    return

  # Create an embed and remember its details
  embed = discord.Embed(title="Pending...")
  message = await interaction.channel.send(embed=embed)
  new_server_config.set_status_embed(message.channel.id, message.id)

  # Store the server description in the cache and in the database
  serverConfigs[new_server_config.identifier] = new_server_config  
  db["servers"][new_server_config.identifier] = vars(new_server_config)

  # Confirm the successful creation of the embed
  # (only the one who used the slash command will see this, and only for 10 seconds)
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

  # Check if the server is known at all
  identifier = ServerConfiguration.build_identifier(ip, port)
  if identifier not in serverConfigs:
    print("INFO: Could not find server %s" % identifier)
    await interaction.response.send_message(
      content="No server registered for IP %s and port %s" % (ip, port),
      ephemeral=True,
      delete_after=10)
    return

  # Remove the status embed if it exists
  server = serverConfigs[identifier]
  if server.has_status_embed():
    try:
      channel = client.get_channel(server.statusChannelId)
      embedMessage = await channel.fetch_message(server.statusEmbedId)
      embedMessage.delete()
    except:
      print("WARN: Could not remove embed for IP %s and port %s" % (ip, port))

  # Remove the server from the cache and database
  del serverConfigs[identifier]
  del db["servers"][identifier]

  print("INFO: Removed server %s" % identifier)
  await interaction.response.send_message(
    content="Successfully removed server %s" % identifier,
    ephemeral=True,
    delete_after=10)


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

  # Check if the given server is known at all
  identifier = ServerConfiguration.build_identifier(ip, port)
  if identifier not in serverConfigs:
    await interaction.response.send_message(
      content="No server registered for IP %s and port %s" % (ip, port),
      ephemeral=True,
      delete_after=10)
    return

  server = serverConfigs[identifier]
  server.set_member_log_channel(interaction.channel_id)
  await interaction.response.send_message(
    content="Activated member log messages for %s" % identifier,
    ephemeral=True,
    delete_after=10)

  # Update the database
  db["servers"][server.identifier] = vars(server)


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
      print("Trying to find embed for %s" % entry["Name"])
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
    if server.has_member_log_channel():
      channel = client.get_channel(server.memberLogChannelId)
      await channel.send(content="%s is now online on %s" %
                         (playerName, serverName))

  db["players"] = players


async def set_players_offline(server, serverName, onlinePlayerNames):
  print(onlinePlayerNames)

  playersKnownByServer = players.get(serverName)
  if playersKnownByServer == None:
    return

  for playerName in playersKnownByServer:
    if playerName not in onlinePlayerNames and playersKnownByServer[
        playerName]["online"] == True:
      print("Player %s is no longer on %s" % (playerName, serverName))
      playersKnownByServer[playerName]["online"] = False
      if server.has_member_log_channel():
        channel = client.get_channel(server.memberLogChannelId)
        await channel.send(content="%s signed out of %s" %
                           (playerName, serverName))

  db["players"] = players


async def get_status():
  """
  Retrieves the server status from each server
  """
  http = urllib3.PoolManager()

  print("Reading status from each server")
  allServersData = []
  for identifier in serverConfigs:
    print("Processing server %s" % identifier)
    server = serverConfigs[identifier]
    serverData = {}
    serverData["Status"] = "Online"
    serverData["Mods Link"] = "%s:%s/mods.html" % (server.ip, server.port)
    serverData["Players"] = []
    onlinePlayers = []
    try:
      url = "http://%s:%s/feed/dedicated-server-stats.xml?code=%s" % (
        server.ip, server.port, server.apiCode)
      print("Connecting to %s" % url)
      response = http.request('GET', url, timeout=urllib3.util.Timeout(2))
    except:
      print("Failed connecting to %s" % url)
      continue
      
    try:
      data = xmltodict.parse(response.data)
    except:
      print("Failed parsing XML data from %s" % url)
      continue 
        
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
        await set_player_online(server, serverData["Name"],
                                playerElement["#text"])
        onlinePlayers.append(playerElement["#text"])
    serverData["EmbedId"] = server.statusEmbedId
    serverData["ChannelId"] = server.statusChannelId
    serverData["IP"] = server.ip
    serverData["Port"] = server.port

    await set_players_offline(server, serverData["Name"], onlinePlayers)

    allServersData.append(serverData)

  return allServersData

# Build a ditionary of server configuration objects from the database
if db.get("servers") == None:
  db["servers"] = {}

serversInDb = db["servers"]
serverConfigs = {}
for serverIdentifier in serversInDb:
  serverJson = serversInDb[serverIdentifier]
  serverObj = ServerConfiguration.from_json(serverJson)
  serverConfigs[serverObj.identifier] = serverObj

# Remember player info
#if db.get("players") == None:
db["players"] = {}
players = db["players"]

# Run the bot
discord_token = os.environ['DISCORD_TOKEN']
client.run(discord_token)
