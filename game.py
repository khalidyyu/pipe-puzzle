from constants import UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
import time
from collections import deque

class GameState:
    """管理游戏状态的类，包括网格、锁定状态和胜利检测。"""
    
    def __init__(self, rows, cols, start, grid):
        """初始化游戏状态。
        
        Args:
            rows: 网格行数
            cols: 网格列数
            start: 起始位置 (row, col)
            grid: 2D列表，每个单元格包含方向开口列表
        """
        self.rows = rows
        self.cols = cols
        self.start = start
        self.grid = grid
        self.victory = False
        self.locked = [[False] * cols for _ in range(rows)]
        self.start_time = time.time()
        self.end_time = None
        self.is_custom_level = False  # 标记是否为导入的关卡
        self.used_solver = False  # 标记是否使用了求解器
        self.is_generated_level = False  # 标记是否为生成的关卡

    def rotate_cell(self, r, c):
        """将位置(r, c)的单元格顺时针旋转90度。
        
        Args:
            r: 行索引
            c: 列索引
        """
        if self.victory:
            return
        if self.locked[r][c]:
            return
        self.grid[r][c] = [(d + 1) % 4 for d in self.grid[r][c]]

    def toggle_lock(self, r, c):
        """切换位置(r, c)的单元格的锁定状态。
        
        Args:
            r: 行索引
            c: 列索引
        """
        if self.victory:
            return
        self.locked[r][c] = not self.locked[r][c]

    def check_victory(self):
        """检查是否满足胜利条件：所有格子被恰好访问一次，且管道连接正确。
        
        Returns:
            bool: 如果满足胜利条件返回True，否则返回False
        """
        visited = [[0] * self.cols for _ in range(self.rows)]
        fail_reason = [None]

        def dfs(r, c, enter_dir):
            """深度优先搜索检查管道连接。
            
            Args:
                r: 当前行
                c: 当前列
                enter_dir: 进入方向，None表示起始点
                
            Returns:
                bool: 连接正确返回True，否则返回False
            """
            if enter_dir is not None:
                if OPPOSITE[enter_dir] not in self.grid[r][c]:
                    fail_reason[0] = f"入口不匹配 at ({r},{c}), enter_dir={enter_dir}, openings={self.grid[r][c]}"
                    return False

            visited[r][c] += 1
            if visited[r][c] > 1:
                fail_reason[0] = f"重复访问 at ({r},{c})"
                return False

            for d in self.grid[r][c]:
                if enter_dir is not None and d == OPPOSITE[enter_dir]:
                    continue
                dr, dc = DIR_VECTORS[d]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    fail_reason[0] = f"越界 at ({r},{c}) 方向 {d} 到 ({nr},{nc})"
                    return False
                if not dfs(nr, nc, d):
                    return False
            return True

        result = dfs(self.start[0], self.start[1], None)
        if not result:
            return False

        for r in range(self.rows):
            for c in range(self.cols):
                if visited[r][c] != 1:
                    return False
        return True

    def get_elapsed_time(self):
        """获取游戏已用时间（秒）。
        
        Returns:
            float: 已用时间（秒），如果游戏结束则返回总用时
        """
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def stop_timer(self):
        """停止计时器，记录结束时间。"""
        if not self.end_time:
            self.end_time = time.time()

    def calculate_water_flow(self, grid=None):
        """计算水流路径，返回标记有水的网格。
        
        Args:
            grid: 可选的网格，如果提供则使用该网格，否则使用 self.grid
        
        Returns:
            list: 2D布尔列表，True表示该格子有水流过
        """
        if grid is None:
            grid = self.grid
        
        water = [[False] * self.cols for _ in range(self.rows)]
        
        def dfs(r, c, enter_dir):
            """深度优先搜索计算水流路径。
            
            Args:
                r: 当前行
                c: 当前列
                enter_dir: 进入方向，None表示起始点
            """
            if water[r][c]:
                return
            
            if enter_dir is not None:
                if OPPOSITE[enter_dir] not in grid[r][c]:
                    return
            
            water[r][c] = True
            
            for d in grid[r][c]:
                if enter_dir is not None and d == OPPOSITE[enter_dir]:
                    continue
                dr, dc = DIR_VECTORS[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    dfs(nr, nc, d)
        
        dfs(self.start[0], self.start[1], None)
        return water
    
    def detect_cycles(self, water, grid=None):
        """检测环路，返回充水和未充水的环路标记。

        Args:
            water: 2D布尔列表，标记有水的格子
            grid: 可选的网格，如果提供则使用该网格，否则使用 self.grid

        Returns:
            tuple: (water_cycles, dry_cycles) 两个2D布尔列表
        """
        if grid is None:
            grid = self.grid
        
        rows, cols = self.rows, self.cols
        water_cycles = [[False] * cols for _ in range(rows)]
        dry_cycles = [[False] * cols for _ in range(rows)]

        def is_connected(r1, c1, r2, c2):
            """检查两个格子是否正确连接（内部函数）"""
            if not (0 <= r1 < rows and 0 <= c1 < cols):
                return False
            if not (0 <= r2 < rows and 0 <= c2 < cols):
                return False
            openings1 = grid[r1][c1]
            openings2 = grid[r2][c2]
            for d1 in openings1:
                dr, dc = DIR_VECTORS[d1]
                if r1 + dr == r2 and c1 + dc == c2:
                    if OPPOSITE[d1] in openings2:
                        return True
            return False

        # 辅助函数：构建指定水状态的邻接表
        def build_adjacency(water_flag):
            adj = {}
            # 收集所有符合水状态的格子
            for r in range(rows):
                for c in range(cols):
                    if water[r][c] == water_flag:
                        adj[(r, c)] = []
            # 添加边（根据连接关系）
            for r in range(rows):
                for c in range(cols):
                    if water[r][c] == water_flag:
                        for d in grid[r][c]:
                            dr, dc = DIR_VECTORS[d]
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < rows and 0 <= nc < cols and water[nr][nc] == water_flag:
                                if is_connected(r, c, nr, nc):
                                    if (nr, nc) not in adj[(r, c)]:
                                        adj[(r, c)].append((nr, nc))
            return adj

        # 剥洋葱法找环
        def find_cycle_nodes(adj):
            if not adj:
                return set()
            # 计算每个节点的度数
            degree = {node: len(neighbors) for node, neighbors in adj.items()}
            q = deque()
            # 将所有度数为1的节点（叶子）入队
            for node, deg in degree.items():
                if deg == 1:
                    q.append(node)
            # 反复移除叶子
            while q:
                node = q.popleft()
                for nb in adj[node]:
                    if degree[nb] > 0:
                        degree[nb] -= 1
                        if degree[nb] == 1:
                            q.append(nb)
                degree[node] = 0  # 标记为已移除
            # 剩余度数大于0的节点即为环上节点
            cycle_nodes = {node for node, deg in degree.items() if deg > 0}
            return cycle_nodes

        # 处理有水区域
        water_adj = build_adjacency(True)
        water_cycle_set = find_cycle_nodes(water_adj)
        for (r, c) in water_cycle_set:
            water_cycles[r][c] = True

        # 处理无水区域
        dry_adj = build_adjacency(False)
        dry_cycle_set = find_cycle_nodes(dry_adj)
        for (r, c) in dry_cycle_set:
            dry_cycles[r][c] = True

        return water_cycles, dry_cycles

    def detect_closed_paths(self, water, grid=None):
        """检测闭路（不与水源连通的封闭连通分量），返回每个分量的格子列表。

        Args:
            water: 2D布尔列表，标记有水的格子
            grid: 可选的网格，如果提供则使用该网格，否则使用 self.grid

        Returns:
            list: 每个元素是一个列表，包含该分量的所有格子坐标 (r, c)
        """
        if grid is None:
            grid = self.grid
        
        rows, cols = self.rows, self.cols
        visited = [[False] * cols for _ in range(rows)]
        closed_components = []

        def is_connected(r1, c1, r2, c2):
            """检查两个格子是否正确连接（双向匹配）"""
            if not (0 <= r1 < rows and 0 <= c1 < cols):
                return False
            if not (0 <= r2 < rows and 0 <= c2 < cols):
                return False
            openings1 = grid[r1][c1]
            openings2 = grid[r2][c2]
            for d1 in openings1:
                dr, dc = DIR_VECTORS[d1]
                if r1 + dr == r2 and c1 + dc == c2:
                    if OPPOSITE[d1] in openings2:
                        return True
            return False

        def dfs(r, c, component):
            visited[r][c] = True
            component.append((r, c))
            for d in grid[r][c]:
                dr, dc = DIR_VECTORS[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if not visited[nr][nc] and not water[nr][nc]:
                        if is_connected(r, c, nr, nc):
                            dfs(nr, nc, component)

        for r in range(rows):
            for c in range(cols):
                if not water[r][c] and not visited[r][c] and grid[r][c]:
                    component = []
                    dfs(r, c, component)
                    if component:
                        # 检查该分量是否真正封闭：每个格子的每个开口都必须与分量内的某个邻居双向匹配
                        is_closed = True
                        for (cr, cc) in component:
                            if not grid[cr][cc]:
                                is_closed = False
                                break
                            for d in grid[cr][cc]:
                                dr, dc = DIR_VECTORS[d]
                                nr, nc = cr + dr, cc + dc
                                # 邻居必须在分量内，且双向连接必须成立
                                if not (0 <= nr < rows and 0 <= nc < cols):
                                    is_closed = False
                                    break
                                if (nr, nc) not in component:
                                    is_closed = False
                                    break
                                # 即使邻居在分量内，也要确保双向匹配（防御性检查）
                                if not is_connected(cr, cc, nr, nc):
                                    is_closed = False
                                    break
                            if not is_closed:
                                break
                        if is_closed:
                            closed_components.append(component)

        return closed_components