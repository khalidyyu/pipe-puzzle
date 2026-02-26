"""
搜索求解动画演示模块（重写版）
实现真正的逐步DFS搜索动画，包含回溯功能。

算法流程：
1. 初始化阶段（基于当前棋盘状态）：
   a. 设置边界方向状态
   b. 应用边界约束排除候选
   c. 处理锁定格子（根据当前棋盘状态）
   d. 处理相邻单开口规则
2. 执行演绎推理直到稳定
3. 如果还有未确定格子，进入DFS搜索：
   a. 选择候选数最少的未确定格子
   b. 对每个候选旋转进行测试
   c. 保存状态，假设旋转，执行演绎推理
   d. 如果矛盾，回溯并尝试下一个旋转
   e. 如果无矛盾，继续DFS
   f. 如果所有旋转都失败，回溯到上一层
"""

from constants import UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
from collections import deque
import copy


class AnimatedSearchSolver:
    """支持动画演示的搜索求解器（重写版）
    
    使用DFS深度优先搜索算法，结合演绎推理进行约束传播。
    """
    
    def __init__(self, rows, cols, start, grid, locked=None):
        """初始化求解器
        
        Args:
            rows: 行数
            cols: 列数
            start: 起始位置 (row, col)
            grid: 2D列表，每个单元格包含方向开口列表（当前棋盘状态）
            locked: 2D布尔列表，标记锁定格子（可选）
        """
        self.rows = rows
        self.cols = cols
        self.start = start
        self.grid = [row[:] for row in grid]
        self.locked = [[False] * cols for _ in range(rows)]
        if locked:
            for r in range(rows):
                for c in range(cols):
                    self.locked[r][c] = locked[r][c]
        
        self.failed = False
        self.finished = False
        self.current_step = 0
        
        # 初始化所有后续会用到的属性
        self.phase = 'init_boundary_cand'
        self.init_r = 0
        self.init_c = 0
        
        self.deductive_phase = 'update_dir'
        self.deductive_r = 0
        self.deductive_c = 0
        
        self.dfs_stack = []
        self.current_dfs_cell = None
        self.current_dfs_rotations = []
        self.current_rot_index = 0
        self.dfs_depth = 0
        self.max_dfs_depth = 10000
        self.assumption_history = []
        
        self.test_candidates = None
        self.test_dir_state = None
        self.test_deductive_phase = None
        self.test_deductive_r = 0
        self.test_deductive_c = 0
        
        self.checking_cell = None
        self.search_cell = None
        
        self.solution = None
        self.determined_mask = None
        
        self.candidates = [[set(range(4)) for _ in range(cols)] for _ in range(rows)]
        self.dir_state = [[[None for _ in range(4)] for _ in range(cols)] for _ in range(rows)]
        
        for r in range(self.rows):
            for c in range(self.cols):
                if r == 0:
                    self.dir_state[r][c][UP] = False
                if r == self.rows - 1:
                    self.dir_state[r][c][DOWN] = False
                if c == 0:
                    self.dir_state[r][c][LEFT] = False
                if c == self.cols - 1:
                    self.dir_state[r][c][RIGHT] = False
        
        # 一次性完成当前棋盘状态处理（锁定格子）
        for r in range(self.rows):
            for c in range(self.cols):
                if self.locked[r][c]:
                    current_openings = self.grid[r][c]
                    valid_rots = set()
                    for rot in range(4):
                        rotated = sorted([(d + rot) % 4 for d in current_openings])
                        if rotated == sorted(current_openings):
                            valid_rots.add(rot)
                    
                    if not valid_rots:
                        self.failed = True
                        return
                    
                    self.candidates[r][c] = valid_rots
                    
                    for d in range(4):
                        expected = d in current_openings
                        current_state = self.dir_state[r][c][d]
                        if current_state is not None and current_state != expected:
                            self.failed = True
                            return
                        if current_state is None:
                            self.dir_state[r][c][d] = expected
                            result = self._propagate_dir_state(r, c, d, expected, self.dir_state)
                            if result == 'conflict':
                                self.failed = True
                                return
        
        self._build_single_opening_pairs()
    
    def _build_single_opening_pairs(self):
        """构建相邻单开口格子对列表"""
        self.single_opening_pairs = []
        visited = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if len(self.grid[r][c]) == 1:
                    for d in range(4):
                        dr, dc = DIR_VECTORS[d]
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if len(self.grid[nr][nc]) == 1:
                                pair = tuple(sorted([(r, c), (nr, nc)]))
                                if pair not in visited:
                                    visited.add(pair)
                                    if not self.locked[r][c] and not self.locked[nr][nc]:
                                        self.single_opening_pairs.append(((r, c), (nr, nc), d))
        self.single_opening_index = 0
    
    def _propagate_dir_state(self, r, c, d, val, dir_state):
        """将格子(r,c)方向d的确定状态val传播到相邻格子的相反方向
        
        Args:
            r: 行索引
            c: 列索引
            d: 方向
            val: 状态值 (True/False)
            dir_state: 方向状态数组
            
        Returns:
            bool: 是否改变了邻居状态
        """
        dr, dc = DIR_VECTORS[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < self.rows and 0 <= nc < self.cols:
            opp = OPPOSITE[d]
            if dir_state[nr][nc][opp] is None:
                dir_state[nr][nc][opp] = val
                return True
            elif dir_state[nr][nc][opp] != val:
                return 'conflict'
        return False
    
    def _apply_boundary(self, r, c, candidates):
        """边界约束：排除导致边界开口的旋转
        
        Args:
            r: 行索引
            c: 列索引
            candidates: 候选集数组
            
        Returns:
            bool: 是否有变化
        """
        orig = self.grid[r][c]
        to_remove = set()
        for rot in candidates[r][c]:
            openings = [(d + rot) % 4 for d in orig]
            if (r == 0 and UP in openings) or \
               (r == self.rows-1 and DOWN in openings) or \
               (c == 0 and LEFT in openings) or \
               (c == self.cols-1 and RIGHT in openings):
                to_remove.add(rot)
        if to_remove:
            candidates[r][c] -= to_remove
            return True
        return False
    
    def _update_dir_state_from_candidates_single(self, r, c, candidates, dir_state):
        """根据候选集更新单个格子的方向状态
        
        Args:
            r: 行索引
            c: 列索引
            candidates: 候选集数组
            dir_state: 方向状态数组
            
        Returns:
            bool or str: 是否发生改变，'conflict'表示矛盾
        """
        if not candidates[r][c]:
            return False
        changed = False
        orig = self.grid[r][c]
        cand_list = list(candidates[r][c])
        for d in range(4):
            all_open = all((d in [(dir+rot)%4 for dir in orig]) for rot in cand_list)
            all_closed = all((d not in [(dir+rot)%4 for dir in orig]) for rot in cand_list)
            if all_open and dir_state[r][c][d] != True:
                dir_state[r][c][d] = True
                result = self._propagate_dir_state(r, c, d, True, dir_state)
                if result == 'conflict':
                    return 'conflict'
                changed = True
            elif all_closed and dir_state[r][c][d] != False:
                dir_state[r][c][d] = False
                result = self._propagate_dir_state(r, c, d, False, dir_state)
                if result == 'conflict':
                    return 'conflict'
                changed = True
        return changed
    
    def _apply_fixed_non_openings_single(self, r, c, candidates, dir_state):
        """根据确定非开口排除单个格子的候选旋转
        
        Args:
            r: 行索引
            c: 列索引
            candidates: 候选集数组
            dir_state: 方向状态数组
            
        Returns:
            bool: 是否有变化
        """
        if not candidates[r][c]:
            return False
        orig = self.grid[r][c]
        to_remove = set()
        for rot in candidates[r][c]:
            openings = [(d + rot) % 4 for d in orig]
            for d in range(4):
                if dir_state[r][c][d] is False and d in openings:
                    to_remove.add(rot)
                    break
        if to_remove:
            candidates[r][c] -= to_remove
            return True
        return False
    
    def _apply_fixed_openings_single(self, r, c, candidates, dir_state):
        """根据确定开口排除单个格子的候选旋转
        
        Args:
            r: 行索引
            c: 列索引
            candidates: 候选集数组
            dir_state: 方向状态数组
            
        Returns:
            bool: 是否有变化
        """
        if not candidates[r][c]:
            return False
        orig = self.grid[r][c]
        to_remove = set()
        for rot in candidates[r][c]:
            openings = [(d + rot) % 4 for d in orig]
            for d in range(4):
                if dir_state[r][c][d] is True and d not in openings:
                    to_remove.add(rot)
                    break
        if to_remove:
            candidates[r][c] -= to_remove
            return True
        return False
    
    def _any_empty(self, candidates):
        """检查是否有候选集为空
        
        Args:
            candidates: 候选集数组
            
        Returns:
            bool: 是否存在空候选集
        """
        for r in range(self.rows):
            for c in range(self.cols):
                if not candidates[r][c]:
                    return True
        return False
    
    def _build_solution_and_mask(self, candidates):
        """根据候选集构建解和确定掩码
        
        Args:
            candidates: 候选集数组
            
        Returns:
            tuple: (solution, determined_mask) 或 (None, None)
        """
        solution = [[None] * self.cols for _ in range(self.rows)]
        determined_mask = [[False] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                cand = candidates[r][c]
                if not cand:
                    return None, None
                orig = self.grid[r][c]
                possible_openings = set()
                for rot in cand:
                    rotated = sorted([(d + rot) % 4 for d in orig])
                    possible_openings.add(tuple(rotated))
                if len(possible_openings) == 1:
                    rot = next(iter(cand))
                    solution[r][c] = [(d + rot) % 4 for d in orig]
                    determined_mask[r][c] = True
                else:
                    solution[r][c] = self.grid[r][c][:]
        return solution, determined_mask
    
    def _is_connected(self, r1, c1, r2, c2, grid):
        """检查两个格子是否双向连通
        
        Args:
            r1, c1: 第一个格子坐标
            r2, c2: 第二个格子坐标
            grid: 网格数据
            
        Returns:
            bool: 是否连通
        """
        if not (0 <= r1 < self.rows and 0 <= c1 < self.cols):
            return False
        if not (0 <= r2 < self.rows and 0 <= c2 < self.cols):
            return False
        openings1 = grid[r1][c1]
        openings2 = grid[r2][c2]
        for d1 in openings1:
            dr, dc = DIR_VECTORS[d1]
            if r1 + dr == r2 and c1 + dc == c2:
                if OPPOSITE[d1] in openings2:
                    return True
        return False
    
    def _calculate_water_flow(self, grid):
        """计算水流覆盖（DFS）
        
        Args:
            grid: 网格数据
            
        Returns:
            list: 水流覆盖的二维布尔数组
        """
        water = [[False] * self.cols for _ in range(self.rows)]
        
        def dfs(r, c, enter_dir):
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
    
    def _check_victory(self, grid):
        """检查给定网格是否满足胜利条件
        
        Args:
            grid: 要检查的网格
            
        Returns:
            bool: 如果满足胜利条件返回True
        """
        visited = [[0] * self.cols for _ in range(self.rows)]

        def dfs(r, c, enter_dir):
            if enter_dir is not None:
                if OPPOSITE[enter_dir] not in grid[r][c]:
                    return False

            visited[r][c] += 1
            if visited[r][c] > 1:
                return False

            for d in grid[r][c]:
                if enter_dir is not None and d == OPPOSITE[enter_dir]:
                    continue
                dr, dc = DIR_VECTORS[d]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    return False
                if not dfs(nr, nc, d):
                    return False
            return True

        if not dfs(self.start[0], self.start[1], None):
            return False

        for r in range(self.rows):
            for c in range(self.cols):
                if visited[r][c] != 1:
                    return False
        return True
    
    def _detect_cycles(self, grid, water):
        """检测环路
        
        Args:
            grid: 网格数据
            water: 水流覆盖数组
            
        Returns:
            tuple: (water_cycle, dry_cycle)
        """
        rows, cols = self.rows, self.cols
        
        def build_adjacency(water_flag):
            adj = {}
            for r in range(rows):
                for c in range(cols):
                    if water[r][c] == water_flag:
                        adj[(r, c)] = []
            for r in range(rows):
                for c in range(cols):
                    if water[r][c] == water_flag:
                        for d in grid[r][c]:
                            dr, dc = DIR_VECTORS[d]
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < rows and 0 <= nc < cols and water[nr][nc] == water_flag:
                                if self._is_connected(r, c, nr, nc, grid):
                                    if (nr, nc) not in adj[(r, c)]:
                                        adj[(r, c)].append((nr, nc))
            return adj
        
        def find_cycle_nodes(adj):
            if not adj:
                return set()
            degree = {node: len(neighbors) for node, neighbors in adj.items()}
            q = deque()
            for node, deg in degree.items():
                if deg == 1:
                    q.append(node)
            while q:
                node = q.popleft()
                for nb in adj[node]:
                    if degree[nb] > 0:
                        degree[nb] -= 1
                        if degree[nb] == 1:
                            q.append(nb)
                degree[node] = 0
            return {node for node, deg in degree.items() if deg > 0}
        
        water_adj = build_adjacency(True)
        water_cycle_nodes = find_cycle_nodes(water_adj)
        water_cycle = len(water_cycle_nodes) > 0
        
        dry_adj = build_adjacency(False)
        dry_cycle_nodes = find_cycle_nodes(dry_adj)
        dry_cycle = len(dry_cycle_nodes) > 0
        
        return water_cycle, dry_cycle
    
    def _detect_closed_paths(self, grid, water):
        """检测不与水源连通的封闭连通分量
        
        Args:
            grid: 网格数据
            water: 水流覆盖数组
            
        Returns:
            bool: 是否存在封闭连通分量
        """
        rows, cols = self.rows, self.cols
        visited = [[False] * cols for _ in range(rows)]
        
        def dfs(r, c, component):
            visited[r][c] = True
            component.append((r, c))
            for d in grid[r][c]:
                dr, dc = DIR_VECTORS[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if not visited[nr][nc] and not water[nr][nc]:
                        if self._is_connected(r, c, nr, nc, grid):
                            dfs(nr, nc, component)
        
        for r in range(rows):
            for c in range(cols):
                if not water[r][c] and not visited[r][c] and grid[r][c]:
                    component = []
                    dfs(r, c, component)
                    if component:
                        is_closed = True
                        for (cr, cc) in component:
                            if not grid[cr][cc]:
                                is_closed = False
                                break
                            for d in grid[cr][cc]:
                                dr, dc = DIR_VECTORS[d]
                                nr, nc = cr + dr, cc + dc
                                if not (0 <= nr < rows and 0 <= nc < cols):
                                    is_closed = False
                                    break
                                if (nr, nc) not in component:
                                    is_closed = False
                                    break
                                if not self._is_connected(cr, cc, nr, nc, grid):
                                    is_closed = False
                                    break
                            if not is_closed:
                                break
                        if is_closed:
                            return True
        return False
    
    def _check_conflict(self, candidates, dir_state):
        """检查当前状态是否产生矛盾
        
        Args:
            candidates: 候选集数组
            dir_state: 方向状态数组
            
        Returns:
            str: 'conflict', 'victory', 或 'continue'
        """
        if self._any_empty(candidates):
            return 'conflict'
        
        partial_solution, partial_mask = self._build_solution_and_mask(candidates)
        if partial_solution is None:
            return 'conflict'
        
        if all(all(row) for row in partial_mask):
            if self._check_victory(partial_solution):
                return 'victory'
            return 'conflict'
        
        test_grid = [[[] for _ in range(self.cols)] for _ in range(self.rows)]
        for rr in range(self.rows):
            for cc in range(self.cols):
                if partial_mask[rr][cc]:
                    test_grid[rr][cc] = partial_solution[rr][cc]
                else:
                    test_grid[rr][cc] = []
        
        if not test_grid[self.start[0]][self.start[1]]:
            test_grid[self.start[0]][self.start[1]] = self.grid[self.start[0]][self.start[1]][:]
        
        water = self._calculate_water_flow(test_grid)
        water_cycle, dry_cycle = self._detect_cycles(test_grid, water)
        if water_cycle or dry_cycle:
            return 'conflict'
        
        if self._detect_closed_paths(test_grid, water):
            return 'conflict'
        
        return 'continue'
    
    def _find_first_undetermined(self, candidates, mask):
        """找到第一个未确定的格子（按候选数排序）
        
        Args:
            candidates: 候选集数组
            mask: 确定掩码
            
        Returns:
            tuple: (r, c) 或 None
        """
        undetermined = []
        for r in range(self.rows):
            for c in range(self.cols):
                if not mask[r][c] and not self.locked[r][c]:
                    undetermined.append((r, c, len(candidates[r][c])))
        
        if not undetermined:
            return None
        
        undetermined.sort(key=lambda x: x[2])
        return (undetermined[0][0], undetermined[0][1])
    
    def _build_result(self, step_type, cell, checking_cell):
        """构建步骤结果字典
        
        Args:
            step_type: 步骤类型
            cell: 当前格子
            checking_cell: 正在检查的格子
            
        Returns:
            dict: 步骤信息字典
        """
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        determined_count = sum(sum(row) for row in determined_mask) if determined_mask else 0
        return {
            'type': step_type,
            'cell': cell,
            'cells': [cell] if cell else None,
            'direction': None,
            'value': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'determined_count': determined_count,
            'finished': self.finished,
            'failed': self.failed,
            'dfs_depth': self.dfs_depth,
            'search_cell': self.search_cell,
            'checking_cell': checking_cell,
            'assumption_history': list(self.assumption_history)
        }
    
    def step(self):
        """执行一步搜索求解
        
        Returns:
            dict: 包含当前步骤信息的字典
        """
        if self.failed:
            return self._build_result('fail', None, None)
        
        if self.finished:
            solution, determined_mask = self._build_solution_and_mask(self.candidates)
            determined_count = sum(sum(row) for row in determined_mask)
            return {
                'type': 'finish',
                'cell': None,
                'cells': None,
                'direction': None,
                'value': None,
                'candidates': self.candidates,
                'dir_state': self.dir_state,
                'solution': solution,
                'determined_mask': determined_mask,
                'determined_count': determined_count,
                'finished': True,
                'failed': False,
                'dfs_depth': self.dfs_depth,
                'search_cell': self.search_cell,
                'checking_cell': self.checking_cell,
                'assumption_history': list(self.assumption_history)
            }
        
        # 初始化阶段
        if self.phase.startswith('init_'):
            return self._init_step()
        
        if self.phase == 'deductive':
            return self._deductive_step()
        
        if self.phase == 'dfs_deductive':
            return self._dfs_deductive_step()
        
        if self.phase == 'dfs_test':
            return self._dfs_test_step()
        
        if self.phase == 'dfs_backtrack':
            return self._dfs_backtrack_step()
        
        return self._build_result('fail', None, None)
    
    def _init_step(self):
        """执行初始化阶段的一步"""
        # 阶段1：应用边界约束排除候选
        if self.phase == 'init_boundary_cand':
            while self.init_r < self.rows:
                while self.init_c < self.cols:
                    r, c = self.init_r, self.init_c
                    if self._apply_boundary(r, c, self.candidates):
                        self.init_c += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('init_fail', (r, c), (r, c))
                        return self._build_init_step('init_boundary_cand', (r, c))
                    self.init_c += 1
                self.init_c = 0
                self.init_r += 1
            
            self.phase = 'init_single_opening'
            self.single_opening_index = 0
            return self._init_step()
        
        # 阶段3：处理相邻单开口规则
        elif self.phase == 'init_single_opening':
            while self.single_opening_index < len(self.single_opening_pairs):
                (r1, c1), (r2, c2), d = self.single_opening_pairs[self.single_opening_index]
                self.single_opening_index += 1
                
                if (self.dir_state[r1][c1][d] is True or 
                    self.dir_state[r2][c2][OPPOSITE[d]] is True):
                    self.failed = True
                    return self._build_result('init_fail', (r1, c1), (r1, c1))
                
                if self.dir_state[r1][c1][d] is None or self.dir_state[r2][c2][OPPOSITE[d]] is None:
                    self.dir_state[r1][c1][d] = False
                    self.dir_state[r2][c2][OPPOSITE[d]] = False
                    return self._build_init_step('init_single_opening', (r1, c1))
            
            self.phase = 'deductive'
            self.deductive_phase = 'update_dir'
            self.deductive_r = 0
            self.deductive_c = 0
            return self._deductive_step()
        
        return self._build_result('fail', None, None)
    
    def _build_init_step(self, step_type, cell):
        """构建初始化步骤结果
        
        Args:
            step_type: 步骤类型
            cell: 当前格子
            
        Returns:
            dict: 步骤信息字典
        """
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        determined_count = sum(sum(row) for row in determined_mask) if determined_mask else 0
        return {
            'type': step_type,
            'cell': cell,
            'cells': [cell] if cell else None,
            'direction': None,
            'value': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'determined_count': determined_count,
            'finished': False,
            'failed': False,
            'dfs_depth': 0,
            'search_cell': None,
            'checking_cell': cell,
            'assumption_history': []
        }
    
    def _deductive_step(self):
        """执行演绎推理的一步"""
        if self.deductive_phase == 'update_dir':
            while self.deductive_r < self.rows:
                while self.deductive_c < self.cols:
                    r, c = self.deductive_r, self.deductive_c
                    result = self._update_dir_state_from_candidates_single(r, c, self.candidates, self.dir_state)
                    if result == 'conflict':
                        self.failed = True
                        return self._build_result('deductive_fail', (r, c), (r, c))
                    if result:
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('deductive_fail', (r, c), (r, c))
                        
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'deductive_update_dir',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': 0,
                            'search_cell': None,
                            'checking_cell': (r, c),
                            'assumption_history': []
                        }
                    self.deductive_c += 1
                self.deductive_c = 0
                self.deductive_r += 1
            
            self.deductive_phase = 'apply_non_openings'
            self.deductive_r = 0
            self.deductive_c = 0
            return self._deductive_step()
        
        elif self.deductive_phase == 'apply_non_openings':
            while self.deductive_r < self.rows:
                while self.deductive_c < self.cols:
                    r, c = self.deductive_r, self.deductive_c
                    if self._apply_fixed_non_openings_single(r, c, self.candidates, self.dir_state):
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('deductive_fail', (r, c), (r, c))
                        
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'deductive_apply_non_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': 0,
                            'search_cell': None,
                            'checking_cell': (r, c),
                            'assumption_history': []
                        }
                    self.deductive_c += 1
                self.deductive_c = 0
                self.deductive_r += 1
            
            self.deductive_phase = 'apply_openings'
            self.deductive_r = 0
            self.deductive_c = 0
            return self._deductive_step()
        
        elif self.deductive_phase == 'apply_openings':
            while self.deductive_r < self.rows:
                while self.deductive_c < self.cols:
                    r, c = self.deductive_r, self.deductive_c
                    if self._apply_fixed_openings_single(r, c, self.candidates, self.dir_state):
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('deductive_fail', (r, c), (r, c))
                        
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'deductive_apply_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': 0,
                            'search_cell': None,
                            'checking_cell': (r, c),
                            'assumption_history': []
                        }
                    self.deductive_c += 1
                self.deductive_c = 0
                self.deductive_r += 1
            
            self.deductive_phase = 'update_dir'
            self.deductive_r = 0
            self.deductive_c = 0
            
            solution, determined_mask = self._build_solution_and_mask(self.candidates)
            if solution is None:
                self.failed = True
                return self._build_result('deductive_fail', None, None)
            
            if all(all(row) for row in determined_mask):
                if self._check_victory(solution):
                    self.finished = True
                    determined_count = sum(sum(row) for row in determined_mask)
                    return {
                        'type': 'victory',
                        'cell': None,
                        'cells': None,
                        'direction': None,
                        'value': None,
                        'candidates': self.candidates,
                        'dir_state': self.dir_state,
                        'solution': solution,
                        'determined_mask': determined_mask,
                        'determined_count': determined_count,
                        'finished': True,
                        'failed': False,
                        'dfs_depth': 0,
                        'search_cell': None,
                        'checking_cell': None
                    }
                else:
                    self.failed = True
                    return self._build_result('victory_check_fail', None, None)
            
            self.phase = 'dfs_start'
            return self._dfs_start_step()
        
        return self._build_result('fail', None, None)
    
    def _dfs_start_step(self):
        """开始DFS搜索"""
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        cell = self._find_first_undetermined(self.candidates, determined_mask)
        
        if cell is None:
            self.finished = True
            return self._build_result('finish', None, None)
        
        r, c = cell
        self.search_cell = cell
        self.current_dfs_cell = cell
        self.current_dfs_rotations = list(self.candidates[r][c])
        self.current_rot_index = 0
        
        self.dfs_stack = [{
            'candidates': copy.deepcopy(self.candidates),
            'dir_state': copy.deepcopy(self.dir_state),
            'cell': cell,
            'rotations': self.current_dfs_rotations[:],
            'rot_index': 0
        }]
        
        self.phase = 'dfs_test'
        self.test_candidates = None
        self.test_dir_state = None
        
        return {
            'type': 'dfs_start',
            'cell': cell,
            'cells': [cell],
            'direction': None,
            'value': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'finished': False,
            'failed': False,
            'dfs_depth': self.dfs_depth,
            'search_cell': cell,
            'checking_cell': cell,
            'assumption_history': list(self.assumption_history)
        }
    
    def _dfs_test_step(self):
        """执行DFS测试的一步"""
        if self.current_rot_index >= len(self.current_dfs_rotations):
            if self.dfs_stack:
                self.phase = 'dfs_backtrack'
                return self._dfs_backtrack_step()
            else:
                self.failed = True
                return self._build_result('dfs_exhausted', self.current_dfs_cell, self.current_dfs_cell)
        
        r, c = self.current_dfs_cell
        rot = self.current_dfs_rotations[self.current_rot_index]
        
        if self.test_candidates is None:
            self.test_candidates = copy.deepcopy(self.candidates)
            self.test_dir_state = copy.deepcopy(self.dir_state)
            
            # 检查旋转是否与已确定的方向状态一致
            orig = self.grid[r][c]
            openings = [(d + rot) % 4 for d in orig]
            conflict = False
            for d in range(4):
                expected_open = d in openings
                if self.test_dir_state[r][c][d] is not None:
                    if self.test_dir_state[r][c][d] != expected_open:
                        conflict = True
                        break
            
            if conflict:
                # 该旋转与已确定的方向状态矛盾，尝试下一个
                self.current_rot_index += 1
                self.test_candidates = None
                self.test_dir_state = None
                return self._dfs_test_step()
            
            self.test_candidates[r][c] = {rot}
            self.test_deductive_phase = 'update_dir'
            self.test_deductive_r = 0
            self.test_deductive_c = 0
            self.checking_cell = (r, c)
            
            solution, determined_mask = self._build_solution_and_mask(self.test_candidates)
            return {
                'type': 'dfs_test_rot',
                'cell': (r, c),
                'cells': [(r, c)],
                'direction': rot,
                'value': rot,
                'candidates': self.test_candidates,
                'dir_state': self.test_dir_state,
                'solution': solution,
                'determined_mask': determined_mask,
                'finished': False,
                'failed': False,
                'dfs_depth': self.dfs_depth,
                'search_cell': self.search_cell,
                'checking_cell': (r, c),
                'rot_index': self.current_rot_index + 1,
                'rot_total': len(self.current_dfs_rotations),
                'assumption_history': list(self.assumption_history)
            }
        
        return self._dfs_deductive_step()
    
    def _dfs_deductive_step(self):
        """执行DFS测试状态下的演绎推理一步"""
        if self.test_deductive_phase == 'update_dir':
            while self.test_deductive_r < self.rows:
                while self.test_deductive_c < self.cols:
                    r, c = self.test_deductive_r, self.test_deductive_c
                    result = self._update_dir_state_from_candidates_single(r, c, self.test_candidates, self.test_dir_state)
                    if result == 'conflict':
                        return self._handle_dfs_conflict()
                    if result:
                        if self._any_empty(self.test_candidates):
                            return self._handle_dfs_conflict()
                        
                        solution, determined_mask = self._build_solution_and_mask(self.test_candidates)
                        return {
                            'type': 'dfs_deductive_update_dir',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.test_candidates,
                            'dir_state': self.test_dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': self.dfs_depth,
                            'search_cell': self.search_cell,
                            'checking_cell': (r, c),
                            'assumption_history': list(self.assumption_history)
                        }
                    self.test_deductive_c += 1
                self.test_deductive_c = 0
                self.test_deductive_r += 1
            
            self.test_deductive_phase = 'apply_non_openings'
            self.test_deductive_r = 0
            self.test_deductive_c = 0
            return self._dfs_deductive_step()
        
        elif self.test_deductive_phase == 'apply_non_openings':
            while self.test_deductive_r < self.rows:
                while self.test_deductive_c < self.cols:
                    r, c = self.test_deductive_r, self.test_deductive_c
                    if self._apply_fixed_non_openings_single(r, c, self.test_candidates, self.test_dir_state):
                        if self._any_empty(self.test_candidates):
                            return self._handle_dfs_conflict()
                        
                        solution, determined_mask = self._build_solution_and_mask(self.test_candidates)
                        return {
                            'type': 'dfs_deductive_apply_non_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.test_candidates,
                            'dir_state': self.test_dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': self.dfs_depth,
                            'search_cell': self.search_cell,
                            'checking_cell': (r, c),
                            'assumption_history': list(self.assumption_history)
                        }
                    self.test_deductive_c += 1
                self.test_deductive_c = 0
                self.test_deductive_r += 1
            
            self.test_deductive_phase = 'apply_openings'
            self.test_deductive_r = 0
            self.test_deductive_c = 0
            return self._dfs_deductive_step()
        
        elif self.test_deductive_phase == 'apply_openings':
            while self.test_deductive_r < self.rows:
                while self.test_deductive_c < self.cols:
                    r, c = self.test_deductive_r, self.test_deductive_c
                    if self._apply_fixed_openings_single(r, c, self.test_candidates, self.test_dir_state):
                        if self._any_empty(self.test_candidates):
                            return self._handle_dfs_conflict()
                        
                        solution, determined_mask = self._build_solution_and_mask(self.test_candidates)
                        return {
                            'type': 'dfs_deductive_apply_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'candidates': self.test_candidates,
                            'dir_state': self.test_dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False,
                            'dfs_depth': self.dfs_depth,
                            'search_cell': self.search_cell,
                            'checking_cell': (r, c),
                            'assumption_history': list(self.assumption_history)
                        }
                    self.test_deductive_c += 1
                self.test_deductive_c = 0
                self.test_deductive_r += 1
            
            self.test_deductive_phase = 'update_dir'
            self.test_deductive_r = 0
            self.test_deductive_c = 0
            
            solution, determined_mask = self._build_solution_and_mask(self.test_candidates)
            if solution is None:
                return self._handle_dfs_conflict()
            
            if all(all(row) for row in determined_mask):
                if self._check_victory(solution):
                    self.candidates = self.test_candidates
                    self.dir_state = self.test_dir_state
                    self.finished = True
                    determined_count = sum(sum(row) for row in determined_mask)
                    return {
                        'type': 'victory',
                        'cell': None,
                        'cells': None,
                        'direction': None,
                        'value': None,
                        'candidates': self.candidates,
                        'dir_state': self.dir_state,
                        'solution': solution,
                        'determined_mask': determined_mask,
                        'determined_count': determined_count,
                        'finished': True,
                        'failed': False,
                        'dfs_depth': self.dfs_depth,
                        'search_cell': self.search_cell,
                        'checking_cell': None,
                        'assumption_history': list(self.assumption_history)
                    }
                else:
                    return self._handle_dfs_conflict()
            
            conflict_result = self._check_conflict(self.test_candidates, self.test_dir_state)
            if conflict_result == 'conflict':
                return self._handle_dfs_conflict()
            elif conflict_result == 'victory':
                self.candidates = self.test_candidates
                self.dir_state = self.test_dir_state
                self.finished = True
                solution, determined_mask = self._build_solution_and_mask(self.candidates)
                determined_count = sum(sum(row) for row in determined_mask)
                return {
                    'type': 'victory',
                    'cell': None,
                    'cells': None,
                    'direction': None,
                    'value': None,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': solution,
                    'determined_mask': determined_mask,
                    'determined_count': determined_count,
                    'finished': True,
                    'failed': False,
                    'dfs_depth': self.dfs_depth,
                    'search_cell': self.search_cell,
                    'checking_cell': None,
                    'assumption_history': list(self.assumption_history)
                }
            
            self.candidates = copy.deepcopy(self.test_candidates)
            self.dir_state = copy.deepcopy(self.test_dir_state)
            self.dfs_depth += 1
            
            if self.dfs_depth > self.max_dfs_depth:
                self.failed = True
                return self._build_result('dfs_max_depth', None, None)
            
            solution, determined_mask = self._build_solution_and_mask(self.candidates)
            next_cell = self._find_first_undetermined(self.candidates, determined_mask)
            
            if next_cell is None:
                self.finished = True
                return {
                    'type': 'victory',
                    'cell': None,
                    'cells': None,
                    'direction': None,
                    'value': None,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': solution,
                    'determined_mask': determined_mask,
                    'finished': True,
                    'failed': False,
                    'dfs_depth': self.dfs_depth,
                    'search_cell': self.search_cell,
                    'checking_cell': None,
                    'assumption_history': list(self.assumption_history)
                }
            
            self.dfs_stack.append({
                'candidates': copy.deepcopy(self.candidates),
                'dir_state': copy.deepcopy(self.dir_state),
                'cell': next_cell,
                'rotations': list(self.candidates[next_cell[0]][next_cell[1]]),
                'rot_index': 0
            })
            
            self.assumption_history.append(next_cell)
            
            self.search_cell = next_cell
            self.current_dfs_cell = next_cell
            self.current_dfs_rotations = list(self.candidates[next_cell[0]][next_cell[1]])
            self.current_rot_index = 0
            self.test_candidates = None
            self.test_dir_state = None
            self.phase = 'dfs_test'
            
            return {
                'type': 'dfs_next_level',
                'cell': next_cell,
                'cells': [next_cell],
                'direction': None,
                'value': None,
                'candidates': self.candidates,
                'dir_state': self.dir_state,
                'solution': solution,
                'determined_mask': determined_mask,
                'finished': False,
                'failed': False,
                'dfs_depth': self.dfs_depth,
                'search_cell': self.search_cell,
                'checking_cell': next_cell
            }
        
        return self._build_result('fail', None, None)
    
    def _handle_dfs_conflict(self):
        """处理DFS测试中的矛盾"""
        r, c = self.current_dfs_cell
        rot = self.current_dfs_rotations[self.current_rot_index]
        rot_index = self.current_rot_index
        rot_total = len(self.current_dfs_rotations)
        
        self.current_rot_index += 1
        self.test_candidates = None
        self.test_dir_state = None
        
        if self.current_rot_index < len(self.current_dfs_rotations):
            self.phase = 'dfs_test'
        else:
            self.phase = 'dfs_backtrack'
        
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        
        return {
            'type': 'dfs_conflict',
            'cell': (r, c),
            'cells': [(r, c)],
            'direction': rot,
            'value': rot,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'finished': False,
            'failed': False,
            'dfs_depth': self.dfs_depth,
            'search_cell': self.search_cell,
            'checking_cell': (r, c),
            'rot_index': rot_index + 1,
            'rot_total': rot_total,
            'assumption_history': list(self.assumption_history)
        }
    
    def _dfs_backtrack_step(self):
        """执行DFS回溯"""
        if not self.dfs_stack:
            self.failed = True
            return self._build_result('dfs_exhausted', None, None)
        
        state = self.dfs_stack.pop()
        if self.assumption_history:
            self.assumption_history.pop()
        state['rot_index'] += 1
        
        if state['rot_index'] >= len(state['rotations']):
            if self.dfs_stack:
                return self._dfs_backtrack_step()
            else:
                self.failed = True
                return self._build_result('dfs_exhausted', None, None)
        
        self.candidates = state['candidates']
        self.dir_state = state['dir_state']
        self.current_dfs_cell = state['cell']
        self.current_dfs_rotations = state['rotations']
        self.current_rot_index = state['rot_index']
        self.dfs_depth = len(self.dfs_stack)
        self.search_cell = state['cell']
        self.test_candidates = None
        self.test_dir_state = None
        self.phase = 'dfs_test'
        
        self.dfs_stack.append(state)
        self.assumption_history.append(state['cell'])
        
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        return {
            'type': 'dfs_backtrack',
            'cell': state['cell'],
            'cells': [state['cell']],
            'direction': None,
            'value': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'finished': False,
            'failed': False,
            'dfs_depth': self.dfs_depth,
            'search_cell': self.search_cell,
            'checking_cell': state['cell'],
            'assumption_history': list(self.assumption_history)
        }
