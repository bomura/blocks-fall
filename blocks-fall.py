import uasyncio as asyncio
from machine import Pin, PWM, I2C
import ssd1306
import time
import random

# --------- ディスプレイとボタンの設定 ----------
_i2c = I2C(1, sda=Pin(14), scl=Pin(15))
_display = ssd1306.SSD1306_I2C(128, 32, _i2c, addr=0x3C)

# --------- PWMによる音楽再生用のタスク ----------
# PWM出力の設定（例：ピン15）
_sound_pwm = PWM(Pin(2))
_sound_pwm.duty_u16(0)

tones = {"C3": 132, "D3": 148, "E3": 166, "F3": 176, "G3": 196, "A3": 220, "B3": 248,
         "C4": 262, "D4": 294, "E4": 330, "F4": 349, "G4": 392, "A4": 440, "B4": 494,
         "C5": 524}
melody = [("E4",500),("B3",250), ("C4",250), ("D4",500), ("C4",250), ("B3",250), ("A3",500),("A3",250),("C4",250), ("E4",500), ("D4",250), ("C4",250), ("B3",500),
          ("C4",250),("D4",500),("E4",500),("C4",500),("A3",500),("A3",1000),
          ("D4",500),("F4",250),("A4",500),("G4",250),("F4",250),("E4",500),("C4",250),("E4",500),("D4",250),("C4",250),("B3",500),
          ("B3",250),("C4",250),("D4",500),("E4",500),("C4",500),("A3",500),("A3",1000)]

music_playing = True

_btn_right = Pin(28, Pin.IN, Pin.PULL_UP)
_btn_left = Pin(27, Pin.IN, Pin.PULL_UP)
_btn_rotate = Pin(26, Pin.IN, Pin.PULL_UP)

DISPLAY_WIDTH = 32
DISPLAY_HEIGHT = 128
UI_WIDTH = 8
GAME_AREA_WIDTH = DISPLAY_WIDTH - UI_WIDTH
GAME_AREA_HEIGHT = DISPLAY_HEIGHT

BLOCK_SIZE = 3
FIELD_ROWS = GAME_AREA_HEIGHT // BLOCK_SIZE
FIELD_COLS = GAME_AREA_WIDTH // BLOCK_SIZE
CELL_W = BLOCK_SIZE
CELL_H = BLOCK_SIZE

BLOCKS = {
    'I': [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)]
    ],
    'T': [
        [(0, 1), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 1)],
        [(0, 0), (0, 1), (0, 2), (1, 1)],
        [(0, 1), (1, 1), (1, 2), (2, 1)]
    ],
    'S': [
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 0), (1, 0), (1, 1), (2, 1)]
    ],
    'Z': [
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 0)]
    ],
    'J': [
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 0), (2, 1)],
        [(0, 0), (0, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 0), (2, 0)]
    ],
    'L': [
        [(0, 0), (0, 1), (1, 0), (2, 0)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 0), (2, 1)],
        [(0, 0), (0, 1), (0, 2), (1, 2)]
    ],
    'U': [
        [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2)],
        [(0, 0), (0, 1), (1, 0), (2, 0), (2, 1)],
        [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (2, 0), (2, 1)]
    ]
}

fall_interval = 1
_last_fall_time = time.ticks_ms()
score = 0
game_field = [[0 for _ in range(FIELD_COLS)] for _ in range(FIELD_ROWS)]


def can_move(piece, drow, dcol):
    for (dr, dc) in piece['shape']:
        new_row = piece['row'] + dr + drow
        new_col = piece['col'] + dc + dcol
        if new_col < 0 or new_col >= FIELD_COLS or new_row < 0 or new_row >= FIELD_ROWS:
            return False
        if game_field[new_row][new_col]:
            return False
    return True

def fix_piece(piece):
    for (dr, dc) in piece['shape']:
        r = piece['row'] + dr
        c = piece['col'] + dc
        if 0 <= r < FIELD_ROWS and 0 <= c < FIELD_COLS:
            game_field[r][c] = 1

def spawn_piece():
    word, shapes = random.choice(list(BLOCKS.items()))
    rotation = random.randint(0, len(shapes) - 1)
    shape = shapes[rotation]
    col = FIELD_COLS // 2
    return {
        'row': 0,
        'col': col,
        'word': word,
        'rotation': rotation,
        'shape': shape
    }

def rotate_piece(piece):
    shapes = BLOCKS[piece['word']]
    new_rotation = (piece['rotation'] + 1) % len(shapes)
    new_shape = shapes[new_rotation]
    offsets = [(0, 0), (0, -1), (0, 1), (0, -2), (0, 2)]
    original_row = piece['row']
    original_col = piece['col']
    for drow, dcol in offsets:
        piece['row'] = original_row + drow
        piece['col'] = original_col + dcol
        piece['shape'] = new_shape
        if can_move(piece, 0, 0):
            piece['rotation'] = new_rotation
            return
    piece['row'] = original_row
    piece['col'] = original_col

def clear_lines():
    global game_field, score
    cleared_lines = 0
    new_field = []
    for row in game_field:
        if all(cell == 1 for cell in row):
            cleared_lines += 1
        else:
            new_field.append(row)
    for _ in range(cleared_lines):
        new_field.insert(0, [0] * FIELD_COLS)
    game_field = new_field
    score += 100 * cleared_lines

def draw_ui(piece):
    _display.fill_rect(0, 0, DISPLAY_HEIGHT, UI_WIDTH, 0)
    _display.text("Score:%d" % score, UI_WIDTH + CELL_H, 0, 1)
    for (dr, dc) in piece['shape']:
        x = dr * CELL_H
        y = dc * CELL_W
        _display.fill_rect(x, y, CELL_W, CELL_H, 1)

def draw_game_field(piece):
    _display.fill_rect(0, UI_WIDTH, GAME_AREA_HEIGHT, GAME_AREA_WIDTH, 0)
    for r in range(FIELD_ROWS):
        for c in range(FIELD_COLS):
            if game_field[r][c]:
                x = r * CELL_H
                y = UI_WIDTH + c * CELL_W
                _display.fill_rect(x, y, CELL_W, CELL_H, 1)
    for (dr, dc) in piece['shape']:
        r = piece['row'] + dr
        c = piece['col'] + dc
        x = r * CELL_H
        y = UI_WIDTH + c * CELL_W
        _display.fill_rect(x, y, CELL_W, CELL_H, 1)


async def play_music():
    global music_playing
    while True:
        if not music_playing:
            break
        for tone, duration in melody:
            _sound_pwm.freq(tones[tone])
            _sound_pwm.duty_u16(32768)  # 50% duty cycle
            await asyncio.sleep_ms(duration)
            _sound_pwm.duty_u16(0)
            await asyncio.sleep_ms(50)

# --------- ゲームのメインループ（非同期タスク） ----------
async def run_game():
    global score, game_field, _last_fall_time, music_playing
    falling_piece = spawn_piece()
    next_piece = spawn_piece()
    game_over = False

    while not game_over:
        current_time = time.ticks_ms()
        if _btn_left.value() == 0 and can_move(falling_piece, 0, -1):
            falling_piece['col'] -= 1
            await asyncio.sleep(0.1)
        if _btn_right.value() == 0 and can_move(falling_piece, 0, 1):
            falling_piece['col'] += 1
            await asyncio.sleep(0.1)
        if _btn_rotate.value() == 0:
            rotate_piece(falling_piece)
            await asyncio.sleep(0.1)
        if time.ticks_diff(current_time, _last_fall_time) > fall_interval:
            if can_move(falling_piece, 1, 0):
                falling_piece['row'] += 1
            else:
                fix_piece(falling_piece)
                score += 10
                clear_lines()
                if any(cell == 1 for cell in game_field[0]):
                    game_over = True
                else:
                    falling_piece = next_piece
                    next_piece = spawn_piece()
            _last_fall_time = current_time

        draw_ui(next_piece)
        draw_game_field(falling_piece)
        _display.show()
        await asyncio.sleep(0.05)

    while True:
        music_playing = False
        _display.fill(0)
        _display.text("GAME OVER", 0, 10, 1)
        _display.text("Score:%d" % score, 0, 20, 1)
        _display.show()
        await asyncio.sleep(10)
        _display.fill(0)
        _display.show()
        break

# --------- メイン関数で両タスクを並行実行 ----------
async def main():
    game_task = asyncio.create_task(run_game())
    music_task = asyncio.create_task(play_music())
    await asyncio.gather(game_task, music_task)

if __name__ == '__main__':
    asyncio.run(main())