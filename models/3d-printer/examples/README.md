# 使用示例

最小完整示例为 [../src/build.py](../src/build.py)，其中只调用本主题建模模块并生成可编辑模型。

start.blend 为整机，gantry.blend 为运动机构，stepper-cutaway.blend 为电机剖面。单位为毫米（1 Blender 单位 = 1 mm）；与其他包合并时保留或正确换算单位。源码整机.整机().pose(x=...,y=...,z=...) 控制喷头姿态；动画需对相关物体写入关键帧或从脚本逐帧生成。
