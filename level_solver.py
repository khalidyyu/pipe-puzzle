from constants import UP, RIGHT, DOWN, LEFT, OPPOSITE, DIR_VECTORS
from collections import deque
import copy
import multiprocessing as mp
import os

# ---------- 并行任务函数（必须定义在模块顶层以便 pickle）----------
def _check_rotation_task(solver, r, c, rot):
    """
    并行任务：检查在给定求解器状态下，将格子 (r,c) 强制设为旋转 rot 是否导致矛盾。
    返回:
        - 'exclude': 应排除该旋转（矛盾）
        - 'victory': 该假设导致胜利
        - 'keep': 可保留该旋转（无矛盾但未胜利）
    """
    # 使用 solver 副本中的 candidates 和 dir_state（已通过深拷贝传入）
    solver.candidates[r][c] = {rot}
    # 运行演绎推理直到稳定
    if not solver._deductive_iteration(solver.candidates, solver.dir_state):
        return 'exclude'
    # 构造部分确定的棋盘
    partial_solution, partial_mask = solver._build_solution_and_mask(solver.candidates)
    if partial_solution is None:
        return 'exclude'
    # 构建用于检测的临时棋盘（未确定格子开口置空）
    test_grid = [[[] for _ in range(solver.cols)] for _ in range(solver.rows)]
    for rr in range(solver.rows):
        for cc in range(solver.cols):
            if partial_mask[rr][cc]:
                test_grid[rr][cc] = partial_solution[rr][cc]
            else:
                test_grid[rr][cc] = []
    # 如果起始点未确定，使用原始开口
    if not test_grid[solver.start[0]][solver.start[1]]:
        test_grid[solver.start[0]][solver.start[1]] = solver.grid[solver.start[0]][solver.start[1]][:]
    # 检查是否胜利（所有格子都确定且满足胜利条件）
    if all(all(row) for row in partial_mask):
        if solver._check_victory(test_grid):
            return 'victory'
    # 计算水流
    water = solver._calculate_water_flow(test_grid)
    # 检测环路
    water_cycle, dry_cycle = solver._detect_cycles(test_grid, water)
    if water_cycle or dry_cycle:
        return 'exclude'
    # 检测闭路
    if solver._detect_closed_paths(test_grid, water):
        return 'exclude'
    return 'keep'


class LevelSolver:
    """关卡求解器，支持演绎推理、假设推理（并行）与深度优先回溯搜索。"""

    def __init__(self, rows, cols, start, grid, locked=None, num_workers=None):
        """
        初始化求解器。
        :param rows: 网格行数
        :param cols: 网格列数
        :param start: 起始位置 (row, col)
        :param grid: 2D列表，每个单元格包含方向开口列表
        :param locked: 2D布尔列表，标记锁定格子（可选）
        :param num_workers: 并行工作进程数，None 表示使用 os.cpu_count() // 2
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
        # 默认使用 CPU 核心数的一半，但至少为 1
        default_workers = max(1, os.cpu_count() // 2) if os.cpu_count() else 1
        self.num_workers = num_workers if num_workers is not None else default_workers
        self.solution = None

    # ------------------ 工具函数 ------------------
    def _is_connected(self, r1, c1, r2, c2, grid):
        """检查两个格子是否正确连接（双向匹配）"""
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
        """计算水流路径，返回标记有水的网格"""
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
        """检测环路，返回 (有环路标志, 无水环路标志) 两个布尔值"""
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
        """检测闭路（不与水源连通的封闭连通分量），返回是否存在这样的分量"""
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
                if not water[r][c] and not visited[r][c]:
                    component = []
                    dfs(r, c, component)
                    if component:
                        # 检查该分量是否真正封闭
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

    # ------------------ 演绎推理核心 ------------------
    def _initialize_candidates_and_dir_state(self):
        """初始化候选集和方向状态，返回 (candidates, dir_state)"""
        candidates = [[set(range(4)) for _ in range(self.cols)] for _ in range(self.rows)]
        dir_state = [[[None for _ in range(4)] for _ in range(self.cols)] for _ in range(self.rows)]

        # 边界上的确定非开口
        for r in range(self.rows):
            for c in range(self.cols):
                if r == 0:
                    dir_state[r][c][UP] = False
                if r == self.rows - 1:
                    dir_state[r][c][DOWN] = False
                if c == 0:
                    dir_state[r][c][LEFT] = False
                if c == self.cols - 1:
                    dir_state[r][c][RIGHT] = False

        # 应用边界约束
        for r in range(self.rows):
            for c in range(self.cols):
                self._apply_boundary(r, c, candidates)

        # 处理被锁定的格子
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
                        return None
                    candidates[r][c] = valid_rots & candidates[r][c]
                    if not candidates[r][c]:
                        return None
                    for d in range(4):
                        expected = d in current_openings
                        current_state = dir_state[r][c][d]
                        if current_state is not None and current_state != expected:
                            return None
                        if current_state is None:
                            dir_state[r][c][d] = expected
                            result = self._propagate_dir_state(r, c, d, expected, dir_state)
                            if result == 'conflict':
                                return None

        # 相邻单开口规则（仅执行一次）
        for r in range(self.rows):
            for c in range(self.cols):
                if len(self.grid[r][c]) == 1:
                    for d in range(4):
                        dr, dc = DIR_VECTORS[d]
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if len(self.grid[nr][nc]) == 1:
                                if dir_state[r][c][d] is True or dir_state[nr][nc][OPPOSITE[d]] is True:
                                    return None
                                dir_state[r][c][d] = False
                                dir_state[nr][nc][OPPOSITE[d]] = False

        return candidates, dir_state

    def _propagate_dir_state(self, r, c, d, val, dir_state):
        """将格子(r,c)方向d的确定状态val传播到相邻格子的相反方向。返回是否改变了邻居状态，'conflict'表示矛盾。"""
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
        """根据候选集更新方向状态。返回是否改变，'conflict'表示矛盾。"""
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
                result = self._propagate_dir_state(r, c, d, True, dir_state)
                if result == 'conflict':
                    return 'conflict'
                if result:
                    changed = True
            elif all_closed and dir_state[r][c][d] != False:
                dir_state[r][c][d] = False
                changed = True
                result = self._propagate_dir_state(r, c, d, False, dir_state)
                if result == 'conflict':
                    return 'conflict'
                if result:
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
        for r in range(self.rows):
            for c in range(self.cols):
                if not candidates[r][c]:
                    return True
        return False

    def _deductive_iteration(self, candidates, dir_state):
        """迭代推理直到稳定，返回True表示无矛盾，False表示矛盾"""
        max_iters = 200
        iter_count = 0
        changed = True
        while changed and iter_count < max_iters:
            iter_count += 1
            changed = False

            # 步骤a：根据候选集更新方向状态，并传播
            for r in range(self.rows):
                for c in range(self.cols):
                    result = self._update_dir_state_from_candidates(r, c, candidates, dir_state)
                    if result == 'conflict':
                        return False
                    if result:
                        changed = True
            if self._any_empty(candidates):
                return False

            # 步骤b：根据确定非开口排除候选
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_non_openings(r, c, candidates, dir_state):
                        changed = True
            if self._any_empty(candidates):
                return False

            # 步骤c：根据确定开口排除候选
            for r in range(self.rows):
                for c in range(self.cols):
                    if self._apply_fixed_openings(r, c, candidates, dir_state):
                        changed = True
            if self._any_empty(candidates):
                return False

        return True

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

    # ------------------ 胜利检测 ------------------
    def _check_victory(self, grid):
        """检查给定棋盘是否满足胜利条件"""
        visited = [[0] * self.cols for _ in range(self.rows)]
        fail_reason = [None]

        def dfs(r, c, enter_dir):
            if enter_dir is not None:
                if OPPOSITE[enter_dir] not in grid[r][c]:
                    fail_reason[0] = f"入口不匹配 at ({r},{c})"
                    return False
            visited[r][c] += 1
            if visited[r][c] > 1:
                fail_reason[0] = f"重复访问 at ({r},{c})"
                return False
            for d in grid[r][c]:
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

    # ------------------ 深度优先搜索 ------------------
    def _dfs_search(self, candidates, dir_state, depth=0):
        """深度优先回溯搜索，返回 (完整解, 全True掩码) 或 None"""
        max_depth = 10000
        if depth > max_depth:
            return None
        
        if not self._deductive_iteration(candidates, dir_state):
            return None
        solution, mask = self._build_solution_and_mask(candidates)
        if solution is None:
            return None
        if all(all(row) for row in mask):
            if self._check_victory(solution):
                return solution, mask
            return None
        undetermined = [(r, c) for r in range(self.rows) for c in range(self.cols) if not mask[r][c]]
        undetermined.sort(key=lambda p: len(candidates[p[0]][p[1]]))
        r, c = undetermined[0]
        for rot in sorted(candidates[r][c]):
            # 检查旋转是否与已确定的方向状态一致
            orig = self.grid[r][c]
            openings = [(d + rot) % 4 for d in orig]
            conflict = False
            for d in range(4):
                expected_open = d in openings
                if dir_state[r][c][d] is not None:
                    if dir_state[r][c][d] != expected_open:
                        conflict = True
                        break
            if conflict:
                continue
            
            cand_copy = copy.deepcopy(candidates)
            dir_copy = copy.deepcopy(dir_state)
            cand_copy[r][c] = {rot}
            if not self._deductive_iteration(cand_copy, dir_copy):
                continue
            res = self._dfs_search(cand_copy, dir_copy, depth + 1)
            if res is not None:
                return res
        return None

    # ------------------ 主求解方法 ------------------
    def solve(self):
        """求解关卡，返回 (solution_grid, determined_count, determined_mask)"""
        result = self._solve_with_assumption()
        if result is None:
            return (None, 0, [])
        solution, determined_mask = result
        determined_count = sum(sum(row) for row in determined_mask)
        return (solution, determined_count, determined_mask)

    def _solve_with_assumption(self):
        """演绎推理 + 并行假设推理 + 深度优先搜索"""
        init_result = self._initialize_candidates_and_dir_state()
        if init_result is None:
            return None
        candidates, dir_state = init_result

        if not self._deductive_iteration(candidates, dir_state):
            return None

        solution, determined_mask = self._build_solution_and_mask(candidates)
        if solution is None:
            return None

        if all(all(row) for row in determined_mask):
            return solution, determined_mask

        # 假设推理循环（并行）
        max_assumption_iters = 200
        assumption_iter_count = 0
        while True:
            assumption_iter_count += 1
            if assumption_iter_count > max_assumption_iters:
                break
            
            undetermined = []
            for r in range(self.rows):
                for c in range(self.cols):
                    if not determined_mask[r][c]:
                        undetermined.append((r, c))
            if not undetermined:
                break

            undetermined.sort(key=lambda pos: len(candidates[pos[0]][pos[1]]))

            # 收集所有需要检测的任务 (r, c, rot)
            tasks = []
            for r, c in undetermined:
                for rot in candidates[r][c]:
                    tasks.append((r, c, rot))

            if not tasks:
                break

            # 使用进程池并行检测
            with mp.Pool(processes=self.num_workers) as pool:
                # 为每个任务创建求解器副本（深拷贝当前状态）
                starmap_args = []
                for r, c, rot in tasks:
                    # 将当前候选集和方向状态暂时挂载到 self 上，以便深拷贝包含它们
                    self.candidates = candidates
                    self.dir_state = dir_state
                    solver_copy = copy.deepcopy(self)
                    # 从 self 中移除临时属性（避免影响后续）
                    del self.candidates
                    del self.dir_state
                    starmap_args.append((solver_copy, r, c, rot))

                # 并发执行，results 列表与 tasks 顺序对应
                results = pool.starmap(_check_rotation_task, starmap_args)

            # 根据结果排除非法旋转或检查胜利
            any_excluded = False
            victory_solution = None
            for (r, c, rot), result in zip(tasks, results):
                if result == 'exclude':
                    if rot in candidates[r][c]:
                        candidates[r][c].discard(rot)
                        any_excluded = True
                elif result == 'victory':
                    # 找到胜利解，保存并提前退出
                    self.candidates = candidates
                    self.dir_state = dir_state
                    solver_copy = copy.deepcopy(self)
                    del self.candidates
                    del self.dir_state
                    solver_copy.candidates[r][c] = {rot}
                    solver_copy._deductive_iteration(solver_copy.candidates, solver_copy.dir_state)
                    victory_solution, victory_mask = solver_copy._build_solution_and_mask(solver_copy.candidates)
                    break
            
            # 如果找到胜利解，直接返回
            if victory_solution is not None:
                return victory_solution, [[True] * self.cols for _ in range(self.rows)]

            if not any_excluded:
                break

            # 重新运行演绎推理
            if not self._deductive_iteration(candidates, dir_state):
                return None

            solution, determined_mask = self._build_solution_and_mask(candidates)
            if solution is None:
                return None

        # 若仍有未确定格子，启动深度优先搜索
        if not all(all(row) for row in determined_mask):
            result = self._dfs_search(candidates, dir_state)
            if result is None:
                return None
            solution, determined_mask = result

        return solution, determined_mask

    def solve_with_hint(self):
        """返回提示信息"""
        solution, determined_count, determined_mask = self.solve()
        if solution is None:
            return {
                'success': False,
                'solution': None,
                'rotations': [],
                'rotation_count': 0,
                'determined_count': 0,
                'determined_mask': []
            }

        rotations = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] != solution[r][c]:
                    for rotation in range(4):
                        rotated = [(d + rotation) % 4 for d in self.grid[r][c]]
                        if rotated == solution[r][c]:
                            rotations.append((r, c, rotation * 90))
                            break

        return {
            'success': True,
            'solution': solution,
            'rotations': rotations,
            'rotation_count': len(rotations),
            'determined_count': determined_count,
            'determined_mask': determined_mask
        }


def solve_level(rows, cols, start, grid, locked=None, num_workers=None):
    """
    求解关卡主函数。
    :param rows: 网格行数
    :param cols: 网格列数
    :param start: 起始位置 (row, col)
    :param grid: 2D列表，每个单元格包含方向开口列表
    :param locked: 2D布尔列表，标记锁定格子（可选）
    :param num_workers: 并行工作进程数，None 表示使用 os.cpu_count() // 2
    :return: 包含求解结果的字典
    """
    solver = LevelSolver(rows, cols, start, grid, locked, num_workers)
    return solver.solve_with_hint()

def solve_step1_deductive(rows, cols, start, grid, locked=None, num_workers=None):
    """
    求解步骤1：仅执行演绎推理。
    :param rows: 网格行数
    :param cols: 网格列数
    :param start: 起始位置 (row, col)
    :param grid: 2D列表，每个单元格包含方向开口列表
    :param locked: 2D布尔列表，标记锁定格子（可选）
    :param num_workers: 并行工作进程数，None 表示使用 os.cpu_count() // 2
    :return: 包含求解结果的字典
    """
    solver = LevelSolver(rows, cols, start, grid, locked, num_workers)
    init_result = solver._initialize_candidates_and_dir_state()
    if init_result is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '演绎推理'
        }
    candidates, dir_state = init_result
    
    if not solver._deductive_iteration(candidates, dir_state):
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '演绎推理'
        }
    
    solution, determined_mask = solver._build_solution_and_mask(candidates)
    if solution is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '演绎推理'
        }
    
    determined_count = sum(sum(row) for row in determined_mask)
    
    rotations = []
    for r in range(solver.rows):
        for c in range(solver.cols):
            if determined_mask[r][c] and solver.grid[r][c] != solution[r][c]:
                for rotation in range(4):
                    rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                    if rotated == solution[r][c]:
                        rotations.append((r, c, rotation * 90))
                        break
    
    return {
        'success': True,
        'solution': solution,
        'rotations': rotations,
        'rotation_count': len(rotations),
        'determined_count': determined_count,
        'determined_mask': determined_mask,
        'step': '演绎推理'
    }

def solve_step2_assumption(rows, cols, start, grid, locked=None, num_workers=None):
    """
    求解步骤2：演绎推理 + 假设推理。
    :param rows: 网格行数
    :param cols: 网格列数
    :param start: 起始位置 (row, col)
    :param grid: 2D列表，每个单元格包含方向开口列表
    :param locked: 2D布尔列表，标记锁定格子（可选）
    :param num_workers: 并行工作进程数，None 表示使用 os.cpu_count() // 2
    :return: 包含求解结果的字典
    """
    solver = LevelSolver(rows, cols, start, grid, locked, num_workers)
    init_result = solver._initialize_candidates_and_dir_state()
    if init_result is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '假设推理'
        }
    candidates, dir_state = init_result
    
    # 先运行演绎推理
    if not solver._deductive_iteration(candidates, dir_state):
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '假设推理'
        }
    
    solution, determined_mask = solver._build_solution_and_mask(candidates)
    if solution is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '假设推理'
        }
    
    if all(all(row) for row in determined_mask):
        determined_count = sum(sum(row) for row in determined_mask)
        rotations = []
        for r in range(solver.rows):
            for c in range(solver.cols):
                if determined_mask[r][c] and solver.grid[r][c] != solution[r][c]:
                    for rotation in range(4):
                        rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                        if rotated == solution[r][c]:
                            rotations.append((r, c, rotation * 90))
                            break
        return {
            'success': True,
            'solution': solution,
            'rotations': rotations,
            'rotation_count': len(rotations),
            'determined_count': determined_count,
            'determined_mask': determined_mask,
            'step': '假设推理'
        }
    
    max_assumption_iter_count = 1000
    assumption_iter_count = 0
    while True:
        assumption_iter_count += 1
        if assumption_iter_count > max_assumption_iter_count:
            break
        undetermined = []
        for r in range(solver.rows):
            for c in range(solver.cols):
                if not determined_mask[r][c]:
                    undetermined.append((r, c))
        if not undetermined:
            break
        
        undetermined.sort(key=lambda pos: len(candidates[pos[0]][pos[1]]))
        
        tasks = []
        for r, c in undetermined:
            for rot in candidates[r][c]:
                tasks.append((r, c, rot))
        
        if not tasks:
            break
        
        with mp.Pool(processes=solver.num_workers) as pool:
            starmap_args = []
            for r, c, rot in tasks:
                solver.candidates = candidates
                solver.dir_state = dir_state
                solver_copy = copy.deepcopy(solver)
                del solver.candidates
                del solver.dir_state
                starmap_args.append((solver_copy, r, c, rot))
            
            results = pool.starmap(_check_rotation_task, starmap_args)
        
        any_excluded = False
        victory_solution = None
        for (r, c, rot), result in zip(tasks, results):
            if result == 'exclude':
                if rot in candidates[r][c]:
                    candidates[r][c].discard(rot)
                    any_excluded = True
            elif result == 'victory':
                # 找到胜利解
                solver.candidates = candidates
                solver.dir_state = dir_state
                solver_copy = copy.deepcopy(solver)
                del solver.candidates
                del solver.dir_state
                solver_copy.candidates[r][c] = {rot}
                solver_copy._deductive_iteration(solver_copy.candidates, solver_copy.dir_state)
                victory_solution, victory_mask = solver_copy._build_solution_and_mask(solver_copy.candidates)
                break
        
        # 如果找到胜利解，直接返回
        if victory_solution is not None:
            determined_count = sum(sum(row) for row in victory_mask)
            rotations = []
            for r in range(solver.rows):
                for c in range(solver.cols):
                    if victory_mask[r][c] and solver.grid[r][c] != victory_solution[r][c]:
                        for rotation in range(4):
                            rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                            if rotated == victory_solution[r][c]:
                                rotations.append((r, c, rotation * 90))
                                break
            return {
                'success': True,
                'solution': victory_solution,
                'rotations': rotations,
                'rotation_count': len(rotations),
                'determined_count': determined_count,
                'determined_mask': victory_mask,
                'step': '假设推理'
            }
        
        if not any_excluded:
            break
        
        if not solver._deductive_iteration(candidates, dir_state):
            return {
                'success': False,
                'solution': None,
                'rotations': [],
                'rotation_count': 0,
                'determined_count': 0,
                'determined_mask': [],
                'step': '假设推理'
            }
        
        solution, determined_mask = solver._build_solution_and_mask(candidates)
        if solution is None:
            return {
                'success': False,
                'solution': None,
                'rotations': [],
                'rotation_count': 0,
                'determined_count': 0,
                'determined_mask': [],
                'step': '假设推理'
            }
        
        if all(all(row) for row in determined_mask):
            determined_count = sum(sum(row) for row in determined_mask)
            rotations = []
            for r in range(solver.rows):
                for c in range(solver.cols):
                    if determined_mask[r][c] and solver.grid[r][c] != solution[r][c]:
                        for rotation in range(4):
                            rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                            if rotated == solution[r][c]:
                                rotations.append((r, c, rotation * 90))
                                break
            return {
                'success': True,
                'solution': solution,
                'rotations': rotations,
                'rotation_count': len(rotations),
                'determined_count': determined_count,
                'determined_mask': determined_mask,
                'step': '假设推理'
            }
    
    # 假设推理结束，返回当前部分解
    determined_count = sum(sum(row) for row in determined_mask)
    rotations = []
    for r in range(solver.rows):
        for c in range(solver.cols):
            if determined_mask[r][c] and solver.grid[r][c] != solution[r][c]:
                for rotation in range(4):
                    rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                    if rotated == solution[r][c]:
                        rotations.append((r, c, rotation * 90))
                        break
    return {
        'success': True,
        'solution': solution,
        'rotations': rotations,
        'rotation_count': len(rotations),
        'determined_count': determined_count,
        'determined_mask': determined_mask,
        'step': '假设推理',
        'fully_solved': all(all(row) for row in determined_mask)  # 可选，表示是否完全解
    }

def solve_step3_search(rows, cols, start, grid, locked=None, num_workers=None):
    """
    求解步骤3：深度优先搜索（假设假设推理已完成）。
    :param rows: 网格行数
    :param cols: 网格列数
    :param start: 起始位置 (row, col)
    :param grid: 2D列表，每个单元格包含方向开口列表
    :param locked: 2D布尔列表，标记锁定格子（可选）
    :param num_workers: 并行工作进程数，None 表示使用 os.cpu_count() // 2
    :return: 包含求解结果的字典
    """
    solver = LevelSolver(rows, cols, start, grid, locked, num_workers)
    init_result = solver._initialize_candidates_and_dir_state()
    if init_result is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '搜索求解'
        }
    candidates, dir_state = init_result
    
    result = solver._dfs_search(candidates, dir_state)
    if result is None:
        return {
            'success': False,
            'solution': None,
            'rotations': [],
            'rotation_count': 0,
            'determined_count': 0,
            'determined_mask': [],
            'step': '搜索求解'
        }
    
    solution, determined_mask = result
    determined_count = sum(sum(row) for row in determined_mask)
    
    rotations = []
    for r in range(solver.rows):
        for c in range(solver.cols):
            if determined_mask[r][c] and solver.grid[r][c] != solution[r][c]:
                for rotation in range(4):
                    rotated = [(d + rotation) % 4 for d in solver.grid[r][c]]
                    if rotated == solution[r][c]:
                        rotations.append((r, c, rotation * 90))
                        break
    
    return {
        'success': True,
        'solution': solution,
        'rotations': rotations,
        'rotation_count': len(rotations),
        'determined_count': determined_count,
        'determined_mask': determined_mask,
        'step': '搜索求解'
    }