# 方向常量
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

# 方向向量 (dr, dc) - 对应上、右、下、左四个方向的行列偏移量
DIR_VECTORS = [(-1, 0), (0, 1), (1, 0), (0, -1)]

# 方向符号 - 用于文字显示
DIR_SYMBOLS = ['↑', '→', '↓', '←']

# 相反方向映射 - 用于检查管道连接是否匹配
OPPOSITE = {UP: DOWN, RIGHT: LEFT, DOWN: UP, LEFT: RIGHT}

# 管道符号映射（根据开口列表生成显示字符）
def pipe_symbol(openings):
    """根据开口方向列表返回对应的文字符号"""
    if len(openings) == 1:
        # 终点（单开口）：显示方向箭头
        return DIR_SYMBOLS[openings[0]]
    elif len(openings) == 2:
        d1, d2 = openings
        if (d1 + 2) % 4 == d2:  # 相对方向 → 直线
            return '─' if d1 in (LEFT, RIGHT) else '│'
        else:  # 弯角
            # 根据两个方向确定弯角符号
            if {d1, d2} == {UP, RIGHT}: return '└'
            if {d1, d2} == {UP, LEFT}:  return '┘'
            if {d1, d2} == {DOWN, RIGHT}: return '┌'
            if {d1, d2} == {DOWN, LEFT}:  return '┐'
            return '?'  # 不应发生
    elif len(openings) == 3:
        # T型：缺失一个方向
        missing = ({UP, RIGHT, DOWN, LEFT} - set(openings)).pop()
        if missing == UP:    return '┬'
        if missing == RIGHT: return '┤'
        if missing == DOWN:  return '┴'
        if missing == LEFT:  return '├'
    else:
        return '█'  # 错误情况

# 管道图片类型和旋转角度映射（根据开口列表返回基础类型和旋转角度）
def pipe_image_info(openings):
    """
    根据开口方向列表返回 (基础类型, 旋转角度)
    基础类型: 'end', 'straight', 'corner', 't'
    旋转角度: 0, 90, 180, 270 (顺时针)
    """
    if len(openings) == 1:
        # 单开口（终点）：基础类型为 'end'，开口向上，旋转到目标方向
        return ('end', openings[0] * 90)
    elif len(openings) == 2:
        d1, d2 = openings
        if (d1 + 2) % 4 == d2:  # 相对方向 → 直线
            # 直线：基础类型为 'straight'，水平方向，旋转到目标方向
            return ('straight', d1 * 90 if d1 in (LEFT, RIGHT) else d1 * 90)
        else:  # 弯角
            # 弯角：基础类型为 'corner'，右下弯角（DOWN+RIGHT），旋转到目标方向
            if {d1, d2} == {DOWN, RIGHT}: return ('corner', 90)
            if {d1, d2} == {RIGHT, UP}:   return ('corner', 0)
            if {d1, d2} == {UP, LEFT}:    return ('corner', 270)
            if {d1, d2} == {LEFT, DOWN}:  return ('corner', 180)
    elif len(openings) == 3:
        # T型：基础类型为 't'，缺失上方向（即开口为 RIGHT, DOWN, LEFT），旋转到目标方向
        missing = ({UP, RIGHT, DOWN, LEFT} - set(openings)).pop()
        return ('t', missing * 90)
    return ('straight', 0)  # 默认返回