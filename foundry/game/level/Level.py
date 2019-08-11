import wx

from game.Data import Mario3Level, object_set_pointers
from game.File import ROM
from game.ObjectSet import ObjectSet
from game.gfx.Palette import get_bg_color_for, load_palette
from game.gfx.PatternTable import PatternTable
from game.gfx.drawable.Block import Block
from game.gfx.objects.EnemyItem import EnemyObject
from game.gfx.objects.EnemyItemFactory import EnemyItemFactory
from game.gfx.objects.Jump import Jump
from game.gfx.objects.LevelObject import LevelObject
from game.gfx.objects.LevelObjectFactory import LevelObjectFactory
from game.level import _load_level_offsets
from game.level.LevelLike import LevelLike

ENEMY_POINTER_OFFSET = 0x10  # no idea why
LEVEL_POINTER_OFFSET = 0x10010  # also no idea

ENEMY_SIZE = 3

TIME_INF = -1

LEVEL_DEFAULT_HEIGHT = 27
LEVEL_DEFAULT_WIDTH = 16


class Level(LevelLike):
    MIN_LENGTH = 0x10

    offsets, world_indexes = _load_level_offsets()

    WORLDS = len(world_indexes)

    HEADER_LENGTH = 9  # bytes

    palettes = []

    def __init__(self, world, level, object_data_offset, enemy_data_offset, object_set):
        super(Level, self).__init__(world, level, object_set)

        self.attached_to_rom = True

        self.object_set_number = object_set
        self.object_set = ObjectSet(object_set)

        level_index = Level.world_indexes[world] + level

        level_data: Mario3Level = Level.offsets[level_index]

        if world == 0:
            self.name = level_data.name
        else:
            self.name = f"Level {world}-{level}, '{level_data.name}'"

        self.object_offset = object_data_offset
        self.enemy_offset = enemy_data_offset + 1

        self.objects = []
        self.jumps = []
        self.enemies = []

        print(
            f"Loading {self.name} @ {hex(self.object_offset)}/{hex(self.enemy_offset)}"
        )

        rom = ROM()

        self.header = rom.bulk_read(Level.HEADER_LENGTH, self.object_offset)
        self._parse_header()

        object_offset = self.object_offset + Level.HEADER_LENGTH

        object_data = ROM.rom_data[object_offset:]
        enemy_data = ROM.rom_data[self.enemy_offset :]

        self._load_level(object_data, enemy_data)

        self.changed = False

    def _load_level(self, object_data, enemy_data):
        self.object_factory = LevelObjectFactory(
            self.object_set_number,
            self._graphic_set_index,
            self._object_palette_index,
            self.objects,
            self._is_vertical,
        )
        self.enemy_item_factory = EnemyItemFactory(
            self.object_set_number, self._enemy_palette_index
        )

        self._load_objects(object_data)
        self._load_enemies(enemy_data)

        self.object_size_on_disk = self._calc_objects_size()
        self.enemy_size_on_disk = len(self.enemies) * ENEMY_SIZE

    def reload(self):
        header_and_object_data, enemy_data = self.to_bytes()

        object_data = header_and_object_data[1][Level.HEADER_LENGTH :]

        self._load_level(object_data, enemy_data[1])

    def _calc_objects_size(self):
        size = 0

        for obj in self.objects:
            if obj.is_4byte:
                size += 4
            else:
                size += 3

        size += Jump.SIZE * len(self.jumps)

        return size

    def _parse_header(self):
        self._start_y_index = (self.header[4] & 0b1110_0000) >> 5

        self._length = Level.MIN_LENGTH + (self.header[4] & 0b0000_1111) * 0x10
        self.width = self._length
        self.height = LEVEL_DEFAULT_HEIGHT

        self._start_x_index = (self.header[5] & 0b0110_0000) >> 5

        self._enemy_palette_index = (self.header[5] & 0b0001_1000) >> 3
        self._object_palette_index = self.header[5] & 0b0000_0111

        self._pipe_ends_level = not (self.header[6] & 0b1000_0000)
        self._scroll_type_index = (self.header[6] & 0b0110_0000) >> 5
        self._is_vertical = self.header[6] & 0b0001_0000

        if self._is_vertical:
            self.height = self._length
            self.width = LEVEL_DEFAULT_WIDTH

        # todo isn't that the object set for the "next area"?
        self._next_area_object_set = (
            self.header[6] & 0b0000_1111
        )  # for indexing purposes

        self._start_action = (self.header[7] & 0b1110_0000) >> 5

        self._graphic_set_index = self.header[7] & 0b0001_1111

        self._time_index = (self.header[8] & 0b1100_0000) >> 6

        self._music_index = self.header[8] & 0b0000_1111

        # if there is a bonus area or other secondary level, this pointer points to it

        self.object_set_pointer = object_set_pointers[self.object_set_number]

        self._level_pointer = (
            (self.header[1] << 8)
            + self.header[0]
            + LEVEL_POINTER_OFFSET
            + self.object_set_pointer.type
        )
        self._enemy_pointer = (
            (self.header[3] << 8) + self.header[2] + ENEMY_POINTER_OFFSET
        )

        self.has_bonus_area = (
            self.object_set_pointer.min
            <= self._level_pointer
            <= self.object_set_pointer.max
        )

        self.size = self.width, self.height

        self.changed = True

    def _load_enemies(self, data):
        self.enemies.clear()

        def data_left(_data):
            # the commented out code seems to hold for the stock ROM, but if the ROM was already edited with another
            # editor, it might not, since they only wrote the 0xFF to end the enemy data

            return _data and not _data[0] == 0xFF  # and _data[1] in [0x00, 0x01]

        enemy_data, data = data[0:ENEMY_SIZE], data[ENEMY_SIZE:]

        while data_left(enemy_data):
            enemy = self.enemy_item_factory.make_object(enemy_data, 0)

            self.enemies.append(enemy)

            enemy_data, data = data[0:ENEMY_SIZE], data[ENEMY_SIZE:]

    def _load_objects(self, data):
        self.objects.clear()
        self.jumps.clear()

        if not data or data[0] == 0xFF:
            return

        while True:
            obj_data, data = data[0:3], data[3:]

            domain = (obj_data[0] & 0b1110_0000) >> 5

            obj_id = obj_data[2]
            has_length_byte = (
                self.object_set.get_object_byte_length(domain, obj_id) == 4
            )

            if has_length_byte:
                fourth_byte, data = data[0], data[1:]
                obj_data.append(fourth_byte)

            level_object = self.object_factory.from_data(obj_data, len(self.objects))

            if isinstance(level_object, LevelObject):
                self.objects.append(level_object)
            elif isinstance(level_object, Jump):
                self.jumps.append(level_object)

            if data[0] == 0xFF:
                break

    @property
    def next_area_objects(self):
        return self._level_pointer

    @next_area_objects.setter
    def next_area_objects(self, value):
        if value == self._level_pointer:
            return

        value -= LEVEL_POINTER_OFFSET + self.object_set_pointer.type

        self.header[0] = 0x00FF & value
        self.header[1] = value >> 8

        self._parse_header()

    @property
    def next_area_enemies(self):
        return self._enemy_pointer

    @next_area_enemies.setter
    def next_area_enemies(self, value):
        if value == self._enemy_pointer:
            return

        value -= ENEMY_POINTER_OFFSET

        self.header[2] = 0x00FF & value
        self.header[3] = value >> 8

        self._parse_header()

    @property
    def start_y_index(self):
        return self._start_y_index

    @start_y_index.setter
    def start_y_index(self, index):
        if index == self._start_y_index:
            return

        self.header[4] &= 0b0001_1111
        self.header[4] |= index << 5

        self._parse_header()

    # bit 4 unused

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, length):
        """
        Sets the length of the level in "screens".

        :param length: amount of screens the level should have
        :return:
        """

        # internally the level has length + 1 screens
        if length + 1 == self._length:
            return

        self.header[4] &= 0b1111_0000
        self.header[4] |= length // 0x10

        self._parse_header()

    # bit 1 unused

    @property
    def start_x_index(self):
        return self._start_x_index

    @start_x_index.setter
    def start_x_index(self, index):
        if index == self._start_x_index:
            return

        self.header[5] &= 0b1001_1111
        self.header[5] |= index << 5

        self._parse_header()

    @property
    def enemy_palette_index(self):
        return self._enemy_palette_index

    @enemy_palette_index.setter
    def enemy_palette_index(self, index):
        if index == self._enemy_palette_index:
            return

        self.header[5] &= 0b1110_0111
        self.header[5] |= index << 3

        self._parse_header()

    @property
    def object_palette_index(self):
        return self._object_palette_index

    @object_palette_index.setter
    def object_palette_index(self, index):
        if index == self._object_palette_index:
            return

        self.header[5] &= 0b1111_1000
        self.header[5] |= index

        self._parse_header()

    @property
    def pipe_ends_level(self):
        return self._pipe_ends_level

    @pipe_ends_level.setter
    def pipe_ends_level(self, truth_value):
        if truth_value == self._pipe_ends_level:
            return

        self.header[6] &= 0b0111_1111
        self.header[6] |= int(not truth_value) << 7

        self._parse_header()

    @property
    def scroll_type(self):
        return self._scroll_type_index

    @scroll_type.setter
    def scroll_type(self, index):
        if index == self._scroll_type_index:
            return

        self.header[6] &= 0b1001_1111
        self.header[6] |= index << 5

        self._parse_header()

    @property
    def is_vertical(self):
        return self._is_vertical

    @is_vertical.setter
    def is_vertical(self, truth_value):
        if truth_value == self._is_vertical:
            return

        self.header[6] &= 0b1110_1111
        self.header[6] |= int(truth_value) << 4

        self._parse_header()

    @property
    def next_area_object_set(self):
        return self._next_area_object_set

    @next_area_object_set.setter
    def next_area_object_set(self, index):
        if index == self._next_area_object_set:
            return

        self.header[6] &= 0b1111_0000
        self.header[6] |= index

        self._parse_header()

    @property
    def start_action(self):
        return self._start_action

    @start_action.setter
    def start_action(self, index):
        if index == self._start_action:
            return

        self.header[7] &= 0b0001_1111
        self.header[7] |= index << 5

        self._parse_header()

    @property
    def graphic_set(self):
        return self._graphic_set_index

    @graphic_set.setter
    def graphic_set(self, index):
        if index == self._graphic_set_index:
            return

        self.header[7] &= 0b1110_0000
        self.header[7] |= index

        self._parse_header()

    @property
    def time_index(self):
        return self._time_index

    @time_index.setter
    def time_index(self, index):
        if index == self._time_index:
            return

        self.header[8] &= 0b0011_1111
        self.header[8] |= index << 6

        self._parse_header()

    # bit 3 and 4 unused

    @property
    def music_index(self):
        return self._music_index

    @music_index.setter
    def music_index(self, index):
        if index == self._music_index:
            return

        self.header[8] &= 0b1111_0000
        self.header[8] |= index

        self._parse_header()

    def is_too_big(self):
        too_many_enemies = self.enemy_size_on_disk < len(self.enemies) * ENEMY_SIZE
        too_many_objects = self._calc_objects_size() > self.object_size_on_disk

        return too_many_enemies or too_many_objects

    def get_all_objects(self):
        return self.objects + self.enemies

    def get_object_names(self):
        return [obj.description for obj in self.objects + self.enemies]

    def object_at(self, x, y):
        for obj in reversed(self.objects + self.enemies):
            if (x, y) in obj:
                return obj
        else:
            return None

    def draw(self, dc, block_length, transparency):
        bg_color = get_bg_color_for(self.object_set_number, self._object_palette_index)

        dc.SetBackground(wx.Brush(wx.Colour(bg_color)))
        dc.SetPen(wx.Pen(wx.Colour(0x00, 0x00, 0x00, 0x80), width=1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        dc.Clear()

        if self.object_set_number == 9:  # desert
            self._draw_floor(dc, block_length)

        for level_object in self.objects + self.enemies:
            level_object.render()
            level_object.draw(dc, block_length, transparency)

            if level_object.selected:
                x, y, w, h = level_object.get_rect().Get()

                x *= block_length
                w *= block_length
                y *= block_length
                h *= block_length

                dc.DrawRectangle(wx.Rect(x, y, w, h))

    def _draw_floor(self, dc, block_length):
        floor_level = 26
        floor_block_index = 86

        palette_group = load_palette(self.object_set_number, self._object_palette_index)
        pattern_table = PatternTable(self._graphic_set_index)
        tsa_data = ROM().get_tsa_data(self.object_set_number)

        floor_block = Block(floor_block_index, palette_group, pattern_table, tsa_data)

        for x in range(self.width):
            floor_block.draw(
                dc, x * block_length, floor_level * block_length, block_length
            )

    def paste_object_at(self, x, y, obj):
        if isinstance(obj, EnemyObject):
            return self.add_enemy(obj.obj_index, x, y)
        elif isinstance(obj, LevelObject):
            if obj.is_4byte:
                length = obj.data[3]
            else:
                length = None

            return self.add_object(obj.domain, obj.obj_index, x, y, length)

    def create_object_at(self, x, y, domain=0, object_index=0):
        self.add_object(domain, object_index, x, y, None, len(self.objects))

    def create_enemy_at(self, x, y):
        # goomba to have something to display
        self.add_enemy(0x72, x, y, len(self.enemies))

    def add_object(self, domain, object_index, x, y, length, index=-1):
        if index == -1:
            index = len(self.objects)

        obj = self.object_factory.from_properties(
            domain, object_index, x, y, length, index
        )
        self.objects.insert(index, obj)

        self.changed = True

        return obj

    def add_enemy(self, object_index, x, y, index=-1):
        if index == -1:
            index = len(self.enemies)
        else:
            index %= len(self.objects)

        enemy = self.enemy_item_factory.make_object([object_index, x, y], -1)

        self.enemies.insert(index, enemy)

        self.changed = True

        return enemy

    def add_jump(self):
        self.jumps.append(Jump.from_properties(0, 0, 0, 0))

    def index_of(self, obj):
        if obj in self.objects:
            return self.objects.index(obj)
        else:
            return len(self.objects) + self.enemies.index(obj)

    def get_object(self, index):
        if index < len(self.objects):
            return self.objects[index]
        else:
            return self.enemies[index % len(self.objects)]

    def remove_object(self, obj):
        if obj is None:
            return

        try:
            self.objects.remove(obj)
        except ValueError:
            self.enemies.remove(obj)

        self.changed = True

    def to_m3l(self):
        m3l_bytes = bytearray()

        m3l_bytes.append(self.world)
        m3l_bytes.append(self.level)
        m3l_bytes.append(self.object_set_number)

        m3l_bytes.extend(self.header)

        for obj in self.objects + self.jumps:
            m3l_bytes.extend(obj.to_bytes())

        # only write 0xFF, even though the stock ROM would use 0xFF00 or 0xFF01
        # this is done to keep compatibility to older editors
        m3l_bytes.append(0xFF)

        for enemy in sorted(self.enemies, key=lambda _enemy: _enemy.x_position):
            m3l_bytes.extend(enemy.to_bytes())

        m3l_bytes.append(0xFF)

        return m3l_bytes

    def from_m3l(self, m3l_bytes):
        self.world, self.level, self.object_set_number = m3l_bytes[:3]
        self.object_set = ObjectSet(self.object_set_number)

        self.object_offset = self.enemy_offset = 0

        # update the level_object_factory
        self._load_level(b"", b"")

        m3l_bytes = m3l_bytes[3:]

        self.header = m3l_bytes[: Level.HEADER_LENGTH]
        self._parse_header()

        m3l_bytes = m3l_bytes[Level.HEADER_LENGTH :]

        # figure out how many bytes are the objects
        self._load_objects(m3l_bytes)
        object_size = self._calc_objects_size() + len(b"\xFF")  # delimiter

        object_bytes = m3l_bytes[:object_size]
        enemy_bytes = m3l_bytes[object_size:]

        self._load_level(object_bytes, enemy_bytes)

        self.attached_to_rom = False

    def to_bytes(self):
        data = bytearray()

        data.extend(self.header)

        for obj in self.objects:
            data.extend(obj.to_bytes())

        for jump in self.jumps:
            data.extend(jump.to_bytes())

        data.append(0xFF)

        enemies = bytearray()

        for enemy in sorted(self.enemies, key=lambda _enemy: _enemy.x_position):
            enemies.extend(enemy.to_bytes())

        enemies.append(0xFF)

        return [(self.object_offset, data), (self.enemy_offset, enemies)]

    def from_bytes(self, object_data, enemy_data):

        self.object_offset, object_bytes = object_data
        self.enemy_offset, enemies = enemy_data

        self.header = object_bytes[0 : Level.HEADER_LENGTH]
        objects = object_bytes[Level.HEADER_LENGTH :]

        self._parse_header()
        self._load_level(objects, enemies)
