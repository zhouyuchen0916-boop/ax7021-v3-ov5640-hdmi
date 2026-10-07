# AX7021 LPYOLO 4W4A 人脸检测加速器实施结构

## 已验证基础

- OV5640 以 1280×720、3 字节/像素写入 DDR。
- HDMI 从同一组三帧缓冲读取并稳定输出。
- PS 可以通过 AXI GPIO 更新绿色框坐标。
- JTAG 可以暂停摄像头 S2MM VDMA并导出完整帧。
- 导出的自然颜色预览为 `frame_bgr.png`；LPYOLO 前处理执行 BGR→RGB。
- LPYOLO 4W4A 在作者样例中检出 12 张脸，在 AX7021 实采帧中检出 1 张脸。

现有 routed 设计占用 6961 LUT、11737 FF、14 个 RAMB36、3 个 RAMB18、0 个 DSP，WNS 为 0.567 ns，TNS 为 0。它为神经网络保留了全部 220 个 DSP，但 FINN 加速器加入后仍需重新检查布线、时序、DRC 和 CDC。

## 选定模型

模型采用公开预训练的 LPYOLO 4W4A FINN ONNX：

- 输入：`1×3×416×416`，RGB UINT8。
- 输出：`1×18×13×13`；三个锚框，每个锚框含 `x/y/w/h/objectness/class`。
- 锚框：`(10,14)`、`(23,27)`、`(37,58)`，步长 32。
- 权重 4 bit、隐藏层激活 4 bit、输入和输出 8 bit。
- 输出量化缩放为 `1/127`，再执行检测头解码和 NMS。

卷积主干如下：

| 层 | 卷积权重形状 | 空间尺寸 |
|---|---:|---:|
| conv0 | 8×3×3×3 | 416×416 |
| maxpool | 2×2 | 208×208 |
| conv1 | 8×8×3×3 | 208×208 |
| maxpool | 2×2 | 104×104 |
| conv2 | 16×8×3×3 | 104×104 |
| maxpool | 2×2 | 52×52 |
| conv3 | 32×16×3×3 | 52×52 |
| maxpool | 2×2 | 26×26 |
| conv4 | 56×32×3×3 | 26×26 |
| maxpool | 2×2 | 13×13 |
| conv5 | 104×56×3×3 | 13×13 |
| conv6 | 208×104×3×3 | 13×13 |
| conv7 | 56×208×1×1 | 13×13 |
| conv8 | 104×56×3×3 | 13×13 |
| head | 18×104×3×3 | 13×13 |

## 首版系统数据通路

首版保持已经验证的摄像头和 HDMI 通路不变，采用 DDR 旁路推理：

```text
OV5640 -> VDMA S2MM -> DDR 三帧缓冲 -> VDMA MM2S -> bbox_overlay -> HDMI
                         |
                         +-> PS 选取稳定帧并缩放/letterbox/BGR->RGB
                             -> AXI DMA MM2S -> FINN LPYOLO -> AXI DMA S2MM
                             -> PS 解码/NMS -> bbox_ctrl -> bbox_overlay
```

FINN stitched IP 的流接口沿用作者实现：输入 AXI4-Stream 为 24 bit，每拍一个 RGB 像素；输出 AXI4-Stream 为 8 bit，依次返回 13×13×18 个量化值。PS 负责 1280×720 到 416×416 的 letterbox、通道交换、检测头解码和 NMS。

新 AXI DMA 优先连接 Zynq PS 的 `S_AXI_HP1`，避免与当前连接 `S_AXI_HP0` 的摄像头写 VDMA和 HDMI 读 VDMA争用同一 HP 端口。控制寄存器接入现有 `M_AXI_GP0` 外设互联，FINN 和 DMA 采用 100 MHz 时钟域。

## 实施阶段

1. **软件参考验证**：固定 ONNX 哈希、前后处理和阈值，在作者样例及 AX7021 实采帧上复现检测框。
2. **FINN 图转换和折叠**：用 FINN 0.7 生成估算报告、自动 folding 配置和逐层 HLS C++。
3. **HLS/IP 生成**：生成 stitched streaming IP，并对 `xc7z020clg484-2` 做 OOC 综合。
4. **资源门槛**：将 OOC LUT/FF/BRAM/DSP 与现有 HDMI 工程相加；若资源或时序超限，降低 PE/SIMD 并重新生成。
5. **Vivado 集成**：开启 HP1，加入 AXI DMA、FINN IP、AXI-Lite 控制和中断，重新导出 XSA。
6. **裸机软件**：加入输入 letterbox、DMA 缓存刷新/失效、FINN 启动、INT8 输出缩放、解码、NMS和框坐标更新。
7. **实板验证**：串口打印每阶段耗时，OBS 检查连续画面和框位置，至少连续运行 30 分钟。

## 验证门槛

- 官方样例软件推理输出 12 个正确框。
- AX7021 实采帧软件推理至少输出一个与人脸重合的框。
- FINN 转换后的 Python/CPP 仿真与参考 ONNX 输出一致。
- stitched IP 仿真输出的 13×13×18 INT8 张量逐元素一致。
- OOC 综合后资源能够与现有视频系统共同装入 XC7Z020。
- 完整实现 WNS、WHS 不小于 0，TNS、THS 为 0，DRC 无错误。
- 实板框坐标与 PC 参考结果在允许的取整误差内一致。
