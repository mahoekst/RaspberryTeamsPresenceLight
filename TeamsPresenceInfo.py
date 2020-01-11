import sys
import json
import logging
import time
import threading
import multiprocessing
import datetime
import os
import math
import requests
import msal
import random
import colorsys

from random import randint
from luma.core.sprite_system import framerate_regulator
from random import randrange
from luma.core.render import canvas
from luma.oled.device import sh1106
from luma.core.interface.serial import spi 
from PIL import ImageFont

POLLINTERFALL = 2

FALLOFF = 1.9
SCAN_SPEED = 3

sstatus = "Available"
loggedin = False

class Presence(object):
    def __init__(self, status="Away"):
        self.lock = threading.Lock()
        self.value = status
    def setstatus(self,status):
        logging.debug('Waiting for lock')
        self.lock.acquire()
        try:
            logging.debug('Acquired lock')
            self.value = status
        finally:
            self.lock.release()

def thread_getPresence(c):
    accounts = app.get_accounts()
    if accounts:
        logging.info("Account(s) exists in cache, probably with token too. Let's try.")
        print("Account being used:")
        for a in accounts:
            print(a["username"])
        # Assuming the end user chose this one
        chosen = accounts[0]
        # Now let's try to find a token in cache for this account
        
        while True:
            result = app.acquire_token_silent(scope, account=chosen)

            if "access_token" in result:
            
            # Calling graph using the access token
            
                graph_data = requests.get(  # Use token to call downstream service
                    endpoint,
                    headers={'Authorization': 'Bearer ' + result['access_token']},).json()
                #print("Graph API call result: %s" % json.dumps(graph_data, indent=2))

                if "availability" in graph_data:
                    presenceData = graph_data.get('availability')

                    if presenceData == "Busy":
                        c.setstatus("Busy")
                    elif presenceData == "Available":
                        c.setstatus("Available")
                    elif presenceData == "Away":
                        c.setstatus("Away")
                    #something is wrong, switch the leds off
                else:
                    c.setstatus("Unknown")
                time.sleep(POLLINTERFALL)
            
    else:
        print(result.get("error"))
        print(result.get("error_description"))
        print(result.get("correlation_id"))  # You may need this when reporting a bug

def thread_getPresence2(c):
    while True:
        print("thread")
        lstatus = c.value

        if lstatus == "Away":
            lstatus = "Available"
        elif lstatus == "Available":
            lstatus = "Busy"
        elif lstatus == "Busy":
            lstatus = "Away"
        #lock??
        c.setstatus(lstatus)
        time.sleep(POLLINTERFALL)

def oprint(statustext):
    font_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                'fonts', 'C&C Red Alert [INET].ttf'))
    font2 = ImageFont.truetype(font_path, 24)

    with canvas(device) as draw:
        draw.text((0, 0), statustext, font=font2, fill="white")

def init_stars(num_stars, max_depth):
    stars = []
    for i in range(num_stars):
        # A star is represented as a list with this format: [X,Y,Z]
        star = [randrange(-25, 25), randrange(-25, 25), randrange(1, max_depth)]
        stars.append(star)
    return stars

def move_and_draw_stars(stars, max_depth):
    origin_x = device.width // 2
    origin_y = device.height // 2

    with canvas(device) as draw:
        for star in stars:
            # The Z component is decreased on each frame.
            star[2] -= 0.19

            # If the star has past the screen (I mean Z<=0) then we
            # reposition it far away from the screen (Z=max_depth)
            # with random X and Y coordinates.
            if star[2] <= 0:
                star[0] = randrange(-25, 25)
                star[1] = randrange(-25, 25)
                star[2] = max_depth

            # Convert the 3D coordinates to 2D using perspective projection.
            k = 128.0 / star[2]
            x = int(star[0] * k + origin_x)
            y = int(star[1] * k + origin_y)

            # Draw the star (if it is visible in the screen).
            # We calculate the size such that distant stars are smaller than
            # closer stars. Similarly, we make sure that distant stars are
            # darker than closer stars. This is done using Linear Interpolation.
            if 0 <= x < device.width and 0 <= y < device.height:
                size = (1 - float(star[2]) / max_depth) * 4
                if (device.mode == "RGB"):
                    shade = (int(100 + (1 - float(star[2]) / max_depth) * 155),) * 3
                else:
                    shade = "white"
                draw.rectangle((x, y, x + size, y + size), fill=shade)
            draw.text((68,0),"Away",fill="white")

def posn(angle, arm_length):
    dx = int(math.cos(math.radians(angle)) * arm_length)
    dy = int(math.sin(math.radians(angle)) * arm_length)
    return (dx, dy)

def clock():
    now = datetime.datetime.now()
    today_date = now.strftime("%d %b %y")
    today_time = now.strftime("%H:%M:%S")
  
    with canvas(device) as draw:
        now = datetime.datetime.now()
        today_date = now.strftime("%d %b %y")

        margin = 4

        cx = 30
        cy = min(device.height, 64) / 2

        left = cx - cy
        right = cx + cy

        hrs_angle = 270 + (30 * (now.hour + (now.minute / 60.0)))
        hrs = posn(hrs_angle, cy - margin - 7)

        min_angle = 270 + (6 * now.minute)
        mins = posn(min_angle, cy - margin - 2)

        sec_angle = 270 + (6 * now.second)
        secs = posn(sec_angle, cy - margin - 2)

        draw.ellipse((left + margin, margin, right - margin, min(device.height, 64) - margin), outline="white")
        draw.line((cx, cy, cx + hrs[0], cy + hrs[1]), fill="white")
        draw.line((cx, cy, cx + mins[0], cy + mins[1]), fill="white")
        draw.line((cx, cy, cx + secs[0], cy + secs[1]), fill="red")
        draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill="white", outline="white")
        draw.text((2 * (cx + margin), cy - 8), today_date, fill="yellow")
        draw.text((2 * (cx + margin), cy), today_time, fill="yellow")
        
        draw.text((68,0),"Available",fill="white")

def larson_hue(reg):
    with reg:
        delta = (time.time() - start_time)

        # Offset is a sine wave derived from the time delta
        # we use this to animate both the hue and larson scan
        # so they are kept in sync with each other
        offset = (math.sin(delta * SCAN_SPEED) + 1) / 2

        # Use offset to pick the right colour from the hue wheel
        hue = int(round(offset * 360))

        # Now we generate a value from 0 to 7
        offset = int(round(offset * device.width))

        with canvas(device, dither=True) as draw:
            for x in range(device.width):
                sat = 1.0

                val = (device.width - 1) - (abs(offset - x) * FALLOFF)
                val /= (device.width - 1)  # Convert to 0.0 to 1.0
                val = max(val, 0.0)  # Ditch negative values

                xhue = hue  # Grab hue for this pixel
                xhue += (1 - val) * 10  # Use the val offset to give a slight colour trail variation
                xhue %= 360  # Clamp to 0-359
                xhue /= 360.0  # Convert to 0.0 to 1.0

                r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(xhue, sat, val)]
                draw.line((x, 0, x, device.height), fill=(r, g, b, int(val * 255)))
                draw.text((68,0),"Busy",fill="white")

app = None
scope = None

if __name__ == "__main__":
    #setup OLED display
    interface = spi()
    device = sh1106(interface)
    device.rotate = 2
    draw = canvas(device) 
    
    c = Presence()
    x = threading.Thread(target=thread_getPresence, args=(c,))

    scope = ["Presence.Read"]
    endpoint = "https://graph.microsoft.com/beta/me/presence"

    app = msal.PublicClientApplication("cac6bb8f-4b89-4640-96b1-0e403534d7e9", authority="https://login.microsoftonline.com/63eb1bcb-f74f-4703-8243-6f73d78ebf52")

    result = None

    flow = app.initiate_device_flow(scope)

    if "user_code" not in flow:
        raise ValueError("Fail to create device flow. Err: %s" % json.dumps(flow, indent=4))
    
    #print the URL and Code to the console for easier debugging
    print(flow["message"])

    oprint(flow["user_code"])
        
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        oprint("Login failed")
        raise ValueError("logon failed")
    
    #if login succesful start the background presence poll
    x.start()

    max_depth = 32
    stars = init_stars(512, max_depth)

    start_time = time.time()
    regulator = framerate_regulator(fps=10)


    while True:
        # UI Update piece
        if c.value == "Away":
            move_and_draw_stars(stars, max_depth)
        elif c.value == "Available":
            clock()
        elif c.value == "Busy":
            larson_hue(regulator)
        else:
            oprint(c.value)