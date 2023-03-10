class ServerConfiguration:

  def __init__(self, ip, port, apiCode, color):
    self.ip = ip
    self.port = port
    self.apiCode = apiCode
    self.color = color
    self.identifier = ServerConfiguration.build_identifier(ip, port)
    self.statusChannelId = None
    self.statusEmbedId = None
    self.memberLogChannelId = None
    self.voiceChannelId = None
    self.voiceChannelName = None

  def set_status_embed(self, statusChannelId, statusEmbedId):
    self.statusChannelId = statusChannelId
    self.statusEmbedId = statusEmbedId

  def set_member_log_channel(self, memberLogChannelId):
    self.memberLogChannelId = memberLogChannelId

  def set_voice_channel(self, voiceChannelId, voiceChannelName):
    self.voiceChannelId = voiceChannelId
    self.voiceChannelName = voiceChannelName

  def has_status_embed(self):
    return self.statusChannelId is not None and self.statusEmbedId is not None

  def has_member_log_channel(self):
    return self.memberLogChannelId is not None

  def has_voice_channel(self):
    return self.voiceChannelId is not None

  @staticmethod
  def build_identifier(ip, port):
    return "%s:%s" % (ip, port)

  @staticmethod
  def from_json(j):
    cfg = ServerConfiguration(j["ip"], j["port"], j["apiCode"], j["color"])
    cfg.set_status_embed(j["statusChannelId"], j["statusEmbedId"])
    cfg.set_member_log_channel(j["memberLogChannelId"])
    cfg.set_voice_channel(j.get("voiceChannelId"),j.get("voiceChannelName"))
    cfg.flag = j.get("flag", "")
    return cfg
