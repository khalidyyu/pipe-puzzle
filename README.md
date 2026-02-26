# 水管工游戏 (Pipe Puzzle)

一个经典的管道连接益智游戏，目标是通过旋转管道，让水流从起点出发，连通所有格子并到达每一个终点，且无断路和环路。

## 游戏特性

### 核心玩法
- **关卡自动生成**：每次运行都会生成一个新的、有解的关卡
- **可视化交互**：基于 tkinter 的图形界面
- **胜利检测**：实时检查是否满足胜利条件

### 求解器系统
- **演绎推理求解**：基于约束传播的智能求解算法
- **假设推理求解**：通过假设试探排除无效候选
- **搜索求解**：深度优先搜索(DFS)回溯算法
- **动画演示**：所有求解过程可逐步动画展示

### 辅助功能
- **排行榜系统**：记录最佳成绩
- **关卡导入导出**：支持保存和加载自定义关卡
- **格子锁定**：锁定已确定的格子防止误操作
- **水流可视化**：实时显示水流路径
- **环路检测**：检测并高亮显示水环和闭路
- **游戏介绍**：首次启动显示图文并茂的游戏规则说明

## 项目结构

```
pipe_game/
├── main.py                      # 程序入口
├── game.py                      # 游戏核心状态与胜利检测
├── ui.py                        # 用户界面
├── constants.py                 # 方向常量和管道符号定义
├── level_generator.py           # 关卡生成器（BFS算法）
├── level_solver.py              # 关卡求解器（约束推理算法）
├── leaderboard.py               # 排行榜管理
├── requirements.txt             # Python依赖包
├── pipe_game.spec               # PyInstaller打包配置
├── README.md                    # 项目说明文档
├── animated_solvers/            # 动画求解器模块
│   ├── animated_deductive_solver.py  # 演绎推理动画
│   ├── animated_assumption_solver.py # 假设推理动画
│   └── animated_search_solver.py     # 搜索求解动画
├── animated_generators/          # 动画生成器模块
│   └── animated_generator.py    # 关卡生成动画
├── images/                      # 管道图片资源
│   ├── README.md                # 图片说明
│   ├── pipe_end.png             # 终点管道
│   ├── pipe_straight.png        # 直管
│   ├── pipe_corner.png          # 弯管
│   ├── pipe_t.png               # T型管
│   ├── intro_new_game.jpg       # 游戏介绍-新游戏
│   ├── intro_victory.jpg        # 游戏介绍-通关
│   └── intro_loop_deadend.jpg   # 游戏介绍-环路和断路
└── dist/                        # 打包输出目录
    └── pipe_game.exe            # 可执行文件
```

## 运行要求

- Python 3.6+
- tkinter（Python标准库）
- Pillow（图片处理）
- ttkbootstrap（UI美化）

## 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：
```bash
pip install Pillow ttkbootstrap
```

## 如何运行

### 从源码运行
```bash
python main.py
```

### 运行打包版本
直接运行 `dist/pipe_game.exe`

## 操作说明

### 基本操作
- **左键点击**：旋转管道（顺时针90度）
- **右键点击**：锁定/解锁格子
- **滚轮**：滚动查看大型棋盘

### 菜单功能
- **游戏**：新游戏、重置、导入/导出关卡
- **求解**：演绎推理、假设推理、搜索求解（支持动画）
- **设置**：显示选项、动画速度调节

### 设置选项
- 显示水环和闭路
- 显示网格坐标
- 动画播放速度（10ms-1000ms，对数刻度）
- 排行榜记录选项

### 配置文件存储
游戏配置文件和排行榜数据存储在用户目录中：

**Windows**: `C:\Users\用户名\AppData\Roaming\PipeGame\`
- `settings.json` - 用户设置
- `leaderboard.json` - 排行榜数据

**Linux/Mac**: `~/.config/pipegame/`

## 算法说明

### 关卡生成
使用随机广度优先搜索(BFS)生成覆盖所有格子的树结构，确保每个关卡都有解。

### 求解算法
1. **演绎推理**：通过约束传播确定必然的旋转状态
2. **假设推理**：对未确定的格子进行假设试探，排除矛盾选项
3. **搜索求解**：使用DFS回溯搜索完整解

## 打包说明

使用PyInstaller打包为可执行文件：
```bash
pyinstaller pipe_game.spec
```

打包后的exe文件位于 `dist/pipe_game.exe`，可以直接运行，无需安装Python环境。

## 许可证

MIT License
