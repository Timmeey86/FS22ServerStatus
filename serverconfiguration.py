class ServerConfiguration:

  def __init__(self, ip, port, apiCode):
    self.ip = ip
    self.port = port
    self.apiCode = apiCode
    self.identifier = ServerConfiguration.build_identifier(ip, port)
    self.statusChannelId = None
    self.statusEmbedId = None
    self.memberLogChannelId = None

  def set_status_embed(self, statusChannelId, statusEmbedId):
    self.statusChannelId = statusChannelId
    self.statusEmbedId = statusEmbedId

  def set_member_log_channel(self, memberLogChannelId):
    self.memberLogChannelId = memberLogChannelId

  def has_status_embed(self):
    return self.statusChannelId is not None and self.statusEmbedId is not None

  def has_member_log_channel(self):
    return self.memberLogChannelId is not None

  @staticmethod
  def build_identifier(ip, port):
    return "%s:%s" % (ip, port)

  @staticmethod
  def from_json(j):
    cfg = ServerConfiguration(j["ip"], j["port"], j["apiCode"])
    cfg.set_status_embed(j["statusChannelId"], j["statusEmbedId"])
    cfg.set_member_log_channel(j["memberLogChannelId"])
    return cfg
