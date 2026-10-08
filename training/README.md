# 160×120 INT8 人脸检测模型

该目录负责 PC 端训练和 PL 权值导出。模型输入为单通道 `160×120`，输出为 `20×15` 网格，每格包含人脸置信度以及中心偏移、宽、高四个框参数。三层下采样卷积、两组深度可分离上下文卷积和一个检测头合计 6384 个卷积权值、每帧 3,276,000 次 MAC。

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

当前用于继续训练的基础检查点为 `training/outputs/tiny_face_clean_1to3.pt`。它使用
WIDER FACE 中1～3张、清晰、无遮挡、正脸且缩放后尺寸足够大的样本训练了10轮。
WIDER FACE没有帽子、墨镜等配饰属性，不能依靠官方标注严格排除这些照片；现场微调集
因此只采集不戴帽子、墨镜和口罩的人员。

也可直接读取 YOLO 格式的人脸数据集。当前 FDDB 子集筛选每张 1～3 张脸，并要求所有
人脸缩放到 `160×120` 后短边不小于 16 像素。训练集使用 1985 张，验证集使用 491 张：

```powershell
D:\Python\python.exe -u -m training.train `
  --dataset-format yolo `
  --images training\datasets\fddb_dataset_YOLO\images\train `
  --annotations training\datasets\fddb_dataset_YOLO\labels\train `
  --validation-images training\datasets\fddb_dataset_YOLO\images\val `
  --validation-annotations training\datasets\fddb_dataset_YOLO\labels\val `
  --resume training\outputs\tiny_face_clean_1to3.pt `
  --reset-best-on-resume `
  --epochs 50 --batch-size 64 --workers 4 --learning-rate 0.0003 `
  --min-face-pixels 16 --min-faces-per-image 1 --max-faces-per-image 3 `
  --require-all-faces-detectable `
  --output training\outputs\tiny_face_fddb.pt
```

训练后可按真实检测框评估并生成抽样预览。预览中绿色为标注，红色为预测：

```powershell
D:\Python\python.exe -m training.evaluate_yolo training\outputs\tiny_face_fddb.pt `
  --images training\datasets\fddb_dataset_YOLO\images\val `
  --labels training\datasets\fddb_dataset_YOLO\labels\val `
  --iou 0.3 --output training\outputs\tiny_face_fddb_eval_iou30.json

D:\Python\python.exe -m training.visualize_yolo training\outputs\tiny_face_fddb.pt `
  --images training\datasets\fddb_dataset_YOLO\images\val `
  --labels training\datasets\fddb_dataset_YOLO\labels\val `
  --threshold 0.92 --output training\outputs\tiny_face_fddb_predictions.png
```

## 现场数据采集与标注

先保证板卡电源、JTAG、UART、OV5640和HDMI通路正常。在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File training\collect_field_frames.ps1 -Count 80
```

采集程序使用USB HDMI采集卡，不再通过JTAG中途停止VDMA；后者可能读到未完成的行并产生
横向断裂。运行前关闭OBS，程序会通过JTAG临时关闭FPGA绿色框。预览窗口中按空格保存，
按Q结束。若设备0不是HDMI采集卡，可在命令末尾添加 `-Device 1`、`-Device 2` 等重试。

建议包含1人、2人和3人场景，改变距离、左右位置、光线、表情和背景；所有人完整露出面部，
不戴帽子、普通眼镜、墨镜、口罩等。采集结果保存在
`training/field_dataset/images/`，该目录不会提交到Git。

然后运行标注器：

```powershell
D:\Python\python.exe -m training.annotate_field_faces
```

拖动鼠标框选完整面部，Enter保存并进入下一张，Backspace撤销最后一个框，Delete舍弃
含配饰、模糊、遮挡或人数不符的图片。

从10轮检查点继续训练到50轮时，`--epochs 50`表示最终轮数为50：

```powershell
D:\Python\python.exe -u -m training.train `
  --images training\field_dataset\images `
  --annotations training\field_dataset\field_annotations.txt `
  --resume training\outputs\tiny_face_clean_1to3.pt `
  --epochs 50 `
  --batch-size 16 `
  --workers 0 `
  --min-face-pixels 12 `
  --min-faces-per-image 1 `
  --max-faces-per-image 3 `
  --require-all-faces-detectable `
  --output training\outputs\tiny_face_field.pt
```

## 导出 PL ROM 权值

```powershell
D:\Python\python.exe -m training.export_weights `
  training\outputs\tiny_face.pt `
  --output training\outputs\rom
```

导出器先将 BatchNorm 融合进卷积，再按输出通道量化为有符号 INT8，按 OIHW 顺序生成每字节一行的十六进制 `.mem` 文件。`manifest.json` 记录张量形状、通道尺度、融合偏置和 CRC32。偏置与层间重新量化参数要在完成激活标定后转为定点值。

使用验证集标定 UINT8 激活，并生成 INT32 偏置、Q31 重定标乘数和移位参数：

```powershell
D:\Python\python.exe -m training.calibrate_int8 training\outputs\tiny_face_fddb.pt `
  --images training\datasets\fddb_dataset_YOLO\images\val `
  --labels training\datasets\fddb_dataset_YOLO\labels\val `
  --output training\outputs\rom_fddb_calibrated
```

卷积隐藏层采用无符号 UINT8 ReLU 激活。检测头保留 INT32 累加结果，由后处理按
`calibration.json` 中每个输出通道的尺度恢复 logits，再完成 sigmoid、阈值判断和框解码。

仓库不会提供随机初始化权值作为检测模型；必须训练并验证检查点后再生成比赛使用的 ROM。

## 自检

```powershell
D:\Python\python.exe -m unittest training.tests.test_pipeline -v
```
