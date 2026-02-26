import random
from collections import deque
from constants import UP, RIGHT, DOWN, LEFT, DIR_VECTORS, OPPOSITE

def generate_tree(rows, cols, start, start_openings):
    """
    使用随机Prim算法生成一棵覆盖所有格子的树。
    从水源的所有开口方向开始，维护一个可扩展的边界集合，每次随机选择一个边界格子并连接一个未访问邻居。
    返回邻居列表 neighbors[r][c] = [(nr,nc), ...] 或 None（失败）。
    """
    visited = [[False] * cols for _ in range(rows)]
    neighbors = [[[] for _ in range(cols)] for _ in range(rows)]
    
    # 水源
    sr, sc = start
    visited[sr][sc] = True
    # 水源的度数由其开口数决定，之后不再增加
    source_degree = len(start_openings)
    
    # 可扩展边界集合：已访问且仍有剩余度数且存在未访问邻居的格子（不包括水源，因为水源度数已固定）
    active = []
    
    # 处理水源开口
    for direction in start_openings:
        dr, dc = DIR_VECTORS[direction]
        nr, nc = sr + dr, sc + dc
        if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
            neighbors[sr][sc].append((nr, nc))
            neighbors[nr][nc].append((sr, sc))
            visited[nr][nc] = True
            # 新格子加入 active（度数当前为1，剩余2）
            active.append((nr, nc))
    
    # 如果水源开口数为0，则直接失败（但之前已过滤，不会发生）
    
    # 循环直到所有格子被访问或 active 为空
    total_cells = rows * cols
    visited_count = sum(sum(row) for row in visited)
    
    while active and visited_count < total_cells:
        # 随机选择一个活跃格子
        idx = random.randint(0, len(active) - 1)
        r, c = active[idx]
        
        # 收集未访问邻居
        unvisited = []
        for dr, dc in DIR_VECTORS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                unvisited.append((nr, nc))
        
        if not unvisited:
            # 没有未访问邻居，从活跃列表中移除
            active.pop(idx)
            continue
        
        # 当前格子的度数（已连接数）
        current_degree = len(neighbors[r][c])
        max_degree = 2 if (r, c) == start else 3
        if current_degree >= max_degree:
            # 度数已满，不能再连接，移除
            active.pop(idx)
            continue
        
        # 随机选择一个未访问邻居
        nr, nc = random.choice(unvisited)
        
        # 建立连接
        neighbors[r][c].append((nr, nc))
        neighbors[nr][nc].append((r, c))
        visited[nr][nc] = True
        visited_count += 1
        
        # 新格子加入活跃列表（度数当前为1，剩余2）
        active.append((nr, nc))
        
        # 检查当前格子度数是否已满或再无未访问邻居，若是则从活跃中移除
        # 注意：当前格子可能还有未访问邻居但度数已满，则不能继续连接，应移除
        if len(neighbors[r][c]) >= max_degree:
            # 度数已满，移除
            active.pop(idx)
        else:
            # 度数未满，但可能已无未访问邻居？但上面已经检查过有未访问才连接，但连接后可能还有未访问，所以保留
            # 但需要重新检查是否还有未访问邻居，如果没有也要移除
            # 我们可以留在下次循环再处理，但为了减少无效循环，可以现在检查
            # 简单起见，不移除，下次循环会处理
            pass
    
    # 检查是否所有格子都被访问
    if all(all(row) for row in visited):
        return neighbors
    else:
        return None

def generate_level(rows, cols, max_attempts=1000, shuffle=True):
    """
    生成一个水管工关卡，水源位于正中心 (rows//2, cols//2)。
    返回 (start, grid) 二元组，其中 grid 为每个格子的开口列表（已随机打乱）。
    shuffle 为 True 时，对每个格子随机旋转，增加谜题难度。
    """
    if rows < 2 or cols < 2:
        raise ValueError("Grid must be at least 2x2")
    start = (rows // 2, cols // 2)

    # 随机选择水源格子的类型：单向、弯折、直线、T型
    start_type = random.choice(['end', 'corner', 'straight', 't'])
    start_openings = []
    
    if start_type == 'end':
        # 单向：随机选择一个方向
        start_openings = [random.choice([UP, RIGHT, DOWN, LEFT])]
    elif start_type == 'corner':
        # 弯折：选择两个相邻的方向
        if start[0] > 0 and start[1] > 0:
            start_openings = [UP, RIGHT]
        elif start[0] > 0 and start[1] < cols - 1:
            start_openings = [UP, LEFT]
        elif start[0] < rows - 1 and start[1] > 0:
            start_openings = [DOWN, RIGHT]
        else:
            start_openings = [DOWN, LEFT]
    elif start_type == 'straight':
        # 直线：选择两个相对的方向
        if random.choice([True, False]):
            start_openings = [UP, DOWN]
        else:
            start_openings = [LEFT, RIGHT]
    elif start_type == 't':
        # T型：选择三个方向
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
    
    # 如果没有有效的开口方向，重新生成
    if not valid_openings:
        return generate_level(rows, cols, max_attempts, shuffle)
    
    start_openings = valid_openings

    for _ in range(max_attempts):
        neighbors = generate_tree(rows, cols, start, start_openings)
        if neighbors:
            break
    else:
        raise RuntimeError("Failed to generate a valid tree after many attempts")

    # 根据邻居关系确定每个格子的开口方向
    grid = [[[] for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if (r, c) == start:
                # 水源格子使用预设的开口方向
                grid[r][c] = start_openings
            else:
                dirs = []
                for nr, nc in neighbors[r][c]:
                    if nr == r - 1: dirs.append(UP)
                    elif nr == r + 1: dirs.append(DOWN)
                    elif nc == c - 1: dirs.append(LEFT)
                    elif nc == c + 1: dirs.append(RIGHT)
                grid[r][c] = dirs

    # 随机打乱每个格子的方向，增加谜题难度
    if shuffle:
        for r in range(rows):
            for c in range(cols):
                if grid[r][c]:  # 所有格子（包括水源）都可以旋转
                    rot = random.randint(0, 3)
                    if rot != 0:
                        grid[r][c] = [(d + rot) % 4 for d in grid[r][c]]

    return start, grid