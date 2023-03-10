import os
import discord
import urllib3
import xmltodict
import asyncio
import datetime
import traceback
import time
from serverconfiguration import ServerConfiguration
from serverstatusinfo import ServerStatus, PlayerStatus
from replit import db
from discord import app_commands

# Create a discord client to allow interacting with a discord server
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
firstStart = True

MY_GUILD = 1012809878701613157


#Allows adding a server through a slash command
@tree.command(name="fss_add",
              description="Adds an embed for a new server to this channel",
              guild=discord.Object(id=MY_GUILD))
@app_commands.describe(
  ip="The IP of the FS22 server",
  port="The port of the FS22 server",
  code="The API token required for accessing the XML file",
  color="The color code which identifies the server, like 992D22")
async def fss_add(interaction, ip: str, port: str, code: str, color: str):

  if not interaction.permissions.administrator:
    await interaction.response.send_message(
      "Only administrators are allowed to add servers")
    return

  # Currently, only a single panel is allowed per ip:port combination
  new_server_config = ServerConfiguration(ip, port, code, color)
  if new_server_config.identifier in serverConfigs:
    await interaction.response.send_message("There already is a panel for %s" %
                                            new_server_config.identifier)
    return

  # Create an embed and remember its details
  embed = discord.Embed(title="Pending...",
                        color=int(new_server_config.color, 16))
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


@tree.command(
  name="fss_set_status_channel",
  description="Registers the current channel for status messages of the bot",
  guild=discord.Object(id=MY_GUILD))
@app_commands.describe()
async def fss_set_status_channel(interaction):
  if not interaction.permissions.administrator:
    await interaction.response.send_message(
      "Only administrators are allowed to run commands on this bot")
    return

  db["statuschannel"] = interaction.channel_id
  statusChannel = interaction.channel_id
  await interaction.response.send_message(
    content="Successfully set this channel for bot status messages")


@tree.command(
  name="fss_register_voice_channel",
  description=
  "Makes the bot display the online state and number of online players on a server",
  guild=discord.Object(id=MY_GUILD))
@app_commands.describe(
  ip="The IP of the FS22 server",
  port="The port of the FS22 server",
  channel_id="The channel ID of the voice channel (right click -> copy ID)",
  map_name="A preferrably short name for the map which is hosted on this server"
)
async def fss_register_voice_channel(interaction, ip: str, port: str,
                                     channel_id: str, map_name: str):
  """
  Registers a voice channel, which will receive an online/offline icon and the member count in the name
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
  server.set_voice_channel(channel_id, map_name)
  await interaction.response.send_message(
    content="Registered voice channel for %s" % identifier,
    ephemeral=True,
    delete_after=10)

  # Update the database
  db["servers"][server.identifier] = vars(server)


async def update_status_embeds():
  """
  Update the registered embeds every minute
  """
  await client.wait_until_ready()
  while not client.is_closed():
    try:
      serverStatus = await get_server_status()
      for serverData in serverStatus:
        serverConfig = serverData.serverConfig

        # Try finding the message for the embed
        try:
          channel = client.get_channel(serverConfig.statusChannelId)
          embedMessage = await channel.fetch_message(serverConfig.statusEmbedId
                                                     )
        except:
          print("WARN: Could not find embed for server %s." %
                (serverData.serverConfig.name))
          continue

        # Build the description
        replyMessage = \
          "**Map: **" + serverData.map + "\r\n" + \
          "**Status: **" + serverData.status + "\r\n" + \
          "**Mods Link: **" + serverData.mods_link() + "\r\n" + \
          "**Players Online: **" + str(serverData.online_player_count()) + "/" + serverData.maxPlayers + "\r\n" + \
          "**Players: **"

        if not serverData.players:
          replyMessage = replyMessage + "(none)"
        else:
          for playerName in serverData.players:
            replyMessage = replyMessage + "\r\n - %s (%s min)" % (
              playerName, serverData.players[playerName].onlineTime)

        # Update the embed
        embed = discord.Embed(title=serverData.name,
                              description=replyMessage,
                              color=int(serverConfig.color, 16))
        embed.add_field(name="Last Update",
                        value="%s" % datetime.datetime.now())
        await embedMessage.edit(embed=embed)

        # Wait five seconds before updating the next embed so we don't flood discord
        await asyncio.sleep(5)
    except:
      print(traceback.format_exc())
      print("Waiting 60 seconds because of exception")
      # Most likely "429 Too Many Requests". Ignore this and try again after 60 seconds
      pass

    # Repeat after 60 seconds
    await asyncio.sleep(60)


async def get_server_status():
  """
  Retrieves the server status from each server
  """
  global firstStart
  http = urllib3.PoolManager()

  allServersData = []
  for identifier in serverConfigs:
    serverConfig = serverConfigs[identifier]
    serverData = serverStatus[identifier]

    serverTurnedOffline = False
    serverTurnedOnline = False

    # Retrieve the server XML
    try:
      url = serverData.status_xml_url()
      response = http.request('GET', url, timeout=urllib3.util.Timeout(2))
      # Parse data from the server XML
      try:
        data = xmltodict.parse(response.data)

        try:
          # Check if the server is offline (but the host is online. In this case we get an empty XML):
          serverElement = data["Server"]
          if "@name" not in serverElement:
            if serverData.is_online():
              serverTurnedOffline = True
            serverData.set_offline()
            serverData.update_players([])
          else:
            if not serverData.is_online():
              serverTurnedOnline = True
            # Update the cache with the status values
            serverData.update_attributes(
              status="Online",
              name=serverConfig.flag + " " + serverElement["@name"],
              map=serverElement["@mapName"],
              maxPlayers=serverElement["Slots"]["@capacity"])

            serverData.update_players(serverElement["Slots"]["Player"])

            # Update the database
            db["serverStatus"][serverConfig.identifier] = serverData.to_json()
        except:
          print("Failed updating online state from XML: %s" %
                traceback.format_exc())
          continue
      except:
        print("Failed parsing XML data from %s" % url)
        allServersData.append(serverData)
        continue
    except:
      if serverData.is_online():
        serverTurnedOffline = True
      serverData.set_offline()
      allServersData.append(serverData)

    if serverConfig.has_member_log_channel():
      try:
        channel = client.get_channel(serverConfig.memberLogChannelId)
      except:
        # This could e.g. happen in case of Cloudflare rate limiting
        print("Failed to retrieve member log channel ID. Skipping")
        continue
    else:
      channel = None

    color = int(serverConfig.color, 16)
    # Send a message if the server just went online (before the player list)
    if serverTurnedOnline:
      print("Server %s is now online" % serverData.name)
      if channel is not None:
        embed = discord.Embed(description="???? **%s** is now online" %
                              serverData.name,
                              color=color)
        message = await channel.send(embed=embed)

    # Send a message to discord for every recently logged out player
    for playerStatus in serverData.recentlyLoggedOut:
      print("%s is no longer on %s" %
            (playerStatus.playerName, serverData.name))
      if channel is not None:
        embed = discord.Embed(description="???? **%s** is no longer on **%s**" %
                              (playerStatus.playerName, serverData.name),
                              color=discord.Colour.dark_red())
        message = await channel.send(embed=embed)

    # Send a message to discord for every recently logged in player
    for playerStatus in serverData.recentlyLoggedIn:
      print("%s is now online on %s" %
            (playerStatus.playerName, serverData.name))
      if channel is not None:
        embed = discord.Embed(description="???? **%s** is now online on **%s**" %
                              (playerStatus.playerName, serverData.name),
                              color=color)
        message = await channel.send(embed=embed)

    # Send a message to discord for every player who recently changed to admin
    for playerStatus in serverData.recentlyChangedToAdmin:
      print("%s is now an admin on %s" %
            (playerStatus.playerName, serverData.name))
      if channel is not None:
        embed = discord.Embed(
          description="???? **%s** is now an admin on **%s**" %
          (playerStatus.playerName, serverData.name),
          color=color)
        message = await channel.send(embed=embed)

    # Send a message if the server just went offline (after the player list)
    if serverTurnedOffline:
      print("Server %s is now offline" % serverData.name)
      if channel is not None:
        embed = discord.Embed(description="???? **%s** is now offline" %
                              serverData.name,
                              color=color)
        message = await channel.send(embed=embed)

    # Update the voice channel name
    if serverConfig.has_voice_channel() and serverData.allows_channel_rename(
    ) and (len(serverData.recentlyLoggedOut) > 0
           or len(serverData.recentlyLoggedIn) > 0 or serverTurnedOffline
           or serverTurnedOnline or firstStart):
      try:
        serverData.update_channel_rename_timestamp()
        voiceChannel = client.get_channel(int(serverConfig.voiceChannelId))
        onlineSign = "????" if serverData.is_online() else "????"
        await voiceChannel.edit(
          name="%s %s: %s/%s" %
          (onlineSign, serverConfig.voiceChannelName,
           serverData.online_player_count(), serverData.maxPlayers))
      except:
        print(
          "WARN: Could not locate or change voice channel %s for server %s" %
          (serverConfig.voiceChannelId, serverData.name))
        print(traceback.format_exc())

    allServersData.append(serverData)

  firstStart = False
  return allServersData


@client.event
async def on_ready():
  """
  Tells us when the bot is logged in to discord (in the replit console)
  """

  # Enable slash commands like /fss_add
  await tree.sync(guild=discord.Object(id=MY_GUILD))

  if (statusChannelId is not None):
    statusChannel = client.get_channel(statusChannelId)

    if db["recovery"] == True:
      await statusChannel.send(content="Bot recovered from exception")
      print("Bot recovered from exception")
      db["recovery"] = False
    else:
      await statusChannel.send(content="Bot was restarted")
      print("Bot was restarted")

  # Scan servers regulary
  client.loop.create_task(update_status_embeds())


# Build a ditionary of server configuration objects from the database
if db.get("servers") == None:
  db["servers"] = {}

serversInDb = db["servers"]
serverConfigs = {}
for serverIdentifier in serversInDb:
  serverJson = serversInDb[serverIdentifier]
  serverObj = ServerConfiguration.from_json(serverJson)
  serverConfigs[serverObj.identifier] = serverObj

serverStatus = {}
if db.get("serverStatus") == None:
  db["serverStatus"] = {}
  for serverIdentifier in serverConfigs:
    db["serverStatus"][serverIdentifier] = ServerStatus(
      serverConfigs[serverIdentifier]).to_json()

serverStatusInDb = db["serverStatus"]
for serverIdentifier in serversInDb:
  if serverStatusInDb.get(serverIdentifier):
    serverStatus[serverIdentifier] = ServerStatus.from_json(
      serverStatusInDb[serverIdentifier], serverConfigs[serverIdentifier])
    print("Restored server status for %s" %
          serverStatus[serverIdentifier].name)
  else:
    serverStatus[serverIdentifier] = ServerStatus(
      serverConfigs[serverIdentifier])
    print("No status stored for server identifier %s" % serverIdentifier)

statusChannelId = db.get("statuschannel")
statusChannel = None

# Check if bot was started manually or tried recovery by killing the shell
if db.get("recovery") == None:
  db["recovery"] = False

# Run the bot
discord_token = os.environ['DISCORD_TOKEN']
while True:
  try:
    print("Running client")
    client.run(discord_token)
  except:
    print(traceback.format_exc())

  # This point is usually reached when too many replit bots used the same IP
  # and cloudflare treats it as one spam bot
  print("Killing shell in hopes of getting a new IP")
  db["recovery"] = True
  os.system('kill 1')
