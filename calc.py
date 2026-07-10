# -*- coding: utf-8 -*-
"""双模计算器 — 科学计算器 + 程序员计算器同屏并排，支持一键互传结果。

依赖：PySide6, sympy
启动：python calc.py
"""
#345
import sys
import os
import math

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QGuiApplication, QFont, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QPushButton,
    QLabel, QGridLayout, QVBoxLayout, QHBoxLayout, QSizePolicy,
)


def resource_path(name):
    """兼容开发环境与 PyInstaller 打包环境的资源路径。
    打包后资源在 sys._MEIPASS（临时解压目录）下；开发时在脚本所在目录。
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ---- sympy 引擎 ----
from sympy import (
    parse_expr, sin, cos, tan, log, sqrt, pi, E, S,
)


# =========================================================================
#  数值格式化工具（程序员器四进制显示）
# =========================================================================

def _group(s, n):
    """把字符串从右起每 n 位插一个空格。"""
    if not s:
        return s
    rev = s[::-1]
    chunks = [rev[i:i + n] for i in range(0, len(rev), n)]
    return " ".join(chunks)[::-1]


def format_bin(value):
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    return sign + _group(format(abs(value), "b"), 4)


def format_dec(value):
    sign = "-" if value < 0 else ""
    return sign + _group(str(abs(value)), 3).replace(" ", ",")


def format_hex(value):
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    return sign + _group(format(abs(value), "X"), 4)


def fmt_result(v):
    """格式化科学器结果（int 或 float）。"""
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    if v == 0:
        v = 0.0
    s = f"{v:.15g}"
    if s == "-0":
        s = "0"
    return s


def prettify(expr):
    """把内部 ASCII 表达式转成显示用符号。"""
    if not expr:
        return ""
    s = expr
    s = s.replace("**", "^")
    s = s.replace("*", "×")
    s = s.replace("/", "÷")
    s = s.replace("sqrt(", "√(")
    s = s.replace("pi", "π")
    s = s.replace("E", "e")
    s = s.replace("-", "−")
    return s


# =========================================================================
#  科学器求值
# =========================================================================

def sci_evaluate(expr, use_degrees):
    """返回 (value, error_msg)。value 为 int/float 或 None。"""
    expr = (expr or "").strip()
    if not expr:
        return None, None
    local_dict = {
        "sin": (lambda x: sin(x * pi / 180) if use_degrees else sin(x)),
        "cos": (lambda x: cos(x * pi / 180) if use_degrees else cos(x)),
        "tan": (lambda x: tan(x * pi / 180) if use_degrees else tan(x)),
        "log": (lambda x: log(x, 10)),   # log = 常用对数（底 10）
        "ln":  (lambda x: log(x)),        # 自然对数
        "sqrt": sqrt,
        "pi": pi,
        "E": E,
    }
    try:
        # 注意：不能用 global_dict={}，否则会清掉 sympy 内部的 Integer 等，
        # 导致连 "2" 都无法解析。保持默认全局环境即可。
        parsed = parse_expr(expr, local_dict=local_dict)
        r = parsed.evalf(15)
    except ZeroDivisionError:
        return None, "不能除以零"
    except Exception:
        return None, "表达式无效"

    if r in (S.Infinity, S.NegativeInfinity, S.ComplexInfinity, S.NaN):
        return None, "不能除以零"
    if r.is_real is False:
        return None, "不支持复数结果"
    try:
        if r.is_integer:
            return int(r), None
        fv = float(r)
        if not math.isfinite(fv):
            return None, "结果超出范围"
        return fv, None
    except (OverflowError, ValueError):
        return None, "结果超出范围"


# =========================================================================
#  样式
# =========================================================================

QSS = """
QMainWindow { background: #f0f0f0; }
QFrame#sciPanel, QFrame#progPanel {
    background: #ffffff; border: 2px solid #dadbdc; border-radius: 10px;
}
QFrame[active="true"] { border-color: #0078d4; }
QLabel#panelTitle { font-size: 13px; font-weight: 700; color: #444; padding: 4px 2px; }
QLabel#exprLine { color: #8a8a8a; font-size: 15px; }
QLabel#resultLine { color: #111; font-size: 30px; font-weight: 700; padding: 14px 8px; }
QLabel#resultLine[err="true"] { color: #c0392b; font-size: 22px; }
QLabel#progLine {
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 15px; color: #333; padding: 2px 6px;
}
QPushButton {
    background: #fafafa; border: 1px solid #e4e4e4; border-radius: 6px;
    font-size: 15px; padding: 12px 0; color: #222;
}
QPushButton:hover { background: #f0f0f0; }
QPushButton:pressed { background: #e2e2e2; }
QPushButton:disabled { color: #c2c2c2; background: #f6f6f6; }
QPushButton[role="num"] { background: #ffffff; font-size: 17px; font-weight: 600; }
QPushButton[role="op"] { background: #eef3f8; font-size: 17px; }
QPushButton[role="func"] { background: #e7f0fa; color: #1a5fb4; }
QPushButton[role="hex"] { background: #e7f5e9; color: #1d7a35; font-weight: 700; font-size: 16px; }
QPushButton[role="bit"] { background: #fdf0e0; color: #b5651d; font-weight: 600; }
QPushButton[role="base"] { background: #eef6ef; font-family: Consolas, monospace; text-align: left; padding: 6px 10px; }
QPushButton[role="base"][current="true"] { background: #1d7a35; color: white; }
QPushButton[role="equals"] { background: #0078d4; color: white; font-size: 20px; font-weight: 700; }
QPushButton[role="equals"]:hover { background: #1a86d8; }
QPushButton[role="clear"] { background: #fbeaea; color: #c0392b; }
"""


def refresh_style(w):
    w.style().unpolish(w)
    w.style().polish(w)


# =========================================================================
#  面板基类
# =========================================================================

class Panel(QFrame):
    role = ""

    def __init__(self, mainwin):
        super().__init__()
        self.mw = mainwin
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 10, 12, 10)
        self._lay.setSpacing(8)

    # ---- 子类用的按钮构造器 ----
    def make_btn(self, text, role, onclick, grid, row, col,
                 rowspan=1, colspan=1):
        b = QPushButton(text)
        b.setProperty("role", role)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 用闭包吞掉 clicked 信号的 bool 参数，确保 onclick 始终被无参调用，
        # 这样 onclick 里的 lambda 默认参数捕获（lambda c=ch: ...）才不会被污染。
        def _handle(_checked=False):
            self.mw.set_active_panel(self.role)
            onclick()

        b.clicked.connect(_handle)
        grid.addWidget(b, row, col, rowspan, colspan)
        return b


# =========================================================================
#  科学计算器面板
# =========================================================================

class SciPanel(Panel):
    role = "sci"

    def __init__(self, mainwin):
        super().__init__(mainwin)
        self.setObjectName("sciPanel")

        self.use_degrees = True          # 默认 DEG
        self.expr = ""                    # 内部 ASCII 表达式
        self.last_result = None           # 最近结果（int/float）
        self.error = None                 # 错误信息或 None
        self.just_evaled = False          # 刚求值/刚接收

        title = QLabel("科学计算器")
        title.setObjectName("panelTitle")
        self._lay.addWidget(title)

        # 显示区
        self.expr_label = QLabel("")
        self.expr_label.setObjectName("exprLine")
        self.expr_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lay.addWidget(self.expr_label)

        self.result_label = QLabel("0")
        self.result_label.setObjectName("resultLine")
        self.result_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lay.addWidget(self.result_label)

        # 右键菜单：复制 / 粘贴
        self.result_label.setContextMenuPolicy(Qt.ActionsContextMenu)
        act_copy = QAction("复制", self)
        act_copy.triggered.connect(self.do_copy)
        act_paste = QAction("粘贴", self)
        act_paste.triggered.connect(self.do_paste)
        self.result_label.addAction(act_copy)
        self.result_label.addAction(act_paste)

        # 按键网格
        grid_container = QWidget()
        g = QGridLayout(grid_container)
        g.setSpacing(6)
        g.setContentsMargins(0, 0, 0, 0)

        # 第 0 行：括号 / 清除 / 退格
        self.make_btn("(", "op", lambda: self._input("("), g, 0, 0)
        self.make_btn(")", "op", lambda: self._input(")"), g, 0, 1)
        self.make_btn("C", "clear", self.do_clear, g, 0, 2)
        self.make_btn("⌫", "clear", self.do_backspace, g, 0, 3)
        self.make_btn("x²", "func", lambda: self._input("**2"), g, 0, 4)

        # 第 1 行：三角 / 对数
        self.make_btn("sin", "func", lambda: self._input("sin("), g, 1, 0)
        self.make_btn("cos", "func", lambda: self._input("cos("), g, 1, 1)
        self.make_btn("tan", "func", lambda: self._input("tan("), g, 1, 2)
        self.make_btn("log", "func", lambda: self._input("log("), g, 1, 3)
        self.make_btn("ln", "func", lambda: self._input("ln("), g, 1, 4)

        # 第 2 行：幂 / 根 / 常数
        self.make_btn("xʸ", "func", lambda: self._input("**"), g, 2, 0)
        self.make_btn("√", "func", lambda: self._input("sqrt("), g, 2, 1)
        self.make_btn("π", "func", lambda: self._input("pi"), g, 2, 2)
        self.make_btn("e", "func", lambda: self._input("E"), g, 2, 3)
        self.make_btn("1/x", "func", lambda: self._input("1/("), g, 2, 4)

        # 第 3 行
        self.make_btn("7", "num", lambda: self._input("7"), g, 3, 0)
        self.make_btn("8", "num", lambda: self._input("8"), g, 3, 1)
        self.make_btn("9", "num", lambda: self._input("9"), g, 3, 2)
        self.make_btn("÷", "op", lambda: self._input("/"), g, 3, 3)
        self.make_btn("%", "op", lambda: self._input("%"), g, 3, 4)

        # 第 4 行
        self.make_btn("4", "num", lambda: self._input("4"), g, 4, 0)
        self.make_btn("5", "num", lambda: self._input("5"), g, 4, 1)
        self.make_btn("6", "num", lambda: self._input("6"), g, 4, 2)
        self.make_btn("×", "op", lambda: self._input("*"), g, 4, 3)
        self.make_btn("(", "op", lambda: self._input("("), g, 4, 4)

        # 第 5 行
        self.make_btn("1", "num", lambda: self._input("1"), g, 5, 0)
        self.make_btn("2", "num", lambda: self._input("2"), g, 5, 1)
        self.make_btn("3", "num", lambda: self._input("3"), g, 5, 2)
        self.make_btn("−", "op", lambda: self._input("-"), g, 5, 3)
        # 等号跨 2 行
        self.make_btn("=", "equals", self.do_equals, g, 5, 4, rowspan=2)

        # 第 6 行
        self.make_btn("0", "num", lambda: self._input("0"), g, 6, 0, colspan=2)
        self.make_btn(".", "num", lambda: self._input("."), g, 6, 2)
        self.make_btn("+", "op", lambda: self._input("+"), g, 6, 3)

        self._lay.addWidget(grid_container, 1)
        self._update_view()

    # ---- 输入 ----
    def _is_operator(self, token):
        return token in ("+", "-", "*", "/", "**")

    def _input(self, token):
        # 出错状态下任意输入 = 清除并以新输入开始
        if self.error is not None:
            self.error = None
            self.expr = ""
            self.just_evaled = False

        if self.just_evaled:
            # 刚求值/接收后
            if self._is_operator(token) or token == ")":
                # 用结果继续运算
                self.expr = fmt_result(self.last_result)
            else:
                # 数字/常数/函数/括号 → 开始新表达式
                self.expr = ""
            self.just_evaled = False

        self.expr += token
        self._update_view()

    def do_backspace(self):
        if self.error is not None:
            self.do_clear()
            return
        if self.just_evaled:
            return
        if self.expr:
            self.expr = self.expr[:-1]
        self._update_view()

    def do_clear(self):
        self.expr = ""
        self.last_result = None
        self.error = None
        self.just_evaled = False
        self._update_view()

    def do_equals(self):
        if self.error is not None:
            return
        if not self.expr.strip():
            return
        val, err = sci_evaluate(self.expr, self.use_degrees)
        if err is not None:
            self.error = err
            self.last_result = None
        else:
            self.last_result = val
            self.just_evaled = True
        self._update_view()

    # ---- 显示 ----
    def _update_view(self):
        self.expr_label.setText(prettify(self.expr))
        if self.error is not None:
            self.result_label.setText(self.error)
            self.result_label.setProperty("err", True)
        else:
            self.result_label.setProperty("err", False)
            if self.last_result is not None:
                self.result_label.setText(fmt_result(self.last_result))
            else:
                self.result_label.setText("0")
        refresh_style(self.result_label)

    # ---- 对外接口 ----
    def get_result_value(self):
        """返回当前可用于互传的数值（int/float），出错或无结果返回 None。"""
        if self.error is not None:
            return None
        return self.last_result

    def get_display_text(self):
        """复制用文本。"""
        if self.error is not None:
            return ""
        if self.last_result is not None:
            return fmt_result(self.last_result)
        return prettify(self.expr)

    def receive_value(self, value):
        """从程序员器接收一个数值。"""
        self.error = None
        self.last_result = value
        self.expr = fmt_result(value)
        self.just_evaled = True
        self._update_view()

    def paste_text(self, text):
        """粘贴：把剪贴板内容求值后替换当前值（支持小数/负数/表达式）。"""
        if not text:
            return
        text = text.strip()
        if not text:
            return
        # 尝试作为表达式求值；成功则替换当前值
        val, err = sci_evaluate(text, self.use_degrees)
        if err is not None:
            # 求值失败：仅保留可解析字符追加到表达式（兼容旧行为）
            if self.error is not None:
                self.expr = ""
                self.error = None
                self.just_evaled = False
            if self.just_evaled:
                self.expr = ""
                self.just_evaled = False
            clean = "".join(
                c for c in text if c in "0123456789.+-*/^()eE"
            )
            self.expr += clean
        else:
            # 求值成功：替换为结果
            self.error = None
            self.last_result = val
            self.expr = text
            self.just_evaled = True
        self._update_view()

    # ---- 复制/粘贴 ----
    def do_copy(self):
        text = self.get_display_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def do_paste(self):
        self.paste_text(QGuiApplication.clipboard().text())

    # ---- 键盘 ----
    def handle_key(self, event):
        k = event.key()
        t = event.text()
        if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Equal):
            self.do_equals(); return True
        if k == Qt.Key_Backspace:
            self.do_backspace(); return True
        if k == Qt.Key_Escape:
            self.do_clear(); return True
        if t == "":
            return False
        if t in "0123456789.":
            self._input(t); return True
        if t in "+-*/()":
            self._input(t); return True
        if t == "^":
            self._input("**"); return True
        if t == "%":
            self._input("%"); return True
        return False


# =========================================================================
#  程序员计算器面板
# =========================================================================

class ProgPanel(Panel):
    role = "prog"

    BASE_OF = {16: "HEX", 10: "DEC", 2: "BIN"}
    DIGITS_FOR = {
        2:  "01",
        8:  "01234567",
        10: "0123456789",
        16: "0123456789ABCDEF",
    }

    def __init__(self, mainwin):
        super().__init__(mainwin)
        self.setObjectName("progPanel")

        self.base = 16
        self.entry = "0"          # 当前正在输入的数字串（当前进制字母表）
        self.staged = 0           # 待运算左操作数
        self.pending_op = None    # 待执行运算符
        self.fresh = True         # 下一个数字是否替换当前 entry
        self.just_result = False  # 刚得到结果（= 或互传）
        self.error = None
        self._flash = None        # 截断提示文本

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

        self.digit_btns = {}

        title = QLabel("程序员计算器")
        title.setObjectName("panelTitle")
        self._lay.addWidget(title)

        # 三进制显示行（同时也是切换进制的按钮）：BIN、HEX、DEC
        disp = QVBoxLayout()
        disp.setSpacing(2)
        self.line_btns = {}
        for base, name in [(2, "BIN"), (16, "HEX"), (10, "DEC")]:
            b = QPushButton(name)
            b.setProperty("role", "base")
            b.setProperty("current", base == self.base)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, bb=base: self.mw.set_active_panel(self.role))
            b.clicked.connect(lambda _checked=False, bb=base: self.set_base(bb))
            # 右键菜单：复制本行 / 粘贴
            b.setContextMenuPolicy(Qt.ActionsContextMenu)
            act_copy = QAction("复制", self)
            act_copy.triggered.connect(lambda _checked=False, bb=base: self.do_copy_line(bb))
            act_paste = QAction("粘贴", self)
            act_paste.triggered.connect(self.do_paste)
            b.addAction(act_copy)
            b.addAction(act_paste)
            self.line_btns[base] = b
            disp.addWidget(b)
        self._lay.addLayout(disp)

        # 按键网格（6 列）
        grid_container = QWidget()
        g = QGridLayout(grid_container)
        g.setSpacing(6)
        g.setContentsMargins(0, 6, 0, 0)

        # A ~ F
        letters = ["A", "B", "C", "D", "E", "F"]
        for i, ch in enumerate(letters):
            self.digit_btns[ch] = self.make_btn(
                ch, "hex", lambda c=ch: self.input_digit(c), g, 0, i)

        # 7 8 9 ÷ × −
        for i, ch in enumerate(["7", "8", "9"]):
            self.digit_btns[ch] = self.make_btn(
                ch, "num", lambda c=ch: self.input_digit(c), g, 1, i)
        self.make_btn("÷", "op", lambda: self.press_op("/"), g, 1, 3)
        self.make_btn("×", "op", lambda: self.press_op("*"), g, 1, 4)
        self.make_btn("−", "op", lambda: self.press_op("-"), g, 1, 5)

        # 4 5 6 + % ⌫
        for i, ch in enumerate(["4", "5", "6"]):
            self.digit_btns[ch] = self.make_btn(
                ch, "num", lambda c=ch: self.input_digit(c), g, 2, i)
        self.make_btn("+", "op", lambda: self.press_op("+"), g, 2, 3)
        self.make_btn("%", "op", lambda: self.press_op("%"), g, 2, 4)
        self.make_btn("⌫", "clear", self.do_backspace, g, 2, 5)

        # 1 2 3 AND OR XOR
        for i, ch in enumerate(["1", "2", "3"]):
            self.digit_btns[ch] = self.make_btn(
                ch, "num", lambda c=ch: self.input_digit(c), g, 3, i)
        self.make_btn("AND", "bit", lambda: self.press_op("AND"), g, 3, 3)
        self.make_btn("OR", "bit", lambda: self.press_op("OR"), g, 3, 4)
        self.make_btn("XOR", "bit", lambda: self.press_op("XOR"), g, 3, 5)

        # 0 NOT C = (=跨2列)
        self.digit_btns["0"] = self.make_btn(
            "0", "num", lambda: self.input_digit("0"), g, 4, 0)
        self.make_btn("NOT", "bit", self.do_not, g, 4, 1)
        self.make_btn("C", "clear", self.do_clear, g, 4, 2)
        self.make_btn("=", "equals", self.do_equals, g, 4, 3, colspan=3)

        self._lay.addWidget(grid_container, 1)

        self._update_keys()
        self._update_view()

    # ---- 进制 ----
    def set_base(self, base):
        if base == self.base:
            return
        val = self.current_value()
        self.base = base
        self.entry = self.to_base(val)
        self.fresh = True
        self.just_result = False
        # 出错状态下切进制 = 清错
        self.error = None
        for b, btn in self.line_btns.items():
            btn.setProperty("current", b == base)
            refresh_style(btn)
        self._update_keys()
        self._update_view()

    def _update_keys(self):
        allowed = self.DIGITS_FOR[self.base]
        for ch, btn in self.digit_btns.items():
            btn.setEnabled(ch in allowed)

    # ---- 数值转换 ----
    def to_base(self, n):
        if n == 0:
            return "0"
        sign = "-" if n < 0 else ""
        a = abs(n)
        if self.base == 16:
            return sign + format(a, "X")
        if self.base == 10:
            return sign + str(a)
        if self.base == 8:
            return sign + format(a, "o")
        return sign + format(a, "b")

    def current_value(self):
        try:
            e = self.entry
            if e in ("", "-"):
                return 0
            neg = e.startswith("-")
            body = e[1:] if neg else e
            val = int(body if body else "0", self.base)
            return -val if neg else val
        except ValueError:
            return 0

    # ---- 运算 ----
    @staticmethod
    def _trunc_div(a, b):
        if b == 0:
            raise ZeroDivisionError
        q = abs(a) // abs(b)
        if (a < 0) ^ (b < 0):
            q = -q
        return q

    def _apply(self, a, b, op):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return self._trunc_div(a, b)
        if op == "%":
            return a - self._trunc_div(a, b) * b
        if op == "AND":
            return a & b
        if op == "OR":
            return a | b
        if op == "XOR":
            return a ^ b
        raise ValueError("未知运算符")

    # ---- 输入 ----
    def input_digit(self, ch):
        if self.error is not None:
            self.do_clear()
        if self.fresh or self.just_result:
            # 开始新的操作数输入：非零数字替换占位 0；0 保留 0
            self.entry = ch if ch != "0" else "0"
            self.fresh = False
            self.just_result = False
        else:
            # 避免前导零：当前是单个 "0" 时，新数字替换它而非追加
            if self.entry == "0":
                self.entry = ch if ch != "0" else "0"
            elif self.entry == "-0":
                self.entry = "-" + ch
            else:
                self.entry += ch
        self._update_view()

    def press_op(self, op):
        if self.error is not None:
            self.do_clear()
            return
        if self.pending_op is not None and not self.fresh:
            # 链式：先算出中间结果
            try:
                self.staged = self._apply(self.staged,
                                          self.current_value(),
                                          self.pending_op)
            except ZeroDivisionError:
                self._set_error("不能除以零")
                return
            self.entry = self.to_base(self.staged)
        else:
            self.staged = self.current_value()
        self.pending_op = op
        self.fresh = True
        self.just_result = False
        self._update_view()

    def do_not(self):
        if self.error is not None:
            self.do_clear()
            return
        val = ~self.current_value()
        self.entry = self.to_base(val)
        self.staged = val
        self.pending_op = None
        self.fresh = True
        self.just_result = True
        self._update_view()

    def do_equals(self):
        if self.error is not None:
            return
        if self.pending_op is None:
            # 没有 pending 运算符：把当前值固化为结果
            self.staged = self.current_value()
            self.entry = self.to_base(self.staged)
            self.fresh = True
            self.just_result = True
            self._update_view()
            return
        try:
            result = self._apply(self.staged,
                                 self.current_value(),
                                 self.pending_op)
        except ZeroDivisionError:
            self._set_error("不能除以零")
            return
        self.entry = self.to_base(result)
        self.staged = result
        self.pending_op = None
        self.fresh = True
        self.just_result = True
        self._update_view()

    def do_backspace(self):
        if self.error is not None:
            self.do_clear()
            return
        if self.fresh or self.just_result:
            return
        self.entry = self.entry[:-1]
        if self.entry in ("", "-"):
            self.entry = "0"
        self._update_view()

    def do_clear(self):
        self.entry = "0"
        self.staged = 0
        self.pending_op = None
        self.fresh = True
        self.just_result = False
        self.error = None
        self._flash = None
        self._update_view()

    def _set_error(self, msg):
        self.error = msg
        self._update_view()

    # ---- 显示 ----
    def _update_view(self):
        val = self.current_value()
        self.line_btns[2].setText(
            "BIN    " + format_bin(val))
        self.line_btns[16].setText(
            "HEX    " + format_hex(val))
        self.line_btns[10].setText(
            "DEC    " + (self._flash if self._flash else format_dec(val)))
        if self.error is not None:
            self.line_btns[self.base].setText(
                self.BASE_OF[self.base] + "    " + self.error)
        for b in self.line_btns.values():
            refresh_style(b)

    def _flash_truncate(self):
        self._flash = "⚠ 已截断小数"
        self._flash_timer.start(1500)
        self._update_view()

    def _clear_flash(self):
        self._flash = None
        self._update_view()

    # ---- 对外接口 ----
    def get_value(self):
        return self.current_value()

    def get_display_text(self):
        """复制用：当前进制的无分隔串。"""
        if self.error is not None:
            return ""
        return self.to_base(self.current_value())

    def receive_value(self, value, truncated=False):
        """从科学器接收一个 int。"""
        self.error = None
        self.entry = self.to_base(value)
        self.staged = value
        self.pending_op = None
        self.fresh = True
        self.just_result = True
        self._update_view()
        if truncated:
            self._flash_truncate()

    def paste_text(self, text):
        if not text:
            return
        if self.error is not None:
            self.do_clear()
        text = text.strip()
        truncated = False
        if "." in text:
            truncated = True
            # 截断小数部分
            text = text.split(".")[0]
        # 只保留当前进制合法字符与可选前导负号
        allowed = self.DIGITS_FOR[self.base]
        sign = ""
        if text.startswith("-"):
            sign = "-"
            text = text[1:]
        clean = "".join(c for c in text.upper() if c in allowed)
        if clean == "":
            clean = "0"
        self.entry = sign + clean
        self.staged = self.current_value()
        self.pending_op = None
        self.fresh = True
        self.just_result = True
        self._update_view()
        if truncated:
            self._flash_truncate()

    # ---- 复制/粘贴 ----
    def do_copy_line(self, base):
        """按指定进制复制当前值（无分隔）。"""
        if self.error is not None:
            return
        val = self.current_value()
        sign = "-" if val < 0 else ""
        a = abs(val)
        if base == 16:
            text = sign + format(a, "X")
        elif base == 10:
            text = sign + str(a)
        elif base == 2:
            text = sign + format(a, "b")
        else:
            text = self.to_base(val)
        if text:
            QGuiApplication.clipboard().setText(text)

    def do_copy(self):
        self.do_copy_line(self.base)

    def do_paste(self):
        self.paste_text(QGuiApplication.clipboard().text())

    # ---- 键盘 ----
    def handle_key(self, event):
        k = event.key()
        t = event.text()
        if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Equal):
            self.do_equals(); return True
        if k == Qt.Key_Backspace:
            self.do_backspace(); return True
        if k == Qt.Key_Escape:
            self.do_clear(); return True
        if k == Qt.Key_Ampersand:
            self.press_op("AND"); return True
        if k == Qt.Key_Bar:
            self.press_op("OR"); return True
        if k == Qt.Key_AsciiCircum:
            self.press_op("XOR"); return True
        if k == Qt.Key_AsciiTilde:
            self.do_not(); return True
        if t == "":
            return False
        if t in "0123456789":
            if t in self.DIGITS_FOR[self.base]:
                self.input_digit(t); return True
            return True
        u = t.upper()
        if u in "ABCDEF":
            if u in self.DIGITS_FOR[self.base]:
                self.input_digit(u); return True
            return True
        if t in "+-*/%":
            self.press_op(t); return True
        return False


# =========================================================================
#  主窗口
# =========================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("双模计算器")
        self.setWindowIcon(QIcon(resource_path("Calculator_37533.ico")))
        self.resize(900, 560)
        self.setMinimumSize(780, 480)

        self.sci = SciPanel(self)
        self.prog = ProgPanel(self)
        self.active = "sci"

        central = QWidget()
        central.setObjectName("central")
        h = QHBoxLayout(central)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(10)
        h.addWidget(self.sci, 1)
        h.addWidget(self.prog, 1)

        self.setCentralWidget(central)

        self.setStyleSheet(QSS)
        self._apply_active_style()

        # 捕获所有键盘事件
        app = QApplication.instance()
        app.installEventFilter(self)

        # 启动后居中
        self._center()

    def _center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())

    # ---- 焦点面板 ----
    def set_active_panel(self, role):
        if role == self.active:
            return
        self.active = role
        self._apply_active_style()

    def _apply_active_style(self):
        self.sci.setProperty("active", self.active == "sci")
        self.prog.setProperty("active", self.active == "prog")
        refresh_style(self.sci)
        refresh_style(self.prog)

    # ---- 复制/粘贴 ----
    def _copy_result(self):
        if self.active == "sci":
            self.sci.do_copy()
        else:
            self.prog.do_copy()

    def _paste(self):
        if self.active == "sci":
            self.sci.do_paste()
        else:
            self.prog.do_paste()

    # ---- 键盘事件过滤 ----
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if self._handle_key(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_key(self, event):
        k = event.key()
        mods = event.modifiers()

        # Ctrl+C / Ctrl+V
        if mods & Qt.ControlModifier:
            if k == Qt.Key_C:
                self._copy_result(); return True
            if k == Qt.Key_V:
                self._paste(); return True
            # 其它 Ctrl 组合放行
            return False

        # Tab / Shift+Tab 切换面板
        if k == Qt.Key_Tab:
            if mods & Qt.ShiftModifier:
                self.set_active_panel("sci" if self.active == "prog" else "prog")
            else:
                self.set_active_panel("prog" if self.active == "sci" else "sci")
            return True

        # 分发给当前面板
        if self.active == "sci":
            return self.sci.handle_key(event)
        return self.prog.handle_key(event)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
