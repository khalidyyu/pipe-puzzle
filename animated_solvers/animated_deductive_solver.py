"""演绎推理动画演示模块"""
from constants import UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
import copy


class AnimatedDeductiveSolver:
    """支持动画演示的演绎推理求解器"""
    
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
        
        self.candidates = [[set(range(4)) for _ in range(cols)] for _ in range(rows)]
        self.dir_state = [[[None for _ in range(4)] for _ in range(cols)] for _ in range(rows)]
        
        self.failed = False
        
        self.current_step = 0
        self.finished = False
        
        # 应用已锁定格子的约束
        for r in range(self.rows):
            for c in range(self.cols):
                if self.locked[r][c]:
                    # 已锁定的格子，候选集只有一个值
                    self.candidates[r][c] = {0}  # 简化处理
        
        self.phase = 'locked_cells'
        self.locked_cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.locked[r][c]:
                    self.locked_cells.append((r, c))
        self.locked_index = 0
        
        self.single_opening_pairs = []
        self.single_opening_index = 0
        self._build_single_opening_pairs()
        
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
        
        # 一次性完成已锁定格子的候选集和方向状态更新
        self._update_locked_cells_candidates()
    
    def _build_single_opening_pairs(self):
        """构建相邻单开口格子对列表"""
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
                                    # 只添加未锁定的格子对
                                    if not self.locked[r][c] and not self.locked[nr][nc]:
                                        self.single_opening_pairs.append(((r, c), (nr, nc), d))
        
    def _propagate_dir_state(self, r, c, d, val, dir_state):
        """将格子(r,c)方向d的确定状态val传播到相邻格子的相反方向。返回是否改变了邻居状态。"""
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
    
    def _update_dir_state_from_candidates(self, r, c, candidates, dir_state):
        """根据候选集更新方向状态"""
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
    
    def _apply_fixed_non_openings(self, r, c, candidates, dir_state):
        """根据确定非开口排除候选旋转"""
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
    
    def _apply_fixed_openings(self, r, c, candidates, dir_state):
        """根据确定开口排除候选旋转"""
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
    
    def _run_deductive_to_completion(self):
        """运行演绎推理直到稳定，不产生动画步骤"""
        max_iter = 100
        for _ in range(max_iter):
            changed = False
            # 1. 根据候选集更新方向状态
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._update_dir_state_from_candidates(r, c, self.candidates, self.dir_state):
                        changed = True
            # 2. 根据方向状态更新候选集
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_non_openings(r, c, self.candidates, self.dir_state):
                        changed = True
                    if self._apply_fixed_openings(r, c, self.candidates, self.dir_state):
                        changed = True
            if not changed:
                break
            if self._any_empty(self.candidates):
                self.failed = True
                return
    
    def _update_locked_cells_candidates(self):
        """一次性完成已锁定格子的候选集和方向状态更新"""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.locked[r][c]:
                    # 已锁定的格子，处理其候选集和方向状态
                    current_openings = self.grid[r][c]
                    valid_rots = set()
                    for rot in range(4):
                        rotated = sorted([(d + rot) % 4 for d in current_openings])
                        if rotated == sorted(current_openings):
                            valid_rots.add(rot)
                    if valid_rots:
                        self.candidates[r][c] = valid_rots & self.candidates[r][c]
                        # 根据已锁定格子的开口更新方向状态
                        for d in range(4):
                            expected = d in current_openings
                            if self.dir_state[r][c][d] is None:
                                self.dir_state[r][c][d] = expected
                                # 传播方向状态
                                if expected:
                                    self._propagate_dir_state(r, c, d, True, self.dir_state)
                                else:
                                    self._propagate_dir_state(r, c, d, False, self.dir_state)
    
    def _process_locked_cell(self, r, c):
        """处理锁定的格子，返回是否成功"""
        current_openings = self.grid[r][c]
        valid_rots = set()
        for rot in range(4):
            rotated = sorted([(d + rot) % 4 for d in current_openings])
            if rotated == sorted(current_openings):
                valid_rots.add(rot)
        if not valid_rots:
            return False
        self.candidates[r][c] = valid_rots & self.candidates[r][c]
        if not self.candidates[r][c]:
            return False
        for d in range(4):
            expected = d in current_openings
            current_state = self.dir_state[r][c][d]
            if current_state is not None and current_state != expected:
                return False
            if current_state is None:
                self.dir_state[r][c][d] = expected
                if expected:
                    self._propagate_dir_state(r, c, d, True, self.dir_state)
                else:
                    self._propagate_dir_state(r, c, d, False, self.dir_state)
        return True
    
    def step(self):
        """执行一步演绎推理
        
        Returns:
            dict: 包含当前步骤信息的字典
        """
        if self.failed:
            return self._build_result('fail', None)
        
        if self.finished:
            solution, determined_mask = self._build_solution_and_mask(self.candidates)
            return {
                'type': 'finish',
                'cell': None,
                'cells': None,
                'direction': None,
                'value': None,
                'removed_rotations': None,
                'candidates': self.candidates,
                'dir_state': self.dir_state,
                'solution': solution,
                'determined_mask': determined_mask,
                'finished': True,
                'failed': False
            }
        
        if self.phase == 'locked_cells':
            # 跳过已锁定的格子，因为已经在初始化时处理了
            self.phase = 'init_single_opening'
            return self.step()
        
        if self.phase == 'init_single_opening':
            if self.single_opening_index < len(self.single_opening_pairs):
                cell1, cell2, d = self.single_opening_pairs[self.single_opening_index]
                self.single_opening_index += 1
                
                r1, c1 = cell1
                r2, c2 = cell2
                
                if self.dir_state[r1][c1][d] is True or self.dir_state[r2][c2][OPPOSITE[d]] is True:
                    self.failed = True
                    return self._build_result('init_single_opening_fail', cell1, cells=[cell1, cell2])
                
                changed = False
                if self.dir_state[r1][c1][d] is None:
                    self.dir_state[r1][c1][d] = False
                    changed = True
                if self.dir_state[r2][c2][OPPOSITE[d]] is None:
                    self.dir_state[r2][c2][OPPOSITE[d]] = False
                    changed = True
                
                solution, determined_mask = self._build_solution_and_mask(self.candidates)
                return {
                    'type': 'init_single_opening',
                    'cell': cell1,
                    'cells': [cell1, cell2],
                    'direction': d,
                    'value': None,
                    'removed_rotations': None,
                    'candidates': self.candidates,
                    'dir_state': self.dir_state,
                    'solution': solution,
                    'determined_mask': determined_mask,
                    'finished': False,
                    'failed': False
                }
            else:
                self.phase = 'deductive'
                return self.step()
        
        if self.phase == 'deductive':
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._update_dir_state_from_candidates(r, c, self.candidates, self.dir_state):
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('update_candidates_fail', (r, c))
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'update_candidates',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'removed_rotations': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False
                        }
            
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_non_openings(r, c, self.candidates, self.dir_state):
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('apply_non_openings_fail', (r, c))
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'apply_non_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'removed_rotations': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False
                        }
            
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_openings(r, c, self.candidates, self.dir_state):
                        self.current_step += 1
                        if self._any_empty(self.candidates):
                            self.failed = True
                            return self._build_result('apply_openings_fail', (r, c))
                        solution, determined_mask = self._build_solution_and_mask(self.candidates)
                        return {
                            'type': 'apply_openings',
                            'cell': (r, c),
                            'cells': [(r, c)],
                            'direction': None,
                            'value': None,
                            'removed_rotations': None,
                            'candidates': self.candidates,
                            'dir_state': self.dir_state,
                            'solution': solution,
                            'determined_mask': determined_mask,
                            'finished': False,
                            'failed': False
                        }
            
            self.finished = True
            solution, determined_mask = self._build_solution_and_mask(self.candidates)
            return {
                'type': 'finish',
                'cell': None,
                'cells': None,
                'direction': None,
                'value': None,
                'removed_rotations': None,
                'candidates': self.candidates,
                'dir_state': self.dir_state,
                'solution': solution,
                'determined_mask': determined_mask,
                'finished': True,
                'failed': False
            }
        
        return self._build_result('finish', None)
    
    def _build_result(self, result_type, cell, cells=None):
        """构建结果字典"""
        solution, determined_mask = self._build_solution_and_mask(self.candidates)
        return {
            'type': result_type,
            'cell': cell,
            'cells': cells if cells else ([cell] if cell else None),
            'direction': None,
            'value': None,
            'removed_rotations': None,
            'candidates': self.candidates,
            'dir_state': self.dir_state,
            'solution': solution,
            'determined_mask': determined_mask,
            'finished': result_type in ['finish', 'fail'],
            'failed': result_type in ['fail', 'init_boundary_fail', 'init_locked_fail',
                                      'init_single_opening_fail', 'update_candidates_fail', 
                                      'apply_non_openings_fail', 'apply_openings_fail']
        }
