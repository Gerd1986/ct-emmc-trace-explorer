import csv
import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk, ImageEnhance

EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
def natural_key(path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]

class Explorer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CT eMMC Trace Explorer")
        self.geometry("1250x850")
        self.files = []
        self.index = 0
        self.zoom = 1.0
        self.origin = [0, 0]
        self.traces = {}
        self.signal = tk.StringVar(value="CLK")
        self.mode = tk.StringVar(value="Markieren")
        self.overlay = tk.IntVar(value=0)
        self.threshold = tk.IntVar(value=35)
        self.radius = tk.IntVar(value=14)
        self.last_drag = None
        self.cache = {}
        self.photo = None
        self.build()
        self.bind("<Left>", lambda e: self.step(-1))
        self.bind("<Right>", lambda e: self.step(1))
        self.bind("<Control-s>", lambda e: self.save_project())
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.canvas.bind("<Button-4>", lambda e: self.step(-1))
        self.canvas.bind("<Button-5>", lambda e: self.step(1))
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "last_drag", None))
        self.canvas.bind("<Button-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.pan)

    def build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        for label, action in [("Slices laden", self.load), ("Projekt öffnen", self.open_project),
                              ("Projekt speichern", self.save_project), ("CSV exportieren", self.export_csv),
                              ("Zurück", lambda: self.step(-1)), ("Weiter", lambda: self.step(1)),
                              ("Punkt löschen", self.undo), ("Zoom +", lambda: self.zoom_at(1.25)),
                              ("Zoom -", lambda: self.zoom_at(0.8)), ("Bild einpassen", self.fit_image)]:
            ttk.Button(bar, text=label, command=action).pack(side="left", padx=2)
        opts = ttk.Frame(self)
        opts.pack(fill="x", padx=6)
        ttk.Label(opts, text="Signal:").pack(side="left")
        ttk.Combobox(opts, textvariable=self.signal, width=12,
                     values=["CLK", "CMD"] + [f"DAT{i}" for i in range(8)] + ["VCC", "VCCQ", "GND", "RST_n"]).pack(side="left")
        ttk.Label(opts, text="Modus:").pack(side="left", padx=(12, 0))
        ttk.Combobox(opts, textvariable=self.mode, state="readonly", width=19,
                     values=["Markieren", "Automatisch verfolgen", "Verschieben"]).pack(side="left")
        ttk.Label(opts, text="Overlay %:").pack(side="left", padx=(12, 0))
        ttk.Scale(opts, from_=0, to=90, variable=self.overlay, command=lambda _: self.draw()).pack(side="left")
        ttk.Label(opts, text="Suchradius:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(opts, from_=2, to=80, textvariable=self.radius, width=4).pack(side="left")
        ttk.Label(opts, text="Toleranz:").pack(side="left")
        ttk.Spinbox(opts, from_=1, to=255, textvariable=self.threshold, width=4).pack(side="left")
        self.canvas = tk.Canvas(self, background="#111111", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=6, pady=5)
        self.slice_var = tk.IntVar()
        self.slider = ttk.Scale(bottom, from_=0, to=0, variable=self.slice_var,
                                command=lambda v: self.goto(int(float(v))))
        self.slider.pack(fill="x")
        self.status = ttk.Label(bottom, text="CT-Slices laden, um zu beginnen")
        self.status.pack(anchor="w")

    def load(self):
        folder = filedialog.askdirectory(title="Ordner mit CT-Slices")
        if not folder:
            return
        paths = sorted((p for p in Path(folder).iterdir() if p.suffix.lower() in EXTS), key=natural_key)
        if not paths:
            messagebox.showwarning("Keine Bilder", "Keine unterstützten Bilddateien gefunden.")
            return
        self.files = paths
        self.cache.clear()
        self.index = 0
        self.zoom = 1.0
        self.origin = [0, 0]
        self.slider.configure(to=len(paths)-1)
        self.after_idle(self.fit_image)

    def get_image(self, index):
        if index not in self.cache:
            img = Image.open(self.files[index])
            img.load()
            if img.mode not in ("L", "RGB", "RGBA"):
                arr = np.asarray(img, dtype=np.float32)
                if arr.ndim == 3:
                    arr = arr[..., 0]
                lo, hi = np.percentile(arr, [1, 99.5])
                arr = np.clip((arr-lo)*255/max(hi-lo, 1), 0, 255).astype("uint8")
                img = Image.fromarray(arr, "L")
            self.cache[index] = img.convert("RGB")
            if len(self.cache) > 7:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[index]

    def goto(self, index):
        if not self.files:
            return
        self.index = max(0, min(len(self.files)-1, index))
        self.draw()

    def step(self, n):
        self.goto(self.index+n)

    def zoom_at(self, factor, x=None, y=None):
        if not self.files:
            return
        if x is None:
            x = self.canvas.winfo_width() / 2
        if y is None:
            y = self.canvas.winfo_height() / 2
        previous = self.zoom
        self.zoom = max(0.05, min(20.0, previous * factor))
        scale = self.zoom / previous
        self.origin[0] = x - (x - self.origin[0]) * scale
        self.origin[1] = y - (y - self.origin[1]) * scale
        self.draw()

    def fit_image(self):
        if not self.files:
            return
        w, h = self.get_image(self.index).size
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self.zoom = min(cw / w, ch / h)
        self.origin = [(cw - w*self.zoom)/2, (ch - h*self.zoom)/2]
        self.draw()

    def wheel(self, event):
        if event.state & 0x0004:
            self.zoom_at(1.2 if event.delta > 0 else 1/1.2, event.x, event.y)
        else:
            self.step(-1 if event.delta > 0 else 1)

    def start_pan(self, event):
        self.last_drag = (event.x, event.y)

    def pan(self, event):
        if self.last_drag:
            x, y = self.last_drag
            self.origin[0] += event.x-x
            self.origin[1] += event.y-y
            self.last_drag = (event.x, event.y)
            self.draw()

    def drag(self, event):
        if self.mode.get() == "Verschieben":
            self.pan(event)

    def click(self, event):
        if not self.files:
            return
        if self.mode.get() == "Verschieben":
            self.start_pan(event)
            return
        x = (event.x-self.origin[0])/self.zoom
        y = (event.y-self.origin[1])/self.zoom
        w, h = self.get_image(self.index).size
        if not (0 <= x < w and 0 <= y < h):
            return
        sig = self.signal.get().strip() or "UNNAMED"
        self.traces.setdefault(sig, []).append({"slice": self.index, "x": round(x, 2), "y": round(y, 2), "source": "manual"})
        if self.mode.get() == "Automatisch verfolgen":
            self.follow(sig, x, y)
        self.draw()

    def follow(self, sig, x, y):
        # Local intensity matching is a suggestion, NOT validated electrical continuity.
        base = np.asarray(self.get_image(self.index).convert("L"), dtype=np.float32)
        intensity = float(base[int(y), int(x)])
        previous = (x, y)
        for z in range(self.index+1, min(self.index+16, len(self.files))):
            arr = np.asarray(self.get_image(z).convert("L"), dtype=np.float32)
            cx, cy = previous
            r = max(2, int(self.radius.get()))
            x0, x1 = max(0, int(cx)-r), min(arr.shape[1], int(cx)+r+1)
            y0, y1 = max(0, int(cy)-r), min(arr.shape[0], int(cy)+r+1)
            patch = arr[y0:y1, x0:x1]
            if not patch.size:
                break
            yy, xx = np.mgrid[y0:y1, x0:x1]
            score = np.abs(patch-intensity) + 0.5*np.hypot(xx-cx, yy-cy)
            py, px = np.unravel_index(np.argmin(score), score.shape)
            nx, ny = float(xx[py, px]), float(yy[py, px])
            if abs(float(patch[py, px])-intensity) > int(self.threshold.get()):
                break
            self.traces[sig].append({"slice": z, "x": nx, "y": ny, "source": "suggested"})
            previous = (nx, ny)

    def undo(self):
        sig = self.signal.get()
        if self.traces.get(sig):
            self.traces[sig].pop()
            self.draw()

    def draw(self):
        self.canvas.delete("all")
        if not self.files:
            return
        image = self.get_image(self.index).copy()
        alpha = int(self.overlay.get())/100
        if alpha and self.index+1 < len(self.files):
            other = self.get_image(self.index+1)
            if other.size == image.size:
                image = Image.blend(image, other, alpha)
        w, h = image.size
        scaled = image.resize((max(1, int(w*self.zoom)), max(1, int(h*self.zoom))))
        self.photo = ImageTk.PhotoImage(scaled)
        self.canvas.create_image(*self.origin, image=self.photo, anchor="nw")
        palette = ["#ff4d4d", "#00e5ff", "#ffff55", "#66ff88", "#ff66ff", "#ffaa33"]
        for n, (sig, points) in enumerate(sorted(self.traces.items())):
            color = palette[n % len(palette)]
            current = [p for p in points if p["slice"] == self.index]
            for p in current:
                px = self.origin[0]+p["x"]*self.zoom
                py = self.origin[1]+p["y"]*self.zoom
                self.canvas.create_oval(px-4, py-4, px+4, py+4, outline=color, width=2,
                                        dash=(2, 2) if p["source"] == "suggested" else ())
                self.canvas.create_text(px+7, py-8, text=sig, fill=color, anchor="w")
            for a, b in zip(current, current[1:]):
                self.canvas.create_line(self.origin[0]+a["x"]*self.zoom, self.origin[1]+a["y"]*self.zoom,
                                        self.origin[0]+b["x"]*self.zoom, self.origin[1]+b["y"]*self.zoom,
                                        fill=color, width=2)
        self.slice_var.set(self.index)
        self.status.configure(text=f"Slice {self.index+1}/{len(self.files)} | {self.files[self.index].name} | "
                                   f"Zoom {self.zoom:.2f}x | Punkte {sum(map(len, self.traces.values()))} | "
                                   "Gestrichelt = automatisch vorgeschlagen")

    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            data = {"version": 1, "folder": str(self.files[0].parent) if self.files else "",
                    "files": [p.name for p in self.files], "traces": self.traces}
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        folder = Path(data.get("folder", ""))
        if not folder.is_dir():
            selected = filedialog.askdirectory(title="Ordner der CT-Slices auswählen")
            if not selected:
                return
            folder = Path(selected)
        files = [folder / name for name in data.get("files", [])]
        if not files or not all(p.is_file() for p in files):
            messagebox.showerror("Fehlende Slices", "Nicht alle Bilddateien wurden gefunden.")
            return
        self.files = files
        self.traces = data.get("traces", {})
        self.cache.clear()
        self.index = 0
        self.slider.configure(to=len(files)-1)
        self.draw()

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(["signal", "slice", "x", "y", "source"])
            for sig, points in self.traces.items():
                for p in points:
                    writer.writerow([sig, p["slice"], p["x"], p["y"], p["source"]])

if __name__ == "__main__":
    Explorer().mainloop()
