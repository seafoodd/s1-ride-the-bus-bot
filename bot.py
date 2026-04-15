import logging
import time
from enum import Enum
from typing import Any, Optional, Tuple

import cv2
import keyboard
import numpy as np
import pyautogui
from PIL import Image

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- CONSTANTS & COORDINATES ---
READY_X1, READY_Y1 = 845, 704
READY_X2, READY_Y2 = 1074, 748
READY_COLOR = (46, 128, 219)

OPTION_AVAILABLE_CHECK_POINT = 863, 696
OPTION_AVAILABLE_CHECK_COLOR = (225, 126, 18)
OPTION_X1, OPTION_Y1 = 795, 714
OPTION_X2, OPTION_Y2 = 1124, 757
STEP = 49

CARD1_X1, CARD1_Y1 = 262, 421
CARD1_X2, CARD1_Y2 = 426, 600

CARD2_X1, CARD2_Y1 = 406, 421
CARD2_X2, CARD2_Y2 = 568, 600

CARD3_X1, CARD3_Y1 = 550, 421
CARD3_X2, CARD3_Y2 = 711, 600

# Types
Region = Tuple[int, int, int, int]
Point = Tuple[int, int]


class GameState(Enum):
    READY = "READY"
    ANIMATION = "ANIMATION"
    CHOOSE = "CHOOSE"


# --- HELPER FUNCTIONS ---
def get_region(x1: int, y1: int, x2: int, y2: int) -> Region:
    return (x1, y1, x2 - x1, y2 - y1)


def option_region(i: int) -> Region:
    return get_region(OPTION_X1, OPTION_Y1 + STEP * i, OPTION_X2, OPTION_Y2 + STEP * i)


def region_center(region: Region) -> Point:
    x, y, w, h = region
    return (x + w // 2, y + h // 2)


def screenshot_region(region: Region) -> Image.Image:
    return pyautogui.screenshot(region=region)


def color_close(p1: Tuple[int, ...], p2: Tuple[int, ...], tolerance: int = 10) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(p1, p2))


# --- PRE-CALCULATED REGIONS ---
READY_REGION = get_region(READY_X1, READY_Y1, READY_X2, READY_Y2)
CARD_REGIONS = [
    get_region(CARD1_X1, CARD1_Y1, CARD1_X2, CARD1_Y2),
    get_region(CARD2_X1, CARD2_Y1, CARD2_X2, CARD2_Y2),
    get_region(CARD3_X1, CARD3_Y1, CARD3_X2, CARD3_Y2),
]


# --- VISION & DETECTION ---
def card_exists(region: Region) -> bool:
    img = screenshot_region(region)
    arr = np.array(img)
    return arr.mean() > 80


def ready_available() -> bool:
    """Vectorized check for the ready button color, much faster than nested loops."""
    img = screenshot_region(READY_REGION)
    arr = np.array(img)

    # Calculate absolute difference between image pixels and target color
    diff = np.abs(arr.astype(int) - READY_COLOR)
    matches = np.all(diff <= 25, axis=-1)

    match_ratio = np.mean(matches)
    return match_ratio > 0.3


def options_available() -> bool:
    px = pyautogui.pixel(*OPTION_AVAILABLE_CHECK_POINT)
    return color_close(px, OPTION_AVAILABLE_CHECK_COLOR, 35)


def get_state() -> GameState:
    if ready_available():
        return GameState.READY
    if not options_available():
        return GameState.ANIMATION
    return GameState.CHOOSE


def crop_rank(card: Image.Image) -> Image.Image:
    return card.crop((34, 9, 51, 29))


def crop_suit(card: Image.Image) -> Image.Image:
    return card.crop((30, 30, 48, 48))


def match_template(template_path: str, img: Image.Image) -> float:
    template = cv2.imread(template_path, 0)
    if template is None:
        logger.error(f"Template missing: {template_path}")
        return 0.0

    img_gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    return float(np.max(res))


def detect_rank(rank_img: Image.Image):
    best = ("?", 0.0)
    for r in range(2, 15):
        score = match_template(f"templates/ranks/{r}.png", rank_img)
        if score > best[1]:
            best = (r, score)
    return best[0]


def detect_suit(suit_img: Image.Image):
    best = ("?", 0.0)
    for s in ["hearts", "spades", "diamonds", "clubs"]:
        score = match_template(f"templates/suits/{s}.png", suit_img)
        if score > best[1]:
            best = (s, score)
    return best[0]


def read_card_image(card: Image.Image) -> Tuple[Any, Any]:
    rank = detect_rank(crop_rank(card))
    suit = detect_suit(crop_suit(card))
    return rank, suit


def read_card(region: Region) -> Optional[Tuple[Any, Any]]:
    if not card_exists(region):
        return None

    card = screenshot_region(region)
    rank, suit = read_card_image(card)

    if rank == "?" or suit == "?":
        logger.warning(
            f"Failed to fully read card at {region}. Rank: {rank}, Suit: {suit}"
        )
        return None

    return rank, suit


# --- ACTIONS & LOGIC ---
def click_ready():
    logger.info("Clicking READY")
    pyautogui.moveTo(region_center(READY_REGION))
    pyautogui.click()


def click_option(i: int):
    logger.info(f"Clicking OPTION {i}")
    pyautogui.moveTo(region_center(option_region(i)))
    pyautogui.click()


def decide_option(cards: Tuple) -> int:
    """Calculates which option to pick based on the visible cards."""
    if cards[0] is None:
        return 0

    elif cards[1] is None:
        rank = cards[0][0]
        if rank < 7:
            return 0
        if rank > 10:
            return 1
        return 2

    elif cards[2] is None:
        delta = abs(cards[0][0] - cards[1][0])
        if delta < 5:
            return 1
        if delta >= 7:
            return 0
        return 2

    else:
        suits = [0, 0, 0, 0]  # hearts, clubs, diamonds, spades
        suit_map = {"hearts": 0, "clubs": 1, "diamonds": 2, "spades": 3}

        for i in range(3):
            suit = cards[i][1]
            if suit in suit_map:
                suits[suit_map[suit]] += 1

        return suits.index(min(suits))


def save_debug_cards():
    """Saves screenshots of existing cards to the debug folder."""
    for i, region in enumerate(CARD_REGIONS, start=1):
        if card_exists(region):
            card = screenshot_region(region)
            crop_rank(card).save(f"debug/rank{i}.png")
            crop_suit(card).save(f"debug/suit{i}.png")
            card.save(f"debug/card{i}.png")
            logger.debug(f"Saved Debug Card {i}: {read_card_image(card)}")


# --- MAIN LOOP ---
paused = True


def toggle_pause():
    global paused
    paused = not paused
    logger.info("PAUSED" if paused else "RESUMED")


keyboard.add_hotkey("p", toggle_pause)
logger.info("Script started.")
logger.info("")
logger.info("Set Schedule 1 Display Settings:")
logger.info("Resolution: 1920 x 1080")
logger.info("Active Display: Monitor 1")
logger.info("Display Mode: Fullscreen Window")
logger.info("")
logger.info("ENTER RIDE THE BUS TABLE AND UNPAUSE THE BOT.")
logger.info("Press 'P' to toggle pause/resume.")
logger.info("")

last_state = None

while True:
    if paused:
        time.sleep(0.1)
        continue

    state = get_state()

    if state != last_state:
        logger.info(f"State changed to: {state.name}")
        last_state = state

    if state == GameState.READY:
        click_ready()

    elif state == GameState.CHOOSE:
        cards = (
            read_card(CARD_REGIONS[0]),
            read_card(CARD_REGIONS[1]),
            read_card(CARD_REGIONS[2]),
        )

        logger.debug(f"Detected cards: {cards}")

        option_to_click = decide_option(cards)
        click_option(option_to_click)

        # Save debug info
        # save_debug_cards()

    time.sleep(0.05)
