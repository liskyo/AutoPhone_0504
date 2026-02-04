import tkinter as tk
from tkinter import ttk, Toplevel
from PIL import Image, ImageTk
import threading
from config import UI_PREVIEW_WIDTH, UI_PREVIEW_HEIGHT, CAMERA_COUNT

# Dictionary for status colors
STATUS_COLORS = {
    0: "gray",    # Disconnected
    1: "green",   # Ready/Connected
    2: "yellow",  # Capturing
    3: "blue",    # Success/Queued
    4: "red",      # Error
    5: "orange"   # Reviewing
}

class DashboardApp:
    def __init__(self, root, on_snap, on_confirm, on_retake, capture_manager=None):
        self.root = root
        self.root.title("AutoPhote Operator Dashboard")
        self.root.configure(bg="#1e1e1e") # Dark Root
        
        self.capture_manager = capture_manager
        
        self.on_snap_cb = on_snap
        self.on_confirm_cb = on_confirm
        self.on_retake_cb = on_retake
        
        self.cam_labels = []
        self.cam_canvases = []
        self.tk_images = [None] * CAMERA_COUNT 
        self.original_images = [None] * CAMERA_COUNT 
        self.upload_count_var = tk.StringVar(value="Upload Queue: 0")
        self.sn_var = tk.StringVar()
        
        self.setup_theme()
        self.setup_ui()
        self.setup_bindings()

    def setup_theme(self):
        # Tech Colors
        self.colors = {
            "bg": "#1e1e1e",
            "surface": "#2d2d30",
            "accent": "#00adb5", # Cyan
            "text": "#ffffff",
            "text_dim": "#aaaaaa",
            "success": "#28a745",
            "warning": "#ffc107",
            "danger": "#dc3545",
            "border": "#3e3e42"
        }
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # General Defaults
        style.configure(".", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        
        # Notebook (Tabs)
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", 
                        background=self.colors["surface"], 
                        foreground=self.colors["text_dim"], 
                        padding=[20, 10], 
                        font=("Segoe UI", 12, "bold"),
                        borderwidth=0)
        style.map("TNotebook.Tab", 
                  background=[("selected", self.colors["accent"])],
                  foreground=[("selected", "#000000")])
        
        # Frames
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Card.TFrame", background=self.colors["surface"], relief="flat")
        
        # LabelFrames
        style.configure("TLabelframe", background=self.colors["surface"], bordercolor=self.colors["accent"])
        style.configure("TLabelframe.Label", background=self.colors["surface"], foreground=self.colors["accent"], font=("Segoe UI", 11, "bold"))
        
        # Labels
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("Card.TLabel", background=self.colors["surface"], foreground=self.colors["text"])
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground=self.colors["accent"])
        
        # Buttons (using ttk for settings)
        style.configure("TButton", 
                        font=("Segoe UI", 10, "bold"), 
                        background=self.colors["surface"], 
                        foreground=self.colors["text"], 
                        borderwidth=1,
                        focuscolor=self.colors["accent"])
        style.map("TButton", 
                  background=[("active", self.colors["accent"])], 
                  foreground=[("active", "black")])
        
        # Entry
        style.configure("TEntry", fieldbackground=self.colors["surface"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        
    def setup_ui(self):
        # Fullscreen Mode (Aggressive)
        def enforce_fullscreen():
            self.root.attributes('-fullscreen', True)
            self.root.state('zoomed') # Fallback for Windows
            
        self.root.after(100, enforce_fullscreen)
        
        self.root.bind("<F11>", lambda event: self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen")))
        self.root.bind("<Escape>", lambda event: self.root.attributes("-fullscreen", False)) # Escape to exit fullscreen 

        # Main Container
        main_container = tk.Frame(self.root, bg=self.colors["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20) # Add outer margin

        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Monitor
        self.monitor_frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.monitor_frame, text=' MOMITOR (監控) ')
        
        # Tab 2: Settings
        self.settings_frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.settings_frame, text=' SETTINGS (設定) ')

        self.setup_monitor_tab()
        self.setup_settings_tab()

    def setup_monitor_tab(self):
        main_container = self.monitor_frame
        
        # Header Area
        header_frame = tk.Frame(main_container, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, pady=(10, 0), padx=5)
        
        # Monitor Title
        tk.Label(header_frame, text="MONITOR SYSTEM (監控系統)", font=("Segoe UI", 16, "bold"), bg=self.colors["bg"], fg=self.colors["accent"]).pack(side=tk.LEFT, padx=5)
        
        # SN Input
        tk.Label(header_frame, text="SN (機台序號):", font=("Segoe UI", 11, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(20, 5))
        ttk.Entry(header_frame, textvariable=self.sn_var, width=20).pack(side=tk.LEFT, padx=5)

        # Exit Button
        tk.Button(header_frame, text="EXIT (離開程式)", bg="#d9534f", fg="white", font=("Segoe UI", 10, "bold"), 
                 command=self.on_closing).pack(side=tk.RIGHT, padx=5)
        
        # Grid Area - Use a dark frame
        self.grid_frame = tk.Frame(main_container, bg=self.colors["bg"])
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)

        self.grid_frame.columnconfigure(0, weight=1)
        self.grid_frame.columnconfigure(1, weight=1)
        self.grid_frame.columnconfigure(2, weight=1)
        self.grid_frame.rowconfigure(0, weight=1)
        self.grid_frame.rowconfigure(1, weight=1)

        # --- Generate Camera Blocks ---
        for i in range(CAMERA_COUNT):
            row = 0 if i < 3 else 1
            col = i if i < 3 else (i - 3)
            
            # Card style frame
            frame = tk.Frame(self.grid_frame, bg=self.colors["surface"], bd=1, relief="solid")
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            frame.rowconfigure(1, weight=1)
            frame.columnconfigure(0, weight=1)

            # Header
            header_frame = tk.Frame(frame, bg=self.colors["surface"])
            header_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
            
            # Use accent color for CAM ID
            tk.Label(header_frame, text=f"CAM {i+1}", font=("Segoe UI", 12, "bold"), bg=self.colors["surface"], fg=self.colors["accent"]).pack(side=tk.LEFT, padx=5)
            
            # Image Preview (Black bg)
            preview_canvas = tk.Canvas(frame, bg="black", highlightthickness=0, cursor="hand2")
            preview_canvas.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
            
            preview_canvas.bind("<Button-1>", lambda event, idx=i: self.show_enlarged_image(idx))
            preview_canvas.bind("<Configure>", lambda event, idx=i: self.on_canvas_resize(event, idx))
            self.cam_canvases.append(preview_canvas)

            # Status Bar at bottom of card
            status_frame = tk.Frame(frame, bg=self.colors["surface"])
            status_frame.grid(row=2, column=0, sticky="ew", padx=2, pady=5)
            
            lbl_status = tk.Label(status_frame, text="INIT", bg=self.colors["border"], fg="white", font=("Segoe UI", 9, "bold"), width=10)
            lbl_status.pack(side=tk.RIGHT, padx=5)
            self.cam_labels.append(lbl_status)

        # --- Action Panel (Row 1, Col 2) ---
        action_frame = tk.Frame(self.grid_frame, bg=self.colors["surface"], bd=1, relief="solid")
        action_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
        
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        action_frame.rowconfigure(0, weight=0)
        action_frame.rowconfigure(1, weight=1)

        tk.Label(action_frame, text="CONTROL PANEL", font=("Segoe UI", 14, "bold"), bg=self.colors["surface"], fg=self.colors["text"]).grid(row=0, column=0, columnspan=2, pady=15)

        # Flat styling for Control Buttons
        def make_btn(parent, text, bg, cmd, size=18):
            btn = tk.Button(parent, text=text, bg=bg, fg="white", font=("Segoe UI", size, "bold"), 
                            activebackground="white", activeforeground=bg,
                            relief="flat", cursor="hand2", command=cmd)
            return btn

        self.btn_snap = make_btn(action_frame, "START (拍照)", self.colors["accent"], self.handle_snap)
        self.btn_snap.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=20)
        
        self.btn_retake = make_btn(action_frame, "RETAKE (重拍)", self.colors["danger"], self.handle_retake, size=14)
        self.btn_confirm = make_btn(action_frame, "CONFIRM (確認)", self.colors["success"], self.handle_confirm, size=14)
        
        self.btn_retake.grid_remove()
        self.btn_confirm.grid_remove()

        # Info Section
        info_frame = tk.Frame(main_container, bg=self.colors["bg"])
        info_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(info_frame, textvariable=self.upload_count_var, font=("Segoe UI", 11), bg=self.colors["bg"], fg=self.colors["text_dim"]).pack(side=tk.LEFT)
        tk.Label(info_frame, text="Click image to enlarge", font=("Segoe UI", 10, "italic"), bg=self.colors["bg"], fg=self.colors["text_dim"]).pack(side=tk.RIGHT)

    def browse_directory(self, entry):
        from tkinter import filedialog
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def get_sn(self):
        return self.sn_var.get().strip()

    def setup_settings_tab(self):
        import config 
        from config import save_settings, load_settings, CAMERA_IPS, CAMERA_COUNT, CAMERA_WIDTH, CAMERA_HEIGHT, JPEG_QUALITY, LOCAL_TEMP_BUFFER, REMOTE_SERVER_STORAGE

        # Center the settings form - Use pack to fill
        container = tk.Frame(self.settings_frame, bg=self.colors["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=50, pady=30)
        
        # Use a Canvas with Scrollbar for Settings to ensure it works on small screens
        # Create a main scrollable frame
        canvas = tk.Canvas(container, bg=self.colors["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Custom Style for Combobox to ensure visibility
        style = ttk.Style()
        style.configure('Custom.TCombobox', fieldbackground='white', background='white', foreground='black', arrowcolor='black')
        self.root.option_add("*TCombobox*Listbox*Background", "white")
        self.root.option_add("*TCombobox*Listbox*Foreground", "black")

        # Title and Exit Button inside scrollable area
        header_frame = tk.Frame(scrollable_frame, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(header_frame, text="SYSTEM CONFIGURATION (系統設定)", font=("Segoe UI", 18, "bold"), bg=self.colors["bg"], fg=self.colors["accent"]).pack(side=tk.LEFT)
        
        # Exit Button
        tk.Button(header_frame, text="EXIT (離開程式)", bg="#d9534f", fg="white", font=("Segoe UI", 10, "bold"), 
                 command=self.on_closing).pack(side=tk.RIGHT, padx=5)

        # --- Group 1: Camera Parameters (Compact Single Row) ---
        grp_cam = ttk.LabelFrame(scrollable_frame, text=" Camera Parameters (相機參數) ", padding=10)
        grp_cam.pack(fill=tk.X, pady=5)
        
        # Grid layout: Col 0: Label, 1: Input | Col 2: Label, 3: Input | Col 4: Label, 5: Input
        
        # 1. Camera Count
        ttk.Label(grp_cam, text="Count (數量):", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=5)
        self.ent_cam_count = ttk.Entry(grp_cam, width=5)
        self.ent_cam_count.insert(0, str(CAMERA_COUNT))
        self.ent_cam_count.grid(row=0, column=1, sticky="w", padx=5)

        # 2. Resize Ratio
        ttk.Label(grp_cam, text="Resize (縮放 %):", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(20, 5))
        self.resize_var = tk.StringVar()
        self.cbo_resize = ttk.Combobox(grp_cam, textvariable=self.resize_var, width=5, state="readonly", style='Custom.TCombobox')
        resize_options = ["100", "90", "80", "70", "60", "50", "30"]
        self.cbo_resize['values'] = resize_options
        
        from config import RESIZE_RATIO
        # Ensure it's a string for comparison
        target_resize = str(RESIZE_RATIO)
        if target_resize in resize_options:
            self.cbo_resize.set(target_resize)
        else:
            self.cbo_resize.current(2) # Index 2 is "80"
            
        self.cbo_resize.grid(row=0, column=3, sticky="w", padx=5)

        # 3. JPEG Quality
        ttk.Label(grp_cam, text="Quality (品質):", style="Card.TLabel").grid(row=0, column=4, sticky="w", padx=(20, 5))
        self.quality_var = tk.StringVar()
        self.cbo_quality = ttk.Combobox(grp_cam, textvariable=self.quality_var, width=5, state="readonly", style='Custom.TCombobox')
        quality_options = ["100", "95", "90", "85", "80", "75", "70", "50"]
        self.cbo_quality['values'] = quality_options
        
        from config import JPEG_QUALITY
        target_quality = str(JPEG_QUALITY)
        if target_quality in quality_options:
            self.cbo_quality.set(target_quality)
        else:
            self.cbo_quality.current(4) # Index 4 is "80"
            
        self.cbo_quality.grid(row=0, column=5, sticky="w", padx=5)

        # --- Group 2: Paths ---
        grp_path = ttk.LabelFrame(scrollable_frame, text=" Storage Paths ", padding=10)
        grp_path.pack(fill=tk.X, pady=5)
        grp_path.columnconfigure(1, weight=1)

        # Local
        ttk.Label(grp_path, text="Local:", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=5)
        self.ent_local_path = ttk.Entry(grp_path, width=50) # Increased width
        self.ent_local_path.insert(0, LOCAL_TEMP_BUFFER)
        self.ent_local_path.grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(grp_path, text="...", bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold"), relief="flat", width=3,
                 command=lambda: self.browse_directory(self.ent_local_path)).grid(row=0, column=2, padx=5)
        
        # Remote
        ttk.Label(grp_path, text="Remote:", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=5)
        self.ent_remote_path = ttk.Entry(grp_path, width=50) # Increased width
        self.ent_remote_path.insert(0, REMOTE_SERVER_STORAGE)
        self.ent_remote_path.grid(row=1, column=1, sticky="ew", padx=5)
        tk.Button(grp_path, text="...", bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold"), relief="flat", width=3,
                 command=lambda: self.browse_directory(self.ent_remote_path)).grid(row=1, column=2, padx=5)

        # --- Group 3: IP Config (Compact) ---
        grp_ip = ttk.LabelFrame(scrollable_frame, text=" IP Configuration ", padding=10)
        grp_ip.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.ip_entries = {}
        # Simple Grid: 4 columns
        # Cam 1 [___]  Cam 2 [___]
        # Cam 3 [___]  Cam 4 [___]
        
        columns = 4 # 2 sets of (Label + Entry) per row = 4 cols
        for i in range(1, 9):
            row = (i-1) // 2
            col_offset = ((i-1) % 2) * 2
            
            lbl = ttk.Label(grp_ip, text=f"Cam {i}:", style="Card.TLabel")
            lbl.grid(row=row, column=col_offset, padx=(5, 2), pady=5, sticky="e")
            
            ent = ttk.Entry(grp_ip, width=12)
            val = CAMERA_IPS.get(i, "")
            ent.insert(0, val)
            ent.grid(row=row, column=col_offset+1, padx=2, pady=5, sticky="w")
            self.ip_entries[i] = ent

        # --- Actions ---
        btn_frame = tk.Frame(scrollable_frame, bg=self.colors["bg"])
        btn_frame.pack(fill=tk.X, pady=20, side=tk.BOTTOM)
        
        # Make Save button full width (or at least prominent)
        btn_save = tk.Button(btn_frame, text="SAVE SETTINGS (儲存設定)", bg="lightgreen", fg="black", font=("Segoe UI", 12, "bold"), 
                             relief="flat", command=self.save_settings_ui)
        btn_save.pack(fill=tk.X, ipady=10)

    def save_settings_ui(self):
        from config import save_settings
        from tkinter import messagebox
        
        try:
            new_count = int(self.ent_cam_count.get())
            
            # Read Resize and Quality from Dropdowns
            new_resize_ratio = int(self.cbo_resize.get())
            new_quality = int(self.cbo_quality.get())

            new_local = self.ent_local_path.get().strip()
            new_remote = self.ent_remote_path.get().strip()
            
            new_ips = {}
            for i, ent in self.ip_entries.items():
                val = ent.get().strip()
                if val:
                    new_ips[str(i)] = val
            
            # Load Constants for Dimensions (locked)
            from config import CAMERA_WIDTH, CAMERA_HEIGHT

            payload = {
                "camera_count": new_count,
                "camera_width": CAMERA_WIDTH, 
                "camera_height": CAMERA_HEIGHT,
                "resize_ratio": new_resize_ratio,
                "jpeg_quality": new_quality,
                "local_temp_buffer": new_local,
                "remote_server_storage": new_remote,
                "camera_ips": new_ips
            }
            
            success = save_settings(payload)
            if success:
                messagebox.showinfo("Success", "Settings Saved!\n\nPlease restart application.")
            else:
                messagebox.showerror("Error", "Failed to save settings.")
                
        except ValueError:
            messagebox.showerror("Invalid Input", "Please check numeric fields.")

    def setup_bindings(self):
        self.root.bind("<space>", lambda e: self.btn_snap.invoke() if self.btn_snap.winfo_viewable() else None)
        self.root.bind("<Return>", lambda e: self.btn_confirm.invoke() if self.btn_confirm.winfo_viewable() else None)
        self.root.bind("<Escape>", lambda e: self.btn_retake.invoke() if self.btn_retake.winfo_viewable() else None)

    def handle_snap(self):
        try:
            if self.notebook.index("current") != 0: return
        except: pass
        
        # Stop preview before capturing high-res
        if self.capture_manager:
            self.capture_manager.stop_preview()
            
        self.btn_snap.grid_remove()
        self.btn_retake.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=20)
        self.btn_confirm.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=20)
        if self.on_snap_cb: self.on_snap_cb()

    def handle_retake(self):
        try:
            if self.notebook.index("current") != 0: return
        except: pass
        
        self.btn_retake.grid_remove()
        self.btn_confirm.grid_remove()
        self.btn_snap.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=20)
        
        # Resume preview
        if self.capture_manager:
            self.capture_manager.start_preview()
            
        if self.on_retake_cb: self.on_retake_cb()

    def handle_confirm(self):
        try:
            if self.notebook.index("current") != 0: return
        except: pass
        
        self.btn_retake.grid_remove()
        self.btn_confirm.grid_remove()
        self.btn_snap.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=20)
        
        if self.on_confirm_cb: self.on_confirm_cb()

        # Resume preview after confirm action (which saves files)
        if self.capture_manager:
            self.capture_manager.start_preview()

    def update_camera_status(self, index, status_code):
        color_map = {
            0: self.colors["border"],     # OFF
            1: self.colors["success"],    # READY
            2: self.colors["warning"],    # BUSY
            3: self.colors["accent"],     # OK
            4: self.colors["danger"],     # ERR
            5: self.colors["text_dim"]    # REVIEW
        }
        text_map = {0: "OFF", 1: "READY", 2: "BUSY", 3: "OK", 4: "ERR", 5: "REVIEW"}
        
        color = color_map.get(status_code, "white")
        text = text_map.get(status_code, "???")
        # Black text for yellow (BUSY), white for others
        fg_color = "black" if status_code == 2 else "white"
        
        self.root.after(0, lambda: self._set_cam_label(index, text, color, fg_color))

    def _set_cam_label(self, index, text, bg_color, fg_color):
        if 0 <= index < len(self.cam_labels):
            self.cam_labels[index].config(text=text, bg=bg_color, fg=fg_color) 

    def update_camera_image(self, index, pil_image):
        self.root.after(0, lambda: self._set_cam_image(index, pil_image))

    def _set_cam_image(self, index, pil_image):
        if 0 <= index < len(self.cam_canvases):
            self.original_images[index] = pil_image
            self._redraw_canvas(index)

    def on_canvas_resize(self, event, index):
        self._redraw_canvas(index)

    def _redraw_canvas(self, index):
        canvas = self.cam_canvases[index]
        img_pil = self.original_images[index]
        if img_pil is None: return
        
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 2 or ch < 2: return 

        img_w, img_h = img_pil.size
        ratio = min(cw/img_w, ch/img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        
        if new_w <= 1 or new_h <= 1:
            return # Canvas not ready

        resized = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        
        self.tk_images[index] = tk_img
        canvas.delete("all")
        canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=tk_img)

    def show_enlarged_image(self, index):
        if index < 0 or index >= len(self.original_images) or self.original_images[index] is None: return
        top = Toplevel(self.root, bg="black")
        top.attributes('-fullscreen', True)
        img = self.original_images[index]
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        ratio = min(screen_w/img.size[0], screen_h/img.size[1])
        new_w = max(1, int(img.size[0]*ratio))
        new_h = max(1, int(img.size[1]*ratio))
        new_size = (new_w, new_h)
        tk_img = ImageTk.PhotoImage(img.resize(new_size, Image.Resampling.LANCZOS))
        lbl = tk.Label(top, image=tk_img, bg="black")
        lbl.image = tk_img
        lbl.pack(expand=True) 
        top.bind("<Button-1>", lambda e: top.destroy())
        top.bind("<Escape>", lambda e: top.destroy())

    def update_upload_count(self, count):
        self.root.after(0, lambda: self.upload_count_var.set(f"Upload Queue: {count}"))

    def on_closing(self):
        """Handle application exit."""
        if self.capture_manager:
            self.capture_manager.stop_preview()
        self.root.destroy()
