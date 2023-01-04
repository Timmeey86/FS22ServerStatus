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
    self.maxPlayers = 0
    self.players = {}
    self.recentlyLoggedIn = []
    self.recentlyLoggedOut = []

  def update_attributes(self, status, name, map, maxPlayers):
    self.status = status
    self.name = name
    self.map = map
    self.maxPlayers = maxPlayers
    self.players = {}

  def set_offline(self):
    self.status = "Offline"

  def update_players(self, playerElements):
    self.recentlyLoggedIn = []
    self.recentlyLoggedOut = []
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

    # Find out which players just signed out
    for player in self.players:
      if player.playerName not in onlinePlayers:
        self.recentlyLoggedOut.append(player)

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
