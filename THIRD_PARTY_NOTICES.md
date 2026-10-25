# 第三方文件与授权边界

根目录 LICENSE 仅适用于本项目贡献者原创且有权授权的部分，不改变第三方文件、器件 IP、工具生成物和预训练模型原有的权利状态。

| 来源 | 仓库位置或用途 | 说明 |
| --- | --- | --- |
| Digilent rgb2dvi | Vivado/auto_create_project/my_ip/rgb2dvi_v1_3/ | 源文件头部声明 BSD 3-Clause；保留原版权及许可文字。 |
| ALINX 开发板参考设计 | Vivado/auto_create_project/my_ip/ 中的 OV5640、时钟和相关模块，以及 Vitis/auto_create_vitis/src/an5642_single/ 中的部分显示控制代码 | 这些参考文件不因根目录 MIT 许可而重新授权；使用时请核对开发板配套资料中的授权条件。 |
| AMD/Xilinx 工具与 IP | Block Design、XSA、BIT、ELF 和工具生成报告中的厂商组件 | 遵循对应 Vivado/Vitis 与 IP 授权条款；本仓库不授予厂商组件的新许可。 |
| LPYOLO / FINN 参考实验 | third_party/lpyolo/；旧 Git 历史中含 4W4A ONNX 文件 | 来源为 https://github.com/sefaburakokcu/finn-quantized-yolo 。该模型没有集成到当前 AX7021 程序；当前树不再分发 ONNX 权值。上游仓库首页未列出明确的开源许可证，使用模型前应自行核对其授权。 |

本项目实际运行的检测器是从本项目训练流程导出的 TinyFace INT8 参数，保存在 hls/src/tiny_face_params.h。现场采集的人脸图像、训练检查点和棋盘格原始图像对没有提交到仓库。
