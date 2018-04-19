import pywinauto
from pywinauto import clipboard
from pywinauto import keyboard
from .captcha_recognize import captcha_recognize
import pandas as pd
import io
from .const import BALANCE_CONTROL_ID_GROUP
import time


class THSTrader:

    def __init__(self, exe_path=r"C:\同花顺软件\同花顺\xiadan.exe"): 
        print("正在连接客户端:", exe_path, "......")
        self.app = pywinauto.Application().connect(path=exe_path, timeout=10)
        print("连接成功!!!")
        self.main_wnd = self.app.top_window()
    
    
    
    def buy(self, stock_no, price, amount):
        """ 买入 """
        self.__select_menu(['买入[F1]'])
        return self.__trade(stock_no, price, amount)

    def sell(self, stock_no, price, amount):
        """ 卖出 """
        self.__select_menu(['卖出[F2]'])
        return self.__trade(stock_no, price, amount)

    def cancel_entrust(self, entrust_no):
        """ 撤单 """
        self.__select_menu(['撤单[F3]'])
        cancelable_entrusts = self.__get_grid_data()  # 获取可以撤单的条目

        for i, entrust in enumerate(cancelable_entrusts):
            if str(entrust["合同编号"]) == str(entrust_no):  # 对指定合同进行撤单
                return self.__cancel_by_double_click(i)
        return {"success": False, "msg": "没找到指定订单"}

    def get_balance(self):
        """ 获取资金情况 """
        self.__select_menu(['查询[F4]', '资金股票'])

        result = {}
        for key, control_id in BALANCE_CONTROL_ID_GROUP.items():
            result[key] = float(
                self.main_wnd.window(control_id=control_id, class_name='Static').window_text()
            )
        return result

    def get_position(self):
        """ 获取持仓 """
        self.__select_menu(['查询[F4]', '资金股票'])
        return self.__get_grid_data()

    def get_today_entrusts(self):
        """ 获取当日委托 """
        self.__select_menu(['查询[F4]', '当日委托'])
        return self.__get_grid_data()

    def get_today_trades(self):
        self.__select_menu(['查询[F4]', '当日成交'])
        return self.__get_grid_data()

    def __trade(self, stock_no, price, amount):
        time.sleep(1)
        self.main_wnd.window(control_id=0x408, class_name="Edit").set_text(str(stock_no))  # 设置股票代码
        self.main_wnd.window(control_id=0x409, class_name="Edit").set_text(str(price))  # 设置价格
        self.main_wnd.window(control_id=0x40A, class_name="Edit").set_text(str(amount))  # 设置股数目
        time.sleep(1)
        self.main_wnd.window(control_id=0x3EE, class_name="Button").click()   # 点击卖出
        keyboard.SendKeys("{ENTER}")  
        time.sleep(1)
        self.app.top_window().set_focus()
        keyboard.SendKeys("y")  
        #self.app.top_window().window(control_id=0x6, class_name='Button').click()  # 二次确认买入
        time.sleep(1)
        result = self.app.top_window().window(control_id=0x3EC, class_name='Static').window_text()
        try:
            self.app.top_window().set_focus()
            keyboard.SendKeys("{ENTER}")  
            #self.app.top_window().window(control_id=0x2, class_name='Button').click()  # 确定买入成功的结果
        except:
            pass
        return self.__parse_result(result)

    def __get_grid_data(self):
        """ 获取grid里面的数据 """
        grid = self.main_wnd.window(control_id=0x417, class_name='CVirtualGridCtrl')

        grid.set_focus().right_click()  # 模拟右键
        keyboard.SendKeys('c')  # 模拟发送C

        file_path = "tmp.png"
        self.app.top_window().window(control_id=0x965, class_name='Static').\
            CaptureAsImage().save(file_path)  # 保存验证码

        captcha_num = captcha_recognize(file_path)  # 识别验证码
        print(captcha_num)
        self.app.top_window().window(control_id=0x964, class_name='Edit').set_text(captcha_num)  # 模拟输入验证码
        
        self.app.top_window().set_focus()
        keyboard.SendKeys("{ENTER}")   # 模拟发送enter，点击确定

        data = clipboard.GetData()
        df = pd.read_csv(io.StringIO(data), delimiter='\t', na_filter=False)
        return df.to_dict('records')

    def __select_menu(self, path):
        """ 点击左边菜单 """
        self.__get_left_menus_handle().get_item(path).click()

    def __get_left_menus_handle(self):
        while True:
            try:
                handle = self.main_wnd.window(control_id=129, class_name='SysTreeView32')
                handle.wait('ready', 2)  # sometime can't find handle ready, must retry
                return handle
            except:
                pass

    def __cancel_by_double_click(self, row):
        """ 通过双击撤单 """
        x = 50
        y = 30 + 16 * row
        self.app.top_window().window(control_id=0x417, class_name='CVirtualGridCtrl').double_click(coords=(x, y))
        self.app.top_window().window(control_id=0x6, class_name='Button').click()  # 确定撤单
        result = self.app.top_window().window(control_id=0x3EC, class_name='Static').window_text()
        self.app.top_window().window(control_id=0x2, class_name='Button').click()  # 确定撤单
        return self.__parse_result(result)

    @staticmethod
    def __parse_result(result):
        """ 解析买入卖出的结果 """
        
        # "您的买入委托已成功提交，合同编号：865912566。"
        # "您的卖出委托已成功提交，合同编号：865967836。"
        # "您的撤单委托已成功提交，合同编号：865967836。"
        # "系统正在清算中，请稍后重试！ "
        
        if r"已成功提交，合同编号：" in result:
            return {
                "success": True,
                "msg": result,
                "entrust_no": result.split("合同编号：")[1].split("。")[0]
            }
        else:
            return {
                "success": False,
                "msg": result
            }

