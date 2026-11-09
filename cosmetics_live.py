"""cosmetics_live.py - Changeling Cosmetics Realtime: makeup, hair colour and beards, live on your webcam.

    run.bat                  the window (the webcam)
    run.bat --phone          your phone's camera instead (a QR code in the window; CopyCat Realtime's phone page)
    run.bat --source me.jpg  a photo or video instead of the webcam (for trying it out)

Every frame: the face is read (BiSeNet on the graphics card, Face Mesh following it), and Changeling Cosmetics'
own looks are painted on (the same code as for photos), then the editor's brightness, contrast, warmth, vignette...
Out to the call through OBS Virtual Camera. It runs in Changeling CopyCat Realtime's environment and uses
Changeling Cosmetics' code: both next to this folder (as in Changeling Studio), or in COPYCAT_REALTIME_DIR and
CHANGELING_COSMETICS_DIR.
"""
import argparse
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import fields

import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
COSMETICS = os.environ.get("CHANGELING_COSMETICS_DIR") or os.path.join(STUDIO, "Changeling-Cosmetics")
COPYCAT = os.environ.get("COPYCAT_REALTIME_DIR") or os.path.join(STUDIO, "Changeling-CopyCat-Realtime")
sys.path.insert(0, COSMETICS)
import torch  # noqa: E402,F401 - first, so onnxruntime and MediaPipe find CUDA's DLLs
from cosmetics.adjust import Adjust  # noqa: E402
from cosmetics.facial_hair import BEARD_COLOURS  # noqa: E402
from cosmetics.live import Live  # noqa: E402
from cosmetics.looks import (BLUSH_COLOURS, BROW_COLOURS, HAIR_COLOURS, LINER_COLOURS, LIP_COLOURS,  # noqa: E402
                             SHADOW_COLOURS, Look)

NAME = "Changeling Cosmetics Realtime"
GITHUB = "https://github.com/CursedPrograms/Changeling-Cosmetics-Realtime"
KOFI = "https://ko-fi.com/cursedentertainment"
PINK = "#e0408a"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".jfif")
# (the Look's part, its name in the window, its colours or None)
PARTS = [("hair", "Hair colour", HAIR_COLOURS), ("lips", "Lips", LIP_COLOURS), ("eyeshadow", "Eyeshadow", SHADOW_COLOURS),
         ("eyeliner", "Eyeliner", LINER_COLOURS), ("blush", "Blush", BLUSH_COLOURS), ("brows", "Brows", BROW_COLOURS),
         ("skin", "Smooth skin", None)]
BEARD = [("beard", "Beard colour", BEARD_COLOURS), ("stubble", "Stubble", BEARD_COLOURS), ("shave", "Shave", None)]
EDITOR = [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation"), ("warmth", "Warmth"),
          ("vignette", "Vignette"), ("sharpen", "Sharpen")]


def set_logo(root):
    ico, png = os.path.join(HERE, "logo.ico"), os.path.join(HERE, "logo.png")

    def apply():
        try:
            if os.name == "nt" and os.path.exists(ico):
                root.iconbitmap(ico)
            elif os.path.exists(png):
                root._logo_icon = tk.PhotoImage(file=png)
                root.iconphoto(True, root._logo_icon)
        except tk.TclError:
            pass
    root.after(300, apply)


def open_source(args):
    """read() -> a BGR frame (or None), as CopyCat Realtime does; --phone serves its phone page."""
    if args.phone:
        sys.path.insert(0, COPYCAT)
        from phone import Phone
        phone = Phone(args.phone_port).start()
        return phone.read, phone
    if args.source and args.source.lower().endswith(IMAGE_EXT):
        still = cv2.imdecode(np.fromfile(args.source, np.uint8), cv2.IMREAD_COLOR)

        def read_still():
            time.sleep(1 / 30)
            return still.copy()
        return read_still, None
    cap = cv2.VideoCapture(args.source) if args.source else cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not args.source:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def read():
        ok, frame = cap.read()
        if not ok and args.source:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok:
            return None
        return frame if args.source else cv2.flip(frame, 1)
    return read, None


class Window:
    def __init__(self, args):
        self.args = args
        self.look = Look()
        self.adjust = Adjust()
        self.read, self.phone = open_source(args)
        self.latest = None
        self.fps = 0.0
        self.found = False
        self.running = True
        self.virtual = None
        self.want_virtual = not args.no_virtual
        self.error = ""

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme(os.path.join(HERE, "theme.json"))
        self.root = ctk.CTk()
        set_logo(self.root)
        self.root.title(NAME)
        self.root.geometry("1320x820")
        self.root.minsize(1000, 640)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<Escape>", lambda e: self.quit())
        self.status.configure(text="Loading the face parser ...")
        threading.Thread(target=self.work, daemon=True, name="worker").start()
        self.root.after(30, self.show)

    # ---- the window
    def _build(self):
        stage = ctk.CTkFrame(self.root, corner_radius=12)
        stage.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=14)
        stage.grid_columnconfigure(0, weight=1)
        stage.grid_rowconfigure(0, weight=1)
        self.view = tk.Label(stage, bg="#16161a", bd=0, fg="gray60", font=("Segoe UI", 13), text="Opening the camera ...")
        self.view.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.view_size = (900, 600)
        self.view.bind("<Configure>", lambda e: setattr(self, "view_size", (max(e.width, 64), max(e.height, 36))))
        self.status = ctk.CTkLabel(stage, text="", text_color="gray60", anchor="w")
        self.status.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        side = ctk.CTkScrollableFrame(self.root, width=320, corner_radius=12)
        side.grid(row=0, column=1, sticky="ns", padx=(7, 14), pady=14)
        logo = os.path.join(HERE, "logo.png")
        if os.path.exists(logo):
            ctk.CTkLabel(side, image=ctk.CTkImage(Image.open(logo), size=(56, 56)), text="").pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(side, text="CHANGELING", text_color="gray55",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(12, 0))
        ctk.CTkLabel(side, text="Cosmetics Realtime", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=PINK).pack(anchor="w", padx=12)
        ctk.CTkLabel(side, text="makeup, hair colour and beards, live on a call", text_color="gray60",
                     wraplength=290, justify="left").pack(anchor="w", padx=12)

        if self.phone is not None:
            self._section(side, "Phone")
            qr = Image.fromarray(self.phone.qr(170))
            ctk.CTkLabel(side, image=ctk.CTkImage(qr, size=(170, 170)), text="").pack(anchor="w", padx=12, pady=4)
            ctk.CTkLabel(side, text=self.phone.url, text_color=("#c2186b", "#f29cc0")).pack(anchor="w", padx=12)

        self._section(side, "Makeup and hair")
        for key, label, colours in PARTS:
            self._part(side, key, label, colours)
        self._section(side, "Facial hair")
        for key, label, colours in BEARD:
            self._part(side, key, label, colours)

        self._section(side, "Editor")
        for key, label in EDITOR:
            lo, hi = Adjust.RANGES[key]
            self._slider(side, label, lo, hi, 0, lambda v, k=key: setattr(self.adjust, k, int(v)))
        ctk.CTkButton(side, text="Reset the editor", fg_color="gray25", hover_color="gray30",
                      command=self.reset_editor).pack(fill="x", padx=12, pady=(6, 0))
        self.editor_sliders = [w for w in side.winfo_children() if isinstance(w, ctk.CTkSlider)][-len(EDITOR):]

        self._section(side, "Out")
        self.virt = ctk.BooleanVar(value=self.want_virtual)
        self.virt_sw = ctk.CTkSwitch(side, text="Virtual camera (OBS)", variable=self.virt,
                                     command=lambda: setattr(self, "want_virtual", self.virt.get()))
        self.virt_sw.pack(anchor="w", padx=12, pady=3)
        self.split = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(side, text="Before | after (preview only)", variable=self.split).pack(anchor="w", padx=12, pady=3)

        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.pack(fill="x", padx=12, pady=(18, 6))
        links = ctk.CTkFrame(foot, fg_color="transparent")
        links.pack(anchor="w")
        for text, url in (("GitHub", GITHUB), ("Ko-fi", KOFI)):
            link = ctk.CTkLabel(links, text=text, text_color=("#c2186b", "#f29cc0"), cursor="hand2")
            link.pack(side="left", padx=(0, 14))
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        ctk.CTkLabel(foot, text="© Cursed Entertainment 2026", text_color="gray45").pack(anchor="w")

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text.upper(), text_color="gray50",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(16, 1))

    def _slider(self, parent, text, lo, hi, value, command, fmt="{}"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(4, 0))
        ctk.CTkLabel(row, text=text).pack(side="left")
        shown = ctk.CTkLabel(row, text=fmt.format(value), text_color="gray60")
        shown.pack(side="right")

        def moved(v):
            shown.configure(text=fmt.format(int(v)))
            command(v)
        s = ctk.CTkSlider(parent, from_=lo, to=hi, number_of_steps=hi - lo, command=moved)
        s.set(value)
        s.pack(fill="x", padx=12, pady=(0, 2))
        s.shown = shown
        return s

    def _part(self, parent, key, label, colours):
        """One part of the look: on / off, its colour, how strong."""
        part = getattr(self.look, key)
        box = ctk.CTkFrame(parent, fg_color="gray17", corner_radius=8)
        box.pack(fill="x", padx=12, pady=3)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 0))
        on = ctk.BooleanVar(value=part.on)
        self.part_vars = getattr(self, "part_vars", {})
        self.part_vars[key] = on
        ctk.CTkSwitch(top, text=label, variable=on, command=lambda: setattr(part, "on", on.get())).pack(side="left")
        if colours:
            names = list(colours)
            current = next((n for n, c in colours.items() if c == part.colour), names[0])
            part.colour = colours[current]
            menu = ctk.CTkOptionMenu(top, values=names, width=120,
                                     command=lambda n: (setattr(part, "colour", colours[n]), setattr(part, "on", True),
                                                        on.set(True)))
            menu.set(current)
            menu.pack(side="right")
            self.part_menus = getattr(self, "part_menus", {})
            self.part_menus[key] = menu
        s = ctk.CTkSlider(box, from_=0, to=100, number_of_steps=100,
                          command=lambda v: setattr(part, "strength", v / 100))
        s.set(int(part.strength * 100))
        s.pack(fill="x", padx=8, pady=(4, 8))

    def reset_editor(self):
        for f in fields(Adjust):
            setattr(self.adjust, f.name, 0)
        for s in self.editor_sliders:
            s.set(0)
            s.shown.configure(text="0")

    # ---- the worker: camera, paint, virtual camera
    def work(self):
        try:
            live = Live()
        except Exception as e:  # noqa: BLE001 - shown in the window
            self.error = f"The face parser didn't load: {e}"
            return
        # two threads, one frame apart: this one reads the face in the next frame while the painter paints the last
        self._slot, self._slot_ready = None, threading.Event()
        threading.Thread(target=self.paint_loop, args=(live,), daemon=True, name="painter").start()
        while self.running:
            frame = self.read()
            if frame is None:
                self.error = "The camera stopped giving pictures."
                time.sleep(0.5)
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._slot = (frame, rgb, live.read(rgb))          # the painter takes the newest one
            self._slot_ready.set()
        if self.virtual is not None:
            self.virtual.close()

    def paint_loop(self, live):
        last = time.monotonic()
        while self.running:
            if not self._slot_ready.wait(0.5):
                continue
            self._slot_ready.clear()
            frame, rgb, face = self._slot
            out = live.paint(rgb, face, self.look, self.adjust)
            self.found = face is not None
            bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
            self._virtual(out)
            if self.phone is not None:
                self.phone.show(bgr)
            self.latest = (frame, bgr)
            now = time.monotonic()
            self.fps = self.fps * 0.9 + 0.1 / max(now - last, 1e-3)
            last = now

    def _virtual(self, rgb):
        if self.want_virtual and self.virtual is None:
            try:
                import pyvirtualcam
                h, w = rgb.shape[:2]
                self.virtual = pyvirtualcam.Camera(width=w, height=h, fps=30)
            except Exception:  # noqa: BLE001 - no OBS: say so, carry on
                self.want_virtual = False
                self.root.after(0, lambda: (self.virt.set(False), self.virt_sw.configure(text="Virtual camera: no OBS")))
        elif not self.want_virtual and self.virtual is not None:
            self.virtual.close()
            self.virtual = None
        if self.virtual is not None:
            if (self.virtual.width, self.virtual.height) == (rgb.shape[1], rgb.shape[0]):
                self.virtual.send(rgb)

    def show(self):
        latest = self.latest
        if latest is not None:
            before, after = latest
            pic = np.hstack([before, after]) if self.split.get() else after
            w, h = self.view_size
            ih, iw = pic.shape[:2]
            k = min(w / iw, h / ih)
            small = cv2.resize(pic, (max(int(iw * k), 1), max(int(ih * k), 1)), interpolation=cv2.INTER_AREA)
            photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
            self.view.configure(image=photo, text="")
            self.view.image = photo
            text = f"{self.fps:.0f} fps" + ("" if self.found else "  ·  no face in view")
            if self.virtual is not None:
                text += "  ·  out to OBS Virtual Camera"
            if self.phone is not None:
                text += "  ·  phone " + ("connected" if self.phone.connected else "not connected: scan the QR code")
            self.status.configure(text=text)
        elif self.error:
            self.status.configure(text=self.error)
        self.root.after(30, self.show)

    def quit(self):
        self.running = False
        self.root.after(150, self.root.destroy)

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=NAME)
    ap.add_argument("--camera", type=int, default=0, help="which webcam (default 0)")
    ap.add_argument("--source", help="a photo or video instead of the webcam")
    ap.add_argument("--phone", action="store_true", help="your phone's camera instead (a QR code in the window)")
    ap.add_argument("--phone-port", type=int, default=8443)
    ap.add_argument("--no-virtual", action="store_true", help="don't send to OBS Virtual Camera")
    Window(ap.parse_args()).run()


if __name__ == "__main__":
    main()
