"""
假设推理动画演示模块（重写版）
实现真正的逐步假设推理动画，包含回溯功能。
"""

from constants import UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
from collections import deque
import copy


class AnimatedAssumptionSolver:
    """支持动画演示的假设推理求解器（重写版）
    
    算法流程：
    1. 初始化候选集和方向状态（只处理边界和锁定格子，不运行演绎推理）
    2. 选择一个未确定的格子作为假设目标
    3. 对该格子的每个候选旋转进行测试：
       a. 保存当前状态
       b. 假设该旋转
       c. 逐步运行演绎推理
       d. 检查是否产生矛盾
       e. 如果矛盾，回溯并排除该旋转
       f. 如果不矛盾，继续测试下一个旋转
    4. 如果所有旋转都被排除，标记失败
    5. 如果只剩一个旋转，确定该格子
    6. 重复步骤2-5直到所有格子确定或失败
    """
    
    def __init__(self, rows, cols, start, grid, locked=None):
        """初始化求解器
        
        Args:
            rows: 行数
            cols: 列数
            start: 起始位置 (row, col)
            grid: 2D列表，每个单元格包含方向开口列表
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
        
        self.phase = 'init'
        
        self.assumption_cell = None
        self.assumption_rotations = []
        self.current_rot_index = 0
        
        self.saved_candidates = None
        self.saved_dir_state = None
        self.test_candidates = None
        self.test_dir_state = None
        
        self.deductive_phase = None
        self.deductive_r = 0
        self.deductive_c = 0
        self.deductive_step_type = 'update_dir'
        
        self.excluded_in_round = []
        self.processed_cells = set()
        
        self.assumption_iter_count = 0
        self.max_assumption_iter_count = 1000
        
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
        
        for r in range(self.rows):
            for c in range(self.cols):
                self._apply_boundary(r, c, self.candidates)
        
        for r in range(self.rows):
            for c in range(self.cols):
                if self.locked[r][c]:
                    current_openings = self.grid[r][c]
                    valid_rots = set()
                    for rot in range(4):
                        rotated = sorted([(d + rot) % 4 for d in current_openings])
                        if rotated == sorted(current_openings):
                            valid_rots.add(rot)
                    self.candidates[r][c] = valid_rots & self.candidates[r][c]
                    if not self.candidates[r][c]:
                        self.failed = True
                        return
                    for d in range(4):
                        expected = d in current_openings
                        current_state = self.dir_state[r][c][d]
                        if current_state is not None and current_state != expected:
                            self.failed = True
                            return
                        if current_state is None:
                            self.dir_state[r][c][d] = expected
                            if expected:
                                self._propagate_dir_state(r, c, d, True, self.dir_state)
                            else:
                                self._propagate_dir_state(r, c, d, False, self.dir_state)
        
        for r in range(self.rows):
            for c in range(self.cols):
                if len(self.grid[r][c]) == 1:
                    for d in range(4):
                        dr, dc = DIR_VECTORS[d]
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if len(self.grid[nr][nc]) == 1:
                                if (self.dir_state[r][c][d] is True or 
                                    self.dir_state[nr][nc][OPPOSITE[d]] is True):
                                    self.failed = True
                                    return
                                self.dir_state[r][c][d] = False
                                self.dir_state[nr][nc][OPPOSITE[d]] = False
        
        self._run_initial_deductive()
        
        self.solution, self.determined_mask = self._build_solution_and_mask(self.candidates)
        if self.solution is None:
            self.failed = True
            return
        
        if all(all(row) for row in self.determined_mask):
            self.finished = True
    
    def _run_initial_deductive(self):
        """运行初始演绎推理，更新候选集"""
        max_iters = 200
        for _ in range(max_iters):
            changed = False
            
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._update_dir_state_from_candidates_single(r, c, self.candidates, self.dir_state):
                        changed = True
            if self._any_empty(self.candidates):
                self.failed = True
                return
            
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_non_openings_single(r, c, self.candidates, self.dir_state):
                        changed = True
            if self._any_empty(self.candidates):
                self.failed = True
                return
            
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_openings_single(r, c, self.candidates, self.dir_state):
                        changed = True
            if self._any_empty(self.candidates):
                self.failed = True
                return
            
            if not changed:
                break
    
    def _propagate_dir_state(self, r, c, d, val, dir_state):
        """将格子(r,c)方向d的确定状态val传播到相邻格子的相反方向"""
        dr, dc = DIR_VECTORS[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < self.rows and 0 <= nc < self.cols:
            opp = OPPOSITE[d]
            if dir_state[nr][nc][opp] is None:
                dir_state[nr][nc][opp] = val
                return True
        return False
    
    def _apply_boundary(self, r, c, candidates):
        """边界约束：排除导致边界开口的旋转"""
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
        """根据候选集更新单个格子的方向状态，返回是否发生改变"""
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
                changed = True
                if self._propagate_dir_state(r, c, d, True, dir_state):
                    changed = True
            elif all_closed and dir_state[r][c][d] != False:
                dir_state[r][c][d] = False
                changed = True
                if self._propagate_dir_state(r, c, d, False, dir_state):
                    changed = True
        return changed
    
    def _apply_fixed_non_openings_single(self, r, c, candidates, dir_state):
        """根据确定非开口排除单个格子的候选旋转"""
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
        """根据确定开口排除单个格子的候选旋转"""
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
        """检查是否有候选集为空"""
        for r in range(self.rows):
            for c in range(self.cols):
                if not candidates[r][c]:
                    return True
        return False
    
    def _build_solution_and_mask(self, candidates):
        """根据候选集构建解和确定掩码"""
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
        """检查两个格子是否双向连通"""
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
        """计算水流覆盖（DFS）"""
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
        """检查给定网格是否满足胜利条件：所有格子被恰好访问一次，且管道连接正确。
        
        Args:
            grid: 要检查的网格
            
        Returns:
            bool: 如果满足胜利条件返回True，否则返回False
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
        """检测环路，返回 (water_cycle, dry_cycle)"""
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
        """检测不与水源连通的封闭连通分量"""
        rows, cols = self.rows, self.cols
        visited = [[False] * cols for _ in range(rows)]
        closed_components = []
        
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
                            closed_components.append(component)
        
        return len(closed_components) > 0
    
    def _check_conflict(self, candidates, dir_state):
        """检查当前状态是否产生矛盾，返回:
        - 'conflict': 产生矛盾
        - 'victory': 胜利
        - 'continue': 无矛盾但未胜利
        """
        if self._any_empty(candidates):
            return 'conflict'
        
        partial_solution, partial_mask = self._build_solution_and_mask(candidates)
        if partial_solution is None:
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
    
    def _next_undetermined_cell(self, current_r, current_c):
        """找到下一个未确定的格子（用于演绎推理阶段）。
        
        Args:
            current_r: 当前行
            current_c: 当前列
        
        Returns:
            tuple: (next_r, next_c) 或 (None, None) 如果没有更多未确定格子
        """
        c = current_c + 1
        r = current_r
        while r < self.rows:
            while c < self.cols:
                test_mask = self._build_solution_and_mask(self.test_candidates)[1]
                if not test_mask[r][c] and not self.locked[r][c]:
                    return r, c
                c += 1
            c = 0
            r += 1
        return None, None
    
    def _first_undetermined_cell(self):
        """找到第一个未确定的格子。
        
        Returns:
            tuple: (r, c) 或 (None, None) 如果没有未确定格子
        """
        for r in range(self.rows):
            for c in range(self.cols):
                test_mask = self._build_solution_and_mask(self.test_candidates)[1]
                if not test_mask[r][c] and not self.locked[r][c]:
                    return r, c
        return None, None
    
    def _select_assumption_cell(self):
        """选择下一个假设格子，返回格子坐标或None"""
        undetermined = []
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.determined_mask[r][c] and not self.locked[r][c]:
                    if (r, c) not in self.processed_cells:
                        undetermined.append((r, c))
        
        if not undetermined:
            return None
        
        undetermined.sort(key=lambda pos: len(self.candidates[pos[0]][pos[1]]))
        return undetermined[0]
    
    def step(self):
        """执行一步假设推理，返回当前步骤信息
        
        Returns:
            dict: 包含步骤类型、涉及格子、当前候选集等信息
        """
        if self.failed:
            return self._build_result('fail', None, None, None)
        
        if self.finished:
            return self._build_result('finish', None, None, None)
        
        if self.phase == 'init':
            self.phase = 'select_cell'
            return self.step()
        
        if self.phase == 'select_cell':
            self.assumption_iter_count += 1
            if self.assumption_iter_count > self.max_assumption_iter_count:
                self.finished = True
                return self._build_result('finish', None, None, None)
            
            cell = self._select_assumption_cell()
            if cell is None:
                self.finished = True
                return self._build_result('finish', None, None, None)
            
            self.assumption_cell = cell
            r, c = cell
            self.assumption_rotations = list(self.candidates[r][c])
            self.current_rot_index = 0
            self.excluded_in_round = []
            
            self.phase = 'start_assumption'
            
            return {
                'type': 'assumption_start',
                'cell': cell,
                'cells': [cell],
                'direction': None,
                'value': None,
                'candidates': self.candidates,
                'dir_state': self.dir_state,
                'solution': self.solution,
                'determined_mask': self.determined_mask,
                'finished': False,
                'failed': False,
                'assumption_cell': cell,
                'assumption_original_count': len(self.assumption_rotations),
                'assumption_excluded_count': len(self.excluded_in_round),
                'checking_cell': cell
            }
        
        if self.phase == 'start_assumption':
            if self.current_rot_index >= len(self.assumption_rotations):
                if len(self.excluded_in_round) == len(self.assumption_rotations):
                    self.failed = True
                    return self._build_result('assumption_fail', self.assumption_cell, None, None)
                else:
                    self.processed_cells.add(self.assumption_cell)
                    self.solution, self.determined_mask = self._build_solution_and_mask(self.candidates)
                    if all(all(row) for row in self.determined_mask):
                        self.finished = True
                        return self._build_result('finish', None, None, None)
                    self.phase = 'select_cell'
                    return self.step()
            
            r, c = self.assumption_cell
            rot = self.assumption_rotations[self.current_rot_index]
            
            self.saved_candidates = copy.deepcopy(self.candidates)
            self.saved_dir_state = copy.deepcopy(self.dir_state)
            
            self.test_candidates = copy.deepcopy(self.candidates)
            self.test_dir_state = copy.deepcopy(self.dir_state)
            self.test_candidates[r][c] = {rot}
            
            self.deductive_step_type = 'update_dir'
            self.deductive_r = 0
            self.deductive_c = 0
            
            self.phase = 'deductive_step'
            
            return {
                'type': 'assumption_test',
                'cell': (r, c),
                'cells': [(r, c)],
                'direction': None,
                'value': rot,
                'candidates': self.test_candidates,
                'dir_state': self.test_dir_state,
                'solution': self._build_solution_and_mask(self.test_candidates)[0],
                'determined_mask': self._build_solution_and_mask(self.test_candidates)[1],
                'finished': False,
                'failed': False,
                'assumption_cell': self.assumption_cell,
                'assumption_original_count': len(self.assumption_rotations),
                'assumption_excluded_count': len(self.excluded_in_round),
                'checking_cell': (r, c)
            }
        
        if self.phase == 'deductive_step':
            if self.deductive_step_type == 'update_dir':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._update_dir_state_from_candidates_single(r, c, self.test_candidates, self.test_dir_state):
                            if self._any_empty(self.test_candidates):
                                self.phase = 'check_conflict'
                                return self.step()
                            return {
                                'type': 'deductive_update_dir',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'update_dir_state',
                                'candidates': self.test_candidates,
                                'dir_state': self.test_dir_state,
                                'solution': self._build_solution_and_mask(self.test_candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.test_candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.deductive_step_type = 'apply_non_openings'
                return self.step()
            
            elif self.deductive_step_type == 'apply_non_openings':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._apply_fixed_non_openings_single(r, c, self.test_candidates, self.test_dir_state):
                            if self._any_empty(self.test_candidates):
                                self.phase = 'check_conflict'
                                return self.step()
                            return {
                                'type': 'deductive_apply_non_openings',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'apply_non_openings',
                                'candidates': self.test_candidates,
                                'dir_state': self.test_dir_state,
                                'solution': self._build_solution_and_mask(self.test_candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.test_candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.deductive_step_type = 'apply_openings'
                return self.step()
            
            elif self.deductive_step_type == 'apply_openings':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._apply_fixed_openings_single(r, c, self.test_candidates, self.test_dir_state):
                            if self._any_empty(self.test_candidates):
                                self.phase = 'check_conflict'
                                return self.step()
                            self.deductive_step_type = 'update_dir'
                            return {
                                'type': 'deductive_apply_openings',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'apply_openings',
                                'candidates': self.test_candidates,
                                'dir_state': self.test_dir_state,
                                'solution': self._build_solution_and_mask(self.test_candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.test_candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.phase = 'check_conflict'
                return self.step()
        
        if self.phase == 'check_conflict':
            check_result = self._check_conflict(self.test_candidates, self.test_dir_state)
            r, c = self.assumption_cell
            rot = self.assumption_rotations[self.current_rot_index]
            
            if check_result == 'victory':
                # 胜利！更新候选集并结束
                self.candidates = self.test_candidates
                self.dir_state = self.test_dir_state
                self.solution, self.determined_mask = self._build_solution_and_mask(self.candidates)
                self.finished = True
                return {
                    'type': 'victory',
                    'cell': (r, c),
                    'cells': [(r, c)],
                    'direction': None,
                    'value': rot,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': self.solution,
                    'determined_mask': self.determined_mask,
                    'finished': True,
                    'failed': False,
                    'assumption_cell': self.assumption_cell,
                    'assumption_original_count': len(self.assumption_rotations),
                    'checking_cell': (r, c)
                }
            elif check_result == 'conflict':
                self.excluded_in_round.append(rot)
                
                if rot in self.candidates[r][c]:
                    self.candidates[r][c].discard(rot)
                
                if not self.candidates[r][c]:
                    self.failed = True
                    return {
                        'type': 'assumption_exclude',
                        'cell': (r, c),
                        'cells': [(r, c)],
                        'direction': None,
                        'value': rot,
                        'candidates': self.candidates,
                        'dir_state': self.dir_state,
                        'solution': self.solution,
                        'determined_mask': self.determined_mask,
                        'finished': False,
                        'failed': True,
                        'assumption_cell': self.assumption_cell,
                        'assumption_original_count': len(self.assumption_rotations),
                        'checking_cell': (r, c)
                    }
                
                self.deductive_step_type = 'update_dir'
                self.phase = 'after_exclude_deductive'
                return {
                    'type': 'assumption_exclude',
                    'cell': (r, c),
                    'cells': [(r, c)],
                    'direction': None,
                    'value': rot,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': self.solution,
                    'determined_mask': self.determined_mask,
                    'finished': False,
                    'failed': False,
                    'assumption_cell': self.assumption_cell,
                    'assumption_original_count': len(self.assumption_rotations),
                    'checking_cell': (r, c)
                }
            else:  # 'continue'
                self.current_rot_index += 1
                self.phase = 'start_assumption'
                
                return {
                    'type': 'assumption_keep',
                    'cell': (r, c),
                    'cells': [(r, c)],
                    'direction': None,
                    'value': rot,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': self.solution,
                    'determined_mask': self.determined_mask,
                    'finished': False,
                    'failed': False,
                    'assumption_cell': self.assumption_cell,
                    'assumption_original_count': len(self.assumption_rotations),
                    'checking_cell': (r, c)
                }
        
        if self.phase == 'after_exclude_deductive':
            if self.deductive_step_type == 'update_dir':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._update_dir_state_from_candidates_single(r, c, self.candidates, self.dir_state):
                            if self._any_empty(self.candidates):
                                self.failed = True
                                return {
                                    'type': 'after_exclude_deductive',
                                    'cell': (r, c),
                                    'cells': [(r, c)],
                                    'direction': None,
                                    'value': 'update_dir_state',
                                    'candidates': self.candidates,
                                    'dir_state': self.dir_state,
                                    'solution': self._build_solution_and_mask(self.candidates)[0],
                                    'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                    'finished': False,
                                    'failed': True,
                                    'assumption_cell': self.assumption_cell,
                                    'assumption_original_count': len(self.assumption_rotations),
                                    'checking_cell': (r, c)
                                }
                            return {
                                'type': 'after_exclude_deductive',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'update_dir_state',
                                'candidates': self.candidates,
                                'dir_state': self.dir_state,
                                'solution': self._build_solution_and_mask(self.candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.deductive_step_type = 'apply_non_openings'
                return self.step()
            
            elif self.deductive_step_type == 'apply_non_openings':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._apply_fixed_non_openings_single(r, c, self.candidates, self.dir_state):
                            if self._any_empty(self.candidates):
                                self.failed = True
                                return {
                                    'type': 'after_exclude_deductive',
                                    'cell': (r, c),
                                    'cells': [(r, c)],
                                    'direction': None,
                                    'value': 'apply_non_openings',
                                    'candidates': self.candidates,
                                    'dir_state': self.dir_state,
                                    'solution': self._build_solution_and_mask(self.candidates)[0],
                                    'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                    'finished': False,
                                    'failed': True,
                                    'assumption_cell': self.assumption_cell,
                                    'assumption_original_count': len(self.assumption_rotations),
                                    'checking_cell': (r, c)
                                }
                            return {
                                'type': 'after_exclude_deductive',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'apply_non_openings',
                                'candidates': self.candidates,
                                'dir_state': self.dir_state,
                                'solution': self._build_solution_and_mask(self.candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.deductive_step_type = 'apply_openings'
                return self.step()
            
            elif self.deductive_step_type == 'apply_openings':
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self._apply_fixed_openings_single(r, c, self.candidates, self.dir_state):
                            if self._any_empty(self.candidates):
                                self.failed = True
                                return {
                                    'type': 'after_exclude_deductive',
                                    'cell': (r, c),
                                    'cells': [(r, c)],
                                    'direction': None,
                                    'value': 'apply_openings',
                                    'candidates': self.candidates,
                                    'dir_state': self.dir_state,
                                    'solution': self._build_solution_and_mask(self.candidates)[0],
                                    'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                    'finished': False,
                                    'failed': True,
                                    'assumption_cell': self.assumption_cell,
                                    'assumption_original_count': len(self.assumption_rotations),
                                    'checking_cell': (r, c)
                                }
                            self.deductive_step_type = 'update_dir'
                            return {
                                'type': 'after_exclude_deductive',
                                'cell': (r, c),
                                'cells': [(r, c)],
                                'direction': None,
                                'value': 'apply_openings',
                                'candidates': self.candidates,
                                'dir_state': self.dir_state,
                                'solution': self._build_solution_and_mask(self.candidates)[0],
                                'determined_mask': self._build_solution_and_mask(self.candidates)[1],
                                'finished': False,
                                'failed': False,
                                'assumption_cell': self.assumption_cell,
                                'assumption_original_count': len(self.assumption_rotations),
                                'assumption_excluded_count': len(self.excluded_in_round),
                                'checking_cell': (r, c)
                            }
                
                self.solution, self.determined_mask = self._build_solution_and_mask(self.candidates)
                if all(all(row) for row in self.determined_mask):
                    self.finished = True
                    return {
                        'type': 'finish',
                        'cell': None,
                        'cells': None,
                        'direction': None,
                        'value': None,
                        'candidates': self.candidates,
                        'dir_state': self.dir_state,
                        'solution': self.solution,
                        'determined_mask': self.determined_mask,
                        'finished': True,
                        'failed': False,
                        'assumption_cell': self.assumption_cell,
                        'assumption_original_count': len(self.assumption_rotations),
                        'checking_cell': None
                    }
                
                self.current_rot_index += 1
                self.phase = 'select_cell'
                return self.step()
        
        return self._build_result('finish', None, None, None)
    
    def _build_result(self, result_type, cell, assumption_cell, checking_cell):
        """构建统一的结果字典"""
        return {
            'type': result_type,
            'cell': cell,
            'cells': [cell] if cell else None,
            'direction': None,
            'value': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': self.solution,
            'determined_mask': self.determined_mask,
            'finished': result_type in ['finish', 'fail'],
            'failed': result_type in ['fail', 'assumption_fail'],
            'assumption_cell': assumption_cell,
            'assumption_original_count': len(self.assumption_rotations) if self.assumption_rotations else 1,
            'assumption_excluded_count': len(self.excluded_in_round) if hasattr(self, 'excluded_in_round') else 0,
            'checking_cell': checking_cell
        }
