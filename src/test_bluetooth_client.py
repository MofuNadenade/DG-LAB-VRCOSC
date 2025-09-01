"""
DG-LAB V3蓝牙测试客户端

用于测试BluetoothController的各种功能，包括：
- 设备扫描和连接
- 强度控制测试
- 波形数据循环播放测试
- 状态回调测试
- 协议验证测试
"""

import asyncio
import logging
from typing import Dict, List

from core.bluetooth import BluetoothController, Channel, PulseOperation, DeviceInfo

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BluetoothTestClient:
    """蓝牙测试客户端"""
    
    def __init__(self):
        super().__init__()
        self.controller = BluetoothController()
        self.connected_device: DeviceInfo
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """设置回调函数"""
        self.controller.set_connection_callback(self.on_connection_changed)
        self.controller.set_strength_changed_callback(self.on_strength_changed)
        self.controller.set_battery_callback(self.on_battery_changed)
        self.controller.set_notification_callback(self.on_notification_received)
    
    async def on_connection_changed(self, connected: bool):
        """连接状态变化回调"""
        status = "已连接" if connected else "已断开"
        logger.info(f"🔗 连接状态变化: {status}")
    
    async def on_strength_changed(self, strengths: Dict[Channel, int]):
        """强度变化回调"""
        logger.info(f"⚡ 强度变化: A={strengths[Channel.A]}, B={strengths[Channel.B]}")
    
    async def on_battery_changed(self, battery_level: int):
        """电量变化回调"""
        logger.info(f"🔋 电量变化: {battery_level}%")
    
    async def on_notification_received(self, data: bytes):
        """通知数据回调"""
        logger.debug(f"📨 收到通知: {data.hex().upper()}")
    
    async def scan_and_connect(self):
        """扫描并连接设备"""
        logger.info("🔍 开始扫描DG-LAB V3设备...")
        devices = await self.controller.scan_devices(scan_time=10.0)
        
        if not devices:
            logger.error("❌ 未发现任何DG-LAB V3设备")
            return False
        
        logger.info(f"📱 发现 {len(devices)} 个设备:")
        for i, device in enumerate(devices):
            logger.info(f"  {i+1}. {device['name']} ({device['address']}) RSSI: {device['rssi']}")
        
        # 选择信号最强的设备
        selected_device = devices[0]
        logger.info(f"🎯 选择设备: {selected_device['name']} ({selected_device['address']})")
        
        # 连接设备
        success = await self.controller.connect_device(selected_device)
        if success:
            self.connected_device = selected_device
            logger.info("✅ 设备连接成功")
            return True
        else:
            logger.error("❌ 设备连接失败")
            return False
    
    async def initialize_device(self):
        """初始化设备参数"""
        logger.info("🔧 初始化设备参数...")
        success = await self.controller.set_device_params(
            strength_limit_a=100,  # A通道上限100
            strength_limit_b=100,  # B通道上限100
            freq_balance_a=100,
            freq_balance_b=100,
            strength_balance_a=100,
            strength_balance_b=100
        )
        
        if success:
            logger.info("✅ 设备参数初始化成功")
        else:
            logger.error("❌ 设备参数初始化失败")
        
        return success
    
    async def test_strength_control(self):
        """测试强度控制"""
        logger.info("⚡ 开始测试强度控制...")
        
        # 测试绝对强度设置
        logger.info("📈 测试绝对强度设置")
        await self.controller.set_strength_absolute(Channel.A, 10)
        await asyncio.sleep(1)
        await self.controller.set_strength_absolute(Channel.B, 15)
        await asyncio.sleep(1)
        
        # 测试相对强度调整
        logger.info("📊 测试相对强度调整")
        await self.controller.set_strength_relative(Channel.A, 5)  # A+5
        await asyncio.sleep(1)
        await self.controller.set_strength_relative(Channel.B, -3)  # B-3
        await asyncio.sleep(1)
        
        # 测试强度归零
        logger.info("🔄 测试强度归零")
        await self.controller.reset_strength(Channel.A)
        await asyncio.sleep(1)
        await self.controller.reset_strength(Channel.B)
        await asyncio.sleep(1)
        
        logger.info("✅ 强度控制测试完成")
    
    def create_test_wave_patterns(self) -> List[PulseOperation]:
        """创建测试波形模式"""
        patterns = [
            # 模式1：低频低强度
            ((20, 25, 30, 35), (10, 15, 20, 25)),
            # 模式2：中频中强度  
            ((50, 55, 60, 65), (30, 35, 40, 45)),
            # 模式3：高频高强度
            ((100, 110, 120, 130), (60, 70, 80, 90)),
            # 模式4：变化模式
            ((30, 60, 90, 120), (20, 40, 60, 80)),
            # 模式5：脉冲模式
            ((40, 80, 40, 80), (50, 100, 50, 100))
        ]
        return patterns
    
    async def test_wave_data(self):
        """测试波形数据循环播放"""
        logger.info("🌊 开始测试波形数据...")
        
        # 创建测试波形
        wave_patterns_a = self.create_test_wave_patterns()
        wave_patterns_b = [
            # B通道使用不同的模式
            ((25, 35, 45, 55), (15, 25, 35, 45)),
            ((70, 80, 90, 100), (40, 50, 60, 70)),
            ((15, 25, 35, 45), (10, 20, 30, 40))
        ]
        
        # 设置A通道波形数据
        logger.info("🎵 设置A通道波形数据 (5个模式)")
        success_a = await self.controller.set_pulse_data(Channel.A, wave_patterns_a)
        if success_a:
            logger.info("✅ A通道波形数据设置成功")
        else:
            logger.error("❌ A通道波形数据设置失败")
        
        # 设置B通道波形数据
        logger.info("🎵 设置B通道波形数据 (3个模式)")
        success_b = await self.controller.set_pulse_data(Channel.B, wave_patterns_b)
        if success_b:
            logger.info("✅ B通道波形数据设置成功")
        else:
            logger.error("❌ B通道波形数据设置失败")
        
        if success_a and success_b:
            logger.info("🔄 波形数据将自动循环播放，观察设备输出...")
            # 让波形播放一段时间
            await asyncio.sleep(10)
            
            # 清除波形数据
            logger.info("🧹 清除波形数据")
            await self.controller.clear_pulse_data(Channel.A)
            await self.controller.clear_pulse_data(Channel.B)
            logger.info("✅ 波形数据已清除")
    
    async def test_invalid_parameters(self):
        """测试无效参数处理"""
        logger.info("🚫 开始测试无效参数处理...")
        
        # 测试无效强度值
        logger.info("❌ 测试无效强度值 (超出范围)")
        invalid_strength = await self.controller.set_strength_absolute(Channel.A, 300)  # 超出200上限
        if not invalid_strength:
            logger.info("✅ 正确拒绝了无效强度值")
        
        # 测试无效波形数据
        logger.info("❌ 测试无效波形数据")
        invalid_patterns = [
            ((300, 400, 500, 600), (150, 200, 250, 300))  # 频率和强度都超出范围
        ]
        invalid_wave = await self.controller.set_pulse_data(Channel.A, invalid_patterns)
        if not invalid_wave:
            logger.info("✅ 正确拒绝了无效波形数据")
        
        logger.info("✅ 无效参数处理测试完成")
    
    async def test_device_state(self):
        """测试设备状态获取"""
        logger.info("📊 测试设备状态获取...")
        
        device_state = self.controller.get_device_state()
        logger.info("📋 当前设备状态:")
        logger.info(f"  连接状态: {device_state['is_connected']}")
        logger.info(f"  电量: {device_state['battery_level']}%")
        logger.info(f"  A通道强度: {device_state['channel_a']['strength']}")
        logger.info(f"  B通道强度: {device_state['channel_b']['strength']}")
        logger.info(f"  A通道上限: {device_state['channel_a']['strength_limit']}")
        logger.info(f"  B通道上限: {device_state['channel_b']['strength_limit']}")
        logger.info(f"  A通道波形数: {len(device_state['channel_a']['pulses'])}")
        logger.info(f"  B通道波形数: {len(device_state['channel_b']['pulses'])}")
        
        logger.info("✅ 设备状态获取完成")
    
    async def run_comprehensive_test(self):
        """运行综合测试"""
        logger.info("🚀 开始DG-LAB V3蓝牙控制器综合测试")
        logger.info("=" * 60)
        
        try:
            # 1. 扫描和连接
            if not await self.scan_and_connect():
                logger.error("❌ 连接失败，测试终止")
                return
            
            # 等待连接稳定
            await asyncio.sleep(2)
            
            # 2. 初始化设备
            if not await self.initialize_device():
                logger.warning("⚠️ 设备初始化失败，继续其他测试")
            
            await asyncio.sleep(1)
            
            # 3. 测试强度控制
            await self.test_strength_control()
            await asyncio.sleep(1)
            
            # 4. 测试波形数据
            await self.test_wave_data()
            await asyncio.sleep(1)
            
            # 5. 测试设备状态
            await self.test_device_state()
            await asyncio.sleep(1)
            
            # 6. 测试无效参数
            await self.test_invalid_parameters()
            await asyncio.sleep(1)
            
            logger.info("=" * 60)
            logger.info("🎉 综合测试完成！")
            
            # 保持连接一段时间观察
            logger.info("⏰ 保持连接30秒观察状态变化...")
            await asyncio.sleep(30)
            
        except KeyboardInterrupt:
            logger.info("⏹️ 用户中断测试")
        except Exception as e:
            logger.error(f"❌ 测试过程中发生错误: {e}")
        finally:
            # 清理资源
            logger.info("🧹 清理资源...")
            await self.controller.disconnect_device()
            await self.controller.cleanup()
            logger.info("✅ 资源清理完成")

async def main():
    """主函数"""
    logger.info("DG-LAB V3蓝牙测试客户端启动")
    logger.info("请确保:")
    logger.info("1. 蓝牙已开启")
    logger.info("2. DG-LAB V3设备已开机并处于配对模式")
    logger.info("3. 设备在可连接范围内")
    logger.info("-" * 60)
    
    test_client = BluetoothTestClient()
    await test_client.run_comprehensive_test()

if __name__ == "__main__":
    try:
        # 运行异步主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行错误: {e}")
        import traceback
        logger.error(traceback.format_exc())