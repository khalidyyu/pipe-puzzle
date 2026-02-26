import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from level_generator import generate_level
from game import GameState
from ui import PipeUI

class PipeGameApp:
    """水管工游戏应用程序类"""
    
    def __init__(self, root):
        """初始化游戏应用程序。
        
        Args:
            root: ttkbootstrap 根窗口
        """
        self.root = root
        self.root.title("水管工游戏")
        self.root.geometry("1100x900")
        self.root.resizable(True, True)
        self.ROWS, self.COLS = 5, 5
        self.main_frame = None
        self.start_new_game()
    
    def start_new_game(self, rows=None, cols=None, grid=None, start=None):
        """开始新游戏，生成新的关卡并重置UI。
        
        Args:
            rows: 棋盘行数，如果为None则使用当前值
            cols: 棋盘列数，如果为None则使用当前值
            grid: 自定义棋盘，如果提供则使用该棋盘而不是生成
            start: 水源位置，格式为 (行, 列)
        """
        if grid is not None:
            rows = len(grid)
            cols = len(grid[0]) if rows > 0 else 0
            if start is None:
                start = (rows // 2, cols // 2)
            self.game = GameState(rows, cols, start, grid)
            self.game.is_custom_level = True
        else:
            if rows is not None and cols is not None:
                self.ROWS, self.COLS = rows, cols
            
            start, grid = generate_level(self.ROWS, self.COLS, shuffle=True)
            self.game = GameState(self.ROWS, self.COLS, start, grid)
            self.game.is_custom_level = False
        
        if self.main_frame is not None:
            self.main_frame.destroy()
        
        self.app = PipeUI(self.root, self.game, self.restart_game, self.exit_game, self.change_board_size, self.import_level)
        self.main_frame = self.app.master.winfo_children()[-1]
    
    def change_board_size(self, rows, cols):
        """改变棋盘大小并开始新游戏。
        
        Args:
            rows: 新的行数
            cols: 新的列数
        """
        self.start_new_game(rows, cols)
    
    def import_level(self, grid, start=None):
        """导入自定义关卡并开始新游戏。
        
        Args:
            grid: 自定义棋盘列表
            start: 水源位置，格式为 (行, 列)
        """
        self.start_new_game(grid=grid, start=start)
    
    def restart_game(self):
        """再来一局，重新开始游戏。"""
        self.start_new_game()
    
    def exit_game(self):
        """退出游戏。"""
        self.root.quit()

def main():
    """程序入口函数，初始化游戏并启动GUI。"""
    root = ttk.Window(themename="cosmo")
    app = PipeGameApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
