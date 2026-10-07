# 160×120 INT8 人脸检测模型

该目录负责 PC 端训练和 PL 权值导出。模型输入为单通道 `160×120`，输出为 `20×15` 网格，每格包含人脸置信度以及中心偏移、宽、高四个框参数。三层 3×3 卷积和一个 1×1 检测头合计 4800 个卷积权值、每帧 2,800,800 次 MAC。

## 数据

训练脚本读取 WIDER FACE 官方标注格式。将训练图片目录和 `wider_face_train_bbx_gt.txt` 分别传给 `--images` 与 `--annotations`。板卡采集的本地图像位于 `Vitis/captures/`，该目录已被 Git 忽略，可用于检查真实摄像头颜色和后续补充现场样本。

## 训练

在仓库根目录执行：

```powershell
D:\Python\python.exe -m training.train `
  --images D:\datasets\WIDER_FACE\WIDER_train\images `
  --annotations D:\datasets\wider_face_split\wider_face_split\wider_face_train_bbx_gt.txt `
  --epochs 30 `
  --output training\outputs\tiny_face.pt
```

## 导出 PL ROM 权值

```powershell
D:\Python\python.exe -m training.export_weights `
  training\outputs\tiny_face.pt `
  --output training\outputs\rom
```

导出器先将 BatchNorm 融合进卷积，再按输出通道量化为有符号 INT8，按 OIHW 顺序生成每字节一行的十六进制 `.mem` 文件。`manifest.json` 记录张量形状、通道尺度、融合偏置和 CRC32。偏置与层间重新量化参数要在完成激活标定后转为定点值。

仓库不会提供随机初始化权值作为检测模型；必须训练并验证检查点后再生成比赛使用的 ROM。

## 自检

```powershell
D:\Python\python.exe -m unittest training.tests.test_pipeline -v
```
