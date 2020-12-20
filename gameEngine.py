__version__ = "0.0.1"

from . import parse
from .layers import commandLeaf, hazilLayer, innerLayer, gameDataLayer, rpcLayer, spawnLayer, spawnSubcommandLayer, \
    UpdateGameDataLayer
from .helpers import flatten

import struct
from typing import Union, Any, Dict, List


class PlayerClass:
    def __init__(self, input_game_state):
        self.clientId: Union[bool, Any] = False
        self.playerId: int = -1

        self.color: Union[bool, Any] = False
        self.name: Union[bool, Any] = False
        self.skin: int = 0
        self.hat: int = 0
        self.pet: int = 0

        self.alive: bool = True
        self.infected: bool = False

        self.entities: Dict[Any] = {}
        self.playerControlNetId: Union[bool, Any] = False  # 1
        self.playerPhysicsNetId: Union[bool, Any] = False  # 2
        self.networkTransformNetId: Union[bool, Any] = False  # 3

        self.game_state: GameEngine = input_game_state

        self.gameDataEntities: List[Any] = []

        self.lastMoveSeq: int = -1  # Tracking player movement sequence numbers
        self.x: int = 0
        self.y: int = 0

        self.in_vent: bool = False  # Is player currently in the vents?

    def __getstate__(self):
        state = self.__dict__.copy()
        if "gameState" in state:
            del state["gameState"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def callback(self, callback_name):  # Convenience function to shorten callback updates
        self.game_state.callback(callback_name, {'gameState': self.game_state, 'player': self})

    def snap_to(self, ix, iy, seq):
        if seq > self.lastMoveSeq:
            x = (ix - 32767)  # Offset to center of maps
            y = (iy - 32767)  # Offset to center of maps
            self.x = x
            self.y = y

    def parse_location(self, data):
        seq = ix = iy = x_speed = y_speed = None
        if len(data) == 10:  # Alive movement
            seq, ix, iy, x_speed, y_speed = struct.unpack("<HHHHH", data)
        if len(data) == 6:  # Ghost movement
            seq, ix, iy = struct.unpack("<HHH", data)
            x_speed, y_speed = 0, 0  # Ehh, it works I guess

        if not (len(data) == 6 or len(data) == 10):  # Bad data?
            return False, False

        if seq > self.lastMoveSeq:
            x = (ix - 32767)  # Offset to center of maps
            y = (iy - 32767)  # Offset to center of maps

            x = (x / 32767) * 40  # LERF to -40 to 40
            y = (y / 32767) * 40  # LERF to -40 to 40

            self.x = x
            self.y = y
            self.lastMoveSeq = seq

            return self.x, self.y
        return False, False

    def vent(self, in_vent: bool):
        self.in_vent = in_vent

    def exiled(self):
        self.alive = False
        self.callback("Exiled")

    def murdered(self):
        self.alive = False
        self.callback("Murdered")

    def murder(self, player):
        self.callback("Murder")
        player.murdered()

    def set_skin(self, skin_id):
        self.skin = skin_id
        self.callback("SetSkin")

    def set_hat(self, hat_id):
        self.hat = hat_id
        self.callback("SetHat")

    def set_pet(self, pet_id):
        self.pet = pet_id
        self.callback("SetPet")

    def set_color(self, color_id):
        self.color = color_id
        self.callback("SetColor")

    def set_infected(self, is_infected):
        self.infected = is_infected
        self.callback("Infected")

    def assign_id(self, player_id):
        self.playerId = player_id
        self.game_state.register_player_id(self, self.playerId)
        try:
            pre_name = self.game_state.usernameLookup[player_id]
            if not self.name:
                self.set_name(pre_name)
        except:
            pass

    def chat(self, message):
        self.game_state.callback('Chat', {'gameState': self.game_state, 'player': self, 'message': message})

    def set_username_from_list(self, name):
        self.set_name(name)

    def set_name(self, name):
        self.name = name
        self.callback("SetName")

    def add_entity(self, entity):
        if entity.netId not in self.entities:
            self.entities[entity.netId] = entity
            return True
        return False


# noinspection PyAttributeOutsideInit
class EntityClass:
    def __init__(self, net_id):
        self.netId = net_id

    def add_to_player(self, player):
        if player.add_entity(self):
            self.owner = player
            return True
        return False


# noinspection PyAttributeOutsideInit,PyUnresolvedReferences
class GameEngine:
    def __init__(self, callback_dict=None):
        self.callbackDict = callback_dict if callback_dict is not None else {}  # Will not reset with game state
        self.reset()

    def __getstate__(self):
        state = self.__dict__.copy()
        if "callbackDict" in state:
            del state["callbackDict"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def callback(self, name, data_dict):
        try:
            cb = self.callbackDict[name]
        except:
            cb = False
            pass  # Callback not registered
        if cb:
            # noinspection PyCallingNonCallable
            cb(data_dict)

    def ge_callback(self, name, player=None):  # Convenience function for game state update callbacks
        if name != 'Reset':
            self.callback('Event', {'gameState': self, 'player': player})
        self.callback(name, {'gameState': self, 'player': player})

    def reset(self):
        self.gameId: Union[bool, Any] = False
        self.selfClientID: Union[bool, Any] = False  # Holds a reference to the network id of the computer we run on
        self.hostClientID: Union[bool, Any] = False  # The client id of the host of the game
        self.players: Dict[Any] = {}
        self.entities:  Dict[Any] = {}
        self.playerIdMap:  Dict[Any] = {}
        self.tick: Union[bool, Any] = 0
        self.sendServer: List[Any] = []
        self.sendClient: List[Any] = []
        self.storedValue: Union[bool, Any] = False
        self.time: Union[bool, Any] = 0  # Stores the current time of the engine
        self.usernameLookup:  Dict[Any] = {}  # Stores a map of player id's to usernames to pass between spawn calls
        self.lastSpawnedId: Union[bool, Any] = False
        self.gameHasStarted: Union[bool, Any] = False

        self.meetingStartedBy: Union[bool, Any] = False  # player entity who started the last meeting
        self.meetingStartedAt: Union[bool, Any] = False  # Time it started at
        self.meetingReason: Union[bool, Any] = False  # Will be "Button" or the entity of a murdered player

        self.entityPreload: Dict[Any] = {}  # A dict of entities that had data sent to them before proper instantiation

        self.gameSettings: Dict[Any] = {}

        self.lobbyEntity: Union[bool, Any] = False

        self.ge_callback('Reset')

    def register_player_id(self, player, player_id):
        self.playerIdMap[player_id] = player

    def proc(self, data, ts):
        self.time = ts
        self.tick += 1
        tree = parse(data)
        nodes = []
        flatten(tree, nodes)  # Flatten the tree into the nodes
        for node in nodes:  # Process each node individually, can always traverse if needed
            self.proc_node(node)

    def create_player(self, client_id):
        player = PlayerClass(self)
        player.clientId = client_id
        self.players[client_id] = player
        return player

    def remove_player(self, client_id):
        player = None
        try:
            player = self.players[client_id]
            del self.players[client_id]
        except:
            pass  # Player not in player list

        try:
            if self.playerIdMap[player.playerId] == player:
                del self.playerIdMap[player.playerId]
        except:
            pass  # Player id not registered

        try:
            for entity in player.entities:
                try:
                    del self.entities[entity.netId]
                except:
                    pass
        except:
            pass  # Entity removal issue

    def add_entity(self, player, net_id):
        entity = EntityClass(net_id)
        if entity.add_to_player(player):
            self.entities[net_id] = entity
        else:
            del entity  # Duplicates ?

    def spawn_entity(self, owner_node, command_node):
        if owner_node.commandName == "Player":
            client_id = owner_node.props["clientId"]
            try:
                player = self.players[client_id]
            except:
                # Player not yet instantiated, do so
                player = self.create_player(client_id)
            self.add_entity(player, command_node.props["netId"])
        else:
            client_id = owner_node.props["clientId"]
            if client_id == 4294967294:  # Server Id
                client_id = "SERVER"
            net_id = command_node.props["netId"]
        self.lastSpawnedId = command_node.props["netId"]

    def proc_node(self, command_node):
        if isinstance(command_node, commandLeaf):  # Process command leafs and traverse upward for data where needed
            parent_node = command_node.parent
            # Hazil
            if isinstance(parent_node, hazilLayer):
                if command_node.commandName == "Hello":
                    pass
            # Inner Net
            if isinstance(parent_node, innerLayer):
                if command_node.commandName == "RemovePlayer":
                    removed_client_id = command_node.props["ownerId"]
                    removed_player = self.players[removed_client_id] if removed_client_id in self.players else None
                    self.remove_player(removed_client_id)
                    self.ge_callback('RemovePlayer', player=removed_player)

                if command_node.commandName == "StartGame":
                    self.gameHasStarted = True
                    self.ge_callback('StartGame')

                if command_node.commandName == "EndGame":
                    self.ge_callback('EndGame')
                    self.reset()

                if command_node.commandName == "JoinedGame":  # Joined lobby, reset game state
                    self.reset()
                    self.selfClientID = command_node.props["clientId"]
                    self.hostClientID = command_node.props["hostclientId"]
                    self.ge_callback('JoinedGame')

            # Game Data  Layer
            if isinstance(parent_node, gameDataLayer):
                if command_node.commandName == "Data":
                    owner_id = command_node.props["ownerId"]
                    try:
                        entity = self.entities[owner_id]
                        player = entity.owner
                    except:
                        player = False
                    if player:
                        if owner_id == player.networkTransformNetId:  ## Data addressed to player move handler!
                            player.parse_location(command_node.props["data"])

            # RPC
            if isinstance(parent_node, rpcLayer):
                parent_command_node = parent_node.parent.commandLeafs[parent_node]
                owner_id = parent_command_node.props["ownerId"]
                try:
                    entity = self.entities[owner_id]
                    player: Union[bool, Any] = entity.owner
                except:
                    player = False
                # Traffic sent before player spawn (ALSO OTHER UNKNOWN TRAFFIC?)

                #
                # We do not need a player for these commands
                #

                if command_node.commandName == "SyncSettings":  # Set game settings (no player needed)
                    self.gameSettings = parent_node.children[1].children[0].props
                    self.ge_callback('GameSettings')

                if command_node.commandName == "StartMeeting":  # meeting just started, players have been moved
                    self.gameHasStarted = True
                    if parent_command_node.props["ownerId"] in self.entities:
                        self.meetingStartedBy = self.entities[parent_command_node.props["ownerId"]].owner
                    self.meetingStartedAt = self.time
                    report_id = parent_node.children[0].props["playerId"]
                    self.meetingReason = "Button" if report_id == 255 else report_id
                    self.ge_callback('StartMeeting')

                if command_node.commandName == "Close":  # The meeting is closing
                    self.gameHasStarted = True
                    self.meetingStartedBy = False
                    self.meetingStartedAt = False
                    self.meetingReason = False
                    self.ge_callback('EndMeeting')

                if command_node.commandName == "VotingComplete":  # Meeting voting results
                    self.gameHasStarted = True
                    exile_player = False
                    if command_node.props['exiledPlayerId'] < 255:
                        try:
                            exile_player = self.playerIdMap[command_node.props['exiledPlayerId']]
                        except:
                            pass  # Exiled player not found
                    if exile_player:
                        exile_player.exiled()

                if not player:  # If we don't have a player instantiated yet
                    try:
                        self.entityPreload[owner_id]  # Check if we have established a preload for this entity
                    except:
                        self.entityPreload[owner_id] = []  # Establish one if not
                    self.entityPreload[owner_id].append(
                        command_node)  # Save command, We will rerun these commands if we see the entity spawn

                #
                # We need a player object for these commands to make sense
                #

                if player:
                    if command_node.commandName == "EnterVent":
                        player.vent(True)
                    if command_node.commandName == "ExitVent":
                        player.vent(False)

                    if command_node.commandName == "SnapTo":
                        player.snap_to(command_node.props["x"], command_node.props["y"], command_node.props["seq"])

                    if command_node.commandName == "MurderPlayer":
                        murdered_net_id = command_node.props["netId"]
                        murdered_entity = self.entities[murdered_net_id]
                        murdered_player = murdered_entity.owner
                        player.murder(murdered_player)  # Do the murder

                    if command_node.commandName == "SetName":
                        player.set_name(command_node.props["name"])
                    if command_node.commandName == "SetSkin":
                        player.set_skin(command_node.props['id'])
                    if command_node.commandName == "SetHat":
                        player.set_hat(command_node.props['id'])
                    if command_node.commandName == "SetColor":
                        player.set_color(command_node.props['id'])
                    if command_node.commandName == "SetPet":
                        player.set_pet(command_node.props['id'])

                    if command_node.commandName == "SetInfected":
                        for player_id in command_node.props['playerIdList']:
                            if player_id in self.playerIdMap:
                                self.playerIdMap[player_id].set_infected(True)

                    if command_node.commandName == "SendChat":
                        message = command_node.props["message"]
                        player.chat(message)

            # Game data style player update
            if isinstance(parent_node, UpdateGameDataLayer):
                if command_node.commandName == "Player":
                    try:
                        player = self.playerIdMap[command_node.props["PlayerId"]]
                    except:
                        # Game data update no player
                        return

                    player.set_name(command_node.props["PlayerName"])
                    player.set_skin(command_node.props['SkinId'])
                    player.set_hat(command_node.props['HatId'])
                    player.set_color(command_node.props['ColorId'])
                    player.set_pet(command_node.props['PetId'])

            # Entity spawn
            if isinstance(parent_node, spawnLayer):
                if command_node.commandName == "Lobby":
                    if not self.lobbyEntity:
                        self.lobbyEntity = parent_node.children[1].children[0].props['netId']
                    else:
                        pass  # Happens when we read our own fake lobby spawns
                if command_node.commandName == "Player":
                    # Player spawn
                    for child in parent_node.children[1].children:
                        self.spawn_entity(command_node, child)
                    # Player will exist at this point
                    player = self.players[command_node.props["clientId"]]
                    player_control, player_physics, network_transform = parent_node.children[1].children

                    # Pull out the player id from the data sent on the player control spawn
                    u1, player_id = struct.unpack("BB", player_control.props['data'])
                    player.assign_id(player_id)

                    # Store the network id's of the player entities
                    player.playerControlNetId = player_control.props[
                        'netId']  # Player control entity for the player (handles most actions)
                    player.playerPhysicsNetId = player_physics.props['netId']  ## Handles SnapTo
                    player.networkTransformNetId = network_transform.props['netId']  ## Movement handler

                    # Sometimes commands are sent to entities pre spawn
                    # We keep these and rerun them when the spawn happens

                    for netId in [player.playerControlNetId, player.playerPhysicsNetId, player.networkTransformNetId]:
                        try:
                            commands = self.entityPreload[netId]
                            del self.entityPreload[netId]  # Remove the preload commands from the registry
                        except:
                            commands = []
                        for rerunNode in commands:
                            self.proc_node(rerunNode)  # Rerun the commands sent before spawn

                if command_node.commandName == "GameData":
                    for child in parent_node.children[1].children:
                        self.spawn_entity(command_node, child)
                    a1, a2 = parent_node.children[1].children  # Arguments 1 and 2? (guessing at what to call it)
                    self.gameDataEntities = [a1.props['netId'], a2.props['netId']]
                    user_count = a1.props['data'][0]
                    buffer = a1.props['data'][1:]
                    for i in range(user_count):
                        player_id = buffer[0]
                        buffer = buffer[1:]
                        slen = buffer[0]
                        buffer = buffer[1:]
                        user_name = buffer[0:slen]
                        buffer = buffer[slen:]
                        u1, u2 = struct.unpack("<LH", buffer[0:6])
                        buffer = buffer[6:]
                        self.usernameLookup[player_id] = user_name
                        for clientId in self.players.keys():
                            player = self.players[clientId]
                            if player.playerId == player_id:
                                player.set_username_from_list(user_name)
            if isinstance(parent_node, spawnSubcommandLayer):
                pass  # DO NOT HANDLE HERE!!!

            if "gameId" in command_node.props:
                self.gameId = command_node.props["gameId"]
