"""
DGR文件格式管理器

处理录制会话的保存和加载，支持JSON格式的DGR文件
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from models import Channel, PulseOperation
from .recording_models import (
    RecordingSession, 
    RecordingMetadata, 
    RecordingSnapshot, 
    ChannelSnapshot
)

logger = logging.getLogger(__name__)


class DGRFileManager:
    """DGR文件格式管理器
    
    负责：
    1. 录制会话的保存和加载
    2. DGR文件格式的序列化和反序列化
    3. 文件完整性验证
    """
    
    def __init__(self) -> None:
        """初始化DGR文件管理器"""
        super().__init__()
        self._version = "1.0"
        self._format = "dgr"
    
    async def save_recording(self, session: RecordingSession, file_path: str) -> None:
        """保存录制会话到DGR文件
        
        Args:
            session: 要保存的录制会话
            file_path: 保存路径
            
        Raises:
            ValueError: 会话数据无效
            IOError: 文件写入失败
        """
        if not session.snapshots:
            raise ValueError("录制会话没有快照数据")
        
        try:
            # 构建文件数据结构
            dgr_data: Dict[str, Any] = {
                'version': self._version,
                'format': self._format,
                'metadata': {
                    'session_id': session.metadata.session_id,
                    'start_time': session.metadata.start_time.isoformat(),
                    'end_time': session.metadata.end_time.isoformat() if session.metadata.end_time else None,
                    'duration_ms': session.get_duration_ms(),
                    'total_snapshots': session.get_total_snapshots()
                },
                'snapshots': []
            }
            
            # 序列化快照数据
            snapshots_list: List[Dict[str, Any]] = []
            for snapshot in session.snapshots:
                snapshot_data: Dict[str, Any] = {}
                for channel, channel_snapshot in snapshot.channels.items():
                    # 使用通道名称而不是数值，便于人类阅读和调试
                    channel_key = channel.name  # 'A' 或 'B'
                    snapshot_data[channel_key] = {
                        'pulse_operation': self._serialize_pulse_operation(channel_snapshot.pulse_operation),
                        'current_strength': channel_snapshot.current_strength
                    }
                snapshots_list.append(snapshot_data)
            dgr_data['snapshots'] = snapshots_list
            
            # 写入文件
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path_obj, 'w', encoding='utf-8') as f:
                json.dump(dgr_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"录制会话已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存录制会话失败: {e}")
            raise IOError(f"无法保存录制会话: {e}")
    
    async def load_recording(self, file_path: str) -> RecordingSession:
        """从DGR文件加载录制会话
        
        Args:
            file_path: DGR文件路径
            
        Returns:
            RecordingSession: 加载的录制会话
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式无效
            IOError: 文件读取失败
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"DGR文件不存在: {file_path}")
        
        try:
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                dgr_data = json.load(f)
            
            # 验证文件格式
            self._validate_dgr_format(dgr_data)
            
            # 解析元数据
            metadata_data = dgr_data['metadata']
            metadata = RecordingMetadata(
                session_id=metadata_data['session_id'],
                start_time=datetime.fromisoformat(metadata_data['start_time']),
                end_time=datetime.fromisoformat(metadata_data['end_time']) if metadata_data.get('end_time') else None
            )
            
            # 解析快照数据
            snapshots: List[RecordingSnapshot] = []
            for snapshot_data in dgr_data['snapshots']:
                channels: Dict[Channel, ChannelSnapshot] = {}
                
                for channel_key, channel_data in snapshot_data.items():
                    # 使用通道名称直接创建Channel枚举
                    channel = Channel[channel_key]
                    pulse_operation = self._deserialize_pulse_operation(channel_data['pulse_operation'])
                    
                    channel_snapshot = ChannelSnapshot(
                        pulse_operation=pulse_operation,
                        current_strength=channel_data['current_strength']
                    )
                    channels[channel] = channel_snapshot
                
                snapshots.append(RecordingSnapshot(channels=channels))
            
            session = RecordingSession(metadata=metadata, snapshots=snapshots)
            logger.info(f"录制会话已从文件加载: {file_path}")
            return session
            
        except json.JSONDecodeError as e:
            logger.error(f"DGR文件JSON格式错误: {e}")
            raise ValueError(f"无效的DGR文件格式: {e}")
        except Exception as e:
            logger.error(f"加载录制会话失败: {e}")
            raise IOError(f"无法读取DGR文件: {e}")
    
    def _validate_dgr_format(self, data: Dict[str, Any]) -> None:
        """验证DGR文件格式
        
        Args:
            data: DGR文件数据
            
        Raises:
            ValueError: 格式无效
        """
        required_fields = ['version', 'format', 'metadata', 'snapshots']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"DGR文件缺少必需字段: {field}")
        
        if data['format'] != self._format:
            raise ValueError(f"不支持的文件格式: {data['format']}")
        
        # 验证元数据
        metadata: Dict[str, Any] = data['metadata']
        required_metadata_fields = ['session_id', 'start_time', 'duration_ms', 'total_snapshots']
        for field in required_metadata_fields:
            if field not in metadata:
                raise ValueError(f"DGR文件元数据缺少必需字段: {field}")
        
        # 验证快照数据完整性
        snapshots: List[Any] = data['snapshots']
        if len(snapshots) != metadata['total_snapshots']:
            raise ValueError("快照数量与元数据不匹配")
    
    def _serialize_pulse_operation(self, pulse_op: PulseOperation) -> Dict[str, Any]:
        """序列化脉冲操作数据
        
        Args:
            pulse_op: 脉冲操作对象（Tuple格式）
            
        Returns:
            dict: 序列化的脉冲操作数据
        """
        # PulseOperation是Tuple[WaveformFrequencyOperation, WaveformStrengthOperation]
        freq_data, strength_data = pulse_op
        return {
            'frequency_data': list(freq_data),  # 转换为列表便于序列化
            'strength_data': list(strength_data)
        }
    
    def _deserialize_pulse_operation(self, data: Dict[str, Any]) -> PulseOperation:
        """反序列化脉冲操作数据
        
        Args:
            data: 序列化的脉冲操作数据
            
        Returns:
            PulseOperation: 脉冲操作对象（Tuple格式）
        """
        # 从序列化数据恢复Tuple格式
        freq_list = data.get('frequency_data', [10, 10, 10, 10])
        strength_list = data.get('strength_data', [0, 0, 0, 0])
        
        # 确保是4元素的元组
        freq_data = tuple(freq_list[:4] + [10] * (4 - len(freq_list)))[:4]
        strength_data = tuple(strength_list[:4] + [0] * (4 - len(strength_list)))[:4]
        
        return (freq_data, strength_data)
    
    def get_recording_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取DGR文件的基本信息（不完整加载）
        
        Args:
            file_path: DGR文件路径
            
        Returns:
            Optional[Dict]: 录制信息，失败时返回None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                dgr_data = json.load(f)
            
            if 'metadata' not in dgr_data:
                return None
            
            metadata: Dict[str, Any] = dgr_data['metadata']
            return {
                'session_id': metadata.get('session_id'),
                'start_time': metadata.get('start_time'),
                'end_time': metadata.get('end_time'),
                'duration_ms': metadata.get('duration_ms', 0),
                'total_snapshots': metadata.get('total_snapshots', 0),
                'version': dgr_data.get('version', '未知')
            }
            
        except Exception as e:
            logger.error(f"读取DGR文件信息失败: {e}")
            return None
    
    async def delete_recording(self, file_path: str) -> bool:
        """删除DGR录制文件
        
        Args:
            file_path: DGR文件路径
            
        Returns:
            bool: 是否删除成功
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                logger.warning(f"DGR文件不存在，无需删除: {file_path}")
                return True
            
            file_path_obj.unlink()
            logger.info(f"DGR文件已删除: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"删除DGR文件失败: {e}")
            return False