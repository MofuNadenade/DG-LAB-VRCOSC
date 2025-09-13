"""
LSTM模型用于学习和预测生成RecordingSession录制的波形

该模块实现了基于LSTM的深度学习模型，用于：
1. 学习RecordingSession中的波形模式
2. 预测生成新的波形序列
3. 支持多通道（A、B）波形数据训练和预测
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

# 导入项目相关模块
from core.recording.recording_models import RecordingSession
from models import Channel, WaveformFrequency, WaveformStrength


@dataclass
class WaveformFeatures:
    """波形特征数据 - 同时包含A、B两个通道的数据"""
    # A通道频率特征 (4个频率值)
    freq_a: List[WaveformFrequency]  # [f1, f2, f3, f4]
    # A通道强度特征 (4个强度值)
    strength_a: List[WaveformStrength]  # [s1, s2, s3, s4]
    # A通道当前强度
    current_strength_a: int
    # B通道频率特征 (4个频率值)
    freq_b: List[WaveformFrequency]  # [f1, f2, f3, f4]
    # B通道强度特征 (4个强度值)
    strength_b: List[WaveformStrength]  # [s1, s2, s3, s4]
    # B通道当前强度
    current_strength_b: int


class WaveformDataset(Dataset[Tuple[torch.Tensor, torch.Tensor]]):
    """波形数据集"""
    
    def __init__(self, sessions: List[RecordingSession], sequence_length: int = 50):
        """
        初始化数据集
        
        Args:
            sessions: 录制会话列表
            sequence_length: 序列长度（时间步数）
        """
        super().__init__()
        self.sequence_length = sequence_length
        self.sequences = self._prepare_sequences(sessions)
    
    def _prepare_sequences(self, sessions: List[RecordingSession]) -> List[Tuple[torch.Tensor, torch.Tensor]]:
        """准备训练序列数据"""
        sequences: List[Tuple[torch.Tensor, torch.Tensor]] = []
        
        for session in sessions:
            # 提取所有快照的特征
            features = self._extract_features(session)
            
            # 创建滑动窗口序列
            for i in range(len(features) - self.sequence_length):
                # 输入序列：前sequence_length个时间步
                input_seq = features[i:i + self.sequence_length]
                # 目标序列：下一个时间步
                target_seq = features[i + self.sequence_length]
                
                # 转换为张量
                input_tensor = torch.stack([self._features_to_tensor(f) for f in input_seq])
                target_tensor = self._features_to_tensor(target_seq)
                
                sequences.append((input_tensor, target_tensor))
        
        return sequences
    
    def _extract_features(self, session: RecordingSession) -> List[WaveformFeatures]:
        """从录制会话中提取特征"""
        features: List[WaveformFeatures] = []
        
        for snapshot in session.snapshots:
            # 提取A通道数据
            freq_a = [0, 0, 0, 0]
            strength_a = [0, 0, 0, 0]
            current_strength_a = 0
            
            if Channel.A in snapshot.channels:
                channel_snapshot = snapshot.channels[Channel.A]
                pulse_op = channel_snapshot.pulse_operation
                freq_op, strength_op = pulse_op
                freq_a = list(freq_op)
                strength_a = list(strength_op)
                current_strength_a = channel_snapshot.current_strength
            
            # 提取B通道数据
            freq_b = [0, 0, 0, 0]
            strength_b = [0, 0, 0, 0]
            current_strength_b = 0
            
            if Channel.B in snapshot.channels:
                channel_snapshot = snapshot.channels[Channel.B]
                pulse_op = channel_snapshot.pulse_operation
                freq_op, strength_op = pulse_op
                freq_b = list(freq_op)
                strength_b = list(strength_op)
                current_strength_b = channel_snapshot.current_strength
            
            # 创建特征对象
            feature = WaveformFeatures(
                freq_a=freq_a,
                strength_a=strength_a,
                current_strength_a=current_strength_a,
                freq_b=freq_b,
                strength_b=strength_b,
                current_strength_b=current_strength_b
            )
            features.append(feature)
        
        return features
    
    def _features_to_tensor(self, features: WaveformFeatures) -> torch.Tensor:
        """将特征转换为张量"""
        # 归一化A通道频率 [10, 240] -> [0, 1]
        norm_freq_a = [(f - 10) / 230 for f in features.freq_a]
        
        # 归一化A通道强度 [0, 100] -> [0, 1]
        norm_strength_a = [s / 100 for s in features.strength_a]
        
        # 归一化A通道当前强度 [0, 200] -> [0, 1]
        norm_current_strength_a = features.current_strength_a / 200
        
        # 归一化B通道频率 [10, 240] -> [0, 1]
        norm_freq_b = [(f - 10) / 230 for f in features.freq_b]
        
        # 归一化B通道强度 [0, 100] -> [0, 1]
        norm_strength_b = [s / 100 for s in features.strength_b]
        
        # 归一化B通道当前强度 [0, 200] -> [0, 1]
        norm_current_strength_b = features.current_strength_b / 200
        
        # 合并所有特征: A通道(9) + B通道(9) = 18维
        tensor_data = (norm_freq_a + norm_strength_a + [norm_current_strength_a] + 
                      norm_freq_b + norm_strength_b + [norm_current_strength_b])
        
        return torch.tensor(tensor_data, dtype=torch.float32)
    
    def __len__(self) -> int:
        return len(self.sequences)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.sequences[idx]


class WaveformLSTM(nn.Module):
    """波形预测LSTM模型"""
    
    def __init__(self, input_size: int = 18, hidden_size: int = 128, num_layers: int = 2, 
                 output_size: int = 18, dropout: float = 0.2):
        """
        初始化LSTM模型
        
        Args:
            input_size: 输入特征维度 (A通道9 + B通道9 = 18)
            hidden_size: LSTM隐藏层大小
            num_layers: LSTM层数
            output_size: 输出特征维度
            dropout: Dropout比例
        """
        super().__init__()  # type: ignore
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM层
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        # 全连接层
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size),
            nn.Sigmoid()  # 输出归一化到[0,1]
        )
    
    def forward(self, x: torch.Tensor, hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        前向传播
        
        Args:
            x: 输入张量 [batch_size, sequence_length, input_size]
            hidden: 初始隐藏状态
            
        Returns:
            output: 预测输出 [batch_size, output_size]
            hidden: 新的隐藏状态
        """
        # LSTM前向传播
        lstm_out, hidden = self.lstm(x, hidden)
        
        # 取最后一个时间步的输出
        last_output = lstm_out[:, -1, :]
        
        # 全连接层
        output = self.fc(last_output)
        
        # 确保hidden不为None
        if hidden is None:
            hidden = self.init_hidden(x.size(0), x.device)
        
        return output, hidden
    
    def init_hidden(self, batch_size: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
        """初始化隐藏状态"""
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
        return h0, c0


class WaveformPredictor:
    """波形预测器"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化预测器
        
        Args:
            model_path: 预训练模型路径
        """
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = WaveformLSTM().to(self.device)
        self.scaler_stats = None
        
        if model_path and Path(model_path).exists():
            self.load_model(model_path)
    
    def train(self, sessions: List[RecordingSession], epochs: int = 100, 
              batch_size: int = 32, learning_rate: float = 0.001,
              validation_split: float = 0.2) -> Dict[str, List[float]]:
        """
        训练模型
        
        Args:
            sessions: 训练数据会话列表
            epochs: 训练轮数
            batch_size: 批次大小
            learning_rate: 学习率
            validation_split: 验证集比例
            
        Returns:
            训练历史记录
        """
        # 准备数据集
        dataset = WaveformDataset(sessions)
        
        # 分割训练和验证集
        val_size = int(len(dataset) * validation_split)
        train_size = len(dataset) - val_size
        train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
        
        # 创建数据加载器
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # 优化器和损失函数
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()
        
        # 训练历史
        history: Dict[str, List[float]] = {
            'train_loss': [],
            'val_loss': []
        }
        
        self.model.train()
        
        for epoch in range(epochs):
            # 训练阶段
            train_loss = 0.0
            for batch_inputs, batch_targets in train_loader:
                batch_inputs = batch_inputs.to(self.device)
                batch_targets = batch_targets.to(self.device)
                
                optimizer.zero_grad()
                
                # 前向传播
                outputs, _ = self.model(batch_inputs)
                loss = criterion(outputs, batch_targets)
                
                # 反向传播
                loss.backward()
                optimizer.step()  # type: ignore
                
                train_loss += loss.item()
            
            # 验证阶段
            val_loss = 0.0
            self.model.eval()
            with torch.no_grad():
                for batch_inputs, batch_targets in val_loader:
                    batch_inputs = batch_inputs.to(self.device)
                    batch_targets = batch_targets.to(self.device)
                    
                    outputs, _ = self.model(batch_inputs)
                    loss = criterion(outputs, batch_targets)
                    val_loss += loss.item()
            
            self.model.train()
            
            # 记录损失
            avg_train_loss = train_loss / len(train_loader)
            avg_val_loss = val_loss / len(val_loader)
            
            history['train_loss'].append(avg_train_loss)
            history['val_loss'].append(avg_val_loss)
            
            if epoch % 10 == 0:
                print(f'Epoch {epoch:3d}: Train Loss = {avg_train_loss:.6f}, Val Loss = {avg_val_loss:.6f}')
        
        return history
    
    def predict_sequence(self, initial_features: List[WaveformFeatures], 
                        length: int = 100) -> List[WaveformFeatures]:
        """
        预测波形序列
        
        Args:
            initial_features: 初始特征序列
            length: 预测长度
            
        Returns:
            预测的特征序列
        """
        self.model.eval()
        
        # 转换初始特征为张量
        initial_tensor = torch.stack([self._features_to_tensor(f) for f in initial_features])
        initial_tensor = initial_tensor.unsqueeze(0).to(self.device)  # 添加批次维度
        
        predictions: List[WaveformFeatures] = []
        current_input = initial_tensor
        
        with torch.no_grad():
            hidden = self.model.init_hidden(1, self.device)
            
            for _ in range(length):
                # 预测下一个时间步
                output, hidden = self.model(current_input, hidden)
                
                # 将输出转换回特征
                predicted_features = self._tensor_to_features(output.squeeze(0))
                predictions.append(predicted_features)
                
                # 更新输入（滑动窗口）
                current_input = torch.cat([current_input[:, 1:, :], output.unsqueeze(1)], dim=1)
        
        return predictions
    
    def _features_to_tensor(self, features: WaveformFeatures) -> torch.Tensor:
        """将特征转换为张量（与数据集中的方法相同）"""
        # 归一化A通道
        norm_freq_a = [(f - 10) / 230 for f in features.freq_a]
        norm_strength_a = [s / 100 for s in features.strength_a]
        norm_current_strength_a = features.current_strength_a / 200
        
        # 归一化B通道
        norm_freq_b = [(f - 10) / 230 for f in features.freq_b]
        norm_strength_b = [s / 100 for s in features.strength_b]
        norm_current_strength_b = features.current_strength_b / 200
        
        # 合并所有特征
        tensor_data = (norm_freq_a + norm_strength_a + [norm_current_strength_a] + 
                      norm_freq_b + norm_strength_b + [norm_current_strength_b])
        
        return torch.tensor(tensor_data, dtype=torch.float32)
    
    def _tensor_to_features(self, tensor: torch.Tensor) -> WaveformFeatures:
        """将张量转换回特征"""
        data = tensor.cpu().numpy()
        
        # 反归一化A通道
        freq_a = [int((data[i] * 230) + 10) for i in range(4)]
        strength_a = [int(data[i + 4] * 100) for i in range(4)]
        current_strength_a = int(data[8] * 200)
        
        # 反归一化B通道
        freq_b = [int((data[i + 9] * 230) + 10) for i in range(4)]
        strength_b = [int(data[i + 13] * 100) for i in range(4)]
        current_strength_b = int(data[17] * 200)
        
        return WaveformFeatures(
            freq_a=freq_a,
            strength_a=strength_a,
            current_strength_a=current_strength_a,
            freq_b=freq_b,
            strength_b=strength_b,
            current_strength_b=current_strength_b
        )
    
    def save_model(self, model_path: str) -> None:
        """保存模型"""
        model_data = {
            'model_state_dict': self.model.state_dict(),
            'model_config': {
                'input_size': 18,
                'hidden_size': 128,
                'num_layers': 2,
                'output_size': 18,
                'dropout': 0.2
            }
        }
        
        torch.save(model_data, model_path)
        print(f"模型已保存到: {model_path}")
    
    def load_model(self, model_path: str) -> None:
        """加载模型"""
        model_data = torch.load(model_path, map_location=self.device)
        
        # 重新创建模型
        config = model_data['model_config']
        self.model = WaveformLSTM(**config).to(self.device)
        self.model.load_state_dict(model_data['model_state_dict'])
        
        print(f"模型已从 {model_path} 加载")
