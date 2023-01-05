import datetime


class PlayerStatus:
  """
  Contains information about the current status of a player
  """

  def __init__(self, playerName, onlineTime, isAdmin):
    self.playerName = playerName
    self.onlineTime = onlineTime
    self.isAdmin = isAdmin

  @classmethod
  def from_xml(cls, playerElement):
    return cls(playerElement["#text"], playerElement["@uptime"],
               playerElement["@isAdmin"])


class ServerStatus:
  """
  Contains information about the current status of a server
  """

  def __init__(self, serverConfig):
    self.status = "Offline"
    self.serverConfig = serverConfig
    self.name = "Unknown"
    self.map = "Unknown"
    self.maxPlayers = "0"
    self.players = {}
    self.recentlyLoggedIn = []
    self.recentlyLoggedOut = []
    self.recentlyChangedToAdmin = []
    self.lastChannelRenameTimestamp = datetime.datetime.now(
    ) - datetime.timedelta(seconds=400)

  def update_attributes(self, status, name, map, maxPlayers):
    self.status = status
    self.name = name
    self.map = map
    self.maxPlayers = maxPlayers

  def set_offline(self):
    self.status = "Offline"

  def is_online(self):
    return self.status != "Offline"

  def allows_channel_rename(self):
    """Makes sure we are not being rate limited by discord when renaming a channel"""
    return (datetime.datetime.now() - self.lastChannelRenameTimestamp
            ).total_seconds() > 305  # a bit more than five minutes

  def update_channel_rename_timestamp(self):
    self.lastChannelRenameTimestamp = datetime.datetime.now()

  def update_players(self, playerElements):
    self.recentlyLoggedIn = []
    self.recentlyLoggedOut = []
    self.recentlyChangedToAdmin = []
    onlinePlayers = {}

    for playerElement in playerElements:

      # Skip empty slots
      if playerElement is None or playerElement["@isUsed"] == "false":
        continue

      player = PlayerStatus.from_xml(playerElement)

      # Find out which players just signed in
      if player.playerName not in self.players:
        self.recentlyLoggedIn.append(player)

      # Remember all players who are online now
      onlinePlayers[player.playerName] = player

      # Find out which players are now an admin
      if player.isAdmin == "true":
        if player.playerName not in self.players or self.players[
            player.playerName].isAdmin != "true":
          self.recentlyChangedToAdmin.append(player)

    # Find out which players just signed out
    for playerName in self.players:
      if playerName not in onlinePlayers:
        self.recentlyLoggedOut.append(self.players[playerName])

    # Store the new dictionary of online players
    self.players = onlinePlayers

  def online_player_count(self):
    """Retrieves the amount of currently online players on this server"""
    return len(self.players)

  def mods_link(self):
    """Retrieves the link to the mods page"""
    return "%s:%s/mods.html" % (self.serverConfig.ip, self.serverConfig.port)

  def status_xml_url(self):
    """Retrieves the URL to the XML file which provides status information about the server"""
    return "http://%s:%s/feed/dedicated-server-stats.xml?code=%s" % (
      self.serverConfig.ip, self.serverConfig.port, self.serverConfig.apiCode)
