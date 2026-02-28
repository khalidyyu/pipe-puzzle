import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import os
import ast
import json
import time
import random
from constants import pipe_symbol, DIR_SYMBOLS, pipe_image_info, UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
from leaderboard import Leaderboard
from level_solver import solve_level, solve_step1_deductive, solve_step2_assumption, solve_step3_search

def get_config_dir():
    """获取配置文件存储目录。
    
    Returns:
        str: 配置文件目录路径
    """
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'PipePuzzle')
    else:  # Linux/Mac
        config_dir = os.path.expanduser('~/.config/pipepuzzle')
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    return config_dir

def get_settings_path():
    """获取设置文件路径。
    
    Returns:
        str: 设置文件的完整路径
    """
    return os.path.join(get_config_dir(), 'settings.json')

def get_available_font(font_list):
    """检测系统中可用的字体，返回第一个可用的字体。
    
    Args:
        font_list: 字体列表，按优先级排序
        
    Returns:
        str: 第一个可用的字体，如果都不可用则返回默认字体
    """
    root = tk.Tk()
    available_fonts = set(root.tk.call("font", "families"))
    root.destroy()
    
    for font in font_list:
        if font in available_fonts:
            return font
    return "Arial"  # 默认字体

# 定义中文字体
CHINESE_FONT_NORMAL = get_available_font(["微软雅黑", "黑体", "宋体", "SimHei", "Microsoft YaHei"])
CHINESE_FONT_BOLD = get_available_font(["微软雅黑", "黑体", "宋体", "SimHei", "Microsoft YaHei"])
CHINESE_FONT_MONO = get_available_font(["黑体", "宋体", "微软雅黑", "SimHei", "SimSun", "Microsoft YaHei"])

class PipeUI:
    """基于 tkinter 的可视化界面"""
    def __init__(self, master, game_state, restart_callback=None, exit_callback=None, size_change_callback=None, level_import_callback=None):
        """初始化用户界面。
        
        Args:
            master: tkinter 根窗口
            game_state: GameState 实例，包含游戏状态
            restart_callback: 再来一局按钮的回调函数
            exit_callback: 退出游戏按钮的回调函数
            size_change_callback: 棋盘大小改变的回调函数
            level_import_callback: 导入关卡按钮的回调函数
        """
        self.master = master
        self.game = game_state
        self.restart_callback = restart_callback
        self.exit_callback = exit_callback
        self.size_change_callback = size_change_callback
        self.level_import_callback = level_import_callback
        self.leaderboard = Leaderboard()
        self.save_status = ""
        self.cell_size = 65
        self.scroll_offset = 0
        self.min_cell_size = 20
        self.max_cell_size = 140
        self.is_valid = True
        
        self.show_cycles = True
        self.show_closed_paths = True
        self.show_grid_coordinates = False  # 默认不显示网格坐标
        self.allow_custom_level_leaderboard = False  # 默认不允许导入关卡参与排行榜
        self.allow_solver_leaderboard = False  # 默认不允许使用求解器的关卡参与排行榜
        self.allow_generated_level_leaderboard = False  # 默认不允许生成的关卡参与排行榜
        self.shuffle_after_generation = False  # 默认生成后不打乱顺序
        self.first_launch = True  # 默认为首次启动
        
        self.style = ttk.Style()
        self.style.configure("Gray.Horizontal.TScale", troughcolor="#EF0202")
        self.generation_speed = 100  # 生成速度（毫秒），默认100ms
        
        # 生成动画状态
        self.generating = False  # 是否正在生成
        self.generator = None  # 生成器实例
        self.generation_start = None  # 水源位置
        self.generation_start_openings = None  # 水源开口
        self.checking_leaf = None  # 正在检查的叶子节点
        self.pending_leaves = []  # 待检查的叶子节点列表
        self.generated_grid = None  # 保存动画生成的最终棋盘
        self.generation_info_timer = None  # 生成信息清除定时器
        self.generation_animation_timer = None  # 生成动画定时器
        self.warning_label_timer = None  # warning_label清除定时器
        
        # 动画状态
        self.deductive_animating = False  # 演绎推理动画状态
        self.deductive_solver = None  # 演绎推理求解器
        self.deductive_animation_timer = None  # 演绎推理动画定时器
        self.start_assumption_after_deductive = False  # 演绎推理完成后启动假设推理
        
        self.assumption_animating = False  # 假设推理动画状态
        self.assumption_solver = None  # 假设推理求解器
        self.assumption_animation_timer = None  # 假设推理动画定时器
        
        self.search_animating = False  # 搜索求解动画状态
        self.search_solver = None  # 搜索求解求解器
        self.search_animation_timer = None  # 搜索求解动画定时器
        
        # 初始化生成速度变量
        self.generation_speed_var = tk.IntVar(value=self.generation_speed)
        
        self.load_settings()
        
        main_frame = ttk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.menu_frame = ttk.Frame(main_frame, width=200)
        self.menu_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        self.menu_frame.pack_propagate(False)
        
        ttk.Label(self.menu_frame, text="棋盘大小选择", font=(CHINESE_FONT_BOLD, 18, "bold"), bootstyle=PRIMARY).pack(pady=(10, 10), padx=15)
        
        sizes = [(5, 5), (7, 7), (11, 11), (15, 15), (21, 21)]
        for rows, cols in sizes:
            btn = ttk.Button(self.menu_frame, text=f"{rows}x{cols}", 
                          command=lambda r=rows, c=cols: self.on_size_change(r, c),
                          width=12, bootstyle=SECONDARY)
            btn.pack(pady=2, padx=15)
        
        custom_frame = ttk.Frame(self.menu_frame)
        custom_frame.pack(pady=5, padx=15)
        
        ttk.Label(custom_frame, text="长").grid(row=0, column=0, padx=2)
        self.custom_rows = ttk.Entry(custom_frame, width=8)
        self.custom_rows.grid(row=0, column=1, padx=2)
        
        ttk.Label(custom_frame, text="宽").grid(row=1, column=0, padx=2)
        self.custom_cols = ttk.Entry(custom_frame, width=8)
        self.custom_cols.grid(row=1, column=1, padx=2)
        
        custom_btn = ttk.Button(self.menu_frame, text="自定义", command=self.on_custom_size, width=12, bootstyle=SECONDARY)
        custom_btn.pack(pady=5, padx=15)
        
        import_btn = ttk.Button(self.menu_frame, text="导入关卡", command=self.on_import_level, width=12, bootstyle=SUCCESS)
        import_btn.pack(pady=5, padx=15)
        
        export_btn = ttk.Button(self.menu_frame, text="导出关卡", command=self.on_export_level, width=12, bootstyle=PRIMARY)
        export_btn.pack(pady=5, padx=15)
        
        self.warning_label = ttk.Label(self.menu_frame, text="", font=(CHINESE_FONT_NORMAL, 13), bootstyle=DANGER, wraplength=200)
        self.warning_label.pack(pady=2, padx=5)
        
        ttk.Label(self.menu_frame, text="算法演示", font=(CHINESE_FONT_BOLD, 18, "bold"), bootstyle=PRIMARY).pack(pady=(15, 5), padx=15)
        
        algorithm_btn1 = ttk.Button(self.menu_frame, text="地图生成", command=self.on_generate_level, width=12, bootstyle=INFO)
        algorithm_btn1.pack(pady=2, padx=15)
        
        algorithm_btn2 = ttk.Button(self.menu_frame, text="演绎推理", command=lambda: self.on_solve_step(1), width=12, bootstyle=INFO)
        algorithm_btn2.pack(pady=2, padx=15)
        
        algorithm_btn3 = ttk.Button(self.menu_frame, text="假设推理", command=lambda: self.on_solve_step(2), width=12, bootstyle=INFO)
        algorithm_btn3.pack(pady=2, padx=15)
        
        algorithm_btn4 = ttk.Button(self.menu_frame, text="搜索求解", command=lambda: self.on_solve_step(3), width=12, bootstyle=INFO)
        algorithm_btn4.pack(pady=2, padx=15)
        
        ttk.Label(self.menu_frame, text="排行榜", font=(CHINESE_FONT_BOLD, 18, "bold"), bootstyle=PRIMARY).pack(pady=(15, 5), padx=15)
        
        leaderboard_btn = ttk.Button(self.menu_frame, text="查看排行榜", command=self.show_leaderboard, width=12, bootstyle=WARNING)
        leaderboard_btn.pack(pady=2, padx=15)
        
        game_frame = ttk.Frame(main_frame)
        game_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.top_frame = ttk.Frame(game_frame)
        self.top_frame.pack(pady=5, fill=tk.X)
        
        solve_btn = ttk.Button(self.top_frame, text="一键求解", command=self.on_solve_level, width=9, bootstyle=SUCCESS)
        solve_btn.pack(side=tk.LEFT, padx=10)
        
        solve_menubtn = ttk.Menubutton(self.top_frame, text="分步求解", width=7, bootstyle=SUCCESS)
        solve_menubtn.pack(side=tk.LEFT, padx=0)
        
        solve_menu = tk.Menu(solve_menubtn, tearoff=0)
        solve_menu.add_command(label="演绎推理", command=self.on_deductive_no_animation, font=(CHINESE_FONT_NORMAL, 13))
        solve_menu.add_command(label="假设推理", command=self.on_assumption_no_animation, font=(CHINESE_FONT_NORMAL, 13))
        solve_menu.add_command(label="搜索求解", command=self.on_search_no_animation, font=(CHINESE_FONT_NORMAL, 13))
        solve_menubtn.config(menu=solve_menu)
        
        self.timer_label = ttk.Label(self.top_frame, text="时间: 0.0 秒", font=(CHINESE_FONT_NORMAL, 20), bootstyle=INFO)
        self.timer_label.pack(side=tk.LEFT, expand=True)
        
        settings_menubtn = ttk.Menubutton(self.top_frame, text="设置", width=4)
        settings_menubtn.pack(side=tk.RIGHT, padx=(0, 10))
        
        info_canvas = tk.Canvas(self.top_frame, width=20, height=20, highlightthickness=0, bg=self.master.cget('bg'))
        info_canvas.pack(side=tk.RIGHT, padx=(0, 5))
        info_canvas.create_oval(2, 2, 18, 18, outline="#17a2b8", width=2)
        info_canvas.create_text(10, 10, text="i", font=(CHINESE_FONT_BOLD, 12, "bold"), fill="#17a2b8")
        info_canvas.bind("<Button-1>", lambda e: self.show_game_intro())
        info_canvas.bind("<Enter>", lambda e: info_canvas.config(cursor="hand2"))
        info_canvas.bind("<Leave>", lambda e: info_canvas.config(cursor=""))
        
        settings_menu = tk.Menu(settings_menubtn, tearoff=0)
        self.settings_menu = settings_menu
        self.settings_menubtn = settings_menubtn
        
        self.generation_info_label = ttk.Label(game_frame, text="", font=(CHINESE_FONT_NORMAL, 18), bootstyle=INFO)
        self.generation_info_label.place(relx=0.5, y=60, anchor='center')
        
        self.show_grid_coordinates_var = tk.BooleanVar(value=self.show_grid_coordinates)
        settings_menu.add_checkbutton(label="显示网格坐标", variable=self.show_grid_coordinates_var, command=lambda: self.on_setting_change('show_grid_coordinates', self.show_grid_coordinates_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.show_cycles_var = tk.BooleanVar(value=self.show_cycles)
        settings_menu.add_checkbutton(label="显示环路", variable=self.show_cycles_var, command=lambda: self.on_setting_change('show_cycles', self.show_cycles_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.show_closed_paths_var = tk.BooleanVar(value=self.show_closed_paths)
        settings_menu.add_checkbutton(label="显示闭路", variable=self.show_closed_paths_var, command=lambda: self.on_setting_change('show_closed_paths', self.show_closed_paths_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.allow_custom_level_var = tk.BooleanVar(value=self.allow_custom_level_leaderboard)
        settings_menu.add_checkbutton(label="允许导入的关卡参与排行榜", variable=self.allow_custom_level_var, command=lambda: self.on_setting_change('allow_custom_level_leaderboard', self.allow_custom_level_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.allow_solver_var = tk.BooleanVar(value=self.allow_solver_leaderboard)
        settings_menu.add_checkbutton(label="允许使用求解器参与排行榜", variable=self.allow_solver_var, command=lambda: self.on_setting_change('allow_solver_leaderboard', self.allow_solver_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.allow_generated_level_var = tk.BooleanVar(value=self.allow_generated_level_leaderboard)
        settings_menu.add_checkbutton(label="允许生成的关卡参与排行榜", variable=self.allow_generated_level_var, command=lambda: self.on_setting_change('allow_generated_level_leaderboard', self.allow_generated_level_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        self.shuffle_after_generation_var = tk.BooleanVar(value=self.shuffle_after_generation)
        settings_menu.add_checkbutton(label="生成动画结束后打乱顺序", variable=self.shuffle_after_generation_var, command=lambda: self.on_setting_change('shuffle_after_generation', self.shuffle_after_generation_var.get()), font=(CHINESE_FONT_NORMAL, 13))
        
        settings_menubtn.config(menu=settings_menu)
        
        speed_frame = ttk.Frame(self.top_frame)
        speed_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        ttk.Label(speed_frame, text="动画速度:", font=(CHINESE_FONT_NORMAL, 13)).pack(side=tk.LEFT, padx=2)
        
        def speed_to_slider(speed):
            """将速度(10-1000ms)转换为滑块值(0-100)，对数映射"""
            import math
            if speed <= 10:
                return 0
            return min(100, max(0, int((math.log10(speed) - 1) * 100 / 2)))
        
        def slider_to_speed(slider_val):
            """将滑块值(0-100)转换为速度(10-1000ms)，对数映射"""
            return max(10, min(1000, round(10 ** (slider_val / 100 * 2 + 1))))
        
        self.speed_slider_var = tk.IntVar(value=speed_to_slider(self.generation_speed))
        self.speed_slider = tk.Scale(
            speed_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.speed_slider_var,
            length=80,
            highlightthickness=0,
            relief='flat',
            bd=0,
            sliderlength=20,
            command=lambda v: self.on_speed_slider_change(int(float(v)), slider_to_speed)
        )
        self.speed_slider.pack(side=tk.LEFT)
        
        self.speed_slider.configure(troughcolor="#EAEAEA")
        
        self.speed_label = ttk.Label(speed_frame, text=f"{self.generation_speed}ms", font=(CHINESE_FONT_NORMAL, 13), width=6)
        self.speed_label.pack(side=tk.LEFT)
        
        self.slider_to_speed = slider_to_speed
        
        self.canvas = tk.Canvas(
            game_frame,
            width=self.game.cols * self.cell_size,
            height=self.game.rows * self.cell_size,
            bg='white'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.base_images = {}
        self.rotated_images = {}
        self.animating = False
        self.animation_cell = None
        self.animating_cells = {}  # 存储正在动画的格子 {(r,c): animation_state}
        self.rotation_queue = {}  # 存储每个格子的待处理旋转次数 {(r,c): count}
        self.lock_queue = {}  # 存储每个格子的待处理锁定操作 {(r,c): should_lock}
        self.animation_angle = 0
        self.animation_steps = 0
        self.animation_total_steps = 12
        self.animation_image_cache = {}
        self.cell_tags = {}
        
        # 演绎推理动画状态
        self.deductive_animating = False
        self.deductive_solver = None
        self.deductive_animation_timer = None
        
        self.load_pipe_images()

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        self.update_timer()
        
        self.master.after(100, self.draw_grid)
        
        # 首次启动时显示游戏介绍
        if self.first_launch:
            self.master.after(500, self._show_first_launch_intro)
    
    def _show_first_launch_intro(self):
        """首次启动时显示游戏介绍，并标记为非首次启动。"""
        self.show_game_intro()
        self.first_launch = False
        self.save_settings()

    def on_canvas_resize(self, event):
        """处理画布大小变化事件。
        
        Args:
            event: 画布配置事件
        """
        try:
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self.draw_grid()
        except Exception:
            pass

    def load_pipe_images(self):
        """加载所有管道图片（普通和充水版本）到内存中。"""
        image_dir = os.path.join(os.path.dirname(__file__), 'images')
        base_types = ['end', 'straight', 'corner', 't']
        
        for base_type in base_types:
            filename = f'pipe_{base_type}.png'
            filepath = os.path.join(image_dir, filename)
            try:
                img = Image.open(filepath)
                self.base_images[base_type] = img
            except Exception as e:
                print(f"无法加载图片 {filename}: {e}")
                self.base_images[base_type] = None
            
            water_filename = f'pipe_{base_type}_water.png'
            water_filepath = os.path.join(image_dir, water_filename)
            try:
                water_img = Image.open(water_filepath)
                self.base_images[f'{base_type}_water'] = water_img
            except Exception as e:
                print(f"无法加载图片 {water_filename}: {e}")
                self.base_images[f'{base_type}_water'] = None
            
            red_filename = f'pipe_{base_type}_red.png'
            red_filepath = os.path.join(image_dir, red_filename)
            try:
                red_img = Image.open(red_filepath)
                self.base_images[f'{base_type}_red'] = red_img
            except Exception as e:
                print(f"无法加载图片 {red_filename}: {e}")
                self.base_images[f'{base_type}_red'] = None
            
            red_water_filename = f'pipe_{base_type}_water_red.png'
            red_water_filepath = os.path.join(image_dir, red_water_filename)
            try:
                red_water_img = Image.open(red_water_filepath)
                self.base_images[f'{base_type}_water_red'] = red_water_img
            except Exception as e:
                print(f"无法加载图片 {red_water_filename}: {e}")
                self.base_images[f'{base_type}_water_red'] = None

    def get_rotated_image(self, base_type, angle):
        """获取旋转后的图片，使用缓存避免重复旋转。
        
        Args:
            base_type: 管道类型（'end', 'straight', 'corner', 't' 或 '_water'后缀）
            angle: 旋转角度（0, 90, 180, 270）
            
        Returns:
            ImageTk.PhotoImage: 旋转后的图片对象，失败返回None
        """
        key = (base_type, angle, self.cell_size)
        if key in self.rotated_images:
            return self.rotated_images[key]
        
        if self.base_images.get(base_type) is None:
            return None
        
        try:
            resized = self.base_images[base_type].resize((self.cell_size - 1, self.cell_size - 1), Image.Resampling.LANCZOS)
            rotated = resized.rotate(-angle, expand=False)
            self.rotated_images[key] = ImageTk.PhotoImage(rotated)
            return self.rotated_images[key]
        except Exception as e:
            print(f"旋转图片失败 {base_type} {angle}: {e}")
            return None

    def draw_grid(self):
        """绘制整个游戏网格，包括管道、锁定状态和充水状态。"""
        try:
            self.canvas.delete("all")
        except Exception:
            return
        water = self.game.calculate_water_flow()
        water_cycles, dry_cycles = self.game.detect_cycles(water)
        closed_components = self.game.detect_closed_paths(water)
        
        closed_paths = [[False] * self.game.cols for _ in range(self.game.rows)]
        for component in closed_components:
            for r, c in component:
                closed_paths[r][c] = True
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if canvas_width > 1:
            board_aspect_ratio = self.game.rows / self.game.cols
            
            if 0.8 <= board_aspect_ratio <= 1.25:
                cell_size_by_width = (canvas_width - coord_left_space) // self.game.cols
                cell_size_by_height = (canvas_height - coord_top_space - coord_bottom_space) // self.game.rows
                self.cell_size = max(self.min_cell_size, min(self.max_cell_size, min(cell_size_by_width, cell_size_by_height)))
            else:
                self.cell_size = max(self.min_cell_size, min(self.max_cell_size, (canvas_width - coord_left_space) // self.game.cols))
        
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        board_aspect_ratio = self.game.rows / self.game.cols
        
        if 0.8 <= board_aspect_ratio <= 1.25:
            h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        else:
            if board_width >= canvas_width:
                h_offset = 0
            else:
                h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        # 绘制列号（在每一列的上方）
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for c in range(self.game.cols):
                x = c * self.cell_size + h_offset + self.cell_size // 2
                y = v_offset - 15
                self.canvas.create_text(
                    x, y,
                    text=str(c),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        # 绘制行号（在每一行的左边）
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for r in range(self.game.rows):
                x = h_offset - 15
                y = r * self.cell_size - self.scroll_offset + v_offset + self.cell_size // 2
                self.canvas.create_text(
                    x, y,
                    text=str(r),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x1 = c * self.cell_size + h_offset
                y1 = r * self.cell_size - self.scroll_offset + v_offset
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                bg_color = '#D3D3D3' if self.game.locked[r][c] else 'white'
                self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill=bg_color)

                openings = self.game.grid[r][c]
                
                # 如果正在生成且格子没有开口，显示灰色背景
                if self.generating and not openings:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='#7A7A7A')
                    continue
                
                # 绘制生成过程中的叶子节点背景（在水管图片之前绘制）
                if self.generating:
                    if (r, c) == self.checking_leaf:
                        # 正在检查的叶子节点：红色背景
                        self.canvas.create_rectangle(
                            x1+1, y1+1, x2-1, y2-1, fill="#FFC9C9", outline="#FF0000", width=3
                        )
                    elif (r, c) in self.pending_leaves:
                        # 待检查的叶子节点：黄色背景
                        self.canvas.create_rectangle(
                            x1+1, y1+1, x2-1, y2-1, fill="#FFFFB7", outline="#FFD606", width=3
                        )
                
                base_type, angle = pipe_image_info(openings)
                
                if water[r][c]:
                    if self.show_cycles and water_cycles[r][c]:
                        image_type = f'{base_type}_water_red'
                    else:
                        image_type = f'{base_type}_water'
                else:
                    if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                        image_type = f'{base_type}_red'
                    else:
                        image_type = base_type
                
                rotated_image = self.get_rotated_image(image_type, angle)
                
                if rotated_image:
                    self.canvas.create_image(
                        (x1 + x2) // 2, (y1 + y2) // 2,
                        image=rotated_image
                    )
                else:
                    symbol = pipe_symbol(openings)
                    self.canvas.create_text(
                        (x1 + x2) // 2, (y1 + y2) // 2,
                        text=symbol, font=("Courier", 24), fill='black'
                    )

                if (r, c) == self.game.start:
                    self.canvas.create_rectangle(
                        x1+2, y1+2, x2-2, y2-2, outline='blue', width=3
                    )

        if self.game.victory:
            elapsed_time = self.game.get_elapsed_time()
            
            text1 = f"🎉 胜利！用时: {elapsed_time:.2f}秒 🎉"
            self.canvas.create_rectangle(
                canvas_width // 2 - 240, 5, canvas_width // 2 + 240, 55,
                fill='white', outline='white', width=1
            )
            self.canvas.create_text(
                canvas_width // 2, 30,
                text=text1,
                font=(CHINESE_FONT_BOLD, 26, "bold"),
                fill='green',
                anchor='center'
            )
            
            board_size = f"{self.game.rows}x{self.game.cols}"
            if board_size in ["5x5", "7x7", "11x11", "15x15", "21x21"]:
                if self.save_status:
                    self.canvas.create_rectangle(
                        canvas_width // 2 - 240, 55, canvas_width // 2 + 240, 85,
                        fill='white', outline='white', width=1
                    )
                    self.canvas.create_text(
                        canvas_width // 2, 67,
                        text=self.save_status,
                        font=(CHINESE_FONT_NORMAL, 14),
                        fill='green',
                        anchor='center'
                    )
            
            btn_y = 90
            btn_width = 120
            btn_height = 40
            btn_spacing = 20
            
            restart_x = canvas_width // 2 - btn_width - btn_spacing // 2
            exit_x = canvas_width // 2 + btn_spacing // 2
            
            self.canvas.create_rectangle(
                restart_x, btn_y, restart_x + btn_width, btn_y + btn_height,
                fill='#4CAF50', outline='#388E3C', width=2,
                tags='restart_btn'
            )
            self.canvas.create_text(
                restart_x + btn_width // 2, btn_y + btn_height // 2,
                text="再来一局", fill='white', font=(CHINESE_FONT_BOLD, 16, "bold"),
                tags='restart_btn'
            )
            
            self.canvas.create_rectangle(
                exit_x, btn_y, exit_x + btn_width, btn_y + btn_height,
                fill='#F44336', outline='#D32F2F', width=2,
                tags='exit_btn'
            )
            self.canvas.create_text(
                exit_x + btn_width // 2, btn_y + btn_height // 2,
                text="退出游戏", fill='white', font=(CHINESE_FONT_BOLD, 16, "bold"),
                tags='exit_btn'
            )

    def update_timer(self):
        """更新计时器显示，每100毫秒调用一次。"""
        if not self.is_valid:
            return
        if not self.game.victory:
            elapsed_time = self.game.get_elapsed_time()
            try:
                self.timer_label.config(text=f"时间: {elapsed_time:.1f} 秒")
                self.master.after(100, self.update_timer)
            except tk.TclError:
                self.is_valid = False

    def on_restart(self):
        """处理再来一局按钮点击事件。"""
        if self.generating:
            return  # 正在生成中，不允许重启
        
        if self.restart_callback:
            self.restart_callback()

    def on_exit(self):
        """处理退出游戏按钮点击事件。"""
        if self.generating:
            return  # 正在生成中，不允许退出
        
        if self.exit_callback:
            self.exit_callback()
        else:
            self.master.quit()

    def on_click(self, event):
        """处理鼠标左键点击事件，旋转管道或点击胜利按钮。
        
        Args:
            event: 鼠标点击事件，包含坐标信息
        """
        if self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            return
        
        if self.game.victory:
            canvas_width = self.canvas.winfo_width()
            btn_y = 70
            btn_width = 120
            btn_height = 40
            btn_spacing = 20
            
            restart_x = canvas_width // 2 - btn_width - btn_spacing // 2
            exit_x = canvas_width // 2 + btn_spacing // 2
            
            if restart_x <= event.x <= restart_x + btn_width and btn_y <= event.y <= btn_y + btn_height:
                self.on_restart()
            elif exit_x <= event.x <= exit_x + btn_width and btn_y <= event.y <= btn_y + btn_height:
                self.on_exit()
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_width >= canvas_width:
            h_offset = 0
        else:
            h_offset = (canvas_width - board_width) // 2
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        c = (event.x - h_offset) // self.cell_size
        r = (event.y + self.scroll_offset - v_offset) // self.cell_size
        if 0 <= r < self.game.rows and 0 <= c < self.game.cols:
            self.start_rotation_animation(r, c)

    def on_right_click(self, event):
        """处理鼠标右键点击事件，切换锁定状态。
        
        Args:
            event: 鼠标点击事件，包含坐标信息
        """
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_width >= canvas_width:
            h_offset = 0
        else:
            h_offset = (canvas_width - board_width) // 2
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        c = (event.x - h_offset) // self.cell_size
        r = (event.y + self.scroll_offset - v_offset) // self.cell_size
        if 0 <= r < self.game.rows and 0 <= c < self.game.cols:
            # 如果格子正在动画中，将锁定操作添加到队列
            if (r, c) in self.animating_cells:
                # 锁定队列存储目标锁定状态（True表示锁定，False表示解锁）
                self.lock_queue[(r, c)] = not self.game.locked[r][c]
            else:
                self.game.toggle_lock(r, c)
                self.draw_grid()

    def start_rotation_animation(self, r, c):
        """启动旋转动画，支持多格子同时旋转和同一格子依次旋转。
        
        Args:
            r: 行索引
            c: 列索引
        """
        if self.game.locked[r][c]:
            return
        
        # 如果该格子已经在动画中，将旋转次数添加到队列
        if (r, c) in self.animating_cells:
            self.rotation_queue[(r, c)] = self.rotation_queue.get((r, c), 0) + 1
            return
        
        # 启动动画
        self.animating = True
        
        # 计算水流和状态
        water = self.game.calculate_water_flow()
        water_cycles, dry_cycles = self.game.detect_cycles(water)
        closed_components = self.game.detect_closed_paths(water)
        
        closed_paths = [[False] * self.game.cols for _ in range(self.game.rows)]
        for component in closed_components:
            for cr, cc in component:
                closed_paths[cr][cc] = True
        
        # 存储该格子的动画状态
        self.animating_cells[(r, c)] = {
            'steps': 0,
            'angle': 0,
            'water': water[r][c],
            'water_cycle': water_cycles[r][c],
            'dry_cycle': dry_cycles[r][c],
            'closed_path': closed_paths[r][c],
            'grid_drawn': False  # 标记该格子是否已绘制网格
        }
        
        # 如果这是第一个动画格子，开始动画循环
        if len(self.animating_cells) == 1:
            self.animate_rotation()
    
    def animate_rotation(self):
        """执行旋转动画的每一帧，支持多格子同时旋转和同一格子依次旋转。"""
        if not self.animating or not self.animating_cells:
            return
        
        # 更新所有动画格子
        finished_cells = []
        for (r, c), state in self.animating_cells.items():
            state['steps'] += 1
            
            # 如果是第一步且该格子还未绘制网格，绘制动画网格
            if state['steps'] == 1 and not state['grid_drawn']:
                self.draw_grid_for_animation(r, c)
                state['grid_drawn'] = True
            
            # 如果动画完成
            if state['steps'] > self.animation_total_steps:
                finished_cells.append((r, c))
                self.game.rotate_cell(r, c)
            else:
                # 更新当前格子的动画
                current_angle = state['steps'] * (90 / self.animation_total_steps)
                self.update_animation_cell(r, c, current_angle, state)
        
        # 处理已完成的格子
        for r, c in finished_cells:
            del self.animating_cells[(r, c)]
            
            # 检查队列中是否还有待处理的旋转
            if (r, c) in self.rotation_queue and self.rotation_queue[(r, c)] > 0:
                self.rotation_queue[(r, c)] -= 1
                if self.rotation_queue[(r, c)] == 0:
                    del self.rotation_queue[(r, c)]
                # 重新启动该格子的动画
                self.start_rotation_animation(r, c)
            else:
                # 没有待处理的旋转，检查锁定队列
                if (r, c) in self.lock_queue:
                    should_lock = self.lock_queue[(r, c)]
                    del self.lock_queue[(r, c)]
                    self.game.locked[r][c] = should_lock
                    self.draw_grid()
        
        # 如果所有格子都完成动画且队列为空
        if not self.animating_cells and not self.rotation_queue and not self.lock_queue:
            self.animating = False
            self.animation_cell = None
            
            # 检查胜利
            if self.game.check_victory():
                self.game.victory = True
                self.game.stop_timer()
                board_size = f"{self.game.rows}x{self.game.cols}"
                time_used = self.game.get_elapsed_time()
                
                # 检查是否允许参与排行榜
                allow_leaderboard = True
                if not self.allow_custom_level_leaderboard and self.game.is_custom_level:
                    allow_leaderboard = False
                if not self.allow_solver_leaderboard and self.game.used_solver:
                    allow_leaderboard = False
                if not self.allow_generated_level_leaderboard and self.game.is_generated_level:
                    allow_leaderboard = False
                
                if allow_leaderboard:
                    if self.leaderboard.add_record(board_size, time_used):
                        self.save_status = "✅ 成绩已保存"
                    else:
                        self.save_status = "❌ 成绩保存失败"
                else:
                    self.save_status = "⚠️ 不参与排行榜"
            self.draw_grid()
            return
        
        # 继续下一帧
        self.master.after(4, self.animate_rotation)
    
    def draw_grid_for_animation(self, anim_r, anim_c):
        """为动画准备网格，绘制所有格子（除了动画格子）。
        
        Args:
            anim_r: 动画格子的行索引（已废弃，保留兼容性）
            anim_c: 动画格子的列索引（已废弃，保留兼容性）
        """
        self.canvas.delete("all")
        water = self.game.calculate_water_flow()
        water_cycles, dry_cycles = self.game.detect_cycles(water)
        closed_components = self.game.detect_closed_paths(water)
        
        closed_paths = [[False] * self.game.cols for _ in range(self.game.rows)]
        for component in closed_components:
            for r, c in component:
                closed_paths[r][c] = True
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if canvas_width > 1:
            board_aspect_ratio = self.game.rows / self.game.cols
            
            if 0.8 <= board_aspect_ratio <= 1.25:
                cell_size_by_width = (canvas_width - coord_left_space) // self.game.cols
                cell_size_by_height = (canvas_height - coord_top_space - coord_bottom_space) // self.game.rows
                self.cell_size = max(self.min_cell_size, min(self.max_cell_size, min(cell_size_by_width, cell_size_by_height)))
            else:
                self.cell_size = max(self.min_cell_size, min(self.max_cell_size, (canvas_width - coord_left_space) // self.game.cols))
        
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        board_aspect_ratio = self.game.rows / self.game.cols
        
        if 0.8 <= board_aspect_ratio <= 1.25:
            h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        else:
            if board_width >= canvas_width:
                h_offset = 0
            else:
                h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        # 绘制列号（在每一列的上方）
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for c in range(self.game.cols):
                x = c * self.cell_size + h_offset + self.cell_size // 2
                y = v_offset - 15
                self.canvas.create_text(
                    x, y,
                    text=str(c),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        # 绘制行号（在每一行的左边）
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for r in range(self.game.rows):
                x = h_offset - 15
                y = r * self.cell_size - self.scroll_offset + v_offset + self.cell_size // 2
                self.canvas.create_text(
                    x, y,
                    text=str(r),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill='#252525',
                    anchor='center'
                )
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x1 = c * self.cell_size + h_offset
                y1 = r * self.cell_size - self.scroll_offset + v_offset
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                bg_color = '#D3D3D3' if self.game.locked[r][c] else 'white'
                self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill=bg_color, tags=f"bg_{r}_{c}")

                # 跳过所有正在动画的格子
                if (r, c) in self.animating_cells:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill=bg_color, tags=f"anim_cell_bg_{r}_{c}")
                    if (r, c) == self.game.start:
                        self.canvas.create_rectangle(
                            x1+2, y1+2, x2-2, y2-2, outline='blue', width=3,
                            tags=f"anim_cell_start_{r}_{c}"
                        )
                    continue
                
                openings = self.game.grid[r][c]
                base_type, angle = pipe_image_info(openings)
                
                if water[r][c]:
                    if self.show_cycles and water_cycles[r][c]:
                        image_type = f'{base_type}_water_red'
                    else:
                        image_type = f'{base_type}_water'
                else:
                    if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                        image_type = f'{base_type}_red'
                    else:
                        image_type = base_type
                
                rotated_image = self.get_rotated_image(image_type, angle)
                
                if rotated_image:
                    self.canvas.create_image(
                        (x1 + x2) // 2, (y1 + y2) // 2,
                        image=rotated_image,
                        tags=f"cell_{r}_{c}"
                    )
                else:
                    symbol = pipe_symbol(openings)
                    self.canvas.create_text(
                        (x1 + x2) // 2, (y1 + y2) // 2,
                        text=symbol, font=("Courier", 24), fill='black',
                        tags=f"cell_{r}_{c}"
                    )

                if (r, c) == self.game.start:
                    self.canvas.create_rectangle(
                        x1+2, y1+2, x2-2, y2-2, outline='blue', width=3,
                        tags=f"start_{r}_{c}"
                    )
    
    def update_animation_cell(self, r, c, anim_angle, state):
        """只更新动画格子的图片。
        
        Args:
            r: 动画格子的行索引
            c: 动画格子的列索引
            anim_angle: 当前旋转角度
            state: 该格子的动画状态字典
        """
        self.canvas.delete(f"anim_cell_{r}_{c}")
        self.canvas.delete(f"anim_cell_start_{r}_{c}")
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        board_aspect_ratio = self.game.rows / self.game.cols
        
        if 0.8 <= board_aspect_ratio <= 1.25:
            h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        else:
            if board_width >= canvas_width:
                h_offset = 0
            else:
                h_offset = (canvas_width - board_width) // 2
            if board_height <= canvas_height:
                v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
            else:
                v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        x1 = c * self.cell_size + h_offset
        y1 = r * self.cell_size - self.scroll_offset + v_offset
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        
        openings = self.game.grid[r][c]
        base_type, original_angle = pipe_image_info(openings)
        total_angle = original_angle + anim_angle
        
        if state['water']:
            if self.show_cycles and state['water_cycle']:
                image_type = f'{base_type}_water_red'
            else:
                image_type = f'{base_type}_water'
        else:
            if (self.show_cycles and state['dry_cycle']) or (self.show_closed_paths and state['closed_path']):
                image_type = f'{base_type}_red'
            else:
                image_type = base_type
        
        rotated_image = self.get_rotated_image_dynamic(image_type, total_angle)
        
        if rotated_image:
            self.canvas.create_image(
                (x1 + x2) // 2, (y1 + y2) // 2,
                image=rotated_image,
                tags=f"anim_cell_{r}_{c}"
            )
        else:
            symbol = pipe_symbol(openings)
            self.canvas.create_text(
                (x1 + x2) // 2, (y1 + y2) // 2,
                text=symbol, font=("Courier", 24), fill='black',
                tags=f"anim_cell_{r}_{c}"
            )
        
        if (r, c) == self.game.start:
            self.canvas.create_rectangle(
                x1+2, y1+2, x2-2, y2-2, outline='blue', width=3,
                tags=f"anim_cell_start_{r}_{c}"
            )
    

    def get_rotated_image_dynamic(self, base_type, angle):
        """获取动态旋转后的图片，使用缓存防止图片被回收。
        
        Args:
            base_type: 管道类型
            angle: 旋转角度（可以是任意值）
            
        Returns:
            ImageTk.PhotoImage: 旋转后的图片对象，失败返回None
        """
        if self.base_images.get(base_type) is None:
            return None
        
        key = (base_type, angle, self.cell_size)
        if key in self.animation_image_cache:
            return self.animation_image_cache[key]
        
        try:
            resized = self.base_images[base_type].resize((self.cell_size - 1, self.cell_size - 1), Image.Resampling.LANCZOS)
            rotated = resized.rotate(-angle, expand=False)
            photo_image = ImageTk.PhotoImage(rotated)
            self.animation_image_cache[key] = photo_image
            return photo_image
        except Exception as e:
            print(f"动态旋转图片失败 {base_type} {angle}: {e}")
            return None

    def on_size_change(self, rows, cols):
        """处理棋盘大小选择按钮点击事件。
        
        Args:
            rows: 行数
            cols: 列数
        """
        # 停止正在运行的生成动画
        self.stop_generation_animation()
        
        # 停止所有求解动画
        if self.deductive_animating:
            self.stop_deductive_animation()
        if self.assumption_animating:
            self.stop_assumption_animation()
        if self.search_animating:
            self.stop_search_animation()
        
        if self.size_change_callback:
            self.size_change_callback(rows, cols)

    def on_custom_size(self):
        """处理自定义棋盘大小按钮点击事件。"""
        self.warning_label.config(text="")
        
        rows_input = self.custom_rows.get().strip()
        cols_input = self.custom_cols.get().strip()
        
        if not rows_input or not cols_input:
            self.show_warning("⚠请输入正确正整数")
            return
        
        try:
            rows = int(rows_input)
            cols = int(cols_input)
            
            if rows != float(rows_input) or cols != float(cols_input):
                self.show_warning("⚠请输入正确正整数")
                return
            
            if rows < 2 or cols < 2 or rows > 50 or cols > 50:
                self.show_warning("⚠长宽范围2~50")
                return
            
            if self.size_change_callback:
                self.size_change_callback(rows, cols)
        except ValueError:
            self.show_warning("⚠请输入正确正整数")
        except Exception as e:
            self.show_warning("⚠请输入正确正整数")

    def on_import_level(self):
        """处理导入关卡按钮点击事件。"""
        if self.generating:
            messagebox.showwarning("提示", "正在生成关卡中，无法导入")
            return
        
        # 停止所有正在运行的动画
        self._stop_all_animations()
        
        self.warning_label.config(text="")
        
        import_window = tk.Toplevel(self.master)
        import_window.title("导入关卡")
        import_window.geometry("850x800")
        import_window.resizable(True, True)
        
        ttk.Label(import_window, text="请输入棋盘列表（Python列表格式）：", font=(CHINESE_FONT_NORMAL, 17)).pack(pady=(10, 5))
        
        text_frame = ttk.Frame(import_window)
        text_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_area = tk.Text(text_frame, height=15, width=70, wrap=tk.NONE, 
                           yscrollcommand=scrollbar.set, font=(CHINESE_FONT_MONO, 16),
                           undo=True, maxundo=-1)
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=text_area.yview)
        
        example_text = """示例格式：
[
    [[2], [2, 0], [1, 2], [1], [3, 2, 0], [1, 3], [1]],
    [[1, 2], [2, 3], [1, 0], [2, 0], [3, 0, 1], [0], [1]],
    [[0], [3, 2], [1, 2, 3], [0, 1, 3], [3, 0, 1], [2, 0, 3], [3, 0]],
    [[2], [0, 2], [0, 2, 3], [3, 0], [2, 0, 1], [0, 2, 3], [2, 1]],
    [[0], [0], [3, 1, 2], [0, 1], [2, 1, 0], [0], [3]],
    [[0, 3], [2, 3, 0], [0, 3], [3, 1], [1, 2, 3], [2, 1, 0], [2, 1]],
    [[2], [2, 1], [0], [1, 0], [2], [1], [1]]
], (3,3)

说明：
- 每个数字代表一个开口方向：0=上, 1=右, 2=下, 3=左
- 例如 [2] 表示下方开口，[0, 2] 表示上下开口
- 水源位置可选，格式为 (行, 列)，如 (3,3)
- 若不指定水源位置，默认为中心点"""
        
        example_frame = ttk.Frame(import_window)
        example_frame.pack(padx=10, pady=5, fill=tk.X)
        
        example_scrollbar = ttk.Scrollbar(example_frame)
        example_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        example_text_area = tk.Text(example_frame, height=12, width=70, wrap=tk.NONE, 
                                    yscrollcommand=example_scrollbar.set, font=(CHINESE_FONT_MONO, 15),
                                    bg="#f0f0f0", relief=tk.SUNKEN, bd=1)
        example_text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        example_scrollbar.config(command=example_text_area.yview)
        
        example_text_area.insert(tk.END, example_text)
        example_text_area.config(state=tk.DISABLED)
        
        def on_clear():
            """清空输入框。"""
            text_area.delete("1.0", tk.END)
        
        def on_confirm():
            """确认导入。"""
            grid_text = text_area.get("1.0", tk.END).strip()
            
            try:
                parsed = ast.literal_eval(grid_text)
                
                if isinstance(parsed, tuple) and len(parsed) == 2:
                    grid = parsed[0]
                    start = parsed[1]
                else:
                    grid = parsed
                    start = None
                
                if not isinstance(grid, list) or len(grid) == 0:
                    messagebox.showerror("错误", "棋盘格式错误：必须是非空列表")
                    return
                
                rows = len(grid)
                cols = len(grid[0]) if rows > 0 else 0
                
                if rows < 2 or cols < 2 or rows > 50 or cols > 50:
                    messagebox.showerror("错误", f"棋盘尺寸错误：长宽范围2~50，当前为{rows}x{cols}")
                    return
                
                if start is not None:
                    if not isinstance(start, tuple) or len(start) != 2:
                        messagebox.showerror("错误", f"水源位置格式错误：必须是 (行, 列) 格式的元组")
                        return
                    start_row, start_col = start
                    if not isinstance(start_row, int) or not isinstance(start_col, int):
                        messagebox.showerror("错误", f"水源位置格式错误：行和列必须是整数")
                        return
                    if start_row < 0 or start_row >= rows or start_col < 0 or start_col >= cols:
                        messagebox.showerror("错误", f"水源位置超出范围：({start_row}, {start_col}) 不在 {rows}x{cols} 棋盘范围内")
                        return
                else:
                    start_row = rows // 2
                    start_col = cols // 2
                    start = (start_row, start_col)
                
                for r, row in enumerate(grid):
                    if not isinstance(row, list):
                        messagebox.showerror("错误", f"第{r+1}行格式错误：必须是列表")
                        return
                    if len(row) != cols:
                        messagebox.showerror("错误", f"第{r+1}行列数错误：应为{cols}列，实际为{len(row)}列")
                        return
                    for c, cell in enumerate(row):
                        if not isinstance(cell, list):
                            messagebox.showerror("错误", f"格子({r},{c})格式错误：必须是列表")
                            return
                        for d in cell:
                            if not isinstance(d, int) or d < 0 or d > 3:
                                messagebox.showerror("错误", f"格子({r},{c})包含无效方向：{d}（必须是0-3的整数）")
                                return
                
                if self.level_import_callback:
                    self.level_import_callback(grid, start)
                    import_window.destroy()
                    messagebox.showinfo("成功", f"成功导入{rows}x{cols}的关卡！水源位置：({start_row}, {start_col})")
                
            except SyntaxError:
                messagebox.showerror("错误", "棋盘格式错误：无法解析Python列表")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败：{str(e)}")
        
        def on_cancel():
            """取消导入。"""
            import_window.destroy()
        
        button_frame = ttk.Frame(import_window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="确认", command=on_confirm, width=12, bootstyle=SUCCESS).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空", command=on_clear, width=12, bootstyle=WARNING).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=on_cancel, width=12, bootstyle=DANGER).pack(side=tk.LEFT, padx=5)
    
    def on_export_level(self):
        """处理导出关卡按钮点击事件，将当前棋盘状态复制到剪切板。"""
        if self.generating:
            messagebox.showwarning("提示", "正在生成关卡中，无法导出")
            return
        
        try:
            grid = self.game.grid
            start = self.game.start
            
            # 格式化网格，每行换行，与导入示例格式保持一致
            grid_lines = []
            for row in grid:
                grid_lines.append(str(row))
            grid_str = "[\n    " + ",\n    ".join(grid_lines) + "\n]"
            export_text = f"{grid_str}, {start}"
            
            self.master.clipboard_clear()
            self.master.clipboard_append(export_text)
            self.master.update()
            self.show_warning("✅ 已复制到剪切板")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出失败：{str(e)}")
    
    def on_generate_level(self):
        """处理地图生成按钮点击事件，开始生成动画。"""
        if self.generating:
            # 正在生成中，停止当前动画并重新生成
            self.stop_generation_animation()
        
        # 停止所有求解动画
        if self.deductive_animating:
            self.stop_deductive_animation()
        if self.assumption_animating:
            self.stop_assumption_animation()
        if self.search_animating:
            self.stop_search_animation()
        
        if self.game.victory:
            return  # 已胜利，不允许生成
        
        # 导入动画生成器
        from animated_generators.animated_generator import generate_animated_level
        
        # 生成新的关卡
        result = generate_animated_level(self.game.rows, self.game.cols)
        if result is None:
            messagebox.showerror("生成失败", "无法生成有效的关卡，请重试")
            return
        
        self.generator, self.generation_start, self.generation_start_openings = result
        
        # 初始化空棋盘
        self.game.grid = [[[] for _ in range(self.game.cols)] for _ in range(self.game.rows)]
        self.game.start = self.generation_start
        self.game.is_custom_level = False
        self.game.used_solver = False
        self.game.victory = False
        self.game.is_generated_level = False  # 重置生成关卡标志
        self.game.start_time = time.time()
        self.game.end_time = None
        self.game.locked = [[False] * self.game.cols for _ in range(self.game.rows)]  # 重置锁定状态
        self.save_status = ""
        
        # 设置生成状态
        self.generating = True
        
        # 开始动画
        self.update_generation_animation()
    
    def update_generation_animation(self):
        """更新生成动画。"""
        if not self.generating or self.generator is None:
            return

        # 执行一步生成
        step_info = self.generator.step()

        # 更新棋盘
        self.game.grid = self.generator.get_grid()
        
        # 更新叶子节点信息
        self.checking_leaf = step_info.get('checking_leaf')
        self.pending_leaves = step_info.get('pending_leaves', [])
        
        # 显示步骤信息
        self.show_generation_step_info(step_info)
        
        # 重绘
        self.draw_grid()
        
        # 检查是否完成
        if step_info['finished']:
            self.generating = False
            self.checking_leaf = None
            self.pending_leaves = []
            
            if step_info['failed']:
                messagebox.showerror("生成失败", "生成过程中出现错误，请重试")
            else:
                # 生成成功，保存动画生成的最终棋盘
                self.generated_grid = [row[:] for row in self.game.grid]
                grid = [row[:] for row in self.generated_grid]
                
                # 根据设置决定是否打乱顺序
                if self.shuffle_after_generation:
                    # 随机打乱每个格子的方向
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            if grid[r][c]:  # 所有格子（包括水源）都可以旋转
                                rot = random.randint(0, 3)
                                if rot != 0:
                                    grid[r][c] = [(d + rot) % 4 for d in grid[r][c]]
                
                self.game.grid = grid
                self.game.start = self.generation_start
                self.game.is_generated_level = True  # 标记为生成的关卡
                self.draw_grid()
            return
        
        # 继续下一步，检查是否仍在生成状态
        if self.generating:
            # 取消之前的动画定时器（如果存在）
            if self.generation_animation_timer is not None:
                self.master.after_cancel(self.generation_animation_timer)
            # 设置新的动画定时器
            self.generation_animation_timer = self.master.after(self.generation_speed, self.update_generation_animation)
    
    def stop_generation_animation(self):
        """停止正在运行的生成动画。"""
        self.generating = False
        self.checking_leaf = None
        self.pending_leaves = []
        self.generator = None
        try:
            self.generation_info_label.config(text="")
            self.generation_info_label.place_forget()
        except Exception:
            pass
        # 取消动画定时器（如果存在）
        if self.generation_animation_timer is not None:
            self.master.after_cancel(self.generation_animation_timer)
            self.generation_animation_timer = None
    
    def show_generation_step_info(self, step_info):
        """显示生成动画步骤信息。
        
        Args:
            step_info: 步骤信息字典
        """
        step_type = step_info.get('type', '')
        cell = step_info.get('cell')
        neighbor = step_info.get('neighbor')
        
        info_text = ""
        
        if step_type == 'connect':
            if cell and neighbor:
                info_text = f"连接格子 {cell} 到 {neighbor}"
            elif cell:
                info_text = f"连接格子 {cell}"
        elif step_type == 'remove':
            if cell:
                info_text = f"确定格子 {cell}"
        elif step_type == 'finish':
            info_text = "生成完成！"
        elif step_type == 'fail':
            info_text = "生成失败！"
        
        # 取消之前的定时器（如果存在）
        if self.generation_info_timer is not None:
            self.master.after_cancel(self.generation_info_timer)
        
        # 更新标签显示
        self.generation_info_label.config(text=info_text)
        # 确保文字在画布之上
        self.generation_info_label.lift()
        # 确保标签可见
        self.generation_info_label.place(relx=0.5, y=60, anchor='center')
        
        # 设置新的定时器，2秒后清除信息
        self.generation_info_timer = self.master.after(2000, self.clear_generation_info)
    
    def clear_generation_info(self):
        """清除生成动画步骤信息并隐藏标签。"""
        try:
            self.generation_info_label.config(text="")
            self.generation_info_label.place_forget()
        except Exception:
            pass
    
    def _stop_all_animations(self):
        """停止所有正在运行的动画。"""
        # 停止生成动画
        if self.generating:
            self.generating = False
            if self.generation_animation_timer is not None:
                self.master.after_cancel(self.generation_animation_timer)
                self.generation_animation_timer = None
        
        # 停止演绎推理动画
        if self.deductive_animating:
            self.deductive_animating = False
            if self.deductive_animation_timer is not None:
                self.master.after_cancel(self.deductive_animation_timer)
                self.deductive_animation_timer = None
            self.deductive_solver = None
        
        # 停止假设推理动画
        if self.assumption_animating:
            self.assumption_animating = False
            if self.assumption_animation_timer is not None:
                self.master.after_cancel(self.assumption_animation_timer)
                self.assumption_animation_timer = None
            self.assumption_solver = None
        
        # 停止搜索求解动画
        if self.search_animating:
            self.search_animating = False
            if self.search_animation_timer is not None:
                self.master.after_cancel(self.search_animation_timer)
                self.search_animation_timer = None
            self.search_solver = None
    
    def show_warning(self, text):
        """显示警告信息并在3秒后自动清除。
        
        Args:
            text: 警告信息文本
        """
        # 取消之前的定时器（如果存在）
        if self.warning_label_timer is not None:
            self.master.after_cancel(self.warning_label_timer)
        
        # 显示警告信息
        self.warning_label.config(text=text)
        
        # 设置新的定时器，3秒后清除信息
        self.warning_label_timer = self.master.after(3000, self.clear_warning)
    
    def clear_warning(self):
        """清除警告信息。"""
        try:
            self.warning_label.config(text="")
            self.warning_label_timer = None
        except Exception:
            pass

    def on_setting_change(self, setting_name, value):
        """处理设置变更。"""
        if setting_name == 'show_grid_coordinates':
            self.show_grid_coordinates = value
        elif setting_name == 'show_cycles':
            self.show_cycles = value
        elif setting_name == 'show_closed_paths':
            self.show_closed_paths = value
        elif setting_name == 'allow_custom_level_leaderboard':
            self.allow_custom_level_leaderboard = value
        elif setting_name == 'allow_solver_leaderboard':
            self.allow_solver_leaderboard = value
        elif setting_name == 'allow_generated_level_leaderboard':
            self.allow_generated_level_leaderboard = value
        elif setting_name == 'shuffle_after_generation':
            self.shuffle_after_generation = value
        self.save_settings()
        self.draw_grid()
        # 重新显示设置菜单
        self.show_settings_menu()
    
    def on_speed_slider_change(self, slider_val, slider_to_speed):
        """处理速度滑块变更。"""
        new_speed = slider_to_speed(slider_val)
        self.generation_speed = new_speed
        if hasattr(self, 'generation_speed_var'):
            self.generation_speed_var.set(new_speed)
        self.speed_label.config(text=f"{new_speed}ms")
        self.save_settings()
    
    def on_generation_speed_change(self, speed):
        """处理生成速度变更。"""
        self.generation_speed = speed
        self.generation_speed_var.set(speed)
        self.save_settings()
        # 重新显示设置菜单
        self.show_settings_menu()
    
    def show_settings_menu(self):
        """重新显示设置菜单。"""
        try:
            self.settings_menu.post(
                self.settings_menubtn.winfo_rootx(),
                self.settings_menubtn.winfo_rooty() + self.settings_menubtn.winfo_height()
            )
        except Exception:
            pass
    
    def load_settings(self):
        """从文件加载设置。"""
        settings_file = get_settings_path()
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.show_cycles = settings.get('show_cycles', True)
                    self.show_closed_paths = settings.get('show_closed_paths', True)
                    self.show_grid_coordinates = settings.get('show_grid_coordinates', False)
                    self.allow_custom_level_leaderboard = settings.get('allow_custom_level_leaderboard', False)
                    self.allow_solver_leaderboard = settings.get('allow_solver_leaderboard', False)
                    self.allow_generated_level_leaderboard = settings.get('allow_generated_level_leaderboard', False)
                    self.shuffle_after_generation = settings.get('shuffle_after_generation', False)
                    self.generation_speed = settings.get('generation_speed', 100)
                    self.first_launch = settings.get('first_launch', True)
                    # 更新生成速度变量
                    if hasattr(self, 'generation_speed_var'):
                        self.generation_speed_var.set(self.generation_speed)
                    # 更新滑块和标签
                    if hasattr(self, 'speed_slider_var') and hasattr(self, 'slider_to_speed'):
                        import math
                        slider_val = min(100, max(0, int((math.log10(max(10, self.generation_speed)) - 1) * 100 / 2)))
                        self.speed_slider_var.set(slider_val)
                    if hasattr(self, 'speed_label'):
                        self.speed_label.config(text=f"{self.generation_speed}ms")
            else:
                self.first_launch = True
        except Exception as e:
            print(f"加载设置失败: {e}")
            self.first_launch = True
    
    def save_settings(self):
        """保存设置到文件。"""
        settings_file = get_settings_path()
        try:
            settings = {
                'show_cycles': self.show_cycles,
                'show_closed_paths': self.show_closed_paths,
                'show_grid_coordinates': self.show_grid_coordinates,
                'allow_custom_level_leaderboard': self.allow_custom_level_leaderboard,
                'allow_solver_leaderboard': self.allow_solver_leaderboard,
                'allow_generated_level_leaderboard': self.allow_generated_level_leaderboard,
                'shuffle_after_generation': self.shuffle_after_generation,
                'generation_speed': self.generation_speed,
                'first_launch': self.first_launch
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def on_mousewheel(self, event):
        """处理鼠标滚轮事件，实现上下滚动。
        
        Args:
            event: 鼠标滚轮事件
        """
        if self.game.victory:
            return
        
        canvas_height = self.canvas.winfo_height()
        board_height = self.game.rows * self.cell_size
        
        # 计算坐标预留空间
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            v_offset += coord_top_space
        
        scroll_step = self.cell_size * 3
        
        if event.num == 4 or event.delta > 0:
            self.scroll_offset -= scroll_step
        elif event.num == 5 or event.delta < 0:
            self.scroll_offset += scroll_step
        
        max_scroll = board_height - canvas_height + v_offset + coord_bottom_space
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        
        self.draw_grid()
    
    def show_game_intro(self):
        """显示游戏介绍窗口。"""
        intro_window = tk.Toplevel(self.master)
        intro_window.title("游戏介绍")
        intro_window.geometry("700x750")
        intro_window.resizable(False, False)
        
        canvas = tk.Canvas(intro_window, width=680, height=740)
        scrollbar = ttk.Scrollbar(intro_window, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            intro_window.destroy()
        intro_window.protocol("WM_DELETE_WINDOW", on_close)
        
        # 标题
        title_label = ttk.Label(scrollable_frame, text="🎮 管道连接游戏 🎮", font=(CHINESE_FONT_BOLD, 23, "bold"), bootstyle=PRIMARY)
        title_label.pack(pady=15)
        
        # 游戏目标
        goal_frame = ttk.LabelFrame(scrollable_frame, text="🎯 游戏目标")
        goal_frame.pack(fill=tk.X, padx=15, pady=5)
        
        goal_text = """点击旋转管道格子，使所有管道从水源出发形成一条连通的路径，最终填满整个棋盘。

• 水源位置用蓝色边框格子标记
• 有水流过的管道会显示蓝色
• 所有格子必须被水流填满且不形成环路才能获胜"""
        ttk.Label(goal_frame, text=goal_text, font=(CHINESE_FONT_NORMAL, 14), wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=5)
        
        # 新游戏示例
        example1_frame = ttk.LabelFrame(scrollable_frame, text="📸 刚生成的关卡")
        example1_frame.pack(fill=tk.X, padx=15, pady=5)
        
        try:
            img1_path = os.path.join(os.path.dirname(__file__), "images", "intro_new_game.jpg")
            if os.path.exists(img1_path):
                img1 = Image.open(img1_path)
                img1 = img1.resize((400, 400), Image.LANCZOS)
                photo1 = ImageTk.PhotoImage(img1)
                img1_label = ttk.Label(example1_frame, image=photo1)
                img1_label.image = photo1
                img1_label.pack(padx=10, pady=5)
        except Exception as e:
            ttk.Label(example1_frame, text=f"[图片加载失败: {e}]").pack(padx=10)
        
        ttk.Label(example1_frame, text="刚生成的关卡，管道方向随机排列，需要玩家旋转调整。", font=(CHINESE_FONT_NORMAL, 13)).pack(pady=5, padx=10)
        
        # 胜利示例
        example2_frame = ttk.LabelFrame(scrollable_frame, text="🏆 通关的关卡")
        example2_frame.pack(fill=tk.X, padx=15, pady=5)
        
        try:
            img2_path = os.path.join(os.path.dirname(__file__), "images", "intro_victory.jpg")
            if os.path.exists(img2_path):
                img2 = Image.open(img2_path)
                img2 = img2.resize((400, 400), Image.LANCZOS)
                photo2 = ImageTk.PhotoImage(img2)
                img2_label = ttk.Label(example2_frame, image=photo2)
                img2_label.image = photo2
                img2_label.pack(padx=10, pady=5)
        except Exception as e:
            ttk.Label(example2_frame, text=f"[图片加载失败: {e}]").pack(padx=10)
        
        ttk.Label(example2_frame, text="通关状态！所有管道连通，水流填满整个棋盘。", font=(CHINESE_FONT_NORMAL, 13)).pack(pady=5, padx=10)
        
        # 环路和闭路说明
        example3_frame = ttk.LabelFrame(scrollable_frame, text="⚠️ 环路与闭路")
        example3_frame.pack(fill=tk.X, padx=15, pady=5)
        
        try:
            img3_path = os.path.join(os.path.dirname(__file__), "images", "intro_loop_deadend.jpg")
            if os.path.exists(img3_path):
                img3 = Image.open(img3_path)
                img3 = img3.resize((400, 400), Image.LANCZOS)
                photo3 = ImageTk.PhotoImage(img3)
                img3_label = ttk.Label(example3_frame, image=photo3)
                img3_label.image = photo3
                img3_label.pack(padx=10, pady=5)
        except Exception as e:
            ttk.Label(example3_frame, text=f"[图片加载失败: {e}]").pack(padx=10)
        
        loop_text = """• 环路：水流形成循环，违反规则，不能出现
• 闭路：管道形成封闭区域，水流无法到达

环路和闭路都会导致无法通关！"""
        ttk.Label(example3_frame, text=loop_text, font=(CHINESE_FONT_NORMAL, 13), wraplength=620, justify=tk.LEFT).pack(pady=5, padx=10)
        
        # 操作说明
        control_frame = ttk.LabelFrame(scrollable_frame, text="🖱️ 操作说明")
        control_frame.pack(fill=tk.X, padx=15, pady=5)
        
        control_text = """• 左键点击：旋转管道格子（顺时针90度）
• 右键点击：锁定/解锁格子（锁定后无法旋转）
• 滚轮：上下滚动棋盘（长条棋盘时有效）"""
        ttk.Label(control_frame, text=control_text, font=(CHINESE_FONT_NORMAL, 14), wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=5)
        
        # 功能按钮说明
        func_frame = ttk.LabelFrame(scrollable_frame, text="🔧 功能按钮")
        func_frame.pack(fill=tk.X, padx=15, pady=5)
        
        func_text = """• 再来一局：重新生成当前大小的关卡
• 棋盘大小：选择不同尺寸的棋盘
• 导入/导出关卡：可自由设计关卡
• 地图生成：观看关卡生成算法的动画演示
• 演绎推理/假设推理/搜索求解：观看不同求解算法的动画演示
• 一键求解：自动完成当前关卡
• 拖拽滑块：调整动画播放速度
• 查看排行榜：查看个人最佳成绩"""
        ttk.Label(func_frame, text=func_text, font=(CHINESE_FONT_NORMAL, 14), wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=5)
        
        # 关闭按钮
        close_btn = ttk.Button(scrollable_frame, text="我知道了！", command=on_close, width=15, bootstyle=SUCCESS)
        close_btn.pack(pady=15)
    
    def show_leaderboard(self):
        """显示排行榜窗口。"""
        leaderboard_window = tk.Toplevel(self.master)
        leaderboard_window.title("排行榜")
        leaderboard_window.geometry("500x600")
        leaderboard_window.resizable(False, False)
        
        notebook = ttk.Notebook(leaderboard_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        personal_frame = ttk.Frame(notebook)
        notebook.add(personal_frame, text="个人最好成绩")
        
        global_frame = ttk.Frame(notebook)
        notebook.add(global_frame, text="全球最好成绩")
        
        personal_scroll = ttk.Scrollbar(personal_frame)
        personal_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        personal_canvas = tk.Canvas(personal_frame, yscrollcommand=personal_scroll.set)
        personal_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        personal_scroll.config(command=personal_canvas.yview)
        
        personal_inner_frame = ttk.Frame(personal_canvas)
        personal_canvas.create_window((0, 0), window=personal_inner_frame, anchor="nw")
        
        all_records = self.leaderboard.get_all_personal_best()
        standard_sizes = ["5x5", "7x7", "11x11", "15x15", "21x21"]
        
        current_row = 0
        for size in standard_sizes:
            if size in all_records and all_records[size]:
                ttk.Label(personal_inner_frame, text=f"{size}:", font=(CHINESE_FONT_BOLD, 15, "bold"), bootstyle=PRIMARY).grid(row=current_row, column=0, sticky="w", padx=10, pady=5)
                current_row += 1
                
                records = all_records[size]
                for j, record in enumerate(records[:3]):
                    time_text = f"{record['time']:.1f}秒"
                    timestamp_text = record['timestamp']
                    ttk.Label(personal_inner_frame, text=f"  {j+1}. {time_text} ({timestamp_text})", font=(CHINESE_FONT_NORMAL, 14)).grid(row=current_row, column=0, sticky="w", padx=20, pady=2)
                    current_row += 1
            else:
                ttk.Label(personal_inner_frame, text=f"{size}:", font=(CHINESE_FONT_BOLD, 15, "bold"), bootstyle=PRIMARY).grid(row=current_row, column=0, sticky="w", padx=10, pady=5)
                current_row += 1
                ttk.Label(personal_inner_frame, text="  暂无记录", font=(CHINESE_FONT_NORMAL, 14), bootstyle=SECONDARY).grid(row=current_row, column=0, sticky="w", padx=20, pady=2)
                current_row += 1
        
        personal_inner_frame.update_idletasks()
        personal_canvas.config(scrollregion=personal_canvas.bbox("all"))
        
        ttk.Label(global_frame, text="功能暂未开发", font=(CHINESE_FONT_BOLD, 24, "bold"), bootstyle=SECONDARY).pack(expand=True)
        
        def on_mousewheel(event):
            """排行榜窗口的鼠标滚轮事件。"""
            if event.delta > 0 or event.num == 4:
                personal_canvas.yview_scroll(-2, "units")
            elif event.delta < 0 or event.num == 5:
                personal_canvas.yview_scroll(2, "units")
        
        leaderboard_window.bind("<MouseWheel>", on_mousewheel)
        leaderboard_window.bind("<Button-4>", on_mousewheel)
        leaderboard_window.bind("<Button-5>", on_mousewheel)
        
        def on_reset():
            """重置排行榜记录。"""
            if self.leaderboard.reset_records():
                leaderboard_window.destroy()
                self.show_leaderboard()
            else:
                messagebox.showerror("错误", "重置失败")
        
        reset_btn = ttk.Button(leaderboard_window, text="重置排行榜", command=on_reset, width=15, bootstyle=DANGER)
        reset_btn.pack(side=tk.BOTTOM, pady=10)

    def on_solve_level(self):
        """处理一键求解按钮点击事件。"""
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        result = solve_level(self.game.rows, self.game.cols, self.game.start,
                            [row[:] for row in self.game.grid],
                            locked=[row[:] for row in self.game.locked])
        
        if result['success']:
            solution = result['solution']
            determined_mask = result['determined_mask']
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    self.game.grid[r][c] = solution[r][c]
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask[r][c] and not self.game.locked[r][c]:
                        self.game.locked[r][c] = True
            self.game.used_solver = True  # 标记使用了求解器
            self.draw_grid()
            
            message = f"求解成功！确定了 {result['determined_count']} 个格子，需要旋转 {result['rotation_count']} 个格子"
            messagebox.showinfo("求解成功", message)
        else:
            messagebox.showerror("求解失败", "未找到有效的部分解")
    
    def on_solve_step(self, step):
        """执行指定的求解步骤。
        
        Args:
            step: 求解步骤，1=演绎推理，2=假设推理，3=搜索求解
        """
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        if step == 1:
            # 启动演绎推理动画
            self.on_deductive_animation()
        elif step == 2:
            # 启动假设推理动画
            self.on_assumption_animation()
        elif step == 3:
            # 启动搜索求解动画
            self.on_search_animation()
        else:
            return
    
    def on_deductive_no_animation(self):
        """演绎推理（不播放动画，直接求解）。"""
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        result = solve_step1_deductive(self.game.rows, self.game.cols, self.game.start,
                                       [row[:] for row in self.game.grid],
                                       locked=[row[:] for row in self.game.locked])
        
        if result['success']:
            solution = result['solution']
            determined_mask = result['determined_mask']
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    self.game.grid[r][c] = solution[r][c]
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask[r][c] and not self.game.locked[r][c]:
                        self.game.locked[r][c] = True
            self.game.used_solver = True
            self.draw_grid()
            
            message = f"演绎推理成功！确定了 {result['determined_count']} 个格子"
            messagebox.showinfo("求解成功", message)
        else:
            messagebox.showerror("演绎推理失败", "演绎推理未找到有效的部分解")
    
    def on_deductive_animation(self):
        """启动演绎推理动画。"""
        if self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        from animated_solvers.animated_deductive_solver import AnimatedDeductiveSolver
        
        self.deductive_animating = True
        self.deductive_solver = AnimatedDeductiveSolver(
            self.game.rows, self.game.cols, self.game.start,
            [row[:] for row in self.game.grid],
            locked=[row[:] for row in self.game.locked]
        )
        
        # 开始动画循环
        self.update_deductive_animation()
    
    def update_deductive_animation(self):
        """更新演绎推理动画。"""
        if not self.deductive_animating:
            return
        
        step_info = self.deductive_solver.step()
        
        # 绘制当前步骤
        self.draw_deductive_step(step_info)
        
        # 显示步骤信息
        self.show_deductive_info(step_info)
        
        # 检查是否完成
        if step_info['finished']:
            self.deductive_animating = False
            self.deductive_animation_timer = None
            
            if step_info['failed']:
                self.show_deductive_info({'type': 'fail'})
                self.start_assumption_after_deductive = False
                messagebox.showerror("演绎推理失败", "演绎推理未找到有效的部分解")
            else:
                # 应用最终结果
                solution = step_info['solution']
                determined_mask = step_info['determined_mask']
                if solution:
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            self.game.grid[r][c] = solution[r][c]
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            if determined_mask[r][c] and not self.game.locked[r][c]:
                                self.game.locked[r][c] = True
                    self.game.used_solver = True
                    self.draw_grid()
                    
                    determined_count = sum(sum(row) for row in determined_mask)
                    self.show_deductive_info({'type': 'finish', 'determined_count': determined_count})
                    
                    if self.start_assumption_after_deductive:
                        self.start_assumption_after_deductive = False
                        self.master.after(100, self._start_assumption_after_deductive_finish)
                    else:
                        messagebox.showinfo("演绎推理完成", f"演绎推理成功！确定了 {determined_count} 个格子")
            return
        
        # 继续下一步
        self.deductive_animation_timer = self.master.after(
            self.generation_speed, self.update_deductive_animation
        )
    
    def _start_assumption_after_deductive_finish(self):
        """演绎推理完成后启动假设推理动画。"""
        from animated_solvers.animated_assumption_solver import AnimatedAssumptionSolver
        
        self.assumption_animating = True
        self.assumption_solver = AnimatedAssumptionSolver(
            self.game.rows, self.game.cols, self.game.start,
            [row[:] for row in self.game.grid],
            locked=[row[:] for row in self.game.locked]
        )
        
        self.update_assumption_animation()
    
    def show_deductive_info(self, step_info):
        """显示演绎推理步骤信息。
        
        Args:
            step_info: 步骤信息字典
        """
        info_text = ""
        step_type = step_info.get('type', '')
        
        if step_type == 'fail':
            info_text = "演绎推理：推理失败！"
        elif step_type == 'finish':
            determined_count = step_info.get('determined_count', 0)
            info_text = f"演绎推理：完成！确定了 {determined_count} 个格子"
        elif step_type == 'init_boundary':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：初始化边界约束：格子 ({r}, {c})"
        elif step_type == 'init_locked':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：处理锁定格子：格子 ({r}, {c})"
        elif step_type == 'init_single_opening':
            cells = step_info.get('cells')
            if cells and len(cells) >= 2:
                r1, c1 = cells[0]
                r2, c2 = cells[1]
                info_text = f"演绎推理：相邻单开口规则：格子 ({r1}, {c1}) 和 ({r2}, {c2})"
        elif step_type == 'update_candidates':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：更新候选集：格子 ({r}, {c})"
        elif step_type == 'apply_non_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：应用非开口约束：格子 ({r}, {c})"
        elif step_type == 'apply_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：应用开口约束：格子 ({r}, {c})"
        elif step_type.endswith('_fail'):
            info_text = f"演绎推理：推理失败：{step_type}"
        
        if not info_text:
            return
        
        # 取消之前的定时器（如果存在）
        if self.generation_info_timer is not None:
            self.master.after_cancel(self.generation_info_timer)
        
        # 更新标签显示
        self.generation_info_label.config(text=info_text)
        # 确保文字在画布之上
        self.generation_info_label.lift()
        # 确保标签可见
        self.generation_info_label.place(relx=0.5, y=60, anchor='center')
        
        # 设置新的定时器，2秒后清除信息
        self.generation_info_timer = self.master.after(2000, self.clear_generation_info)
    
    def stop_deductive_animation(self):
        """停止演绎推理动画。"""
        if self.deductive_animation_timer:
            self.master.after_cancel(self.deductive_animation_timer)
            self.deductive_animation_timer = None
        self.deductive_animating = False
        self.deductive_solver = None
        self.canvas.delete("deductive_indicator")
        self.canvas.delete("deductive_bg")
        self.draw_grid()
    
    def draw_deductive_step(self, step_info):
        """绘制演绎推理步骤。
        
        Args:
            step_info: 步骤信息字典
        """
        # 清除之前的指示器
        self.canvas.delete("deductive_indicator")
        self.canvas.delete("deductive_bg")
        
        if step_info['finished'] or step_info['failed']:
            return
        
        # 绘制方向状态指示器
        dir_state = step_info['dir_state']
        if not dir_state:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        # 计算坐标预留空间
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_width >= canvas_width:
            h_offset = 0
        else:
            h_offset = (canvas_width - board_width) // 2
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        # 调整偏移量以包含坐标空间
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        # 先更新棋盘显示并绘制确定的格子背景
        if step_info['solution']:
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if step_info['determined_mask'][r][c]:
                        self.game.grid[r][c] = step_info['solution'][r][c]
                        # 更新锁定状态，这样 draw_grid() 会自动绘制灰色背景
                        self.game.locked[r][c] = True
            self.draw_grid()
        
        # 绘制当前检查格子的红色边框（支持多个格子）
        cells = step_info.get('cells', None)
        if cells:
            for cell in cells:
                if cell:
                    r, c = cell
                    cell_x1 = h_offset + c * self.cell_size
                    cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
                    cell_x2 = cell_x1 + self.cell_size
                    cell_y2 = cell_y1 + self.cell_size
                    self.canvas.create_rectangle(
                        cell_x1, cell_y1, cell_x2, cell_y2,
                        outline="#FF0000", width=3, tags="deductive_indicator"
                    )
        
        # 绘制格子之间的方向状态指示器
        indicator_size = self.cell_size // 4
        determined_mask = step_info.get('determined_mask', None)
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell_x1 = h_offset + c * self.cell_size
                cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
                cell_x2 = cell_x1 + self.cell_size
                cell_y2 = cell_y1 + self.cell_size
                cell_center_x = (cell_x1 + cell_x2) // 2
                cell_center_y = (cell_y1 + cell_y2) // 2
                
                # 上方向
                if dir_state[r][c][UP] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    # 边界矩形：只需当前格子固定就隐藏
                    if r == 0:
                        if current_fixed:
                            pass  # 边界格子已固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        # 非边界：两侧都固定才隐藏
                        upper_fixed = determined_mask and determined_mask[r-1][c]
                        if current_fixed and upper_fixed:
                            pass  # 两侧都固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                # 下方向
                if dir_state[r][c][DOWN] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    # 边界矩形：只需当前格子固定就隐藏
                    if r == self.game.rows - 1:
                        if current_fixed:
                            pass  # 边界格子已固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        # 非边界：两侧都固定才隐藏
                        lower_fixed = determined_mask and determined_mask[r+1][c]
                        if current_fixed and lower_fixed:
                            pass  # 两侧都固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                # 左方向
                if dir_state[r][c][LEFT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    # 边界矩形：只需当前格子固定就隐藏
                    if c == 0:
                        if current_fixed:
                            pass  # 边界格子已固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        # 非边界：两侧都固定才隐藏
                        left_fixed = determined_mask and determined_mask[r][c-1]
                        if current_fixed and left_fixed:
                            pass  # 两侧都固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                # 右方向
                if dir_state[r][c][RIGHT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    # 边界矩形：只需当前格子固定就隐藏
                    if c == self.game.cols - 1:
                        if current_fixed:
                            pass  # 边界格子已固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        # 非边界：两侧都固定才隐藏
                        right_fixed = determined_mask and determined_mask[r][c+1]
                        if current_fixed and right_fixed:
                            pass  # 两侧都固定，跳过绘制
                        else:
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
        
        # 将指示器提升到最上层
        self.canvas.lift("deductive_indicator")
    
    def on_assumption_animation(self):
        """启动假设推理动画（先执行演绎推理动画）。"""
        if self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        self.start_assumption_after_deductive = True
        self.on_deductive_animation()
    
    def update_assumption_animation(self):
        """更新假设推理动画。"""
        if not self.assumption_animating or not self.assumption_solver:
            return
        
        step_info = self.assumption_solver.step()
        
        self.draw_assumption_step(step_info)
        
        self.show_assumption_info(step_info)
        
        if step_info['finished'] or step_info['failed']:
            self.assumption_animating = False
            self.assumption_solver = None
            
            if step_info['finished'] and not step_info['failed']:
                solution = step_info['solution']
                determined_mask = step_info['determined_mask']
                if solution and determined_mask:
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            if determined_mask[r][c]:
                                self.game.grid[r][c] = solution[r][c]
                                self.game.locked[r][c] = True
                    self.game.used_solver = True
                    self.draw_grid()
                    
                    determined_count = sum(sum(row) for row in determined_mask)
                    messagebox.showinfo("假设推理完成", f"假设推理成功！确定了 {determined_count} 个格子")
            elif step_info['failed']:
                self.draw_grid()
                messagebox.showinfo("假设推理失败", "无法继续推理，请尝试其他方法")
            return
        
        self.assumption_animation_timer = self.master.after(
            self.generation_speed, self.update_assumption_animation
        )
    
    def on_search_animation(self):
        """启动搜索求解动画。"""
        if self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        from animated_solvers.animated_search_solver import AnimatedSearchSolver
        
        self.search_animating = True
        self.search_solver = AnimatedSearchSolver(
            self.game.rows, self.game.cols, self.game.start,
            [row[:] for row in self.game.grid],
            locked=[row[:] for row in self.game.locked]
        )
        
        # 开始动画循环
        self.update_search_animation()
    
    def update_search_animation(self):
        """更新搜索求解动画。"""
        if not self.search_animating or not self.search_solver:
            return
        
        try:
            # 执行一步搜索求解
            step_info = self.search_solver.step()
            
            # 绘制当前步骤
            self.draw_search_step(step_info)
            
            # 显示步骤信息
            self.show_search_info(step_info)
        
            # 检查是否完成或失败
            if step_info['finished'] or step_info['failed']:
                self.search_animating = False
                self.search_solver = None
                
                if step_info['finished']:
                    # 应用最终结果
                    solution = step_info['solution']
                    determined_mask = step_info['determined_mask']
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            self.game.grid[r][c] = solution[r][c]
                    for r in range(self.game.rows):
                        for c in range(self.game.cols):
                            if determined_mask[r][c] and not self.game.locked[r][c]:
                                self.game.locked[r][c] = True
                    self.game.used_solver = True
                    self.draw_grid()
                    
                    determined_count = sum(sum(row) for row in determined_mask)
                    self.show_search_info({'type': 'finish', 'determined_count': determined_count})
                    messagebox.showinfo("搜索求解完成", f"搜索求解成功！确定了 {determined_count} 个格子")
                elif step_info['failed']:
                    self.draw_grid()
                    self.show_search_info({'type': 'fail'})
                    messagebox.showerror("搜索求解失败", "无法找到有效解，请检查锁定格子是否正确")
                return
            
            # 继续下一步
            self.search_animation_timer = self.master.after(
                self.generation_speed, self.update_search_animation
            )
        except tk.TclError:
            # Canvas已被销毁，清理状态
            self.search_animating = False
            self.search_solver = None
            self.search_animation_timer = None
    
    def draw_assumption_step(self, step_info):
        """绘制假设推理步骤。
        
        Args:
            step_info: 步骤信息字典
        """
        self.canvas.delete("all")
        
        if step_info['finished'] or step_info['failed']:
            self.draw_grid()
            return
        
        dir_state = step_info.get('dir_state')
        if not dir_state:
            self.draw_grid()
            return
        
        determined_mask = step_info.get('determined_mask')
        solution = step_info.get('solution')
        
        # 构建 test_grid 时，先检查是否在假设测试阶段
        step_type = step_info.get('type', '')
        is_testing = step_type in ('assumption_test', 'deductive_update_dir', 
                                   'deductive_apply_non_openings', 'deductive_apply_openings',
                                   'assumption_exclude', 'assumption_keep')
        
        # 如果是在测试假设，使用 step_info 中的 candidates 来构建 test_grid
        candidates = step_info.get('candidates')
        
        test_grid = [[[] for _ in range(self.game.cols)] for _ in range(self.game.rows)]
        
        if is_testing and candidates:
            # 使用 candidates 构建 test_grid
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    cand = candidates[r][c]
                    if cand:
                        # 检查候选集是否只有一个旋转
                        orig = self.game.grid[r][c]
                        possible_openings = set()
                        for rot in cand:
                            rotated = sorted([(d + rot) % 4 for d in orig])
                            possible_openings.add(tuple(rotated))
                        if len(possible_openings) == 1:
                            # 只有一个可能的旋转，确定该格子
                            rot = next(iter(cand))
                            test_grid[r][c] = [(d + rot) % 4 for d in orig]
                        else:
                            # 多个可能的旋转，不确定，使用原始管道
                            test_grid[r][c] = orig[:]
                    else:
                        # 候选集为空，使用原始管道
                        test_grid[r][c] = self.game.grid[r][c][:]
        else:
            # 非测试阶段，使用原来的逻辑，但未确定的格子使用原始管道
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask and determined_mask[r][c]:
                        if solution:
                            test_grid[r][c] = solution[r][c]
                        else:
                            test_grid[r][c] = self.game.grid[r][c][:]
                    else:
                        # 未确定的格子使用原始管道
                        test_grid[r][c] = self.game.grid[r][c][:]
        
        # 确保起始点有开口
        if not test_grid[self.game.start[0]][self.game.start[1]]:
            test_grid[self.game.start[0]][self.game.start[1]] = self.game.grid[self.game.start[0]][self.game.start[1]][:]
        
        water = self.game.calculate_water_flow(test_grid)
        water_cycles, dry_cycles = self.game.detect_cycles(water, test_grid)
        closed_components = self.game.detect_closed_paths(water, test_grid)
        
        closed_paths = [[False] * self.game.cols for _ in range(self.game.rows)]
        for component in closed_components:
            for r, c in component:
                closed_paths[r][c] = True
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_width >= canvas_width:
            h_offset = 0
        else:
            h_offset = (canvas_width - board_width) // 2
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for c in range(self.game.cols):
                x = c * self.cell_size + h_offset + self.cell_size // 2
                y = v_offset - 15
                self.canvas.create_text(
                    x, y,
                    text=str(c),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for r in range(self.game.rows):
                x = h_offset - 15
                y = r * self.cell_size - self.scroll_offset + v_offset + self.cell_size // 2
                self.canvas.create_text(
                    x, y,
                    text=str(r),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        determined_mask = step_info.get('determined_mask')
        solution = step_info.get('solution')
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x1 = c * self.cell_size + h_offset
                y1 = r * self.cell_size - self.scroll_offset + v_offset
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                
                is_test_determined = determined_mask and determined_mask[r][c] and not self.game.locked[r][c]
                is_locked = self.game.locked[r][c]
                
                if is_test_determined:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='#D3D3D3')
                elif is_locked:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='#D3D3D3')
                else:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='white')
                
                if is_test_determined and solution:
                    openings = solution[r][c]
                    base_type, angle = pipe_image_info(openings)
                    if water[r][c]:
                        if self.show_cycles and water_cycles[r][c]:
                            image_type = f'{base_type}_water_red'
                        else:
                            image_type = f'{base_type}_water'
                    else:
                        if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                            image_type = f'{base_type}_red'
                        else:
                            image_type = base_type
                    rotated_image = self.get_rotated_image(image_type, angle)
                    if rotated_image:
                        self.canvas.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=rotated_image)
                    else:
                        symbol = pipe_symbol(openings)
                        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=symbol, font=("Courier", 24), fill='black')
                else:
                    openings = test_grid[r][c] if test_grid[r][c] else self.game.grid[r][c]
                    base_type, angle = pipe_image_info(openings)
                    if water[r][c]:
                        if self.show_cycles and water_cycles[r][c]:
                            image_type = f'{base_type}_water_red'
                        else:
                            image_type = f'{base_type}_water'
                    else:
                        if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                            image_type = f'{base_type}_red'
                        else:
                            image_type = base_type
                    rotated_image = self.get_rotated_image(image_type, angle)
                    if rotated_image:
                        self.canvas.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=rotated_image)
                    else:
                        symbol = pipe_symbol(openings)
                        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=symbol, font=("Courier", 24), fill='black')
                
                if (r, c) == self.game.start:
                    self.canvas.create_rectangle(x1+2, y1+2, x2-2, y2-2, outline='blue', width=3)
        
        # 获取假设目标格子
        assumption_cell = step_info.get('assumption_cell')
        
        # 获取当前正在检查的格子
        checking_cell = step_info.get('checking_cell')
        
        # 获取假设目标的原始候选数量和已排除的候选数量
        assumption_original_count = step_info.get('assumption_original_count', 1)
        assumption_excluded_count = step_info.get('assumption_excluded_count', 0)
        
        # 显示正在检查的格子（红色）- 优先显示
        if checking_cell:
            r, c = checking_cell
            cell_x1 = h_offset + c * self.cell_size
            cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
            cell_x2 = cell_x1 + self.cell_size
            cell_y2 = cell_y1 + self.cell_size
            self.canvas.create_rectangle(
                cell_x1, cell_y1, cell_x2, cell_y2,
                outline="#FF0000", width=3, tags="deductive_indicator"
            )
        
        # 显示假设目标格子
        if assumption_cell:
            r, c = assumption_cell
            cell_x1 = h_offset + c * self.cell_size
            cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
            cell_x2 = cell_x1 + self.cell_size
            cell_y2 = cell_y1 + self.cell_size
            
            # 判断逻辑：
            # - 原始候选数量 > 1 且 已排除数量 + 1 == 原始候选数量：真正确定，绿色
            # - 其他情况：还在测试，黄色
            if assumption_original_count > 1 and (assumption_excluded_count + 1 == assumption_original_count):
                # 真正确定了：绿色边框
                self.canvas.create_rectangle(
                    cell_x1, cell_y1, cell_x2, cell_y2,
                    outline="#00FF00", width=3, tags="deductive_indicator"
                )
            else:
                # 还在测试中：黄色边框
                self.canvas.create_rectangle(
                    cell_x1, cell_y1, cell_x2, cell_y2,
                    outline="#FFD700", width=4, tags="deductive_indicator"
                )
        
        indicator_size = self.cell_size // 4
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell_x1 = h_offset + c * self.cell_size
                cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
                cell_x2 = cell_x1 + self.cell_size
                cell_y2 = cell_y1 + self.cell_size
                cell_center_x = (cell_x1 + cell_x2) // 2
                cell_center_y = (cell_y1 + cell_y2) // 2
                
                if dir_state[r][c][UP] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if r == 0:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        upper_fixed = determined_mask and determined_mask[r-1][c]
                        if not (current_fixed and upper_fixed):
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][DOWN] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if r == self.game.rows - 1:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        lower_fixed = determined_mask and determined_mask[r+1][c]
                        if not (current_fixed and lower_fixed):
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][LEFT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if c == 0:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        left_fixed = determined_mask and determined_mask[r][c-1]
                        if not (current_fixed and left_fixed):
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][RIGHT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if c == self.game.cols - 1:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        right_fixed = determined_mask and determined_mask[r][c+1]
                        if not (current_fixed and right_fixed):
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
        
        self.canvas.lift("deductive_indicator")
    
    def _draw_pipe_in_cell(self, r, c, openings, h_offset, v_offset):
        """在指定格子中绘制水管。
        
        Args:
            r: 行索引
            c: 列索引
            openings: 开口方向列表
            h_offset: 水平偏移量
            v_offset: 垂直偏移量
        """
        cell_x1 = h_offset + c * self.cell_size
        cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
        cell_x2 = cell_x1 + self.cell_size
        cell_y2 = cell_y1 + self.cell_size
        
        base_type, angle = pipe_image_info(openings)
        rotated_image = self.get_rotated_image(base_type, angle)
        
        if rotated_image:
            self.canvas.create_image(
                (cell_x1 + cell_x2) // 2, (cell_y1 + cell_y2) // 2,
                image=rotated_image,
                tags="assumption_temp_bg"
            )
        else:
            symbol = pipe_symbol(openings)
            self.canvas.create_text(
                (cell_x1 + cell_x2) // 2, (cell_y1 + cell_y2) // 2,
                text=symbol, font=("Courier", 24), fill='black',
                tags="assumption_temp_bg"
            )
    
    def draw_search_step(self, step_info):
        """绘制搜索求解步骤。
        
        Args:
            step_info: 步骤信息字典
        """
        self.canvas.delete("all")
        
        if step_info['finished'] or step_info['failed']:
            self.draw_grid()
            return
        
        dir_state = step_info.get('dir_state')
        if not dir_state:
            self.draw_grid()
            return
        
        determined_mask = step_info.get('determined_mask')
        solution = step_info.get('solution')
        candidates = step_info.get('candidates')
        
        step_type = step_info.get('type', '')
        is_dfs_phase = step_type.startswith('dfs_')
        
        test_grid = [[[] for _ in range(self.game.cols)] for _ in range(self.game.rows)]
        
        if is_dfs_phase and candidates:
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    cand = candidates[r][c]
                    if cand:
                        orig = self.game.grid[r][c]
                        possible_openings = set()
                        for rot in cand:
                            rotated = sorted([(d + rot) % 4 for d in orig])
                            possible_openings.add(tuple(rotated))
                        if len(possible_openings) == 1:
                            rot = next(iter(cand))
                            test_grid[r][c] = [(d + rot) % 4 for d in orig]
                        else:
                            test_grid[r][c] = orig[:]
                    else:
                        test_grid[r][c] = self.game.grid[r][c][:]
        else:
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask and determined_mask[r][c]:
                        if solution:
                            test_grid[r][c] = solution[r][c]
                        else:
                            test_grid[r][c] = self.game.grid[r][c][:]
                    else:
                        test_grid[r][c] = self.game.grid[r][c][:]
        
        if not test_grid[self.game.start[0]][self.game.start[1]]:
            test_grid[self.game.start[0]][self.game.start[1]] = self.game.grid[self.game.start[0]][self.game.start[1]][:]
        
        water = self.game.calculate_water_flow(test_grid)
        water_cycles, dry_cycles = self.game.detect_cycles(water, test_grid)
        closed_components = self.game.detect_closed_paths(water, test_grid)
        
        closed_paths = [[False] * self.game.cols for _ in range(self.game.rows)]
        for component in closed_components:
            for r, c in component:
                closed_paths[r][c] = True
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        board_width = self.game.cols * self.cell_size
        board_height = self.game.rows * self.cell_size
        
        coord_left_space = 25 if self.show_grid_coordinates else 0
        coord_top_space = 25 if self.show_grid_coordinates else 0
        coord_bottom_space = 5 if self.show_grid_coordinates else 0
        
        if board_width >= canvas_width:
            h_offset = 0
        else:
            h_offset = (canvas_width - board_width) // 2
        
        if board_height <= canvas_height:
            v_offset = (canvas_height - board_height - coord_top_space - coord_bottom_space) // 2
        else:
            v_offset = 0
        
        if self.show_grid_coordinates:
            h_offset += coord_left_space // 2
            v_offset += coord_top_space
        
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for c in range(self.game.cols):
                x = c * self.cell_size + h_offset + self.cell_size // 2
                y = v_offset - 15
                self.canvas.create_text(
                    x, y,
                    text=str(c),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        if self.show_grid_coordinates:
            coord_font_size = max(9, min(17, self.cell_size // 3 + 2))
            for r in range(self.game.rows):
                x = h_offset - 15
                y = r * self.cell_size - self.scroll_offset + v_offset + self.cell_size // 2
                self.canvas.create_text(
                    x, y,
                    text=str(r),
                    font=(CHINESE_FONT_MONO, coord_font_size),
                    fill="#252525",
                    anchor='center'
                )
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x1 = c * self.cell_size + h_offset
                y1 = r * self.cell_size - self.scroll_offset + v_offset
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                
                is_test_determined = determined_mask and determined_mask[r][c] and not self.game.locked[r][c]
                is_locked = self.game.locked[r][c]
                
                if is_test_determined:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='#D3D3D3')
                elif is_locked:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='#D3D3D3')
                else:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline='#CCCCCC', fill='white')
                
                if is_test_determined and solution:
                    openings = solution[r][c]
                    base_type, angle = pipe_image_info(openings)
                    if water[r][c]:
                        if self.show_cycles and water_cycles[r][c]:
                            image_type = f'{base_type}_water_red'
                        else:
                            image_type = f'{base_type}_water'
                    else:
                        if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                            image_type = f'{base_type}_red'
                        else:
                            image_type = base_type
                    rotated_image = self.get_rotated_image(image_type, angle)
                    if rotated_image:
                        self.canvas.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=rotated_image)
                    else:
                        symbol = pipe_symbol(openings)
                        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=symbol, font=("Courier", 24), fill='black')
                else:
                    openings = test_grid[r][c] if test_grid[r][c] else self.game.grid[r][c]
                    base_type, angle = pipe_image_info(openings)
                    if water[r][c]:
                        if self.show_cycles and water_cycles[r][c]:
                            image_type = f'{base_type}_water_red'
                        else:
                            image_type = f'{base_type}_water'
                    else:
                        if (self.show_cycles and dry_cycles[r][c]) or (self.show_closed_paths and closed_paths[r][c]):
                            image_type = f'{base_type}_red'
                        else:
                            image_type = base_type
                    rotated_image = self.get_rotated_image(image_type, angle)
                    if rotated_image:
                        self.canvas.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=rotated_image)
                    else:
                        symbol = pipe_symbol(openings)
                        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=symbol, font=("Courier", 24), fill='black')
                
                if (r, c) == self.game.start:
                    self.canvas.create_rectangle(x1+2, y1+2, x2-2, y2-2, outline='blue', width=3)
        
        search_cell = step_info.get('search_cell')
        checking_cell = step_info.get('checking_cell')
        dfs_depth = step_info.get('dfs_depth', 0)
        
        if checking_cell:
            r, c = checking_cell
            cell_x1 = h_offset + c * self.cell_size
            cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
            cell_x2 = cell_x1 + self.cell_size
            cell_y2 = cell_y1 + self.cell_size
            self.canvas.create_rectangle(
                cell_x1, cell_y1, cell_x2, cell_y2,
                outline="#FF0000", width=3, tags="deductive_indicator"
            )
        
        assumption_history = step_info.get('assumption_history', [])
        for hist_cell in assumption_history:
            if hist_cell != search_cell:
                r, c = hist_cell
                cell_x1 = h_offset + c * self.cell_size
                cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
                cell_x2 = cell_x1 + self.cell_size
                cell_y2 = cell_y1 + self.cell_size
                self.canvas.create_rectangle(
                    cell_x1, cell_y1, cell_x2, cell_y2,
                    outline="#7DB300", width=3, tags="deductive_indicator"
                )
        
        if search_cell:
            r, c = search_cell
            cell_x1 = h_offset + c * self.cell_size
            cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
            cell_x2 = cell_x1 + self.cell_size
            cell_y2 = cell_y1 + self.cell_size
            
            if checking_cell and search_cell == checking_cell:
                pass
            else:
                self.canvas.create_rectangle(
                    cell_x1, cell_y1, cell_x2, cell_y2,
                    outline="#FFD700", width=4, tags="deductive_indicator"
                )
        
        indicator_size = self.cell_size // 4
        
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell_x1 = h_offset + c * self.cell_size
                cell_y1 = v_offset + (r * self.cell_size) - self.scroll_offset
                cell_x2 = cell_x1 + self.cell_size
                cell_y2 = cell_y1 + self.cell_size
                cell_center_x = (cell_x1 + cell_x2) // 2
                cell_center_y = (cell_y1 + cell_y2) // 2
                
                if dir_state[r][c][UP] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if r == 0:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        upper_fixed = determined_mask and determined_mask[r-1][c]
                        if not (current_fixed and upper_fixed):
                            color = "#00FF00" if dir_state[r][c][UP] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y1,
                                cell_center_x + rect_width // 2,
                                cell_y1 + rect_height,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][DOWN] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if r == self.game.rows - 1:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        lower_fixed = determined_mask and determined_mask[r+1][c]
                        if not (current_fixed and lower_fixed):
                            color = "#00FF00" if dir_state[r][c][DOWN] else "#FF0000"
                            rect_width = int(indicator_size * 2 * 0.75)
                            rect_height = int(indicator_size // 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_center_x - rect_width // 2,
                                cell_y2 - rect_height,
                                cell_center_x + rect_width // 2,
                                cell_y2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][LEFT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if c == 0:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        left_fixed = determined_mask and determined_mask[r][c-1]
                        if not (current_fixed and left_fixed):
                            color = "#00FF00" if dir_state[r][c][LEFT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x1,
                                cell_center_y - rect_height // 2,
                                cell_x1 + rect_width,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                
                if dir_state[r][c][RIGHT] is not None:
                    current_fixed = determined_mask and determined_mask[r][c]
                    if c == self.game.cols - 1:
                        if not current_fixed:
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
                    else:
                        right_fixed = determined_mask and determined_mask[r][c+1]
                        if not (current_fixed and right_fixed):
                            color = "#00FF00" if dir_state[r][c][RIGHT] else "#FF0000"
                            rect_width = int(indicator_size // 2 * 0.75)
                            rect_height = int(indicator_size * 2 * 0.75)
                            self.canvas.create_rectangle(
                                cell_x2 - rect_width,
                                cell_center_y - rect_height // 2,
                                cell_x2,
                                cell_center_y + rect_height // 2,
                                fill=color, outline="", tags="deductive_indicator"
                            )
        
        self.canvas.lift("deductive_indicator")
    
    def show_assumption_info(self, step_info):
        """显示假设推理步骤信息。
        
        Args:
            step_info: 步骤信息字典
        """
        info_text = ""
        step_type = step_info.get('type', '')
        
        assumption_original_count = step_info.get('assumption_original_count', 1)
        assumption_excluded_count = step_info.get('assumption_excluded_count', 0)
        
        if step_type == 'fail':
            info_text = "假设推理失败！"
        elif step_type == 'victory':
            info_text = "假设推理成功！找到胜利解！"
        elif step_type == 'finish':
            determined_count = sum(sum(row) for row in step_info.get('determined_mask', []))
            info_text = f"假设推理完成！确定了 {determined_count} 个格子"
        elif step_type == 'assumption_start':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                remaining = assumption_original_count - assumption_excluded_count
                info_text = f"假设目标：格子 ({r}, {c})，候选方向: {remaining} 个"
        elif step_type == 'assumption_test':
            cell = step_info.get('cell')
            rot = step_info.get('value')
            if cell:
                r, c = cell
                current_index = assumption_excluded_count + 1
                info_text = f"测试方向 {current_index}/{assumption_original_count}：格子 ({r}, {c}) 旋转 {rot * 90}°"
        elif step_type == 'deductive_update_dir':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：更新方向约束 ({r}, {c})"
        elif step_type == 'deductive_apply_non_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：排除无效方向 ({r}, {c})"
        elif step_type == 'deductive_apply_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：确定有效方向 ({r}, {c})"
        elif step_type == 'assumption_exclude':
            cell = step_info.get('cell')
            rot = step_info.get('value')
            if cell:
                r, c = cell
                remaining = assumption_original_count - assumption_excluded_count - 1
                info_text = f"矛盾！排除方向 {rot * 90}°，剩余候选: {remaining} 个"
        elif step_type == 'assumption_keep':
            cell = step_info.get('cell')
            rot = step_info.get('value')
            if cell:
                r, c = cell
                remaining = assumption_original_count - assumption_excluded_count - 1
                if remaining > 0:
                    info_text = f"方向 {rot * 90}° 无矛盾，保留。继续测试剩余 {remaining} 个候选"
                else:
                    info_text = f"方向 {rot * 90}° 无矛盾，剩余 1 个候选，格子已确定！"
        elif step_type == 'assumption_fail':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"假设失败：格子 ({r}, {c}) 所有方向都矛盾"
        elif step_type.endswith('_fail'):
            info_text = f"推理失败：{step_type}"
        
        if not info_text:
            return
        
        if self.generation_info_timer is not None:
            self.master.after_cancel(self.generation_info_timer)
        
        self.generation_info_label.config(text=info_text)
        self.generation_info_label.lift()
        self.generation_info_label.place(relx=0.5, y=60, anchor='center')
        
        self.generation_info_timer = self.master.after(2000, self.clear_generation_info)
    
    def show_search_info(self, step_info):
        """显示搜索求解步骤信息。
        
        Args:
            step_info: 步骤信息字典
        """
        info_text = ""
        step_type = step_info.get('type', '')
        dfs_depth = step_info.get('dfs_depth', 0)
        
        if step_type == 'fail':
            info_text = "搜索求解失败！"
        elif step_type == 'victory':
            determined_count = step_info.get('determined_count', 0)
            info_text = f"搜索求解成功！找到胜利解！确定了 {determined_count} 个格子"
        elif step_type == 'finish':
            determined_count = step_info.get('determined_count', 0)
            info_text = f"搜索求解完成！确定了 {determined_count} 个格子"
        elif step_type == 'init':
            info_text = "搜索求解：初始化候选集和方向状态"
        elif step_type == 'deductive_update_dir':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：更新方向约束 ({r}, {c})"
        elif step_type == 'deductive_apply_non_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：排除无效方向 ({r}, {c})"
        elif step_type == 'deductive_apply_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"演绎推理：确定有效方向 ({r}, {c})"
        elif step_type == 'dfs_start':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS搜索开始：选择格子 ({r}, {c}) 作为搜索起点"
        elif step_type == 'dfs_test_rot':
            cell = step_info.get('cell')
            rot = step_info.get('value')
            rot_index = step_info.get('rot_index', 1)
            rot_total = step_info.get('rot_total', 1)
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：测试格子 ({r}, {c}) 旋转 {rot * 90}° [{rot_index}/{rot_total}]"
        elif step_type == 'dfs_deductive_update_dir':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：演绎推理更新方向 ({r}, {c})"
        elif step_type == 'dfs_deductive_apply_non_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：演绎推理排除无效方向 ({r}, {c})"
        elif step_type == 'dfs_deductive_apply_openings':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：演绎推理确定有效方向 ({r}, {c})"
        elif step_type == 'dfs_conflict':
            cell = step_info.get('cell')
            rot = step_info.get('value')
            rot_index = step_info.get('rot_index', 0)
            rot_total = step_info.get('rot_total', 1)
            if cell and rot is not None:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：矛盾！格子 ({r}, {c}) 旋转 {rot * 90}° 无效，尝试下一个 [{rot_index}/{rot_total}]"
            elif cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：矛盾！格子 ({r}, {c}) 测试失败"
        elif step_type == 'dfs_next_level':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：进入下一层，选择格子 ({r}, {c})"
        elif step_type == 'dfs_backtrack':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS深度 {dfs_depth}：回溯到格子 ({r}, {c})，尝试其他候选"
        elif step_type == 'dfs_exhausted':
            cell = step_info.get('cell')
            if cell:
                r, c = cell
                info_text = f"DFS搜索失败：格子 ({r}, {c}) 所有候选都无效"
        elif step_type.endswith('_fail'):
            info_text = f"搜索求解失败：{step_type}"
        
        if not info_text:
            return
        
        if self.generation_info_timer is not None:
            self.master.after_cancel(self.generation_info_timer)
        
        self.generation_info_label.config(text=info_text)
        self.generation_info_label.lift()
        self.generation_info_label.place(relx=0.5, y=60, anchor='center')
        
        self.generation_info_timer = self.master.after(2000, self.clear_generation_info)
    
    def stop_assumption_animation(self):
        """停止假设推理动画。"""
        if self.assumption_animation_timer:
            self.master.after_cancel(self.assumption_animation_timer)
            self.assumption_animation_timer = None
        self.assumption_animating = False
        self.assumption_solver = None
        self.canvas.delete("deductive_indicator")
        self.canvas.delete("deductive_bg")
        self.draw_grid()
    
    def stop_search_animation(self):
        """停止搜索求解动画。"""
        if self.search_animation_timer:
            self.master.after_cancel(self.search_animation_timer)
            self.search_animation_timer = None
        self.search_animating = False
        self.search_solver = None
        self.canvas.delete("deductive_indicator")
        self.canvas.delete("deductive_bg")
        self.draw_grid()
    
    def on_assumption_no_animation(self):
        """假设推理（不播放动画，直接求解）。"""
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        result = solve_step2_assumption(self.game.rows, self.game.cols, self.game.start,
                                       [row[:] for row in self.game.grid],
                                       locked=[row[:] for row in self.game.locked])
        
        if result['success']:
            solution = result['solution']
            determined_mask = result['determined_mask']
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    self.game.grid[r][c] = solution[r][c]
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask[r][c] and not self.game.locked[r][c]:
                        self.game.locked[r][c] = True
            self.game.used_solver = True
            self.draw_grid()
            
            message = f"{result['step']}成功！确定了 {result['determined_count']} 个格子，需要旋转 {result['rotation_count']} 个格子"
            messagebox.showinfo("求解成功", message)
        else:
            messagebox.showerror("求解失败", f"{result['step']}未找到有效的部分解")
    
    def on_search_no_animation(self):
        """搜索求解（不播放动画，直接求解）。"""
        if self.game.victory or self.generating or self.deductive_animating or self.assumption_animating or self.search_animating:
            if self.generating:
                self.show_warning("⚠关卡生成中，请稍后")
            elif self.deductive_animating or self.assumption_animating or self.search_animating:
                self.show_warning("⚠动画播放中，请稍后")
            return
        
        result = solve_step3_search(self.game.rows, self.game.cols, self.game.start,
                                   [row[:] for row in self.game.grid],
                                   locked=[row[:] for row in self.game.locked])
        
        if result['success']:
            solution = result['solution']
            determined_mask = result['determined_mask']
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    self.game.grid[r][c] = solution[r][c]
            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    if determined_mask[r][c] and not self.game.locked[r][c]:
                        self.game.locked[r][c] = True
            self.game.used_solver = True
            self.draw_grid()
            
            message = f"{result['step']}成功！确定了 {result['determined_count']} 个格子，需要旋转 {result['rotation_count']} 个格子"
            messagebox.showinfo("求解成功", message)
        else:
            messagebox.showerror("求解失败", f"{result['step']}未找到有效的部分解")