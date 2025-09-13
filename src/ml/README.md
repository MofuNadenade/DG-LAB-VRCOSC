# LSTM波形预测模型

基于PyTorch的LSTM深度学习模型，用于学习和预测生成RecordingSession录制的波形数据。

## 功能特性

- **多通道支持**: 同时处理A、B两个通道的波形数据
- **序列学习**: 使用LSTM学习时间序列中的波形模式
- **预测生成**: 基于历史数据预测未来的波形序列
- **模型持久化**: 支持模型保存和加载
- **数据归一化**: 自动处理不同范围的特征数据
- **双通道特征**: 每个时间步同时包含A、B通道的完整数据

## 模型架构

### WaveformFeatures
波形特征数据结构，同时包含A、B两个通道的数据：
- `freq_a`: A通道4个频率值 [10-240]
- `strength_a`: A通道4个强度值 [0-100] 
- `current_strength_a`: A通道当前强度 [0-200]
- `freq_b`: B通道4个频率值 [10-240]
- `strength_b`: B通道4个强度值 [0-100]
- `current_strength_b`: B通道当前强度 [0-200]

### WaveformLSTM
LSTM神经网络模型：
- **输入维度**: 18 (A通道9 + B通道9)
- **隐藏层大小**: 128
- **LSTM层数**: 2
- **Dropout**: 0.2
- **输出层**: 全连接层 + Sigmoid激活

### WaveformDataset
PyTorch数据集类：
- 自动从RecordingSession提取特征
- 创建滑动窗口序列用于训练
- 数据归一化处理
- 同时处理A、B两个通道的数据

## 使用方法

### 1. 基本使用

```python
from src.ml.waveform_lstm import WaveformPredictor, WaveformFeatures
from src.core.recording.recording_models import RecordingSession

# 创建预测器
predictor = WaveformPredictor()

# 准备训练数据
training_sessions = [session1, session2, ...]  # RecordingSession列表

# 训练模型
history = predictor.train(
    sessions=training_sessions,
    epochs=100,
    batch_size=32,
    learning_rate=0.001
)

# 预测波形序列
initial_features = [...]  # 初始特征列表
predictions = predictor.predict_sequence(initial_features, length=50)
```

### 2. 模型保存和加载

```python
# 保存模型
predictor.save_model("my_waveform_model.pth")

# 加载模型
predictor = WaveformPredictor("my_waveform_model.pth")
```

### 3. 完整示例

```python
# 运行Jupyter notebook演示（推荐）
jupyter notebook src/ml/waveform.ipynb

# 注意：
# - waveform_lstm.py 只包含核心模型代码
# - create_sample_session 辅助函数已移动到 waveform.ipynb 中
# - 完整的训练和演示代码都在 waveform.ipynb 中
```

## 数据格式

### 输入数据
- **RecordingSession**: 包含多个RecordingSnapshot的录制会话
- **RecordingSnapshot**: 100ms时间片的数据快照
- **ChannelSnapshot**: 单个通道的波形数据

### 特征提取
模型自动从RecordingSession中提取以下特征：
1. A通道频率操作数据 (4个频率值)
2. A通道强度操作数据 (4个强度值)  
3. A通道当前实时强度
4. B通道频率操作数据 (4个频率值)
5. B通道强度操作数据 (4个强度值)  
6. B通道当前实时强度

### 数据归一化
- 频率: [10, 240] → [0, 1]
- 强度: [0, 100] → [0, 1]
- 当前强度: [0, 200] → [0, 1]

## 训练参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| epochs | 100 | 训练轮数 |
| batch_size | 32 | 批次大小 |
| learning_rate | 0.001 | 学习率 |
| validation_split | 0.2 | 验证集比例 |
| sequence_length | 50 | 序列长度 |

## 预测参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| length | 100 | 预测长度（时间步数） |
| initial_features | 必需 | 初始特征序列 |

## 模型性能

### 训练指标
- **损失函数**: MSE (均方误差)
- **优化器**: Adam
- **学习率调度**: 固定学习率
- **正则化**: Dropout (0.2)

### 预测质量
模型预测的特征值范围：
- 频率: 10-240 (符合设备规格)
- 强度: 0-100 (符合设备规格)
- 当前强度: 0-200 (符合设备规格)

## 依赖要求

```python
torch>=1.9.0
numpy
matplotlib
```

## 注意事项

1. **数据质量**: 训练数据质量直接影响预测效果
2. **序列长度**: 较长的序列长度可以学习更复杂的模式，但需要更多计算资源
3. **模型大小**: 默认模型约50K参数，适合大多数应用场景
4. **设备支持**: 自动检测CUDA支持，优先使用GPU训练
5. **内存使用**: 大批量训练时注意内存使用情况
6. **双通道数据**: 确保训练数据包含A、B两个通道的完整信息

## 扩展功能

### 自定义模型架构
```python
# 创建自定义LSTM模型
model = WaveformLSTM(
    input_size=18,
    hidden_size=256,  # 更大的隐藏层
    num_layers=3,     # 更多层数
    output_size=18,
    dropout=0.3       # 更高的dropout
)
```

### 自定义训练参数
```python
# 使用不同的优化器
optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)

# 使用学习率调度
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)
```

## 故障排除

### 常见问题

1. **内存不足**: 减少batch_size或sequence_length
2. **训练不收敛**: 调整学习率或增加训练轮数
3. **预测质量差**: 增加训练数据或调整模型架构
4. **导入错误**: 确保项目路径正确，所有依赖已安装
5. **通道数据缺失**: 确保RecordingSession包含A、B两个通道的数据

### 调试建议

1. 使用小数据集测试模型
2. 监控训练损失变化
3. 检查数据归一化是否正确
4. 验证预测结果的范围是否合理
5. 检查双通道数据的完整性

## 更新日志

- **v2.0**: 重构版本，支持双通道特征数据
  - 重新设计WaveformFeatures结构，同时包含A、B通道数据
  - 更新模型输入/输出维度为18 (A通道9 + B通道9)
  - 移除one-hot编码，直接使用双通道特征
  - 优化数据处理和特征提取流程
- **v1.0**: 初始版本，支持基本的LSTM波形预测功能
  - 支持多通道波形数据训练和预测
  - 实现模型保存和加载功能
  - 提供完整的使用示例和文档