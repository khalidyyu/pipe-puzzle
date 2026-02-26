import random
from constants import UP, RIGHT, DOWN, LEFT, DIR_VECTORS, OPPOSITE


class AnimatedLevelGenerator:
    """支持动画演示的关卡生成器"""
    
    def __init__(self, rows, cols, start, start_openings):
        """初始化生成器
        
        Args:
            rows: 行数
            cols: 列数
            start: 水源位置 (row, col)
            start_openings: 水源开口方向列表
        """
        self.rows = rows
        self.cols = cols
        self.start = start
        self.start_openings = start_openings
        
        # 初始化状态
        self.visited = [[False] * cols for _ in range(rows)]
        self.neighbors = [[[] for _ in range(cols)] for _ in range(rows)]
        self.active = []
        self.visited_count = 0
        self.total_cells = rows * cols
        self.current_step = 0
        self.finished = False
        self.failed = False
        
        # 初始化水源
        sr, sc = start
        self.visited[sr][sc] = True
        self.visited_count = 1
        
        # 处理水源开口
        for direction in start_openings:
            dr, dc = DIR_VECTORS[direction]
            nr, nc = sr + dr, sc + dc
            if 0 <= nr < rows and 0 <= nc < cols and not self.visited[nr][nc]:
                self.neighbors[sr][sc].append((nr, nc))
                self.neighbors[nr][nc].append((sr, sc))
                self.visited[nr][nc] = True
                self.visited_count += 1
                self.active.append((nr, nc))
        
        # 检查是否有有效的开口
        if not self.active and self.visited_count < self.total_cells:
            self.failed = True
            self.finished = True
    
    def step(self):
        """执行一步生成
        
        Returns:
            dict: 包含当前步骤信息的字典，格式为:
                {
                    'type': 'connect' | 'remove' | 'finish' | 'fail',
                    'cell': (row, col),  # 当前处理的格子
                    'neighbor': (row, col) | None,  # 连接的邻居（如果有）
                    'visited': [[bool]],  # 访问状态
                    'neighbors': [[list]],  # 邻居关系
                    'finished': bool,  # 是否完成
                    'failed': bool,  # 是否失败
                    'checking_leaf': (row, col) | None,  # 正在检查的叶子节点
                    'pending_leaves': [(row, col), ...]  # 待检查的叶子节点列表
                }
        """
        if self.finished:
            return {
                'type': 'finish' if not self.failed else 'fail',
                'cell': None,
                'neighbor': None,
                'visited': self.visited,
                'neighbors': self.neighbors,
                'finished': self.finished,
                'failed': self.failed,
                'checking_leaf': None,
                'pending_leaves': []
            }
        
        # 检查是否所有格子都被访问
        if self.visited_count >= self.total_cells:
            self.finished = True
            return {
                'type': 'finish',
                'cell': None,
                'neighbor': None,
                'visited': self.visited,
                'neighbors': self.neighbors,
                'finished': True,
                'failed': False,
                'checking_leaf': None,
                'pending_leaves': []
            }
        
        # 检查是否还有活跃格子
        if not self.active:
            self.failed = True
            self.finished = True
            return {
                'type': 'fail',
                'cell': None,
                'neighbor': None,
                'visited': self.visited,
                'neighbors': self.neighbors,
                'finished': True,
                'failed': True,
                'checking_leaf': None,
                'pending_leaves': []
            }
        
        # 随机选择一个活跃格子（叶子节点）
        idx = random.randint(0, len(self.active) - 1)
        r, c = self.active[idx]
        
        # 收集未访问邻居
        unvisited = []
        for dr, dc in DIR_VECTORS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols and not self.visited[nr][nc]:
                unvisited.append((nr, nc))
        
        if not unvisited:
            # 没有未访问邻居，从活跃列表中移除
            self.active.pop(idx)
            return {
                'type': 'remove',
                'cell': (r, c),
                'neighbor': None,
                'visited': self.visited,
                'neighbors': self.neighbors,
                'finished': False,
                'failed': False,
                'checking_leaf': (r, c),
                'pending_leaves': list(self.active)
            }
        
        # 当前格子的度数（已连接数）
        current_degree = len(self.neighbors[r][c])
        max_degree = 2 if (r, c) == self.start else 3
        if current_degree >= max_degree:
            # 度数已满，不能再连接，移除
            self.active.pop(idx)
            return {
                'type': 'remove',
                'cell': (r, c),
                'neighbor': None,
                'visited': self.visited,
                'neighbors': self.neighbors,
                'finished': False,
                'failed': False,
                'checking_leaf': (r, c),
                'pending_leaves': list(self.active)
            }
        
        # 随机选择一个未访问邻居
        nr, nc = random.choice(unvisited)
        
        # 建立连接
        self.neighbors[r][c].append((nr, nc))
        self.neighbors[nr][nc].append((r, c))
        self.visited[nr][nc] = True
        self.visited_count += 1
        
        # 新格子加入活跃列表
        self.active.append((nr, nc))
        
        # 检查当前格子度数是否已满
        if len(self.neighbors[r][c]) >= max_degree:
            self.active.pop(idx)
        
        self.current_step += 1
        
        return {
            'type': 'connect',
            'cell': (r, c),
            'neighbor': (nr, nc),
            'visited': self.visited,
            'neighbors': self.neighbors,
            'finished': False,
            'failed': False,
            'checking_leaf': (r, c),
            'pending_leaves': list(self.active)
        }
    
    def get_grid(self):
        """根据当前邻居关系生成网格
        
        Returns:
            list: 二维列表，每个元素是该格子的开口方向列表
        """
        grid = [[[] for _ in range(self.cols)] for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) == self.start:
                    grid[r][c] = self.start_openings
                else:
                    dirs = []
                    for nr, nc in self.neighbors[r][c]:
                        if nr == r - 1:
                            dirs.append(UP)
                        elif nr == r + 1:
                            dirs.append(DOWN)
                        elif nc == c - 1:
                            dirs.append(LEFT)
                        elif nc == c + 1:
                            dirs.append(RIGHT)
                    grid[r][c] = dirs
        return grid


def generate_animated_level(rows, cols, max_attempts=10):
    """生成一个支持动画演示的关卡
    
    Args:
        rows: 行数
        cols: 列数
        max_attempts: 最大尝试次数
    
    Returns:
        tuple: (generator, start, start_openings) 或 None（失败）
    """
    if rows < 2 or cols < 2:
        raise ValueError("Grid must be at least 2x2")
    
    start = (rows // 2, cols // 2)
    
    # 随机选择水源格子的类型
    start_type = random.choice(['end', 'corner', 'straight', 't'])
    start_openings = []
    
    if start_type == 'end':
        start_openings = [random.choice([UP, RIGHT, DOWN, LEFT])]
    elif start_type == 'corner':
        if start[0] > 0 and start[1] > 0:
            start_openings = [UP, RIGHT]
        elif start[0] > 0 and start[1] < cols - 1:
            start_openings = [UP, LEFT]
        elif start[0] < rows - 1 and start[1] > 0:
            start_openings = [DOWN, RIGHT]
        else:
            start_openings = [DOWN, LEFT]
    elif start_type == 'straight':
        if random.choice([True, False]):
            start_openings = [UP, DOWN]
        else:
            start_openings = [LEFT, RIGHT]
    elif start_type == 't':
        start_openings = [UP, RIGHT, DOWN]
        if random.choice([True, False]):
            start_openings = [UP, RIGHT, LEFT]
        elif random.choice([True, False]):
            start_openings = [UP, DOWN, LEFT]
        else:
            start_openings = [RIGHT, DOWN, LEFT]
    
    # 检查水源开口方向是否都在边界内
    valid_openings = []
    for direction in start_openings:
        dr, dc = DIR_VECTORS[direction]
        nr, nc = start[0] + dr, start[1] + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            valid_openings.append(direction)
    
    if not valid_openings:
        return generate_animated_level(rows, cols, max_attempts)
    
    start_openings = valid_openings
    
    # 尝试生成
    for _ in range(max_attempts):
        generator = AnimatedLevelGenerator(rows, cols, start, start_openings)
        # 预先生成检查是否成功
        temp_gen = AnimatedLevelGenerator(rows, cols, start, start_openings)
        while not temp_gen.finished:
            temp_gen.step()
        if not temp_gen.failed:
            return generator, start, start_openings
    
    return None
