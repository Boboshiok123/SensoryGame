import pygame
import random
import sys
import numpy as np
import sounddevice as sd
import scipy.signal

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Screen and constants
W, H = 640, 480
FPS = 60
WHITE, BLACK, PINK = (255, 255, 255), (0, 0, 0), (255, 105, 180)
SHIP_R = 25
AST_SIZES = {3: 40, 2: 24, 1: 12}
START_AST = 4
MAX_TIME = 90  # seconds

# Setup
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
Vec = pygame.math.Vector2

# Load custom font
font_path = "Assets/final game/font/CourierNew.ttf"
font = pygame.font.Font(font_path, 24)

# Score history log
score_log = []

# Load Images
AST_IMAGES = [
    pygame.transform.smoothscale(pygame.image.load("Assets/final game/1x/Brain.png").convert_alpha(), (40, 40)),
    pygame.transform.smoothscale(pygame.image.load("Assets/final game/1x/Ear.png").convert_alpha(), (40, 40)),
    pygame.transform.smoothscale(pygame.image.load("Assets/final game/1x/EyeW.png").convert_alpha(), (40, 40)),
    pygame.transform.smoothscale(pygame.image.load("Assets/final game/1x/Mouth.png").convert_alpha(), (40, 40)),
    pygame.transform.smoothscale(pygame.image.load("Assets/final game/1x/Nose.png").convert_alpha(), (40, 40))
]

PLAYER_IMAGE = pygame.transform.smoothscale(
    pygame.image.load("Assets/final game/1x/Player.png").convert_alpha(), (40, 50))

SLAP_SHEET = pygame.image.load("Assets/final game/1x/Slap.png").convert_alpha()
SLAP_FRAMES = []
frame_w, frame_h = 80, 86
for i in range(SLAP_SHEET.get_height() // frame_h):
    frame = SLAP_SHEET.subsurface(pygame.Rect(0, i * frame_h, frame_w, frame_h))
    SLAP_FRAMES.append(pygame.transform.smoothscale(frame, (30, 40)))

SLAP_SOUND = pygame.mixer.Sound("Assets/sound/Slap.mp3")
slap_channel = pygame.mixer.Channel(1)

channel_levels = [0] * 5

samplerate = 44100
lowpass = scipy.signal.butter(4, 300, 'low', fs=samplerate, output='sos')
highpass = scipy.signal.butter(4, 3000, 'high', fs=samplerate, output='sos')
bandpass = scipy.signal.butter(4, [500, 1200], 'bandpass', fs=samplerate, output='sos')

def audio_callback(indata, frames, time, status):
    global channel_levels
    data = indata[:, 0]
    low = scipy.signal.sosfilt(lowpass, data)
    high = scipy.signal.sosfilt(highpass, data)
    band = scipy.signal.sosfilt(bandpass, data)
    channel_levels[0] = min(np.linalg.norm(data) * 10, 10)
    channel_levels[1] = min(np.linalg.norm(high) * 10, 10)
    channel_levels[2] = min(np.linalg.norm(band) * 10, 10)
    channel_levels[3] = min(np.linalg.norm(data - band) * 10, 10)
    channel_levels[4] = min(np.linalg.norm(low) * 10, 10)

stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate)
stream.start()

def wrap(v): return Vec(v.x % W, v.y % H)

def draw_button(text):
    txt_surf = font.render(text, True, PINK)
    rect = txt_surf.get_rect(center=(W//2, H//2))
    box_rect = rect.inflate(40, 20)
    pygame.draw.rect(screen, BLACK, box_rect)
    pygame.draw.rect(screen, PINK, box_rect, 3)
    screen.blit(txt_surf, rect)
    return box_rect

class Ship:
    def __init__(self):
        self.p = Vec(W/2, H/2)
        self.v = Vec()
        self.a = 0
        self.alive = True
        self.inv = 0
        self.attack_timer = 0
        self.anim_index = 0
        self.image = PLAYER_IMAGE

    def update(self, dt, up, down, left, right, shoot):
        speed = 200
        if up: self.p.y -= speed * dt; self.a = 0
        if down: self.p.y += speed * dt; self.a = 180
        if left: self.p.x -= speed * dt; self.a = 270
        if right: self.p.x += speed * dt; self.a = 90
        self.p = wrap(self.p)

        if shoot and self.attack_timer <= 0:
            self.attack_timer = 0.3
            self.anim_index = 0
            if not slap_channel.get_busy():
                slap_channel.play(SLAP_SOUND)

        if self.attack_timer > 0:
            self.attack_timer -= dt
            self.anim_index += 15 * dt
            if self.anim_index >= len(SLAP_FRAMES):
                self.anim_index = 0
                self.attack_timer = 0

    def draw(self, surf):
        if self.attack_timer > 0:
            frame = SLAP_FRAMES[int(self.anim_index)]
            rotated = pygame.transform.rotate(frame, -self.a)
        else:
            rotated = pygame.transform.rotate(PLAYER_IMAGE, -self.a)
        rect = rotated.get_rect(center=(int(self.p.x), int(self.p.y)))
        surf.blit(rotated, rect.topleft)

    def hit(self): self.alive = False
    def respawn(self): self.__init__(); self.inv = 2

class Ast:
    def __init__(self):
        self.s = 3
        self.r = AST_SIZES[self.s]
        self.p = Vec(random.randrange(W), random.randrange(H))
        self.v = Vec(random.uniform(-1, 1), random.uniform(-1, 1)).normalize() * random.uniform(20, 70)
        self.image = random.choice(AST_IMAGES)

    def upd(self, dt):
        speed_multiplier = 1 + (sum(channel_levels) / 10)
        self.p = wrap(self.p + self.v * dt * speed_multiplier)

    def draw(self, surf):
        rect = self.image.get_rect(center=(int(self.p.x), int(self.p.y)))
        surf.blit(self.image, rect.topleft)

    def split(self): return []

def inputs():
    k = pygame.key.get_pressed()
    return dict(left=k[pygame.K_a], right=k[pygame.K_d], up=k[pygame.K_w], down=k[pygame.K_s], shoot=k[pygame.K_SPACE])

color_map = [(255,255,0), (0,255,0), (255,0,0), (0,0,255), (0,255,255)]
terrain_patches = []

def main():
    global score_log
    ship = Ship(); ast = [Ast() for _ in range(START_AST)]; score = 0; high_score = 0
    game_state = "menu"
    time_left = MAX_TIME

    while True:
        dt = clock.tick(FPS) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if game_state in ["menu", "gameover"]:
                    mx, my = pygame.mouse.get_pos()
                    if draw_button("Start" if game_state == "menu" else "Restart").collidepoint(mx, my):
                        if score > high_score:
                            high_score = score
                        score_log.append(score)
                        ship = Ship()
                        ast = [Ast() for _ in range(START_AST)]
                        terrain_patches.clear()
                        score = 0
                        time_left = MAX_TIME
                        game_state = "play"

        screen.fill(BLACK)

        if game_state != "play":
            draw_button("Start" if game_state == "menu" else "Restart")
            high_score_surf = font.render(f"High Score: {high_score}", True, PINK)
            screen.blit(high_score_surf, (W // 2 - high_score_surf.get_width() // 2, H // 2 + 50))

            if score_log:
                log_text = " | ".join(map(str, score_log[-5:]))
                log_surf = font.render(f"History: {log_text}", True, WHITE)
                screen.blit(log_surf, (W // 2 - log_surf.get_width() // 2, H // 2 + 80))

            pygame.display.flip()
            continue

        time_left -= dt
        if time_left <= 0:
            ship.alive = False
            game_state = "gameover"
            continue

        i = inputs()
        ship.update(dt, i['up'], i['down'], i['left'], i['right'], i['shoot'])

        slapped_asset_index = None
        for a in ast[:]:
            a.upd(dt)
            if ship.attack_timer > 0 and ship.p.distance_to(a.p) < a.r + SHIP_R:
                slapped_asset_index = AST_IMAGES.index(a.image) if a.image in AST_IMAGES else None
                ast.remove(a); score += 10 * a.s

        if not ship.alive:
            game_state = "gameover"
            continue

        if not ast: ast = [Ast() for _ in range(START_AST)]

        for patch in terrain_patches:
            pygame.draw.rect(screen, patch['color'], patch['rect'])

        ship_rect = pygame.Rect(int(ship.p.x - SHIP_R), int(ship.p.y - SHIP_R), SHIP_R*2, SHIP_R*2)
        terrain_patches[:] = [patch for patch in terrain_patches if not patch['rect'].colliderect(ship_rect)]

        if ship.attack_timer > 0 and slapped_asset_index is not None:
            chosen_color = color_map[slapped_asset_index]
            blob_x = random.randint(0, W - 100)
            blob_y = random.randint(0, H - 100)
            for i in range(20):
                for j in range(20):
                    if random.random() < 0.95:
                        size = 16
                        rect = pygame.Rect(blob_x + i * size, blob_y + j * size, size, size)
                        terrain_patches.append({'color': chosen_color, 'rect': rect})

        for a in ast: a.draw(screen)
        ship.draw(screen)

        score_surface = font.render(f"Score: {score}", True, PINK)
        score_rect = score_surface.get_rect(topleft=(10, 10))
        pygame.draw.rect(screen, BLACK, score_rect.inflate(10, 6))
        screen.blit(score_surface, score_rect)

        timer_color = PINK if time_left > 10 or int(time_left * 4) % 2 == 0 else BLACK
        timer_surface = font.render(f"Time: {int(time_left)}", True, timer_color)
        timer_rect = timer_surface.get_rect(topright=(W - 10, 10))
        pygame.draw.rect(screen, BLACK, timer_rect.inflate(10, 6))
        screen.blit(timer_surface, timer_rect)

        pygame.display.flip()

if __name__ == "__main__":
    main()
