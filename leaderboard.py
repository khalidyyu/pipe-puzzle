import json
import os
from datetime import datetime, timezone, timedelta

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

def get_leaderboard_path():
    """获取排行榜文件路径。
    
    Returns:
        str: 排行榜文件的完整路径
    """
    return os.path.join(get_config_dir(), 'leaderboard.json')

LEADERBOARD_FILE = get_leaderboard_path()

class Leaderboard:
    """排行榜管理类，负责保存和读取游戏成绩。"""
    
    def __init__(self):
        """初始化排行榜管理器。"""
        self.records = self.load_records()
    
    def load_records(self):
        """从文件加载排行榜记录。
        
        Returns:
            dict: 排行榜记录字典
        """
        if os.path.exists(LEADERBOARD_FILE):
            try:
                with open(LEADERBOARD_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_records(self):
        """保存排行榜记录到文件。"""
        try:
            with open(LEADERBOARD_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False
    
    def add_record(self, board_size, time_used):
        """添加一条新的成绩记录。
        
        Args:
            board_size: 棋盘大小字符串，如 "5x5"
            time_used: 用时（秒）
            
        Returns:
            bool: 是否成功保存
        """
        if board_size not in self.records:
            self.records[board_size] = []
        
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        
        new_record = {
            'time': time_used,
            'timestamp': timestamp
        }
        
        self.records[board_size].append(new_record)
        
        # 按时间排序，保留前10名
        self.records[board_size].sort(key=lambda x: x['time'])
        self.records[board_size] = self.records[board_size][:10]
        
        return self.save_records()
    
    def get_personal_best(self, board_size):
        """获取指定棋盘大小的个人最好成绩。
        
        Args:
            board_size: 棋盘大小字符串，如 "5x5"
            
        Returns:
            list: 个人最好成绩列表
        """
        if board_size in self.records:
            return self.records[board_size]
        return []
    
    def get_all_personal_best(self):
        """获取所有棋盘大小的个人最好成绩。
        
        Returns:
            dict: 所有个人最好成绩字典
        """
        return self.records
    
    def reset_records(self):
        """清空所有排行榜记录。
        
        Returns:
            bool: 是否成功清空
        """
        self.records = {}
        return self.save_records()