# AX7021 V3.0 + AN5642 双路架构

## 显示方式

双路联调阶段使用 1280x720 HDMI 调试画面：

- Camera1 原始帧保持 1280x720，写入独立的三帧缓存。
- Camera2 原始帧保持 1280x720，写入另一组独立的三帧缓存。
- HDMI 预览将两路分别缩小为 640x360，左、右并排并在垂直方向居中。
- 缩小只影响预览；标定、校正和视差计算读取完整原始帧。

最终演示阶段改为 Camera1 全屏显示检测框和距离，Camera2 在后台提供匹配点及视差，不占用半屏。

## 数据通路

```text
Camera1 DVP -> OV5640 RX1 -> RGB888 -> VDMA S2MM1 -> DDR left[3]
Camera2 DVP -> OV5640 RX2 -> RGB888 -> VDMA S2MM2 -> DDR right[3]

DDR left/right -> preview compositor -> DDR preview[3]
DDR preview -> VDMA MM2S -> bbox overlay -> HDMI OUT

DDR left/right -> stereo calibration/rectification -> face matching -> distance
```

Camera1 和 Camera2 必须各自保留帧号。只有两路都完成一帧后才组成一对，不能只按当前 DDR 地址推断左右帧对应关系。

## 分阶段验证

1. 双路采集：两只 OV5640 均读到 `0x5640`，两套写 VDMA 均无错误并持续轮转。
2. 并排预览：遮住任意一只镜头时，只影响对应的左/右半幅。
3. 同步采集：串口输出成对帧号，连续运行不重复、不倒退。
4. 离线标定：采集不少于 20 对不同角度和距离的棋盘格图像，输出左右内参、畸变、旋转和平移矩阵。
5. 双目测距：完成极线校正后，以 `Z = f * B / disparity` 计算距离；AN5642 标称基线约 40 mm，最终采用标定得到的平移向量。
6. 人脸融合：Camera1 继续运行现有人脸检测；在 Camera2 中寻找同一人脸，使用校正后的水平视差生成距离标签。

## 恢复点

- 原单镜头稳定版：`main`，提交 `e19c8d6`。
- Camera2 单独显示版：`codex/camera2-bringup`，提交 `6fb9a6f`。
- 双路开发版：`codex/stereo-bringup`。

切换分支只改变本地文件。若要恢复板卡运行状态，切换后还需在 `Vitis` 目录执行 `run_jtag.bat`，重新下载对应 BIT 和 ELF。
