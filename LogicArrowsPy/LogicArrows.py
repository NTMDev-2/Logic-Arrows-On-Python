""" 
LogicArrows game remade in python. Original game is on steam. 
"""

import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal
import random

import pygame

WORLD: dict[tuple[int, int], 'Block'] = {}
State = Literal[0, 1]
Pos = tuple[int, int]
BEHIND_OFFSETS: list[Pos] = [(0, -1), (-1, 0), (0, 1), (1, 0)]
active_cells: dict[Pos, dict[Pos, State]] = {}
BLOCKED: dict[Pos, int] = {}

class Block(ABC):
    def __init__(self, rotation: int = 0):
        self.next_state = 0
        self.state = 0
        self.rotation = rotation
    def getState(self):
        return self.state
    def changeState(self, new_state: State):
        self.state = new_state

    @abstractmethod
    def outputs(self) -> list[Pos]: ...
    @abstractmethod
    def logic(self, inputs: list[State]) -> State: ...

    def rotate(self, amount: int = 1):
        self.rotation = (self.rotation + amount) % 4
    def rotateOffset(self, offset: tuple[int, int]) -> tuple[int, int]:
        x, y = offset

        for _ in range(self.rotation):
            x, y = y, -x

        return x, y

    def getOutputs(self) -> list[tuple[int, int]]:
        return [self.rotateOffset(offset) for offset in self.outputs()]

class Arrow(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return inputs[0] if inputs else 0
class SideSplitter(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)
    
    def outputs(self):
        return [(1, 0), (-1, 0)]
    def logic(self, inputs: list[State]) -> State:
        return inputs[0] if inputs else 0
class Splitter(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)
    
    def outputs(self):
        return [(0, 1), (1, 0)]
    def logic(self, inputs: list[State]) -> State:
        return inputs[0] if inputs else 0
class MultiSplitter(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(1, 0), (-1, 0), (0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return inputs[0] if inputs else 0
class Source(Block):
    def __init__(self, rotation: int = 0):
        self.active = True
        super().__init__(rotation)
    
    def outputs(self):
        return [(0, 1), (0, -1), (1, 0), (-1, 0)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if self.active else 0

class Blocker(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0
class Detector(Block):
    def __init__(self, rotation: int = 0):
        super().__init__()
        self.rotation = rotation % 4
    def getBehindOffset(self):
        return BEHIND_OFFSETS[self.rotation]

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 0

class Bridge(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)
    
    def outputs(self):
        return [(0, 2)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0
class Diagonal(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(1, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0
class DiagonalSplitter(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1), (1, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0
class DiagonalBridgeSplitter(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 2), (1, 0)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0
class Extender(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1), (0, 2)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if any(inputs) else 0

class Not(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 0 if any(inputs) else 1
class And(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if all(inputs) and inputs and len(inputs) >= 2 else 0
class Xor(Block):
    def __init__(self, rotation: int = 0):
        super().__init__(rotation)

    def outputs(self):
        return [(0, 1)]
    def logic(self, inputs: list[State]) -> State:
        return 1 if sum(inputs) == 1 else 0

class Pulser(Block):
    def __init__(self, rotation: int = 0, interval: float = 0.75):
        super().__init__(rotation)
        self.interval = interval
        self.timer = 0.0
        self.active = False

    def outputs(self) -> list[Pos]:
        return [(0, 1)]

    def logic(self, inputs: list[State]) -> State:
        return 0
#class Random(Block):
screenDirty = True
DIRTY_BLOCKS: set[Pos] = set()

def signalOf(block: Block) -> State:
    if isinstance(block, Source):
        return 1 if block.active else 0
    if isinstance(block, Pulser):
        return 1 if block.active else 0
    return block.getState()
def publish(pos: Pos, block: Block):
    state = signalOf(block)
    x, y = pos
    for dx, dy in block.getOutputs():
        active_cells.setdefault((x + dx, y + dy), {})[pos] = state
def retract(pos: Pos, block: Block):
    x, y = pos
    for dx, dy in block.getOutputs():
        target = (x + dx, y + dy)
        sources = active_cells.get(target)
        if sources is None:
            continue
        sources.pop(pos, None)
        if not sources:
            del active_cells[target]
def shiftBlocked(pos: Pos, block: Block, delta: int):
    x, y = pos
    for dx, dy in block.getOutputs():
        target = (x + dx, y + dy)
        count = BLOCKED.get(target, 0) + delta
        if count > 0:
            BLOCKED[target] = count
        else:
            BLOCKED.pop(target, None)
def attach(pos: Pos, block: Block):
    publish(pos, block)
    if isinstance(block, Blocker) and block.getState() == 1:
        shiftBlocked(pos, block, 1)
def detach(pos: Pos, block: Block):
    retract(pos, block)
    if isinstance(block, Blocker) and block.getState() == 1:
        shiftBlocked(pos, block, -1)
def dirtyDetectors(x: int, y: int):
    for bx, by in BEHIND_OFFSETS:
        detector_pos = (x - bx, y - by)
        detector = WORLD.get(detector_pos)
        if isinstance(detector, Detector) and detector.getBehindOffset() == (bx, by):
            DIRTY_BLOCKS.add(detector_pos)
def updateTimedBlocks(dt: float):
    for pos, block in WORLD.items():
        if not isinstance(block, Pulser): # (Pulser, Random)):
            continue

        block.timer += dt

        if block.timer >= block.interval:
            block.timer %= block.interval
            block.active = not block.active

            DIRTY_BLOCKS.add(pos)


def setBlock(x: int, y: int, block: Block):
    global screenDirty
    if (x, y) not in WORLD:
        WORLD[(x, y)] = block
        attach((x, y), block)
        DIRTY_BLOCKS.add((x, y))
        screenDirty = True
def removeBlock(x: int, y: int):
    global screenDirty

    if (x, y) not in WORLD:
        return
    block = WORLD.pop((x, y))
    detach((x, y), block)
    DIRTY_BLOCKS.add((x, y))
    for dx, dy in block.getOutputs():
        DIRTY_BLOCKS.add((x + dx, y + dy))
    dirtyDetectors(x, y)
    screenDirty = True
def rotateBlock(x: int, y: int, amount: int = 1):
    global screenDirty

    block = WORLD.get((x, y))
    if block is None:
        return
    detach((x, y), block)
    for dx, dy in block.getOutputs():
        DIRTY_BLOCKS.add((x + dx, y + dy))
    block.rotate(amount)
    attach((x, y), block)
    for dx, dy in block.getOutputs():
        DIRTY_BLOCKS.add((x + dx, y + dy))
    DIRTY_BLOCKS.add((x, y))
    screenDirty = True
def setSourceActive(x: int, y: int, active: bool):
    block = WORLD.get((x, y))
    if isinstance(block, Source) and block.active != active:
        block.active = active
        publish((x, y), block)
        DIRTY_BLOCKS.add((x, y))
def getBlock(x: int, y: int) -> Block:
    if (x, y) in WORLD:
        return WORLD.get((x, y))
    else:
        raise ValueError(f"No block at position ({x}, {y})")

def tick():
    global DIRTY_BLOCKS, screenDirty

    dirty = DIRTY_BLOCKS
    DIRTY_BLOCKS = set()

    next_states = {}
    
    for x, y in dirty:
        block = WORLD.get((x, y))
        if block is None:
            continue

        if isinstance(block, (Pulser, Source)):
            next_states[(x, y)] = 1 if block.active else 0
            continue
        if isinstance(block, Detector):
            dx, dy = block.getBehindOffset()
            behind = WORLD.get((x + dx, y + dy))
            next_states[(x, y)] = (
                1 if behind is not None and behind.getState() == 1 else 0
            )
            continue
        dirtyDetectors(x, y)
        signals = {} if (x, y) in BLOCKED else active_cells.get((x, y), {})
        if isinstance(block, Blocker) and block.getState() == 1:
            dx, dy = block.getOutputs()[0]
            front = (x + dx, y + dy)
            inputs = [state for source_pos, state in signals.items() if source_pos != front]
        else:
            inputs = list(signals.values())

        next_states[(x, y)] = block.logic(inputs)

    changed = set()
    for pos, state in next_states.items():
        block = WORLD.get(pos)
        if block is None:
            continue

        if block.getState() != state:
            block.changeState(state)
            publish(pos, block)
            if isinstance(block, Blocker):
                shiftBlocked(pos, block, 1 if state == 1 else -1)
            changed.add(pos)
    for x, y in changed:
        block = WORLD.get((x, y))
        if block is None:
            continue

        for dx, dy in block.getOutputs():
            target = (x + dx, y + dy)

            if target in WORLD:
                DIRTY_BLOCKS.add(target)

    screenDirty = bool(changed)

pygame.init()
screen = pygame.display.set_mode((1100, 733))

pygame.display.set_caption("LogicArrows")
clock = pygame.time.Clock()
running = True
BACKGROUND_COLOR = (255, 255, 255)

CELL_SIZE: int = 32

BASE_DIR = Path(__file__).parent
TEXTURES = {
    'Arrow': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Arrow.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'SideSplitter': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'SideSplitter.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Splitter': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Splitter.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'MultiSplitter': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'MultiSplitter.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Source': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Source.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Blocker': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Blocker.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Detector': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Detector.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Bridge': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Bridge.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Diagonal': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Diagonal.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'DiagonalSplitter': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'DiagonalSplitter.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'DiagonalBridgeSplitter': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'DiagonalBridgeSplitter.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Extender': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Extender.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Not': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Not.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'And': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'And.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Xor': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Xor.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'Pulser': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Pulser.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),

    'On': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'On.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),

    'Hotbar': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'Hotbar.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'HotbarLeft': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'HotbarLeft.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'HotbarRight': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'HotbarRight.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
    'HotbarSelected': pygame.transform.scale(pygame.image.load(BASE_DIR / 'textures' / 'HotbarSelected.png').convert_alpha(), (CELL_SIZE, CELL_SIZE)),
}

HOTBAR_PAGES: list[list[type[Block]]] = [
    [Source, Arrow, Blocker, Detector, Bridge],
    [SideSplitter, Splitter, MultiSplitter, Diagonal, DiagonalSplitter],
    [DiagonalBridgeSplitter, Extender, Not, And, Xor],
    [Pulser]
]

current_page: int = 0
selected_slot: int = -1
GLOBAL_ROTATION: int = 0

HOTBAR_SLOTS: int = 5
HOTBAR_GAP: int = 4
HOTBAR_BUTTON_SIZE: int = CELL_SIZE
HOTBAR_SLOT_SIZE: int = CELL_SIZE
hotbar_rects: dict = {}
def draw_hotbar(screen):
    global hotbar_rects

    hotbar_rects = {}

    page = HOTBAR_PAGES[current_page]
    gap = HOTBAR_GAP
    slot_size = HOTBAR_SLOT_SIZE
    button_size = HOTBAR_BUTTON_SIZE

    total_width = (
        button_size
        + gap
        + HOTBAR_SLOTS * slot_size
        + (HOTBAR_SLOTS - 1) * gap
        + gap
        + button_size
    )

    start_x = (screen.get_width() - total_width) // 2
    start_y = screen.get_height() - slot_size - 16

    left_rect = pygame.Rect(start_x, start_y, button_size, button_size)
    screen.blit(TEXTURES["HotbarLeft"], left_rect)
    hotbar_rects["left"] = left_rect

    slots_x = start_x + button_size + gap

    for i in range(HOTBAR_SLOTS):
        x = slots_x + i * (slot_size + gap)
        rect = pygame.Rect(x, start_y, slot_size, slot_size)

        screen.blit(TEXTURES["Hotbar"], rect)

        if i < len(page):
            block_class = page[i]
            image = TEXTURES[block_class.__name__]
            image_rect = image.get_rect(center=rect.center)
            screen.blit(image, image_rect)

        if i == selected_slot and selected_block is not None:
            screen.blit(TEXTURES["HotbarSelected"], rect)

        hotbar_rects[i] = rect

    right_x = slots_x + HOTBAR_SLOTS * slot_size + (HOTBAR_SLOTS - 1) * gap + gap
    right_rect = pygame.Rect(right_x, start_y, button_size, button_size)

    screen.blit(TEXTURES["HotbarRight"], right_rect)
    hotbar_rects["right"] = right_rect

noWorldRedraw = False
selected_block = None

preview_rect = None
preview_background = None
font = pygame.font.Font(None, 24)

def draw_placement_preview(screen):
    global preview_rect, preview_background

    if preview_background is not None and preview_rect is not None:
        screen.blit(preview_background, preview_rect.topleft)

    preview_rect = None
    preview_background = None

    if selected_slot < 0 or selected_slot >= len(HOTBAR_PAGES[current_page]):
        return

    block_class = HOTBAR_PAGES[current_page][selected_slot]
    image = TEXTURES[block_class.__name__]

    if GLOBAL_ROTATION:
        image = pygame.transform.rotate(image, -90 * GLOBAL_ROTATION)

    image = image.copy()
    image.set_alpha(100)

    grid_x, grid_y = screen_to_world(*pygame.mouse.get_pos())
    screen_x, screen_y = world_to_screen(grid_x, grid_y)

    screen_x = round(screen_x)
    screen_y = round(screen_y)

    full_rect = image.get_rect(topleft=(screen_x, screen_y))
    screen_rect = screen.get_rect()
    clipped_rect = full_rect.clip(screen_rect)

    if clipped_rect.width == 0 or clipped_rect.height == 0:
        return

    preview_background = screen.subsurface(clipped_rect).copy()
    preview_rect = clipped_rect

    screen.blit(
        image,
        full_rect,
        area=clipped_rect.move(-full_rect.x, -full_rect.y)
    )
def draw_world(screen):
    for (x, y), block in WORLD.items():
        image = TEXTURES[type(block).__name__]
        rotation = getattr(block, "rotation", 0)

        if rotation:
            image = pygame.transform.rotate(image, -90 * rotation)

        screen_x, screen_y = world_to_screen(x, y)
        screen_x = round(screen_x)
        screen_y = round(screen_y)

        if screen_x + CELL_SIZE <= 0 or screen_x >= screen.get_width() or screen_y + CELL_SIZE <= 0 or screen_y >= screen.get_height():
            continue

        if block.getState() == 1:
            screen.blit(TEXTURES["On"], (screen_x, screen_y))

        screen.blit(image, (screen_x, screen_y))

camera_x = 0.0
camera_y = 0.0
CAMERA_SPEED = 8
def world_to_screen(x, y):
    return (
        (x - camera_x) * CELL_SIZE,
        screen.get_height() - (y - camera_y + 1) * CELL_SIZE
    )
def screen_to_world(mouse_x, mouse_y):
    return (
        math.floor(mouse_x / CELL_SIZE + camera_x),
        math.floor(
            (screen.get_height() - 1 - mouse_y) / CELL_SIZE + camera_y
        )
    )

BLOCK_ID: dict[type[Block], int] = {
    Arrow: 1,
    SideSplitter: 2,
    Splitter: 3,
    MultiSplitter: 4,
    Source: 5,
    Blocker: 6,
    Detector: 7,
    Bridge: 8,
    Diagonal: 9,
    DiagonalSplitter: 10,
    DiagonalBridgeSplitter: 11,
    Extender: 12,
    Not: 13,
    And: 14,
    Xor: 15,
    Pulser: 16
}

SESSION_ID = random.randint(1, 999999)
def save():
    string = ''
    for (x, y), block in WORLD.items():
        x_segment = f'X{x}'
        y_segment = f'Y{y}'
        block_segment = f'B{BLOCK_ID.get(type(block))}'

        save_segment = f'?{x_segment}{y_segment}{block_segment}'

        string += save_segment

    with open(BASE_DIR / 'saves' / f'save_id_{SESSION_ID}.txt', mode='w') as save:
        save.write(string)
        save.close()
    print(f'Saved with session id {SESSION_ID}')

import re

ID_BLOCK: dict[int, type[Block]] = {
    block_id: block_class
    for block_class, block_id in BLOCK_ID.items()
}
def load(id: int):
    path = BASE_DIR / 'saves' / f'save_id_{id}.txt'

    with open(path, 'r', encoding='utf-8') as save_file:
        loaded_string = save_file.read().strip()

    pattern = re.compile(r'\?X(-?\d+)Y(-?\d+)B(\d+)')
    matches = list(pattern.finditer(loaded_string))

    if not loaded_string:
        return

    if not matches or ''.join(match.group(0) for match in matches) != loaded_string:
        raise ValueError("Invalid save format")

    WORLD.clear()
    active_cells.clear()
    BLOCKED.clear()
    DIRTY_BLOCKS.clear()

    for match in matches:
        x, y, block_id = map(int, match.groups())

        if block_id not in ID_BLOCK:
            raise ValueError(f"Unknown block ID: {block_id}")

        block_class = ID_BLOCK[block_id]
        WORLD[(x, y)] = block_class()

    for pos, block in WORLD.items():
        attach(pos, block)
        DIRTY_BLOCKS.add(pos)

    global screenDirty
    screenDirty = True

while running:
    dt = clock.tick(80) / 1000.0
    updateTimedBlocks(dt)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            world_pos = screen_to_world(*event.pos)
            clicked_hotbar = False

            if hotbar_rects["left"].collidepoint(mouse_pos):
                current_page = (current_page - 1) % len(HOTBAR_PAGES)
                selected_slot = 0
                screenDirty = True
                clicked_hotbar = True
            elif hotbar_rects["right"].collidepoint(mouse_pos):
                current_page = (current_page + 1) % len(HOTBAR_PAGES)
                selected_slot = 0
                screenDirty = True
                clicked_hotbar = True
            else:
                for i in range(HOTBAR_SLOTS):
                    rect = hotbar_rects.get(i)

                    if rect and rect.collidepoint(mouse_pos):
                        selected_slot = i
                        screenDirty = True
                        clicked_hotbar = True
                        break
            
            selected_block = HOTBAR_PAGES[current_page][selected_slot] if selected_slot < len(HOTBAR_PAGES[current_page]) else None
            if selected_block is not None and not clicked_hotbar:
                if selected_block is None or selected_slot == -1:
                    removeBlock(*world_pos)
                else:
                    if world_pos in WORLD:
                        removeBlock(*world_pos)
                    if selected_slot >= 0:
                        setBlock(*world_pos, selected_block(GLOBAL_ROTATION))

        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            GLOBAL_ROTATION = (GLOBAL_ROTATION + 1) % 4
            screenDirty = True
            noWorldRedraw = True
        if event.type == pygame.MOUSEMOTION:
            screenDirty = True
            noWorldRedraw = True
    
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKQUOTE:
            selected_block = None
            selected_slot = -1
            noWorldRedraw = True
            screenDirty = True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
            save()
            continue
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l and pygame.key.get_mods() & pygame.KMOD_CTRL:
            load(int(input('Enter save id: ')))
            continue
                
        
        if event.type == pygame.KEYDOWN and event.key == pygame.K_w:
            camera_y += 1
            screenDirty = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
            camera_y -= 1
            screenDirty = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:
            camera_x -= 1
            screenDirty = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_d:
            camera_x += 1
            screenDirty = True

        
    if screenDirty:
        if noWorldRedraw and selected_block is not None and selected_slot >= 0:
            draw_placement_preview(screen)
        else:
            preview_rect = None
            preview_background = None

            screen.fill(BACKGROUND_COLOR)
            draw_world(screen)
            draw_hotbar(screen)
    pygame.display.flip()
    screenDirty = False
    noWorldRedraw = False
    tick()
