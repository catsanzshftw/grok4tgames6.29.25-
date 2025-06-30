import asyncio
import platform
import pygame
import numpy as np
import random

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60
INVADER_ROWS, INVADER_COLS = 5, 11
INVADER_SIZE, INVADER_SPACING = 20, 10
PLAYER_SPEED, PROJECTILE_SPEED = 5, 7
SHIELD_COUNT, SHIELD_WIDTH, SHIELD_HEIGHT, SHIELD_HEALTH = 4, 60, 20, 5
SHOT_COOLDOWN = 0.3  # New: Firing cooldown in seconds

# Colors
BLACK, WHITE, GREEN, CYAN, MAGENTA, RED = (0, 0, 0), (255, 255, 255), (0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 0, 0)

# Game States
MENU, PLAYING, WIN, LOSE = 0, 1, 2, 3

# Setup Screen
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders")
clock = pygame.time.Clock()

# Font
font = pygame.font.Font(None, 24)

# Vignette Surface (Precomputed)
vignette_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
for x in range(WIDTH):
    for y in range(HEIGHT):
        dist = ((x - WIDTH / 2) ** 2 + (y - HEIGHT / 2) ** 2) ** 0.5
        if dist > 300:
            alpha = min(255, int((dist - 300) / 100 * 50))
            vignette_surface.set_at((x, y), (0, 0, 0, alpha))

# Sound Generation
def generate_sound(frequency, duration, volume=0.5, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(frequency * t * 2 * np.pi) * volume
    stereo_wave = np.column_stack((wave, wave))
    return pygame.sndarray.make_sound((stereo_wave * 32767).astype(np.int16))

# Sound Effects
shoot_sound = generate_sound(440, 0.1)
hit_sound = generate_sound(220, 0.1)
explosion_sound = generate_sound(100, 0.2)
move_sound = generate_sound(200, 0.05)
win_sound = generate_sound(880, 0.5, volume=0.3)
lose_sound = generate_sound(110, 0.5, volume=0.3)

# Background Music with Bassline
def generate_music():
    notes = [440, 494, 523, 587, 659]
    bass_notes = [110, 123, 138]
    music = np.array([])
    bass = np.array([])
    for _ in range(16):
        note = random.choice(notes)
        bass_note = random.choice(bass_notes)
        wave = np.sin(note * np.linspace(0, 0.2, 8820) * 2 * np.pi)
        bass_wave = np.sin(bass_note * np.linspace(0, 0.4, 17640) * 2 * np.pi) * 0.5
        music = np.append(music, wave)
        bass = np.append(bass, bass_wave[:8820])
    combined = music * 0.7 + bass * 0.3
    stereo_music = np.column_stack((combined, combined))
    return pygame.sndarray.make_sound((stereo_music * 0.1 * 32767).astype(np.int16))

music = generate_music()
music.set_volume(0.2)

# Game Objects
player_x, player_y, player_lives, player_score = WIDTH // 2, HEIGHT - 50, 3, 0
invader_grid = [[{'x': 240 + col * (INVADER_SIZE + INVADER_SPACING), 'y': 100 + row * (INVADER_SIZE + INVADER_SPACING), 'alive': True}
                 for col in range(INVADER_COLS)] for row in range(INVADER_ROWS)]
invader_direction, invader_speed = 1, 1
player_projectiles, invader_projectiles = [], []
shields = [{'x': 100 + i * (WIDTH - 200) // (SHIELD_COUNT - 1), 'y': HEIGHT - 100, 'health': SHIELD_HEALTH} for i in range(SHIELD_COUNT)]
game_state = MENU
last_shot_time = 0  # New: Track last shot for cooldown
blink_timer = 0  # New: For menu text blinking

# Drawing Functions
def draw_player():
    pygame.draw.polygon(screen, GREEN, [(player_x, player_y - 10), (player_x - 10, player_y + 10), (player_x + 10, player_y + 10)])

def draw_invader(row, x, y):
    if row == 0: pygame.draw.rect(screen, CYAN, (x - 10, y - 10, 20, 20))
    elif row == 1: pygame.draw.polygon(screen, MAGENTA, [(x, y - 10), (x - 10, y + 10), (x + 10, y + 10)])
    elif row == 2: pygame.draw.circle(screen, WHITE, (int(x), int(y)), 10)
    elif row == 3: pygame.draw.polygon(screen, CYAN, [(x - 10, y - 10), (x + 10, y - 10), (x, y + 10)])
    elif row == 4: pygame.draw.polygon(screen, MAGENTA, [(x - 10, y + 10), (x + 10, y + 10), (x, y - 10)])

def draw_projectile(x, y, color):
    pygame.draw.rect(screen, color, (x - 2, y - 5, 4, 10))

def draw_shield(shield):
    if shield['health'] > 0:
        health_factor = shield['health'] / SHIELD_HEALTH
        rect = pygame.Rect(shield['x'] - SHIELD_WIDTH // 2, shield['y'] - SHIELD_HEIGHT // 2,
                           SHIELD_WIDTH * health_factor, SHIELD_HEIGHT)
        pygame.draw.rect(screen, GREEN, rect)
        if shield['health'] < SHIELD_HEALTH:
            for _ in range(int((SHIELD_HEALTH - shield['health']) * 2)):
                x1 = rect.left + random.randint(0, rect.width)
                y1 = rect.top + random.randint(0, rect.height)
                x2 = x1 + random.randint(-5, 5)
                y2 = y1 + random.randint(-5, 5)
                pygame.draw.line(screen, WHITE, (x1, y1), (x2, y2), 1)

def draw_hud():
    screen.blit(font.render(f"Score: {player_score}", True, WHITE), (10, 10))
    screen.blit(font.render(f"Lives: {player_lives}", True, WHITE), (WIDTH - 100, 10))

def draw_crt_effects():
    for y in range(0, HEIGHT, 4):
        if random.random() < 0.1:
            pygame.draw.line(screen, WHITE, (0, y), (WIDTH, y), 1)
    screen.blit(vignette_surface, (0, 0))

# Game Logic
def move_invaders():
    global invader_direction, invader_speed
    move_sound.play()
    for row in invader_grid:
        for invader in row:
            if invader['alive']:
                invader['x'] += invader_direction * invader_speed
    edge_hit = any(invader['alive'] and (invader['x'] < 50 or invader['x'] > WIDTH - 50) for row in invader_grid for invader in row)
    if edge_hit:
        invader_direction *= -1
        for row in invader_grid:
            for invader in row:
                if invader['alive']:
                    invader['y'] += 10
    alive_count = sum(1 for row in invader_grid for invader in row if invader['alive'])
    invader_speed = 1 + (55 - alive_count) * 0.05

def invader_shoot():
    alive_invaders = [invader for row in invader_grid for invader in row if invader['alive']]
    if alive_invaders and random.random() < 0.05:
        shooter = random.choice(alive_invaders)
        invader_projectiles.append({'x': shooter['x'], 'y': shooter['y']})

def check_collisions():
    global player_score, player_lives, game_state
    score_values = [50, 40, 30, 20, 10]  # New: Points per row (top to bottom)
    for p in player_projectiles[:]:
        for row_idx, row in enumerate(invader_grid):
            for invader in row:
                if invader['alive'] and abs(p['x'] - invader['x']) < 10 and abs(p['y'] - invader['y']) < 10:
                    invader['alive'] = False
                    player_projectiles.remove(p)
                    player_score += score_values[row_idx]
                    hit_sound.play()
                    break
            else:
                continue
            break
    for p in invader_projectiles[:]:
        if abs(p['x'] - player_x) < 10 and abs(p['y'] - player_y) < 10:
            invader_projectiles.remove(p)
            player_lives -= 1
            explosion_sound.play()
            if player_lives <= 0:
                game_state = LOSE
                lose_sound.play()
                music.fadeout(1000)  # New: Fade out music
        for shield in shields:
            if shield['health'] > 0 and abs(p['x'] - shield['x']) < SHIELD_WIDTH // 2 and abs(p['y'] - shield['y']) < SHIELD_HEIGHT // 2:
                invader_projectiles.remove(p)
                shield['health'] -= 1
                break
    for p in player_projectiles[:]:
        for shield in shields:
            if shield['health'] > 0 and abs(p['x'] - shield['x']) < SHIELD_WIDTH // 2 and abs(p['y'] - shield['y']) < SHIELD_HEIGHT // 2:
                player_projectiles.remove(p)
                shield['health'] -= 1
                break
    if any(invader['alive'] and invader['y'] >= player_y - 20 for row in invader_grid for invader in row):
        game_state = LOSE
        lose_sound.play()
        music.fadeout(1000)
    elif all(not invader['alive'] for row in invader_grid for invader in row):
        game_state = WIN
        win_sound.play()
        music.fadeout(1000)

def reset_game():
    global player_x, player_lives, player_score, invader_grid, player_projectiles, invader_projectiles, shields, invader_speed, game_state, last_shot_time
    player_x, player_lives, player_score = WIDTH // 2, 3, 0
    invader_grid = [[{'x': 240 + col * (INVADER_SIZE + INVADER_SPACING), 'y': 100 + row * (INVADER_SIZE + INVADER_SPACING), 'alive': True}
                     for col in range(INVADER_COLS)] for row in range(INVADER_ROWS)]
    player_projectiles, invader_projectiles = [], []
    shields = [{'x': 100 + i * (WIDTH - 200) // (SHIELD_COUNT - 1), 'y': HEIGHT - 100, 'health': SHIELD_HEALTH} for i in range(SHIELD_COUNT)]
    invader_speed = 1
    game_state = PLAYING
    last_shot_time = 0
    music.play(-1)  # Restart music

# Main Game Setup and Loop
def setup():
    music.play(-1)

def update_loop():
    global player_x, game_state, last_shot_time, blink_timer
    current_time = pygame.time.get_ticks() / 1000  # Seconds
    blink_timer += 1 / FPS  # Update blink timer

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN) and (event.button == 1 or event.key == pygame.K_SPACE):
            if game_state == MENU:
                reset_game()
            elif game_state == PLAYING and current_time - last_shot_time >= SHOT_COOLDOWN:
                player_projectiles.append({'x': player_x, 'y': player_y - 10})
                shoot_sound.play()
                last_shot_time = current_time
            elif game_state in (WIN, LOSE):
                game_state = MENU

    if game_state == PLAYING:
        mouse_x, _ = pygame.mouse.get_pos()
        player_x += (mouse_x - player_x) * 0.1
        player_x = max(20, min(WIDTH - 20, player_x))
        
        for p in player_projectiles[:]:
            p['y'] -= PROJECTILE_SPEED
            if p['y'] < 0:
                player_projectiles.remove(p)
        for p in invader_projectiles[:]:
            p['y'] += PROJECTILE_SPEED
            if p['y'] > HEIGHT:
                invader_projectiles.remove(p)
        
        if random.random() < 0.02:
            move_invaders()
        invader_shoot()
        check_collisions()

    screen.fill(BLACK)
    if game_state == MENU:
        screen.blit(font.render("Space Invaders", True, WHITE), (WIDTH // 2 - 70, HEIGHT // 2 - 50))
        if int(blink_timer * 2) % 2:  # Blink every 0.5 seconds
            screen.blit(font.render("Click or Space to Start", True, WHITE), (WIDTH // 2 - 90, HEIGHT // 2))
    elif game_state == PLAYING:
        draw_player()
        for row_idx, row in enumerate(invader_grid):
            for invader in row:
                if invader['alive']:
                    draw_invader(row_idx, invader['x'], invader['y'])
        for p in player_projectiles:
            draw_projectile(p['x'], p['y'], GREEN)
        for p in invader_projectiles:
            draw_projectile(p['x'], p['y'], RED)
        for shield in shields:
            draw_shield(shield)
        draw_hud()
        draw_crt_effects()
    elif game_state == WIN:
        screen.blit(font.render("You Win!", True, WHITE), (WIDTH // 2 - 40, HEIGHT // 2))
        draw_crt_effects()
    elif game_state == LOSE:
        screen.blit(font.render("Game Over", True, WHITE), (WIDTH // 2 - 50, HEIGHT // 2))
        draw_crt_effects()
    
    pygame.display.flip()
    return True

async def main():
    setup()
    running = True
    while running:
        running = update_loop()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())
