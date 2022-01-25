# -*- coding: utf-8 -*-
"""
Created on 2021/11/22 0022 2:01
@python version     : 3.6.3
@version            : 1.0
@author             : Wangjw
@describe           : 练手用的俄罗斯方块小游戏
@guide              :  
"""

import tkinter as tk
# from tkinter import ttk
from enum import Enum
from time import sleep, time
import random
import threading
from queue import Queue


class Status(Enum):
    New = 0,
    Stop = 1,
    Run = 2,
    Pause = 3,
    Close = 4


class Tetris:
    """
    主类
    """
    def __init__(self):
        # 程序属性
        self.xblocks = 10  # 纵横向格子数
        self.yblocks = 20
        self.blockPatten_False = '  '  # dictBlocks有/无方块时的样式
        self.blockPatten_True = '■'

        self.status = Status.New  # 游戏整体状态

        self.block_can_move = False  # block是否处于可控制（能响应键盘）状态
        self.block_can_drop = False  # block是否会自动下降
        self.speed = 1  # 游戏速度
        self.speedlines = 0  # 控制游戏速度的要素
        self.score = 0  # 得分
        self.lines = 0  # 消除行数
        self.blockCount = 0  # 已使用的的方块数

        self.forceDrop_time = 0.00  # 可以强制出发drop的时间
        self.forceDrop_time_delay = 0.5  # block移动在底部或障碍上方移动时推迟强制drop的时间，单位（秒）

        self.cmdQueue = Queue()

        # UI
        self.master = tk.Tk()  # 主窗体
        self.master.protocol("WM_DELETE_WINDOW", self.on_exit)

        self.master.title("Tertis")

        self.fontsize = 20
        self.font = ('新宋体', -1 * self.fontsize)

        self.width = self.fontsize * self.xblocks + self.fontsize * 6 + 10
        self.height = self.fontsize * self.yblocks
        self.move_to_center()

        self.varBlocks = tk.StringVar()  # 显示全局blocks的动态字符串
        self.varNextBlocks = tk.StringVar()  # 显示下两个blocks的动态字符串
        self.varStatus = tk.StringVar()  # 显示游戏状态的动态字符串

        self.set_menu()  # 装载菜单
        self.set_layout()  # 装载游戏面板
        self.display_init()  # 展示初始界面

        # 游戏整体点阵状态 使用dictBlocks[x][y]获取某个点应显示True还是False
        self.dictBlocks = {x: {y: False for y in range(-3, self.yblocks + 1)} for x in range(1, self.xblocks + 1)}  # 初始化Blocks
        self.TetrisSelf = self  # 实例的引用地址，后续传给实例化的Block，用于属性、方法的调用
        self.block = self.Block(self.TetrisSelf)  # 实例化Block

        self.master.bind('<Key>', self.key_event)  # 为窗口绑定键盘按键事件

        self.thdExecCmd = threading.Thread(target=self.execCmd)
        self.thdExecCmd.start()

        self.thdDrop = threading.Thread(target=self.forceDrop)
        self.thdDrop.start()

        self.master.mainloop()

    class Block:
        def __init__(self, root):
            """
            方块类。用于记录、调整方块的属性。
            整个游戏过程中永远只会有一个实例化的方块。方块落地后，不会生成新的方块实例，而是刷新当前方块实例的属性。
            :param root Tetris主类，用于调用实例化的Tetris中的属性及函数。
            """
            self.debug = True

            self.root = root

            self.dictblockType = {
                0: 'None',
                1: 'I',
                2: 'T',
                3: 'O',
                4: 'J',
                5: 'L',
                6: 'Z',
                7: 'S'
            }

            self.dictTypeCode = {  # 每种方块对应的字符串
                'I': '11110000',
                'T': '01110010',
                'O': '01100110',
                'J': '00101110',
                'L': '01000111',
                'Z': '11000110',
                'S': '00110110'
            }

            self.posList = []  # 记录组成block的每个点的位置 [(x1, y1), (x2, y2), (x3, y3), (x4, y4)

            self.type = self.dictblockType[random.randint(1, 7)]

            # 旋转用对象
            self.poseOrder = 0  # 用于记录block旋转后的姿态，每个方块都分为姿态0、姿态1、姿态2、姿态3
            self.dictDistribution = {}  # 记录每种方块各个姿态的点分布
            self.dictSwitchDelta = {}  # 记录每种方块旋转时每个点x,y的位移
            self.dicOffset = {}  # 记录每种方块旋转后额外的x,y的位移（针对T、S、Z型）

            self.next_1 = self.dictblockType[random.randint(1, 7)]
            self.next_2 = self.dictblockType[random.randint(1, 7)]

            self.left_x = 0
            self.right_x = 0
            self.bottom_y = 0

        def create(self):
            # 获取方块类型
            self.root.blockCount += 1

            self.type = self.next_1
            self.poseOrder = 0
            self.next_1 = self.next_2
            self.next_2 = self.dictblockType[random.randint(1, 7)]

            # 获取、记录各点的坐标
            patten = self.root.display_str_to_patten(self.dictTypeCode[self.type], self.root.xblocks, '1', '0')
            self.posList = self.root.get_pos_list(patten)
            self.root.display_lbNextBlocks()

            # 方块与其他点重合则游戏结束
            for (x, y) in self.posList:
                if self.root.dictBlocks[x][y]:
                    self.root.gameover()
                    break

            # 更新左右下边界值
            self.update_border(*self.get_border(self.posList))

            # 通知blocksPanel、nextblocksPanel、statusPanel更新图案
            self.root.update_dictBlocks(self.get_pos_update_info(True))
            self.root.display_lbStatus()

        def move(self, direction):
            """
            移动方块
            :param direction : 移动的方向
            """
            if direction == 'left':
                # 如已无移动空间，则不移动
                if self.left_x == 1:
                    return
                posList_new = [(p[0] - 1, p[1]) for p in self.posList]  # 移动后的各点坐标

            elif direction == 'right':
                if self.right_x == self.root.xblocks:
                    return
                posList_new = [(p[0] + 1, p[1]) for p in self.posList]

            else:
                if self.bottom_y == self.root.yblocks:  # 落到底部触发blockdie
                    self.root.update_dictBlocks(self.get_pos_update_info(True))  # block的点化为其他点
                    self.root.blockdie(self.posList)
                    return
                posList_new = [(p[0], p[1] + 1) for p in self.posList]

            # 移动后的格子坐标已经显示为True且不是因为移动前的方块自身显示True，则不移动（左右）或出发blockdie（下）
            for p_new in posList_new:
                if self.root.dictBlocks[p_new[0]][p_new[1]] and p_new not in self.posList:
                    if direction == 'down':  # 落到底部出发blockdie
                        self.root.update_dictBlocks(self.get_pos_update_info(True))  # block的点化为障碍点
                        self.root.blockdie(self.posList)
                        return
                    else:
                        return
            # 符合移动条件，生成移动信息并推送
            info_old = self.get_pos_update_info(False)  # 获取点消失的指令
            self.posList = posList_new
            info_new = self.get_pos_update_info(True)  # 获取点显示的指令
            self.root.update_dictBlocks('|'.join([info_old, info_new]))
            self.update_border(*self.get_border(self.posList))  # 更新边界

            # 移动后如果方块接触到面板底部或障碍，则更新延缓强制生效时间
            self.delay_forceDrop(self.posList)

        def switch(self):
            # 各个方块每种形态的点分布
            if len(self.dictDistribution) == 0:
                self.dictDistribution = {  # 每种方块各个姿态对应的点分布
                    'I': ([(1, 2), (2, 2), (3, 2), (4, 2)], [(3, 1), (3, 2), (3, 3), (3, 4)], [(1, 3), (2, 3), (3, 3), (4, 3)], [(2, 1), (2, 2), (2, 3), (2, 4)]),
                    'T': ([(2, 2), (3, 2), (4, 2), (3, 3)], [(3, 1), (2, 2), (3, 2), (3, 3)], [(3, 1), (2, 2), (3, 2), (4, 2)], [(3, 1), (3, 2), (4, 2), (3, 3)]),
                    'O': ([(2, 2), (3, 2), (2, 3), (3, 3)], [(2, 2), (3, 2), (2, 3), (3, 3)], [(2, 2), (3, 2), (2, 3), (3, 3)], [(2, 2), (3, 2), (2, 3), (3, 3)]),
                    'J': ([(3, 2), (1, 3), (2, 3), (3, 3)], [(2, 1), (2, 2), (2, 3), (3, 3)], [(2, 2), (3, 2), (4, 2), (2, 3)], [(2, 2), (3, 2), (3, 3), (3, 4)]),
                    'L': ([(2, 2), (2, 3), (3, 3), (4, 3)], [(2, 2), (3, 2), (2, 3), (2, 4)], [(1, 2), (2, 2), (3, 2), (3, 3)], [(3, 1), (3, 2), (2, 3), (3, 3)]),
                    'Z': ([(1, 2), (2, 2), (2, 3), (3, 3)], [(3, 1), (2, 2), (3, 2), (2, 3)], [(2, 2), (3, 2), (3, 3), (4, 3)], [(3, 2), (2, 3), (3, 3), (2, 4)]),
                    'S': ([(3, 2), (4, 2), (2, 3), (3, 3)], [(2, 2), (2, 3), (3, 3), (3, 4)], [(2, 2), (3, 2), (1, 3), (2, 3)], [(2, 1), (2, 2), (3, 2), (3, 3)])
                }

            if len(self.dictSwitchDelta) == 0:
                self.dictSwitchDelta = {
                    (1, 1): (3, 0), (2, 1): (2, 1), (3, 1): (1, 2), (4, 1): (0, 3),
                    (1, 2): (2, -1), (2, 2): (1, 0), (3, 2): (0, 1), (4, 2): (-1, 2),
                    (1, 3): (1, -2), (2, 3): (0, -1), (3, 3): (-1, 0), (4, 3): (-2, 1),
                    (1, 4): (0, -3), (2, 4): (-1, -2), (3, 4): (-2, -1), (4, 4): (-3, 0)
                }

            if len(self.dicOffset) == 0:
                self.dicOffset = {'T': [(0, -1), (0, -1), (0, -1), (0, -1)],
                                  'S': [(1, -1), (0, 1), (0, 0), (-1, 0)],
                                  'Z': [(-1, 0), (0, 0), (0, -1), (1, 1)]
                                  }

            # 计算旋转后的各个点坐标
            posList_new = []

            distribution = self.dictDistribution[self.type][self.poseOrder]  # 各个点的分布
            for n in range(0, 4):  # 逐个点计算旋转后的坐标
                x = self.posList[n][0]  # 点当前的坐标
                y = self.posList[n][1]
                delta_x = self.dictSwitchDelta[distribution[n]][0]
                delta_y = self.dictSwitchDelta[distribution[n]][1]
                if self.type in 'TSZ':  # 非对称旋转，需修正坐标
                    offset_x = self.dicOffset[self.type][self.poseOrder][0]
                    offset_y = self.dicOffset[self.type][self.poseOrder][1]
                    x_new = x + delta_x + offset_x
                    y_new = y + delta_y + offset_y
                else:
                    x_new = x + delta_x
                    y_new = y + delta_y
                posList_new.append((x_new, y_new))

            # 对posList_new进行重新排序
            posList_new = sorted(posList_new, key=(lambda p: (p[1], p[0])))

            # 判断各个点是否合理
            if not self.is_new_position_ok(posList_new, self.posList):
                posOKFlag = False
                # 是否超出边界
                left_new, right_new, bottom_new = self.get_border(posList_new)
                if left_new < 1 or right_new > self.root.xblocks or bottom_new > self.root.yblocks:
                    posList_new_moved = []
                    if left_new < 1:  # 超出左边界：需要右移
                        move_right = 1 - left_new
                        posList_new_moved = [(x + move_right, y) for (x, y) in posList_new]
                    elif right_new > self.root.xblocks:  # 超出右边界：需要左移
                        move_left = right_new - self.root.xblocks
                        posList_new_moved = [(x - move_left, y) for (x, y) in posList_new]
                    elif bottom_new > self.root.yblocks:  # 超出底部：需要上移
                        move_up = bottom_new - self.root.yblocks
                        posList_new_moved = [(x, y - move_up) for (x, y) in posList_new]
                    if self.is_new_position_ok(posList_new_moved, self.posList):
                        posOKFlag = True
                    # else:
                    #     return  # 平移后位置仍不合理，则不旋转
                if not posOKFlag:
                    # 方块所在点已被障碍点占用根据情况上移,左移，右移或
                    for x_new, y_new in posList_new:
                        if self.root.dictBlocks[x_new][y_new] and (x_new, y_new) not in self.posList:
                            left_dsts = x_new - left_new  # 当前点距离左边距的距离
                            right_dsts = right_new - x_new  # 当前点距离右边距的距离
                            bottom_dsts = bottom_new - y_new  # 当前点距离底边距的距离

                            if not posOKFlag:
                                if bottom_dsts == min(bottom_dsts, left_dsts, right_dsts):  # 优先上移
                                    posList_new_moved = [(x, y - bottom_dsts - 1) for (x, y) in posList_new]
                                    if self.is_new_position_ok(posList_new_moved, self.posList):
                                        posOKFlag = True

                            if not posOKFlag:
                                if left_dsts == min(bottom_dsts, left_dsts, right_dsts):
                                    posList_new_moved = [(x + left_dsts + 1, y) for (x, y) in posList_new]
                                    if self.is_new_position_ok(posList_new_moved, self.posList):
                                        posOKFlag = True

                            if not posOKFlag:
                                if right_dsts == min(bottom_dsts, left_dsts, right_dsts):
                                    posList_new_moved = [(x - right_dsts - 1, y) for (x, y) in posList_new]
                                    if self.is_new_position_ok(posList_new_moved, self.posList):
                                        posOKFlag = True

                if not posOKFlag:
                    return

                posList_new = posList_new_moved

            # 可以旋转
            self.poseOrder += 1 if self.poseOrder < 3 else -3  # 旋转成功后切换姿态

            info_old = self.get_pos_update_info(False)  # 获取点消失的指令

            self.posList = posList_new

            info_new = self.get_pos_update_info(True)  # 获取点显示的指令
            self.root.update_dictBlocks('|'.join([info_old, info_new]))
            self.update_border(*self.get_border(self.posList))  # 更新边界

            # 旋转后如果方块接触到面板底部或障碍，则更新延缓强制生效时间
            self.delay_forceDrop(self.posList)

        def delay_forceDrop(self, posList):
            """
            延缓强制drop的生效
            用于block在底部或其他障碍上被玩家移动或旋转后，保留一段时间停止强制下降方块一保证玩家可以继续操作。
            :param posList：移动或旋转后的坐标列表
            """
            for (x, y) in posList:
                if self.bottom_y == self.root.yblocks or (self.root.dictBlocks[x][y+1] is True and (x, y + 1) not in posList):
                    self.root.forceDrop_time = time() + self.root.forceDrop_time_delay
                    return

        def is_new_position_ok(self, postList_new, posList_old):
            """
            判断列表中的各个点的移动后的位置是否合理。
            判断原则：1:在边界内，2:不和已占用的格子重叠
            :return Boolean
            """
            for x, y in postList_new:
                if x < 1 or x > self.root.xblocks or y > self.root.yblocks:  # 超出边界，返回False
                    return False
                if self.root.dictBlocks[x][y] and (x, y) not in posList_old:  # 移动后的格子坐标在背景中已经显示为True且不是因为移动前的方块自身显示True，
                    return False
            return True

        def get_pos_update_info(self, display: bool):
            """
            获取方块各点更新的命令码
            :param display:更新为True或者False
            """
            strList = ['%s-%s-%s' % (str(x[0]), str(x[1]), str(display)) for x in self.posList]
            return '|'.join(strList)

        def get_block_code(self, order):
            """
            获取当前、下一个、再一下的方块的编码
            """
            if order == 0:
                blockType = self.type
            elif order == 1:
                blockType = self.next_1
            else:
                blockType = self.next_2
            return self.dictTypeCode[blockType]

        def get_border(self, postList):
            """
            计算block的左、右、下边界的x,y值。
            :param postList 记录block各个point的列表
            """
            left_x = min([x[0] for x in postList])
            right_x = max([x[0] for x in postList])
            bottom_y = max([x[1] for x in postList])
            return left_x, right_x, bottom_y

        def update_border(self, left_x, right_x, bottom_y):
            """
            计算block的左右边界的x值。
            """
            self.left_x = left_x
            self.right_x = right_x
            self.bottom_y = bottom_y

    def move_to_center(self):
        width_win = self.master.winfo_screenwidth()
        height_win = self.master.winfo_screenheight()
        x = width_win / 2 - self.width / 2
        y = height_win / 2 - self.height / 2
        self.master.geometry('%dx%d+%d+%d' % (self.width, self.height, x, y))

    def set_menu(self):
        menubar = tk.Menu(self.master)
        # 游戏
        menubar.add_command(label='重置', command=self.restart)
        # 退出’
        menubar.add_command(label='退出', command=self.on_exit)

        # 显示菜单
        self.master.config(menu=menubar)

    def set_layout(self):
        self.lbBlocks = tk.Label(self.master, font=self.font, textvariable=self.varBlocks, relief='groove', justify='left', anchor='w')
        self.lbBlocks.pack(side=tk.LEFT)
        # self.lbBlocks.grid(row=0, column=0, rowspan=2, sticky='NW')

        self.lbNextBlocks = tk.Label(self.master, font=self.font, textvariable=self.varNextBlocks, relief='groove', justify='left', anchor='ne')
        self.lbNextBlocks.pack(side=tk.TOP)
        # self.lbNextBlocks.grid(row=0, column=1)

        self.lbStatus = tk.Label(self.master, font=self.font, textvariable=self.varStatus, relief='groove', justify='left',
                                 anchor='ne')
        self.lbStatus.pack(side=tk.BOTTOM)
        # self.lbStatus.grid(row=1, column=1)

    def display_init(self):
        """
        运行游戏后的初始界面
        """
        # Blocks
        dispStr = self.blockPatten_True + self.blockPatten_False * (self.xblocks - 2) + self.blockPatten_True + '\n'
        dispStr += '\n' * 4
        dispStr += self.blockPatten_False * int((self.xblocks - 6) / 2) + 'ＴＥＴＲＩＳ' + self.blockPatten_False * int((self.xblocks - 6) / 2) + '\n'
        dispStr += '\n'
        dispStr += self.blockPatten_False * int((self.xblocks - 6) / 2) + '  by  Luke  ' + self.blockPatten_False * int((self.xblocks - 6) / 2) + '\n'
        dispStr += '\n' * 4
        dispStr += 'Press ENTER to Start\n'
        dispStr += '\n' * (self.yblocks - 14)
        dispStr += self.blockPatten_True + self.blockPatten_False * (self.xblocks - 2) + self.blockPatten_True
        self.varBlocks.set(dispStr)

        # NextBlocks
        dispStr = 'Next:       \n' + '\n' * 5
        self.varNextBlocks.set(dispStr)

        # Status
        dispStr = 'SPEED:\n'
        dispStr += '%12s' % 99999999
        dispStr += '\nSCORE:\n'
        dispStr += '%12s' % 99999999
        dispStr += '\nLINES:\n'
        dispStr += '%12s' % 99999999
        dispStr += '\nBLOCKS:\n'
        dispStr += '%12s' % 99999999
        dispStr += '\n' * (self.yblocks - 17)
        dispStr += 'STATUS:\n'
        dispStr += '%12s' % Status(self.status).name

        self.varStatus.set(dispStr)

    def update_dictBlocks(self, strInfo):
        """
        更新dictBlocks
        :param strInfo ： "横坐标-纵坐标-True|横坐标-纵坐标-False" 格式的信息
        """
        infoList = strInfo.split('|')
        for l in infoList:
            x = int(l.split('-')[0])  # 横坐标
            y = int(l.split('-')[1])  # 纵坐标
            b = True if l.split('-')[2] == 'True' else False  # 是否显示
            if 1 <= x <= self.xblocks and 1 <= y <= self.yblocks:
                self.dictBlocks[x][y] = b

        # 刷新界面
        self.display_lbBlocks()

    def display_lbBlocks(self):
        dispStr = ''
        for y in range(1, self.yblocks + 1):
            for x in range(1, self.xblocks + 1):
                if self.dictBlocks[x][y]:
                    dispStr += self.blockPatten_True
                else:
                    dispStr += self.blockPatten_False
            if y != self.yblocks:  # 除最后一行，其余每行打印完后要换行
                dispStr += '\n'
        self.varBlocks.set(dispStr)

    def display_lbNextBlocks(self):
        dispStr = 'Next:\n'
        dispStr += self.display_str_to_patten(self.block.get_block_code(1), 6, self.blockPatten_True, self.blockPatten_False)
        dispStr += '\n\n'
        dispStr += self.display_str_to_patten(self.block.get_block_code(2), 6, self.blockPatten_True, self.blockPatten_False)
        dispStr += '\n'

        self.varNextBlocks.set(dispStr)

    def display_lbStatus(self):
        dispStr = 'SPEED:\n'
        dispStr += '%12s' % self.speed
        dispStr += '\nSCORE:\n'
        dispStr += '%12s' % self.score
        dispStr += '\nLINES:\n'
        dispStr += '%12s' % self.lines
        dispStr += '\nBLOCKS:\n'
        dispStr += '%12s' % self.blockCount
        dispStr += '\n' * (self.yblocks - 17)
        dispStr += 'STATUS:\n'
        dispStr += '%12s' % Status(self.status).name

        self.varStatus.set(dispStr)

    def display(self, blocks=True, nextBlocks=True, status=True):
        if blocks:
            self.display_lbBlocks()
        if nextBlocks:
            self.display_lbNextBlocks()
        if status:
            self.display_lbStatus()

    @staticmethod
    def display_str_to_patten(blockTypeCode: str, width: int, tPatten: str, fPatten: str):
        """
        将数字形式的方块状态字符串转换为图案形式的字符串
        :param blockTypeCode：方块的编码，固定为8位，每4位代表1行的格子点分布
        :param width：行宽。超过4将会自动补全
        :param tPatten : 编码为1时显示的格子图案
        :param fPatten : 编码为0时显示的格子图案
        11000110, 6, ■ ,□  →
        □■■□□□
        □□■■□□
        (Z型方块)
        """
        line_1 = '{str:0^{len}}'.format(str=blockTypeCode[:4], len=width)
        line_2 = '{str:0^{len}}'.format(str=blockTypeCode[4:], len=width)
        patten = '{}{}{}'.format(line_1, '\n', line_2).replace('0', fPatten).replace('1', tPatten)
        return patten

    @staticmethod
    def get_pos_list(patten):
        """
        返回点的坐标
        :param patten ： 用1和0表示的方块图案
        """
        posList = []
        x = 1
        y = 1
        for s in patten:
            if s == '1':
                posList.append((x, y))
            if s == '\n':
                y += 1
                x = 0
            x += 1
        return posList

    def key_event(self, event):
        """
        响应键盘按键。
        event.keycode——上：38  下：40  左：37  右：39  Enter：13 ESC：27 SPACE：32
        """
        # print(event.keycode)
        if self.status == Status.New:  #
            if event.keycode == 13:  # 回车
                self.status = Status.Run
                self.block.create()

                self.display_lbNextBlocks()
                self.display_lbStatus()

        elif self.status == Status.Run:
            if event.keycode in [37, 39, 40, 32]:
                if event.keycode == 37:  # 左键
                    self.cmdQueue.put('left')
                elif event.keycode == 39:  # 右键
                    self.cmdQueue.put('right')
                elif event.keycode == 40:  # 下键
                    self.cmdQueue.put('down')
                elif event.keycode == 32:  # 空格
                    self.cmdQueue.put('switch')
            elif event.keycode == 13:  # 回车
                self.status = Status.Pause
                self.display_lbStatus()

        elif self.status == Status.Pause:
            if event.keycode == 13:  # 回车
                self.status = Status.Run
                self.display_lbStatus()

        elif self.status == Status.Stop:
            pass

    def execCmd(self):
        while True:
            if self.status == Status.Close:
                break

            if not self.cmdQueue.empty():
                cmd = self.cmdQueue.get()
                if cmd == 'left':
                    self.block.move('left')
                elif cmd == 'right':
                    self.block.move('right')
                elif cmd == 'down':
                    self.block.move('down')
                elif cmd == 'switch':
                    self.block.switch()

    def forceDrop(self):
        """
        定时强制方块下落
        """
        while True:
            if self.status == Status.Close:
                break

            if self.status == Status.Run:

                if self.speed > 11:
                    delay = 11
                else:
                    delay = self.speed
                sleep((1101 - delay * 100) / 1000)

                if self.status != Status.Run:
                    continue
                if time() < self.forceDrop_time:
                    continue
                self.cmdQueue.put('down')

    def blockdie(self, posList):
        # 检查是否需要消除
        self.erase(posList)

        # 刷新Block属性
        self.display_lbStatus()
        self.block.create()

    def erase(self, posList):
        check_row_list = []  # 方块所在的行数
        for x, y in posList:
            if y not in check_row_list:
                check_row_list.append(y)

        erase_row_list = []  # 满足消除条件的行数
        for r in check_row_list:  # 逐行检查是否需要消除
            full = True
            for c in range(1, self.xblocks + 1):
                if not self.dictBlocks[c][r]:
                    full = False
                    break
            if full:
                erase_row_list.append(r)

        if len(erase_row_list) > 0:
            self.play_erase_animation(erase_row_list)

            dictBlocks_new = self.dictBlocks
            for y in range(self.yblocks, -3, -1):  # 逐行处理
                if y < -3 + len(erase_row_list):  # 补充最上方的空白
                    for x in range(1, self.xblocks):
                        dictBlocks_new[x][y] = False
                elif y in erase_row_list:  # 当前行为消除行，不处理
                    continue
                else:
                    drop_row_count = 0  # 计算需要下降的行数
                    for r in erase_row_list:
                        if r > y:  # 待消除行在当前行下方，需下移1行
                            drop_row_count += 1
                    for x in range(1, self.xblocks + 1):
                        dictBlocks_new[x][y + drop_row_count] = self.dictBlocks[x][y]
            self.dictBlocks = dictBlocks_new
            self.display_lbBlocks()

            # 根据消除的行数调整Score、Lines、Speed
            erase_lines = len(erase_row_list)
            self.lines += erase_lines
            self.score += int(erase_lines * (erase_lines + 1) / 2 * 100)
            self.speedlines += erase_lines
            self.speed = int(self.speedlines / 5) + 1

    def play_erase_animation(self, erase_row_list):
        interval = 0.1

        self.status = Status.Pause  # 切换状态，屏蔽其他指令输入

        for t in range(1, 4):
            for y in erase_row_list:
                for x in range(1, self.xblocks + 1):
                    self.dictBlocks[x][y] = False
            self.display_lbBlocks()

            sleep(interval)

            for y in erase_row_list:
                for x in range(1, self.xblocks + 1):
                    self.dictBlocks[x][y] = True
            self.display_lbBlocks()

            sleep(interval)

        self.status = Status.Run

    def gameover(self):
        self.status = Status.Stop
        self.display_lbStatus()

        # lbNextBlocks显示GameOver
        dispStr = '\n' * 2
        dispStr += '  ＧＡＭＥ  \n  ＯＶＥＲ  '
        dispStr += '\n' * 3
        self.varNextBlocks.set(dispStr)

    def restart(self):
        # 清空游戏面板
        self.dictBlocks = {x: {y: False for y in range(-3, self.yblocks + 1)} for x in range(1, self.xblocks + 1)}

        # 重置方块属性
        self.block.type = self.block.dictblockType[random.randint(1, 7)]
        self.block.next_1 = self.block.dictblockType[random.randint(1, 7)]
        self.block.next_2 = self.block.dictblockType[random.randint(1, 7)]
        self.block.create()

        # 重置状态
        self.score = 0
        self.lines = 0
        self.blockCount = 0
        self.speedlines = 0
        self.speed = 1
        self.status = Status.Run

        # 显示
        self.display()

    def on_exit(self):
        self.status = Status.Close
        self.master.destroy()

    def test(self):
        pass


if __name__ == "__main__":
    t = Tetris()
