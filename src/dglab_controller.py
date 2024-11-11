import asyncio
import math
from typing import Optional

from PySide6.QtWidgets import (QPushButton, QComboBox, QSpinBox, QTextEdit, QCheckBox)
from PySide6.QtGui import QPixmap

from pydglab_ws import StrengthData, FeedbackButton, Channel, StrengthOperationType, RetCode, DGLabWSServer, DGLabLocalClient, PulseDataTooLong
from pydglab_ws.typing import PulseOperation
from pythonosc import dispatcher, osc_server, udp_client

from osc_binding import OSCActionRegistry, OSCParameterBindings, OSCParameterRegistry
from pulse import Pulse, PulseRegistry
from util import generate_qrcode

import logging
logger = logging.getLogger(__name__)

class UICallback:
    controller: 'DGLabController'
    pulse_registry: PulseRegistry
    parameter_registry: OSCParameterRegistry
    action_registry: OSCActionRegistry
    parameter_bindings: OSCParameterBindings

    start_button: QPushButton
    pulse_mode_a_combobox: QComboBox
    pulse_mode_b_combobox: QComboBox
    enable_chatbox_status_checkbox: QCheckBox
    dynamic_bone_mode_a_checkbox: QCheckBox
    dynamic_bone_mode_b_checkbox: QCheckBox
    strength_step_spinbox: QSpinBox
    enable_panel_control_checkbox: QCheckBox
    log_text_edit: QTextEdit

    def update_current_channel_display(self, channel_name: str): ...
    def update_qrcode(self, qrcode_pixmap: QPixmap): ...
    def bind_controller_settings(self): ...
    def update_connection_status(self, is_online: bool): ...
    def update_status(self, strength_data: StrengthData): ...

class ChannelPulseTask:
    def __init__(self, client: DGLabLocalClient, channel: Channel):
        self.client = client
        self.channel = channel
        self.pulse: Optional[Pulse] = None
        self.task: Optional[asyncio.Task] = None

    def set_pulse(self, pulse: Pulse):
        """
        设置波形
        """
        old_pulse = self.pulse
        self.pulse = pulse
        if old_pulse is None or pulse.index != old_pulse.index:
            self.set_pulse_data(pulse.data)

    def set_pulse_data(self, data: list[PulseOperation]):
        """
        设置波形数据
        """
        self.data = data
        if self.task and not self.task.cancelled() and not self.task.done():
            self.task.cancel()
        self.task = asyncio.create_task(self.internal_task(data))

    async def internal_task(self, data: list[PulseOperation], send_duration=5, send_interval=1):
        try:
            await self.client.clear_pulses(self.channel)

            data_duration = len(data) * 0.1
            repeat_num = int(send_duration // data_duration)
            duration = repeat_num * data_duration
            pulse_num = int(50 // duration)
            pulse_data = data * repeat_num

            try:
                for _ in range(pulse_num):
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(send_interval)

                await asyncio.sleep(abs(data_duration - send_interval))
                while True:
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(data_duration)
            except PulseDataTooLong:
                logger.warning(f"发送失败，波形数据过长")
        except Exception as e:
            logger.error(f"send_pulse_task 任务中发生错误: {e}")

class DGLabController:
    def __init__(self, client: DGLabLocalClient, osc_client: udp_client.SimpleUDPClient, ui_callback: UICallback):
        """
        初始化 DGLabController 实例
        :param client: DGLabWSServer 的客户端实例
        :param osc_client: 用于发送 OSC 回复的客户端实例
        :param ui_callback: UI 回调函数
        """
        self.client = client
        self.osc_client = osc_client
        self.ui_callback = ui_callback
        ui_callback.controller = self
        
        self.last_strength: Optional[StrengthData] = None  # 记录上次的强度值, 从 app更新, 包含 a b a_limit b_limit
        self.app_status_online = False  # App 端在线情况
        # 功能控制参数
        self.enable_panel_control = True   # 禁用面板控制功能 (双向)
        self.is_dynamic_bone_mode_a = False  # Default mode for Channel A (仅程序端)
        self.is_dynamic_bone_mode_b = False  # Default mode for Channel B (仅程序端)
        self.pulse_mode_a = 0  # pulse mode for Channel A (双向 - 更新名称)
        self.pulse_mode_b = 0  # pulse mode for Channel B (双向 - 更新名称)
        self.current_select_channel = Channel.A  # 游戏内面板控制的通道选择, 默认为 A (双向)
        self.fire_mode_disabled = False  # 禁用一键开火模式
        self.fire_mode_strength_step = 30    # 一键开火默认强度 (双向)
        self.fire_mode_active = False  # 标记当前是否在进行开火操作
        self.fire_mode_lock = asyncio.Lock()  # 一键开火模式锁
        self.data_updated_event = asyncio.Event()  # 数据更新事件
        self.fire_mode_origin_strength_a = 0  # 进入一键开火模式前的强度值
        self.fire_mode_origin_strength_b = 0
        self.enable_chatbox_status = 1  # ChatBox 发送状态 (双向，游戏内暂无直接开关变量)
        self.previous_chatbox_status = 1  # ChatBox 状态记录, 关闭 ChatBox 后进行内容清除
        # 定时任务
        self.send_status_task = asyncio.create_task(self.periodic_status_update())  # 启动ChatBox发送任务
        # 波形发送任务
        self.channel_a_pulse_task = ChannelPulseTask(client, Channel.A)
        self.channel_b_pulse_task = ChannelPulseTask(client, Channel.B)
        # 按键延迟触发计时
        self.chatbox_toggle_timer = None
        self.set_mode_timer = None
        #TODO: 增加状态消息OSC发送, 比使用 ChatBox 反馈更快
        # 回报速率设置为 1HZ，Updates every 0.1 to 1 seconds as needed based on parameter changes (1 to 10 updates per second), but you shouldn't rely on it for fast sync.

    async def periodic_status_update(self):
        """
        周期性通过 ChatBox 发送当前的配置状态
        TODO: ChatBox 消息发送的速率限制是多少？当前的设置还是会撞到限制..
        """
        while True:
            try:
                if self.enable_chatbox_status:
                    await self.send_strength_status()
                    self.previous_chatbox_status = True
                elif self.previous_chatbox_status: # clear chatbox
                    self.send_message_to_vrchat_chatbox("")
                    self.previous_chatbox_status = False
            except Exception as e:
                logger.error(f"periodic_status_update 任务中发生错误: {e}")
                await asyncio.sleep(5)  # 延迟后重试
            await asyncio.sleep(3)  # 每 x 秒发送一次

    async def update_pulse_data(self):
        """
            更新波形数据
        """
        pulse_a = self.ui_callback.pulse_registry.pulses[self.pulse_mode_a]
        pulse_b = self.ui_callback.pulse_registry.pulses[self.pulse_mode_b]
        logger.info(f"更新波形 A {pulse_a.name} B {pulse_b.name}")
        # A B 通道设定波形
        self.channel_a_pulse_task.set_pulse(pulse_a)
        self.channel_b_pulse_task.set_pulse(pulse_b)

    async def set_pulse_data(self, value, channel: Channel, pulse_index: int, update_ui=True):
        """
            立即切换为当前指定波形，清空原有波形
        """
        if channel == Channel.A:
            self.pulse_mode_a = pulse_index
            if (update_ui):
                self.ui_callback.pulse_mode_a_combobox.setCurrentIndex(pulse_index)
        else:
            self.pulse_mode_b = pulse_index
            if (update_ui):
                self.ui_callback.pulse_mode_b_combobox.setCurrentIndex(pulse_index)
        await self.update_pulse_data()

    async def set_float_output(self, value, channel: Channel):
        """
        动骨与碰撞体激活对应通道输出
        """
        # 不启用面板控制时，直接返回
        if not self.enable_panel_control:
            return

        if value >= 0.0 and self.last_strength:
            if channel == Channel.A and self.is_dynamic_bone_mode_a:
                final_output_a = math.ceil(self.map_value(value, self.last_strength.a_limit * 0.2, self.last_strength.a_limit))
                await self.client.set_strength(channel, StrengthOperationType.SET_TO, final_output_a)
            elif channel == Channel.B and self.is_dynamic_bone_mode_b:
                final_output_b = math.ceil(self.map_value(value, self.last_strength.b_limit * 0.2, self.last_strength.b_limit))
                await self.client.set_strength(channel, StrengthOperationType.SET_TO, final_output_b)

    async def chatbox_toggle_timer_handle(self):
        """1秒计时器 计时结束后切换 Chatbox 状态"""
        await asyncio.sleep(1)

        self.enable_chatbox_status = not self.enable_chatbox_status
        mode_name = "开启" if self.enable_chatbox_status else "关闭"
        logger.info("ChatBox显示状态切换为:" + mode_name)
        # 若关闭 ChatBox, 则立即发送一次空字符串
        if not self.enable_chatbox_status:
            self.send_message_to_vrchat_chatbox("")
        self.chatbox_toggle_timer = None
        # 更新UI
        self.ui_callback.enable_chatbox_status_checkbox.blockSignals(True)  # 防止触发 valueChanged 事件
        self.ui_callback.enable_chatbox_status_checkbox.setChecked(self.enable_chatbox_status)
        self.ui_callback.enable_chatbox_status_checkbox.blockSignals(False)

    async def toggle_chatbox(self, value):
        """
        开关 ChatBox 内容发送
        TODO: 修改为按键按下 3 秒后触发 enable_chatbox_status 的变更
        """
        if value == 1: # 按下按键
            if self.chatbox_toggle_timer is not None:
                self.chatbox_toggle_timer.cancel()
            self.chatbox_toggle_timer = asyncio.create_task(self.chatbox_toggle_timer_handle())
        elif value == 0: #松开按键
            if self.chatbox_toggle_timer:
                self.chatbox_toggle_timer.cancel()
                self.chatbox_toggle_timer = None

    async def set_mode_timer_handle(self, channel):
        await asyncio.sleep(1)

        if channel == Channel.A:
            self.is_dynamic_bone_mode_a = not self.is_dynamic_bone_mode_a
            mode_name = "可交互模式" if self.is_dynamic_bone_mode_a else "面板设置模式"
            logger.info("通道 A 切换为" + mode_name)
            # 更新UI
            self.ui_callback.dynamic_bone_mode_a_checkbox.blockSignals(True)  # 防止触发 valueChanged 事件
            self.ui_callback.dynamic_bone_mode_a_checkbox.setChecked(self.is_dynamic_bone_mode_a)
            self.ui_callback.dynamic_bone_mode_a_checkbox.blockSignals(False)
        elif channel == Channel.B:
            self.is_dynamic_bone_mode_b = not self.is_dynamic_bone_mode_b
            mode_name = "可交互模式" if self.is_dynamic_bone_mode_b else "面板设置模式"
            logger.info("通道 B 切换为" + mode_name)
            # 更新UI
            self.ui_callback.dynamic_bone_mode_b_checkbox.blockSignals(True)  # 防止触发 valueChanged 事件
            self.ui_callback.dynamic_bone_mode_b_checkbox.setChecked(self.is_dynamic_bone_mode_b)
            self.ui_callback.dynamic_bone_mode_b_checkbox.blockSignals(False)

    async def set_mode(self, value, channel):
        """
        切换工作模式, 延时一秒触发，更改按下时对应的通道
        """
        if value == 1: # 按下按键
            if self.set_mode_timer is not None:
                self.set_mode_timer.cancel()
            self.set_mode_timer = asyncio.create_task(self.set_mode_timer_handle(channel))
        elif value == 0: #松开按键
            if self.set_mode_timer:
                self.set_mode_timer.cancel()
                self.set_mode_timer = None


    async def reset_strength(self, value, channel):
        """
        强度重置为 0
        """
        if value:
            await self.client.set_strength(channel, StrengthOperationType.SET_TO, 0)

    async def increase_strength(self, value, channel):
        """
        增大强度, 固定 1
        """
        if value:
            await self.client.set_strength(channel, StrengthOperationType.INCREASE, 1)

    async def decrease_strength(self, value, channel):
        """
        减小强度, 固定 1
        """
        if value:
            await self.client.set_strength(channel, StrengthOperationType.DECREASE, 1)

    async def strength_fire_mode(self, value, channel, fire_strength, last_strength):
        """
        一键开火：
            按下后设置为当前通道强度值 +fire_mode_strength_step
            松开后恢复为通道进入前的强度
        TODO: 修复连点开火按键导致输出持续上升的问题
        """
        if self.fire_mode_disabled:
            return

        logger.info(f"Trigger FireMode: {value}")

        await asyncio.sleep(0.01)

        # 如果是开始开火并且已经在进行中，直接跳过
        if value and self.fire_mode_active:
            print("已有开火操作在进行中，跳过本次开始请求")
            return
        # 如果是结束开火并且当前没有进行中的开火操作，跳过
        if not value and not self.fire_mode_active:
            print("没有进行中的开火操作，跳过本次结束请求")
            return

        async with self.fire_mode_lock:
            if value:
                # 开始 fire mode
                self.fire_mode_active = True
                logger.debug(f"FIRE START {last_strength}")
                if last_strength:
                    if channel == Channel.A:
                        self.fire_mode_origin_strength_a = last_strength.a
                        await self.client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self.fire_mode_origin_strength_a + fire_strength, last_strength.a_limit)
                        )
                    elif channel == Channel.B:
                        self.fire_mode_origin_strength_b = last_strength.b
                        await self.client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self.fire_mode_origin_strength_b + fire_strength, last_strength.b_limit)
                        )
                self.data_updated_event.clear()
                await self.data_updated_event.wait()
            else:
                if channel == Channel.A:
                    await self.client.set_strength(channel, StrengthOperationType.SET_TO, self.fire_mode_origin_strength_a)
                elif channel == Channel.B:
                    await self.client.set_strength(channel, StrengthOperationType.SET_TO, self.fire_mode_origin_strength_b)
                # 等待数据更新
                self.data_updated_event.clear()  # 清除事件状态
                await self.data_updated_event.wait()  # 等待下次数据更新
                # 结束 fire mode
                logger.debug(f"FIRE END {last_strength}")
                self.fire_mode_active = False

    async def set_strength_step(self, value):
        """
          开火模式步进值设定
        """
        self.fire_mode_strength_step = math.floor(self.map_value(value, 0, 100))
        logger.info(f"current strength step: {self.fire_mode_strength_step}")
        # 更新 UI 组件 (QSpinBox) 以反映新的值
        self.ui_callback.strength_step_spinbox.blockSignals(True)  # 防止触发 valueChanged 事件
        self.ui_callback.strength_step_spinbox.setValue(self.fire_mode_strength_step)
        self.ui_callback.strength_step_spinbox.blockSignals(False)

    async def set_channel(self, value):
        """
        value: INT
        选定当前调节对应的通道, 目前 Page 1-2 为 Channel A， Page 3 为 Channel B
        """
        if value >= 0:
            self.current_select_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"set activate channel to: {self.current_select_channel}")
            if self.ui_callback:
                channel_name = "A" if self.current_select_channel == Channel.A else "B"
                self.ui_callback.update_current_channel_display(channel_name)

    async def set_panel_control(self, value):
        """
        面板控制功能开关，禁用控制后无法通过 OSC 对郊狼进行调整
        """
        if value > 0:
            self.enable_panel_control = True
        else:
            self.enable_panel_control = False
        mode_name = "开启面板控制" if self.enable_panel_control else "已禁用面板控制"
        logger.info(f": {mode_name}")
        # 更新 UI 组件 (QSpinBox) 以反映新的值
        self.ui_callback.enable_panel_control_checkbox.blockSignals(True)  # 防止触发 valueChanged 事件
        self.ui_callback.enable_panel_control_checkbox.setChecked(self.enable_panel_control)
        self.ui_callback.enable_panel_control_checkbox.blockSignals(False)

    async def handle_osc_message(self, address, *args):
        """
        处理 OSC 消息
        1. Bool: Bool 类型变量触发时，VRC 会先后发送 True 与 False, 回调中仅处理 True
        2. Float: -1.0 to 1.0， 但对于 Contact 与  Physbones 来说范围为 0.0-1.0
        """
        # Parameters Debug
        logger.info(f"Received OSC message on {address} with arguments {args}")

        # OSC参数
        if address.startswith("/avatar/parameters/"):
            parameter_code = address[len("/avatar/parameters/"):]
            if parameter_code in self.ui_callback.parameter_registry.parameters_by_code:
                parameter = self.ui_callback.parameter_registry.parameters_by_code[parameter_code]
                await self.ui_callback.parameter_bindings.handle(parameter, *args)

    def map_value(self, value, min_value, max_value):
        """
        将 Contact/Physbones 值映射到强度范围
        """
        return min_value + value * (max_value - min_value)

    def send_message_to_vrchat_chatbox(self, message: str):
        '''
        /chatbox/input s b n Input text into the chatbox.
        '''
        self.osc_client.send_message("/chatbox/input", [message, True, False])

    def send_value_to_vrchat(self, path: str, value):
        '''
        /chatbox/input s b n Input text into the chatbox.
        '''
        self.osc_client.send_message(path, value)

    async def send_strength_status(self):
        """
        通过 ChatBox 发送当前强度数值
        """
        if self.last_strength:
            mode_name_a = "交互" if self.is_dynamic_bone_mode_a else "面板"
            mode_name_b = "交互" if self.is_dynamic_bone_mode_b else "面板"
            channel_strength = f"[A]: {self.last_strength.a} B: {self.last_strength.b}" if self.current_select_channel == Channel.A else f"A: {self.last_strength.a} [B]: {self.last_strength.b}"
            self.send_message_to_vrchat_chatbox(
                f"MAX A: {self.last_strength.a_limit} B: {self.last_strength.b_limit}\n"
                f"Mode A: {mode_name_a} B: {mode_name_b} \n"
                f"Pulse A: {self.ui_callback.pulse_registry.pulses[self.pulse_mode_a].name} B: {self.ui_callback.pulse_registry.pulses[self.pulse_mode_b].name} \n"
                f"Fire Step: {self.fire_mode_strength_step}\n"
                f"Current: {channel_strength} \n"
            )
        else:
            self.send_message_to_vrchat_chatbox("未连接")

def handle_osc_message_task(address, list_object, *args):
    asyncio.create_task(list_object[0].handle_osc_message(address, *args))


async def run_server(ui_callback: UICallback, ip: str, port: int, osc_port: int):
    """运行服务器并启动OSC服务器"""
    try:
        async with DGLabWSServer(ip, port, 60) as server:
            client = server.new_local_client()
            logger.info("WebSocket 客户端已初始化")

            # 生成二维码
            url = client.get_qrcode(f"ws://{ip}:{port}")
            if (not url):
                raise RuntimeError("无法生成二维码")
            qrcode_image = generate_qrcode(url)
            ui_callback.update_qrcode(qrcode_image)
            logger.info(f"二维码已生成，WebSocket URL: ws://{ip}:{port}")

            osc_client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
            # 初始化控制器
            controller = DGLabController(client, osc_client, ui_callback)
            logger.info("DGLabController 已初始化")
            # 在 controller 初始化后调用绑定函数
            ui_callback.bind_controller_settings()

            # 设置OSC服务器
            disp = dispatcher.Dispatcher()
            # 面板控制对应的 OSC 地址
            disp.map("/avatar/parameters/SoundPad/Button/*", handle_osc_message_task, controller)
            disp.map("/avatar/parameters/SoundPad/Volume", handle_osc_message_task, controller)
            disp.map("/avatar/parameters/SoundPad/Page", handle_osc_message_task, controller)
            disp.map("/avatar/parameters/SoundPad/PanelControl", handle_osc_message_task, controller)
            disp.map("/avatar/parameters/DG-LAB/*", handle_osc_message_task, controller)
            disp.map("/avatar/parameters/Tail_Stretch",handle_osc_message_task, controller)

            event_loop = asyncio.get_event_loop()
            if (not isinstance(event_loop, asyncio.BaseEventLoop)):
                raise RuntimeError("无法获取事件循环")
            osc_server_instance = osc_server.AsyncIOOSCUDPServer(("0.0.0.0", osc_port), disp, event_loop)
            osc_transport, osc_protocol = await osc_server_instance.create_serve_endpoint()
            logger.info(f"OSC Server Listening on port {osc_port}")

            async for data in client.data_generator():
                if isinstance(data, StrengthData):
                    # 首次连接更新波形数据
                    if controller.last_strength is None:
                        asyncio.create_task(controller.update_pulse_data())
                    controller.last_strength = data
                    controller.data_updated_event.set()  # 数据更新，触发开火操作的后续事件
                    logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")
                    controller.app_status_online = True
                    ui_callback.update_connection_status(controller.app_status_online)
                    ui_callback.update_status(data)
                # 接收 App 反馈按钮
                elif isinstance(data, FeedbackButton):
                    logger.info(f"App 触发了反馈按钮：{data.name}")
                # 接收 心跳 / App 断开通知
                elif data == RetCode.CLIENT_DISCONNECTED:
                    logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")
                    controller.app_status_online = False
                    ui_callback.update_connection_status(controller.app_status_online)
                    await client.rebind()
                    logger.info("重新绑定成功")
                    controller.app_status_online = True
                    ui_callback.update_connection_status(controller.app_status_online)

            osc_transport.close()
    except Exception as e:
        # Handle specific errors and log them
        error_message = f"WebSocket 服务器启动失败: {str(e)}"
        logger.exception(error_message)

        # 启动过程中发生异常，恢复按钮状态为可点击的红色
        ui_callback.start_button.setText("启动失败，请重试")
        ui_callback.start_button.setStyleSheet("background-color: red; color: white;")
        ui_callback.start_button.setEnabled(True)
        ui_callback.log_text_edit.append(f"ERROR: {error_message}")
