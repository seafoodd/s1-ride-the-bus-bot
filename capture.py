import pyautogui
from PIL import Image
import time
from typing import Tuple
import numpy as np
import cv2
import keyboard

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

# (x, y, width, height)
Region = Tuple[int, int, int, int]
Point = Tuple[int, int]

def get_region(x1: int, y1: int, x2: int, y2: int) -> Region:
    return (x1, y1, x2-x1, y2-y1)

def option_region(i: int) -> Region:
    return get_region(OPTION_X1, OPTION_Y1 + STEP * i, OPTION_X2, OPTION_Y2 + STEP * i)

def region_center(region: Region) -> Point:
    x, y, w, h = region
    return (x + w // 2, y + h // 2)

def screenshot_region(region: Region) -> Image.Image:
    return pyautogui.screenshot(region=region)


READY_REGION = get_region(READY_X1, READY_Y1, READY_X2, READY_Y2)

CARD1_REGION = get_region(CARD1_X1, CARD1_Y1, CARD1_X2, CARD1_Y2)
CARD2_REGION = get_region(CARD2_X1, CARD2_Y1, CARD2_X2, CARD2_Y2)
CARD3_REGION = get_region(CARD3_X1, CARD3_Y1, CARD3_X2, CARD3_Y2)

def color_close(p1, p2, tolerance=10):
    return all(abs(a - b) <= tolerance for a, b in zip(p1, p2))

def card_exists(region):
    img = screenshot_region(region)
    arr = np.array(img)

    brightness = arr.mean()
    return brightness > 80

def ready_available() -> bool:
    img = screenshot_region(READY_REGION)
    pixels = img.load()

    match_count = 0
    total = 0

    for x in range(0, READY_REGION[2], 5):
        for y in range(0, READY_REGION[3], 5):
            total += 1
            if color_close(pixels[x, y], READY_COLOR, 25):
                match_count += 1

    return match_count / total > 0.3

def get_state():
    if ready_available():
        return "READY"

    if not options_available():
        return "ANIMATION"

    return "CHOOSE"

#for i in range(4):
#    img = screenshot_region(option_region(i))
#    img.save(f"debug/option_{i}.png")
#    pyautogui.moveTo(region_center(option_region(i)))
#    time.sleep(0.2)

#print("Done")

def options_available():
    px = pyautogui.pixel(*OPTION_AVAILABLE_CHECK_POINT)
    return color_close(px, OPTION_AVAILABLE_CHECK_COLOR, 35) 

def crop_rank(card):
    return card.crop((34, 9, 51, 29))

def crop_suit(card):
    return card.crop((30, 30, 48, 48))

def match(template_path, img):
    template = cv2.imread(template_path, 0)
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    return np.max(res)

def detect_rank(rank_img):
    best = ("?", 0)

    for r in range(2, 15):
        
        score = match(f"templates/ranks/{r}.png", rank_img)
        if score > best[1]:
            best = (r, score)

    return best[0]

def detect_suit(suit_img):
    best = ("?", 0)

    for s in ["hearts","spades","diamonds","clubs"]:
        score = match(f"templates/suits/{s}.png", suit_img)
        if score > best[1]:
            best = (s, score)

    return best[0]

def read_card(region):
    if not card_exists(region):
        return None
    card = screenshot_region(region)

    rank_img = crop_rank(card)
    suit_img = crop_suit(card)

    rank = detect_rank(rank_img)
    suit = detect_suit(suit_img)

    if rank == "?" or suit == "?":
        return None

    return rank, suit

def read_card_image(card):
    rank_img = crop_rank(card)
    suit_img = crop_suit(card)

    rank = detect_rank(rank_img)
    suit = detect_suit(suit_img)

    return rank, suit

def click_ready():
    pyautogui.moveTo(region_center(READY_REGION))
    pyautogui.click()

def click_option(i):
    pyautogui.moveTo(region_center(option_region(i)))
    pyautogui.click()

#card = Image.open("debug/card1.png")
#card.show()
#rank = card.crop((34, 9, 51, 29))
#suit = card.crop((30, 30, 48, 48))

#print("TEST CARD: ", read_card_image(card))
#rank.show()
#suit.show()

paused = True

def toggle_pause():
    global paused
    paused = not paused
    print("PAUSED" if paused else "RESUMED")

keyboard.add_hotkey('p', toggle_pause)

last_state = None
while True:
    if paused:
        time.sleep(0.1)
        continue

    state = get_state()

    if state != last_state:
        print(f"{state} STATE")
        last_state = state
    if state == "READY":
        click_ready()
    if state == "CHOOSE":
        cards = (
            read_card(CARD1_REGION),
            read_card(CARD2_REGION),
            read_card(CARD3_REGION),
        )

        print(cards, len(cards))

        if cards[0] == None:
            click_option(0)
        elif cards[1] == None:
            option = 2
            if cards[0][0] < 7: option = 0
            elif cards[0][0] > 10: option = 1
            click_option(option)
        elif cards[2] == None:
            option = 2
            delta = abs(cards[0][0] - cards[1][0])

            if delta < 5:
                option = 1
            elif delta >= 7:
                option = 0

            click_option(option)
        else:
            option = 0
            #        h c d s
            suits = [0,0,0,0]

            for i in range(3):
                suit = cards[i][1]
                if suit == "hearts": suits[0] += 1
                elif suit == "clubs": suits[1] +=1
                elif suit == "diamonds": suits[2] +=1
                elif suit == "spades": suits[3] +=1

            option = suits.index(min(suits))
            click_option(option)

        if card_exists(CARD1_REGION):
            card = screenshot_region(CARD1_REGION)
            rank = crop_rank(card)
            suit = crop_suit(card)

            rank.save("debug/rank1.png")
            suit.save("debug/suit1.png")
            card.save("debug/card1.png")
            print("CARD 1 EXISTS", read_card(CARD1_REGION))
        if card_exists(CARD2_REGION):
            card = screenshot_region(CARD2_REGION)
            rank = crop_rank(card)
            suit = crop_suit(card)

            rank.save("debug/rank2.png")
            suit.save("debug/suit2.png")
            card.save("debug/card2.png")
            print("CARD 2 EXISTS", read_card(CARD2_REGION))
        if card_exists(CARD3_REGION):
            card = screenshot_region(CARD3_REGION)
            rank = crop_rank(card)
            suit = crop_suit(card)

            rank.save("debug/rank3.png")
            suit.save("debug/suit3.png")
            card.save("debug/card3.png")
            print("CARD 3 EXISTS", read_card(CARD3_REGION))

    time.sleep(0.05)
