#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genereert dravezoom.ico uit logo.png."""
import os
from PIL import Image
SIZES=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
def main():
    if os.path.exists("logo.png"):
        im=Image.open("logo.png").convert("RGBA")
        w,h=im.size; s=min(w,h)
        im=im.crop(((w-s)//2,(h-s)//2,(w-s)//2+s,(h-s)//2+s))
        im.save("dravezoom.ico", sizes=SIZES); print("dravezoom.ico geschreven")
    else: print("logo.png niet gevonden")
if __name__=="__main__": main()
